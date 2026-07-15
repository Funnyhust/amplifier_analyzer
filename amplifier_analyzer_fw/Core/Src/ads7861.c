#include "ads7861.h"

#include <stddef.h>
#include <string.h>

#define ADS7861_STATUS_CH_SHIFT          15U
#define ADS7861_STATUS_AB_SHIFT          14U
#define ADS7861_DATA_SHIFT               2U
#define ADS7861_DATA_MASK                0x0FFFU
#define ADS7861_SIGN_BIT                 0x0800U
#define ADS7861_TRAILING_MASK            0x0003U

static uint8_t ads7861_device_valid(const ads7861_t *dev)
{
    return dev != NULL && dev->hspi != NULL &&
           dev->cs_port != NULL && dev->convst_port != NULL &&
           dev->a0_port != NULL && dev->m0_port != NULL &&
           dev->m1_port != NULL && dev->clock_port != NULL &&
           dev->data_port != NULL;
}

#if ADS7861_USE_BUSY_PIN
static uint32_t ads7861_timeout_cycles(const ads7861_t *dev)
{
    uint32_t timeout_us = dev->timeout_us;
    uint32_t cycles_per_us = SystemCoreClock / 1000000U;

    if (timeout_us == 0U) timeout_us = ADS7861_DEFAULT_TIMEOUT_US;
    if (cycles_per_us == 0U) cycles_per_us = 1U;
    return timeout_us * cycles_per_us;
}
#endif

static void ads7861_enable_cycle_counter(void)
{
#if defined(DWT) && defined(CoreDebug_DEMCR_TRCENA_Msk) && defined(DWT_CTRL_CYCCNTENA_Msk)
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0U;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
#endif
}

static uint32_t ads7861_cycles_now(void)
{
#if defined(DWT) && defined(DWT_CTRL_CYCCNTENA_Msk)
    return DWT->CYCCNT;
#else
    return HAL_GetTick() * (SystemCoreClock / 1000U);
#endif
}

static void ads7861_delay_us(uint32_t delay_us)
{
    uint32_t started = ads7861_cycles_now();
    uint32_t cycles_per_us = SystemCoreClock / 1000000U;
    uint32_t delay_cycles;

    if (cycles_per_us == 0U) cycles_per_us = 1U;
    delay_cycles = delay_us * cycles_per_us;
    while ((uint32_t)(ads7861_cycles_now() - started) < delay_cycles) {
        __NOP();
    }
}

static ads7861_status_t ads7861_wait_busy_state(
    ads7861_t *dev, GPIO_PinState state)
{
#if ADS7861_USE_BUSY_PIN
    uint32_t started;
    uint32_t timeout_cycles;

    if (!ads7861_device_valid(dev) || dev->busy_port == NULL) {
        return ADS7861_ERR_NULL;
    }

    started = ads7861_cycles_now();
    timeout_cycles = ads7861_timeout_cycles(dev);
    while (HAL_GPIO_ReadPin(dev->busy_port, dev->busy_pin) != state) {
        if ((uint32_t)(ads7861_cycles_now() - started) >= timeout_cycles) {
            return ADS7861_ERR_TIMEOUT;
        }
    }
#else
    (void)dev;
    (void)state;
#endif
    return ADS7861_OK;
}

#if !ADS7861_USE_BITBANG_BRINGUP
static uint32_t ads7861_spi_timeout_ms(const ads7861_t *dev)
{
    uint32_t timeout_us = dev->timeout_us;
    if (timeout_us == 0U) timeout_us = ADS7861_DEFAULT_TIMEOUT_US;
    return (timeout_us + 999U) / 1000U;
}
#endif

static ads7861_status_t ads7861_receive_word(
    ads7861_t *dev, uint16_t *word)
{
#if ADS7861_USE_BITBANG_BRINGUP
    uint16_t value = 0U;

    if (!ads7861_device_valid(dev) || word == NULL) {
        return ADS7861_ERR_NULL;
    }

    /* Capture after the rising edge, where this board shows stable live data. */
    for (uint8_t bit = 0U; bit < 16U; bit++) {
        HAL_GPIO_WritePin(dev->clock_port, dev->clock_pin, GPIO_PIN_SET);
        ads7861_delay_us(ADS7861_BITBANG_HALF_PERIOD_US);
        value = (uint16_t)(value << 1);
        if (HAL_GPIO_ReadPin(dev->data_port, dev->data_pin) == GPIO_PIN_SET) {
            value |= 1U;
        }
        HAL_GPIO_WritePin(dev->clock_port, dev->clock_pin, GPIO_PIN_RESET);
        ads7861_delay_us(ADS7861_BITBANG_HALF_PERIOD_US);
        if (bit == 0U) {
            /* RD must remain HIGH through the first falling CLOCK edge. */
            HAL_GPIO_WritePin(dev->convst_port, dev->convst_pin,
                              GPIO_PIN_RESET);
            ads7861_delay_us(ADS7861_BITBANG_HALF_PERIOD_US);
        }
    }
    *word = value;
    return ADS7861_OK;
#else
    HAL_StatusTypeDef hal_status;

    if (dev == NULL || word == NULL) return ADS7861_ERR_NULL;

#if defined(SPI_DATASIZE_16BIT)
    if (dev->hspi->Init.DataSize == SPI_DATASIZE_16BIT) {
        uint16_t rx16 = 0U;
        hal_status = HAL_SPI_Receive(dev->hspi, (uint8_t *)&rx16, 1U,
                                    ads7861_spi_timeout_ms(dev));
        *word = rx16;
    } else
#endif
    {
        uint8_t rx8[2] = {0U, 0U};
        hal_status = HAL_SPI_Receive(dev->hspi, rx8, 2U,
                                    ads7861_spi_timeout_ms(dev));
        *word = ((uint16_t)rx8[0] << 8) | (uint16_t)rx8[1];
    }

    return (hal_status == HAL_OK) ? ADS7861_OK : ADS7861_ERR_SPI;
#endif
}

ads7861_status_t ads7861_init(
    ads7861_t *dev,
    SPI_HandleTypeDef *hspi,
    GPIO_TypeDef *cs_port, uint16_t cs_pin,
    GPIO_TypeDef *convst_port, uint16_t convst_pin,
    GPIO_TypeDef *busy_port, uint16_t busy_pin,
    GPIO_TypeDef *a0_port, uint16_t a0_pin,
    GPIO_TypeDef *m0_port, uint16_t m0_pin,
    GPIO_TypeDef *m1_port, uint16_t m1_pin,
    GPIO_TypeDef *clock_port, uint16_t clock_pin,
    GPIO_TypeDef *data_port, uint16_t data_pin)
{
    if (dev == NULL || hspi == NULL || cs_port == NULL ||
        convst_port == NULL || a0_port == NULL || m0_port == NULL ||
        m1_port == NULL || clock_port == NULL || data_port == NULL) {
        return ADS7861_ERR_NULL;
    }

    memset(dev, 0, sizeof(*dev));
    dev->hspi = hspi;
    dev->cs_port = cs_port;
    dev->cs_pin = cs_pin;
    dev->convst_port = convst_port;
    dev->convst_pin = convst_pin;
    dev->busy_port = busy_port;
    dev->busy_pin = busy_pin;
    dev->a0_port = a0_port;
    dev->a0_pin = a0_pin;
    dev->m0_port = m0_port;
    dev->m0_pin = m0_pin;
    dev->m1_port = m1_port;
    dev->m1_pin = m1_pin;
    dev->clock_port = clock_port;
    dev->clock_pin = clock_pin;
    dev->data_port = data_port;
    dev->data_pin = data_pin;
    dev->vref = ADS7861_DEFAULT_VREF;
    dev->timeout_us = ADS7861_DEFAULT_TIMEOUT_US;

    ads7861_enable_cycle_counter();

#if ADS7861_USE_BITBANG_BRINGUP
    {
        GPIO_InitTypeDef gpio = {0};

        /* Take SPI2 SCK ownership and use a deterministic idle-LOW GPIO clock. */
        __HAL_SPI_DISABLE(dev->hspi);
        gpio.Pin = dev->clock_pin;
        gpio.Mode = GPIO_MODE_OUTPUT_PP;
        gpio.Pull = GPIO_NOPULL;
        gpio.Speed = GPIO_SPEED_FREQ_HIGH;
        HAL_GPIO_Init(dev->clock_port, &gpio);
        HAL_GPIO_WritePin(dev->clock_port, dev->clock_pin, GPIO_PIN_RESET);

        /* Weak pull-up makes a disconnected/tri-stated SDA read FFFF, not 0000. */
        gpio.Pin = dev->data_pin;
        gpio.Mode = GPIO_MODE_INPUT;
        gpio.Pull = GPIO_PULLUP;
        HAL_GPIO_Init(dev->data_port, &gpio);
    }
#endif

    /* Idle levels from the board schematic: CS high, tied RD/CONVST low. */
    HAL_GPIO_WritePin(dev->cs_port, dev->cs_pin, GPIO_PIN_SET);
    HAL_GPIO_WritePin(dev->convst_port, dev->convst_pin, GPIO_PIN_RESET);

    /*
     * Only SERIAL DATA A is wired to STM32 MISO; SDB is unused. Therefore the
     * safe default is Mode II: M0=0, M1=1, A0=0 (simultaneous A0/B0).
     */
    return ads7861_set_mode(dev, ADS7861_MODE_TWO_CH_SERIAL_A_ONLY);
}

ads7861_status_t ads7861_set_mode(ads7861_t *dev, ads7861_mode_t mode)
{
    GPIO_PinState m0;
    GPIO_PinState m1;

    if (!ads7861_device_valid(dev)) return ADS7861_ERR_NULL;

    switch (mode) {
    case ADS7861_MODE_TWO_CH_SERIAL_A_ONLY:
        m0 = GPIO_PIN_RESET;
        m1 = GPIO_PIN_SET;
        break;
    case ADS7861_MODE_TWO_CH_DUAL_SERIAL:
        m0 = GPIO_PIN_RESET;
        m1 = GPIO_PIN_RESET;
        break;
    case ADS7861_MODE_FOUR_CH_SERIAL_A_ONLY:
        m0 = GPIO_PIN_SET;
        m1 = GPIO_PIN_SET;
        break;
    case ADS7861_MODE_FOUR_CH_DUAL_SERIAL:
        m0 = GPIO_PIN_SET;
        m1 = GPIO_PIN_RESET;
        break;
    default:
        return ADS7861_ERR_INVALID_MODE;
    }

    HAL_GPIO_WritePin(dev->m0_port, dev->m0_pin, m0);
    HAL_GPIO_WritePin(dev->m1_port, dev->m1_pin, m1);
    if (m0 == GPIO_PIN_RESET) {
        HAL_GPIO_WritePin(dev->a0_port, dev->a0_pin, GPIO_PIN_RESET);
        dev->pair = ADS7861_PAIR_0;
    }
    dev->mode = mode;
    return ADS7861_OK;
}

ads7861_status_t ads7861_select_pair(ads7861_t *dev, ads7861_pair_t pair)
{
    if (!ads7861_device_valid(dev)) return ADS7861_ERR_NULL;
    if (pair != ADS7861_PAIR_0 && pair != ADS7861_PAIR_1) {
        return ADS7861_ERR_INVALID_MODE;
    }
    if (dev->mode == ADS7861_MODE_FOUR_CH_SERIAL_A_ONLY ||
        dev->mode == ADS7861_MODE_FOUR_CH_DUAL_SERIAL) {
        return ADS7861_ERR_INVALID_MODE;
    }

    HAL_GPIO_WritePin(dev->a0_port, dev->a0_pin,
                      (pair == ADS7861_PAIR_1) ? GPIO_PIN_SET
                                              : GPIO_PIN_RESET);
    dev->pair = pair;
    return ADS7861_OK;
}

ads7861_status_t ads7861_start_conversion(ads7861_t *dev)
{
    if (!ads7861_device_valid(dev)) return ADS7861_ERR_NULL;

    /*
     * RD and CONVST share this net on the schematic. The rising edge starts
     * conversion and synchronizes serial output. HAL GPIO writes plus four
     * NOPs at 72 MHz hold HIGH well beyond the datasheet minimum of 15 ns.
     */
    HAL_GPIO_WritePin(dev->convst_port, dev->convst_pin, GPIO_PIN_RESET);
#if ADS7861_USE_BITBANG_BRINGUP
    ads7861_delay_us(ADS7861_BITBANG_HALF_PERIOD_US);
    HAL_GPIO_WritePin(dev->convst_port, dev->convst_pin, GPIO_PIN_SET);
    ads7861_delay_us(ADS7861_BITBANG_HALF_PERIOD_US);
    /* receive_word() lowers tied RD/CONVST after CLOCK cycle 1 falling. */
#else
    __NOP();
    __NOP();
    HAL_GPIO_WritePin(dev->convst_port, dev->convst_pin, GPIO_PIN_SET);
    __NOP();
    __NOP();
    __NOP();
    __NOP();
    HAL_GPIO_WritePin(dev->convst_port, dev->convst_pin, GPIO_PIN_RESET);
#endif
    return ADS7861_OK;
}

ads7861_status_t ads7861_wait_busy_done(ads7861_t *dev)
{
    return ads7861_wait_busy_state(dev, GPIO_PIN_RESET);
}

ads7861_status_t ads7861_read_words_serial_a(
    ads7861_t *dev, uint16_t *word_a, uint16_t *word_b)
{
    ads7861_status_t status;

    if (!ads7861_device_valid(dev) || word_a == NULL || word_b == NULL) {
        return ADS7861_ERR_NULL;
    }
    if (dev->mode != ADS7861_MODE_TWO_CH_SERIAL_A_ONLY &&
        dev->mode != ADS7861_MODE_FOUR_CH_SERIAL_A_ONLY) {
        /* SDB is not wired, so dual-serial modes cannot return both channels. */
        return ADS7861_ERR_INVALID_MODE;
    }

    HAL_GPIO_WritePin(dev->cs_port, dev->cs_pin, GPIO_PIN_RESET);
    status = ads7861_receive_word(dev, word_a);
    if (status == ADS7861_OK) {
        /*
         * In M1=1 the second RD/CONVST pulse is ignored as a new conversion,
         * but it synchronizes the B word onto SERIAL DATA A (datasheet Mode II).
         */
        status = ads7861_start_conversion(dev);
    }
    if (status == ADS7861_OK) {
        status = ads7861_receive_word(dev, word_b);
    }
    HAL_GPIO_WritePin(dev->cs_port, dev->cs_pin, GPIO_PIN_SET);
    return status;
}

int16_t ads7861_parse_word(
    uint16_t word, uint8_t *status_ch, uint8_t *status_ab)
{
    uint16_t data12 = (word >> ADS7861_DATA_SHIFT) & ADS7861_DATA_MASK;

    if (status_ch != NULL) {
        *status_ch = (uint8_t)((word >> ADS7861_STATUS_CH_SHIFT) & 0x01U);
    }
    if (status_ab != NULL) {
        *status_ab = (uint8_t)((word >> ADS7861_STATUS_AB_SHIFT) & 0x01U);
    }

    if ((data12 & ADS7861_SIGN_BIT) != 0U) {
        data12 |= 0xF000U;
    }
    return (int16_t)data12;
}

ads7861_status_t ads7861_read_pair(
    ads7861_t *dev, ads7861_pair_t pair, ads7861_sample_pair_t *sample)
{
    ads7861_status_t status;
    uint8_t ch_a;
    uint8_t ab_a;
    uint8_t ch_b;
    uint8_t ab_b;

    if (!ads7861_device_valid(dev) || sample == NULL) {
        return ADS7861_ERR_NULL;
    }
    memset(sample, 0, sizeof(*sample));

    status = ads7861_select_pair(dev, pair);
    if (status != ADS7861_OK) return status;

    /*
     * CS must already be LOW when the shared RD/CONVST rising edge
     * synchronizes SERIAL DATA A. Keeping CS high until the first SPI read
     * leaves SDA tri-stated and commonly produces 0x0000/0x0000 frames.
     */
    HAL_GPIO_WritePin(dev->cs_port, dev->cs_pin, GPIO_PIN_RESET);
    status = ads7861_start_conversion(dev);
    if (status != ADS7861_OK) {
        HAL_GPIO_WritePin(dev->cs_port, dev->cs_pin, GPIO_PIN_SET);
        return status;
    }

#if ADS7861_USE_BUSY_PIN
    /* BUSY must first assert; it cannot deassert until CLOCKs are supplied. */
    status = ads7861_wait_busy_state(dev, GPIO_PIN_SET);
    if (status != ADS7861_OK) {
        HAL_GPIO_WritePin(dev->cs_port, dev->cs_pin, GPIO_PIN_SET);
        return status;
    }
#endif

    /* read_words keeps CS low, then returns it to the idle HIGH level. */
    status = ads7861_read_words_serial_a(dev, &sample->word_a,
                                         &sample->word_b);
    if (status != ADS7861_OK) return status;

    /* BUSY returns low near the end of the 32-clock Mode-II transfer. */
    status = ads7861_wait_busy_done(dev);
    if (status != ADS7861_OK) return status;

    sample->ch_a_raw = ads7861_parse_word(sample->word_a, &ch_a, &ab_a);
    sample->ch_b_raw = ads7861_parse_word(sample->word_b, &ch_b, &ab_b);

    /*
     * Depending on the RD/CONVST phase at startup, SERIAL DATA A can present
     * the B word before the A word. Normalize the public result by the A/B
     * status flag instead of assuming transfer order forever.
     */
    if (ab_a == 1U && ab_b == 0U) {
        uint16_t word_tmp = sample->word_a;
        sample->word_a = sample->word_b;
        sample->word_b = word_tmp;
        sample->ch_a_raw = ads7861_parse_word(sample->word_a, &ch_a, &ab_a);
        sample->ch_b_raw = ads7861_parse_word(sample->word_b, &ch_b, &ab_b);
    }
    sample->status_a = (uint8_t)((ch_a << 1) | ab_a);
    sample->status_b = (uint8_t)((ch_b << 1) | ab_b);

    /*
     * Check framing and status identity. Logic-analyzer bring-up must still
     * verify which physical word appears first on this board.
     */
    sample->valid = (uint8_t)(
        ((sample->word_a & ADS7861_TRAILING_MASK) == 0U) &&
        ((sample->word_b & ADS7861_TRAILING_MASK) == 0U) &&
        (ab_a == 0U) && (ab_b == 1U) &&
        (ch_a == (uint8_t)pair) && (ch_b == (uint8_t)pair));
#if ADS7861_RELAX_FRAME_VALIDATION
    if (sample->valid == 0U) {
        uint8_t both_low = (sample->word_a == 0x0000U &&
                            sample->word_b == 0x0000U);
        uint8_t both_high = (sample->word_a == 0xFFFFU &&
                             sample->word_b == 0xFFFFU);
        sample->valid = (uint8_t)(!both_low && !both_high);
    }
#endif
    return ADS7861_OK;
}

float ads7861_raw_to_voltage(const ads7861_t *dev, int16_t raw)
{
    float vref = ADS7861_DEFAULT_VREF;
    if (dev != NULL && dev->vref > 0.0f) vref = dev->vref;
    return ((float)raw / 2048.0f) * vref;
}

ads7861_status_t ads7861_read_voltage_pair(
    ads7861_t *dev, ads7861_pair_t pair, float *voltage_a, float *voltage_b)
{
    ads7861_sample_pair_t sample;
    ads7861_status_t status;

    if (dev == NULL || voltage_a == NULL || voltage_b == NULL) {
        return ADS7861_ERR_NULL;
    }
    status = ads7861_read_pair(dev, pair, &sample);
    if (status != ADS7861_OK) return status;
    if (sample.valid == 0U) return ADS7861_ERR_SPI;

    *voltage_a = ads7861_raw_to_voltage(dev, sample.ch_a_raw);
    *voltage_b = ads7861_raw_to_voltage(dev, sample.ch_b_raw);
    return ADS7861_OK;
}

ads7861_status_t ads7861_self_test_parse(void)
{
    uint8_t ch;
    uint8_t ab;

    if (ads7861_parse_word((uint16_t)(0x000U << 2), &ch, &ab) != 0) {
        return ADS7861_ERR_SPI;
    }
    if (ads7861_parse_word((uint16_t)(0x7FFU << 2), NULL, NULL) != 2047) {
        return ADS7861_ERR_SPI;
    }
    if (ads7861_parse_word((uint16_t)(0x800U << 2), NULL, NULL) != -2048) {
        return ADS7861_ERR_SPI;
    }
    if (ads7861_parse_word((uint16_t)(0xFFFU << 2), NULL, NULL) != -1) {
        return ADS7861_ERR_SPI;
    }
    if (ch != 0U || ab != 0U) return ADS7861_ERR_SPI;
    return ADS7861_OK;
}
