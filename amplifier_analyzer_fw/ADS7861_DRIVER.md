# ADS7861 blocking driver

The driver lives in `Core/Inc/ads7861.h` and `Core/Src/ads7861.c`. It uses an
`ads7861_t` instance, so neither `hspi2` nor board pins are hardcoded inside the
driver. The current implementation is deliberately blocking for bring-up.

## Board mapping

| ADS7861 signal | STM32F103C8 | Configuration |
|---|---|---|
| SERIAL DATA A | PB14 / SPI2_MISO | Input, no pull |
| CLOCK | PB13 / SPI2_SCK | Alternate-function push-pull |
| CS2 | PB12 | GPIO output, idle HIGH |
| RD/CONVST_2 | PA8 | GPIO output, idle LOW |
| BUSY2 | PB10 | GPIO input, no pull |
| M0 | PB0 | GPIO output, default LOW |
| A0 | PB1 | GPIO output, pair select |
| M1 | PB11 | GPIO output, default HIGH |
| SERIAL DATA B | Not connected | Not used by this board |

REFIN is tied to REFOUT, so the default reference is 2.5 V. The ideal signed
differential transfer is `voltage = raw / 2048 * VREF`; one LSB is
`VREF / 2048`. Raw zero means zero differential voltage, not zero common-mode
voltage.

## Default mode and SPI

Initialization selects Mode II (`M0=0`, `M1=1`, `A0=0`). This converts A0/B0
simultaneously and returns both words through SERIAL DATA A. Pair 1 is selected
with `ads7861_select_pair(..., ADS7861_PAIR_1)`.

The current SPI2 bring-up configuration is:

- master, full-duplex wiring but receive data only;
- 8-bit data units (the driver also detects and supports HAL 16-bit mode);
- MSB first, software NSS;
- CPOL low, CPHA second edge;
- 1.125 MHz from APB1 at 36 MHz.

The current first-board build defines `ADS7861_USE_BITBANG_BRINGUP=1` and
temporarily overrides PB13 as a slow GPIO clock. This removes HAL SPI/CPHA from
the bring-up path. PB14 has a weak diagnostic pull-up: an undriven SDA reads
`FFFF`, while a short/active-low line reads `0000`. Set the macro to `0` only
after valid frames are proven, then return to hardware SPI and DMA.

`ADS7861_RELAX_FRAME_VALIDATION=1` is also temporary. It accepts two live words
that are neither both `0000` nor both `FFFF`, even if the status/trailing bits
are not yet strict. The 12-bit payload remains real ADC data; this mode exists
only to bring up the complete USB/application path before final timing work.

The bring-up capture limit is 512 samples and the DAC LUT limit is 256 entries.
The previous pair of 2048-entry static buffers left only a few hundred bytes of
RAM headroom and caused USB IRQ stack corruption/HardFault after START.

The ADS7861 changes data after a rising CLOCK edge and specifies it valid on the
falling edge, which is why CPHA second edge is selected. Verify this on the real
board before increasing SPI to 4 MHz or 8 MHz.

## Important Mode-II timing detail

BUSY goes HIGH during conversion and only returns LOW near the end of the serial
transfer. Because SPI2 supplies the ADS7861 conversion clock, software must not
wait for BUSY LOW before generating clocks. The blocking sequence is:

1. Set A0 and pulse the shared RD/CONVST net HIGH.
2. Confirm BUSY asserted HIGH (with a microsecond timeout).
3. Read the first 16-bit word from SDA.
4. Pulse shared RD/CONVST again. In `M1=1` this second CONVST is ignored as a
   new conversion but synchronizes the second output word.
5. Read the second 16-bit word (32 clocks total).
6. Confirm BUSY returned LOW (with a timeout), then parse both words.

Set `ADS7861_USE_BUSY_PIN=0` at compile time only for early diagnosis when BUSY
is not trustworthy. This disables BUSY waits; it does not add a long delay.

The current bring-up build uses this fallback because BUSY did not repeat
reliably over a 512-sample blocking capture. The fixed two-word clock sequence
still controls conversion timing deterministically.

## Usage

```c
ads7861_t adc = {0};

ads7861_init(&adc, &hspi2,
             GPIOB, GPIO_PIN_12, /* CS2 */
             GPIOA, GPIO_PIN_8,  /* RD/CONVST */
             GPIOB, GPIO_PIN_10, /* BUSY2 */
             GPIOB, GPIO_PIN_1,  /* A0 */
             GPIOB, GPIO_PIN_0,  /* M0 */
             GPIOB, GPIO_PIN_11, /* M1 */
             GPIOB, GPIO_PIN_13, /* CLOCK */
             GPIOB, GPIO_PIN_14  /* SERIAL DATA A */);

ads7861_set_mode(&adc, ADS7861_MODE_TWO_CH_SERIAL_A_ONLY);

ads7861_sample_pair_t sample;
if (ads7861_read_pair(&adc, ADS7861_PAIR_0, &sample) == ADS7861_OK &&
    sample.valid) {
    float va = ads7861_raw_to_voltage(&adc, sample.ch_a_raw);
    float vb = ads7861_raw_to_voltage(&adc, sample.ch_b_raw);
}
```

`ads7861_self_test_parse()` checks offline parsing for raw values 0, +2047,
-2048 and -1. The application capture buffer remains 12-bit offset-binary for
compatibility with the existing USB protocol; conversion from signed ADS7861
raw happens once at the `test_controller.c` boundary.

## Bring-up checklist

1. Before acquisition, measure CS2=HIGH, RD/CONVST=LOW, M0=LOW, M1=HIGH,
   A0=LOW.
2. Call `ads7861_start_conversion()` and verify a HIGH pulse on PA8 longer than
   15 ns.
3. Call `ads7861_read_pair()` and verify two groups of 16 CLOCK pulses (32
   pulses total) and an RD/CONVST synchronization pulse before each group.
4. Verify BUSY asserts after the first pulse and deasserts during/after the
   second 16-clock group. A wiring/timing fault must return timeout, not hang.
5. Short each differential input around its allowed common-mode point; signed
   raw should be close to zero. Apply a small known differential voltage and
   verify magnitude and polarity.
6. Read pair 0 (`A0=0`) and pair 1 (`A0=1`) if both analog pairs are populated.

## Logic-analyzer TODOs

- Verify CPOL/CPHA on the assembled PCB; try CPHA first edge only if bit framing
  is visibly shifted.
- Verify the exact BUSY assertion/deassertion sequence at the selected SPI rate.
- Verify that the first word on SERIAL DATA A is channel A and the second is B,
  and confirm status-bit polarity. The driver marks unexpected status framing
  as `sample.valid = 0` instead of silently swapping or inventing data.
- After blocking bring-up passes, add a timer-triggered/DMA acquisition path for
  deterministic 100-200 kSPS sampling. The blocking path is not a sample-rate
  scheduler.
