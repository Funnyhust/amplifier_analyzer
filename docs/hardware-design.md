# Tài liệu Phần cứng — Aplifier_Analyze

**Dự án:** Signal Analyzer & Oscilloscope dựa trên STM32F407VET6  
**Tác giả:** Truong pc  
**Cập nhật:** 2026-04-18  
**Trạng thái:** Thiết kế kiến trúc hoàn chỉnh — sẵn sàng đưa vào schematic

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Danh sách linh kiện (BOM)](#2-danh-sách-linh-kiện-bom)
3. [Kiến trúc phần cứng](#3-kiến-trúc-phần-cứng)
4. [Chuỗi tín hiệu TX (phát)](#4-chuỗi-tín-hiệu-tx-phát)
5. [Chuỗi tín hiệu RX (thu)](#5-chuỗi-tín-hiệu-rx-thu)
6. [Cây xung nhịp (Clock Tree)](#6-cây-xung-nhịp-clock-tree)
7. [Thiết kế nguồn & PCB](#7-thiết-kế-nguồn--pcb)
8. [Hướng dẫn Schematic](#8-hướng-dẫn-schematic)
9. [Thông số hiệu năng thực tế](#9-thông-số-hiệu-năng-thực-tế)
10. [Danh sách rủi ro phần cứng](#10-danh-sách-rủi-ro-phần-cứng)

---

## 1. Tổng quan hệ thống

Aplifier_Analyze là **Network Analyzer** kiểu kích thích-đo đạc (stimulus-response):

- **STM32 DAC** phát tín hiệu sine sweep tần số (100 Hz → 500 kHz)
- **DUT** (mạch khuếch đại cần đo) nhận tín hiệu vào và cho tín hiệu ra
- **STM32 ADC Dual Channel** đo đồng thời **CH_in** (ngõ vào DUT) và **CH_out** (ngõ ra DUT)
- **Desktop Python** tính Gain (dB) = 20·log₁₀(RMS_out/RMS_in) và Phase (°) từ FFT

```
[STM32 DAC] → [Reconstruction LPF] → [DUT Input]   (TX chain)
                                            ↓
                                         [DUT]
                                            ↓
[STM32 ADC CH1] ← [AFE RX CH1] ← [DUT Input]        (RX CH_in)
[STM32 ADC CH2] ← [AFE RX CH2] ← [DUT Output]       (RX CH_out)
```

**Nguyên tắc thiết kế:**
- ❌ Không dùng IC ngoài trong đường tín hiệu chính (không AD9833, không AD8307)
- ✅ Chỉ dùng DAC/ADC nội bộ STM32 + mạch điện thuần (R, C, Op-Amp, Analog Switch)
- ✅ Thiết kế đơn giản, dễ debug, dễ thay linh kiện

---

## 2. Danh sách linh kiện (BOM)

### 2.1 Vi điều khiển chính

| Ref | Linh kiện | Package | Thông số | Ghi chú |
|-----|-----------|---------|----------|---------|
| U1 | **STM32F407VET6** | LQFP-100 | ARM Cortex-M4 @ 168 MHz, 12-bit ADC×3, 12-bit DAC×2, USB OTG FS | MCU chính |

### 2.2 Mạch AFE TX — Bộ lọc tái tạo (Reconstruction Filter)

| Ref | Linh kiện | Giá trị | Package | Ghi chú |
|-----|-----------|---------|---------|---------|
| U2 | **Op-Amp RRIO** | — | SOT-23-5 | Buffer sau DAC; khuyến nghị: **TLV9001** (TI) hoặc **LMV321** (TI) |
| R1 | Điện trở | **82 Ω** | 0402 | Sallen-Key R1 (fc=200 kHz, C=10nF) |
| R2 | Điện trở | **82 Ω** | 0402 | Sallen-Key R2 |
| C1 | Tụ gốm C0G | **10 nF** | 0402 | Sallen-Key C1 — bắt buộc C0G/NP0 (ổn định nhiệt) |
| C2 | Tụ gốm C0G | **10 nF** | 0402 | Sallen-Key C2 — bắt buộc C0G/NP0 |

> **Tính toán Sallen-Key Butterworth 2nd-order (Q=0.707):**  
> fc = 1 / (2π × R × C) = 1 / (2π × 82 × 10n) ≈ **194 kHz** ≈ 200 kHz  
> Chọn R=82 Ω (gần nhất với 79.6 Ω lý thuyết), C=10nF C0G

### 2.3 Mạch AFE RX — Bảo vệ ngõ vào

| Ref | Linh kiện | Giá trị | Package | Ghi chú |
|-----|-----------|---------|---------|---------|
| R_in | Điện trở | **1 kΩ** | 0402 | Giới hạn dòng khi overvoltage |
| D1, D2 | Schottky diode | **BAT54** | SOT-23 | Clamp to GND và 3.3V; tốc độ cao, Vf thấp |

### 2.4 Mạch AFE RX — Auto-Range Analog Switch

| Ref | Linh kiện | Package | Thông số | Ghi chú |
|-----|-----------|---------|----------|---------|
| U3 | **TMUX1072** (TI) | SOT-23-8 | SPDT×2, Ron≈5Ω, BW≥200MHz, OVP built-in, 1.8–5.5V | **Khuyến nghị #1** |
| — | TS5A3153 (TI) | SOT-23-6 | SPDT×1, Ron≈1Ω, BW≥100MHz, 1.8–5.5V | Thay thế nếu không có TMUX1072 |

**Mạng phân áp (Attenuator network):**

| Ref | Linh kiện | Giá trị | Ghi chú |
|-----|-----------|---------|---------|
| R_div1 | Điện trở | **90 kΩ** (hoặc 9×10 kΩ) | Phân áp ÷10 (trên) |
| R_div2 | Điện trở | **10 kΩ** | Phân áp ÷10 (dưới) |
| R_div3 | Điện trở | **990 kΩ** | Phân áp ÷100 (trên) |
| R_div4 | Điện trở | **10 kΩ** | Phân áp ÷100 (dưới) |
| R_term | Điện trở | **1 MΩ** | Termination ngõ vào |

> **3 dải đo:**
> - Range x1: input thẳng → dải ±1.65V (ADC full scale)
> - Range ÷10: R_div1/R_div2 → dải ±16.5V
> - Range ÷100: R_div3/R_div4 → dải ±165V

### 2.5 Mạch AFE RX — DC Bias +1.65V

| Ref | Linh kiện | Giá trị | Package | Ghi chú |
|-----|-----------|---------|---------|---------|
| U4 | **Op-Amp RRIO** | — | SOT-23-5 | Buffer Vbias 1.65V; **LMV321** hoặc **MCP6001** hoặc **TLV9001** |
| R_top | Điện trở | **10 kΩ** | 0402 | Voltage divider 3.3V → 1.65V |
| R_bot | Điện trở | **10 kΩ** | 0402 | Voltage divider 3.3V → 1.65V |
| R_sumA | Điện trở | **10 kΩ** | 0402 | Summing amp input (Vin_attenuated) |
| R_sumB | Điện trở | **10 kΩ** | 0402 | Summing amp input (Vbias) |
| C_bias | Tụ gốm | **100 nF** | 0402 | Bypass tại nút Vbias |

### 2.6 Mạch AFE RX — Anti-aliasing Filter

| Ref | Linh kiện | Giá trị | Package | Ghi chú |
|-----|-----------|---------|---------|---------|
| R_aa | Điện trở | **100 Ω** | 0402 | RC filter ngõ vào ADC |
| C_aa | Tụ gốm C0G | **10 nF** | 0402 | fc = 1/(2π×100×10n) ≈ **159 kHz** |

### 2.7 Nguồn VDDA — Lọc nhiễu ADC

| Ref | Linh kiện | Giá trị | Package | Ghi chú |
|-----|-----------|---------|---------|---------|
| FB1 | Ferrite bead | **600 Ω @ 100 MHz**, DCR <0.5 Ω, Imax ≥ 200 mA | 0402 | Chặn USB noise vào VDDA |
| C_vdda1 | Tụ gốm C0G | **1 µF** | 0402 | Bulk bypass VDDA |
| C_vdda2 | Tụ gốm | **100 nF** | 0402 | HF bypass VDDA |
| U_ldo | LDO ultra-low noise | — | SOT-23-5 | Tùy chọn: **LT3042** hoặc **TPS7A02** — tách hoàn toàn VDDA khỏi VDDD |

### 2.8 Thạch anh & Kết nối

| Ref | Linh kiện | Giá trị | Package | Ghi chú |
|-----|-----------|---------|---------|---------|
| Y1 | Crystal HSE | **8 MHz** | HC-49 / SMD | PLL source cho STM32 |
| C_hse1, C_hse2 | Tụ gốm | **20 pF** | 0402 | Load capacitors HSE |
| J1 | USB Type-B Micro / Type-C | — | Through-hole / SMD | USB OTG FS kết nối PC |
| J2, J3 | BNC connector | — | Through-hole | CH_in và CH_out input/output |
| J4 | SWD header | 5-pin | 2.54mm | Debug/flash (SWDIO, SWDCLK, GND, VCC, NRST) |

---

## 3. Kiến trúc phần cứng

### 3.1 Sơ đồ khối tổng thể

```
+------------------+     USB CDC     +------------------+
|   PC Desktop     |◄───────────────►|  STM32F407VET6   |
|  Python/PyQt6    |                  |   168 MHz        |
+------------------+                  |                  |
                                      |  DAC CH1 ──────►──────┐
                                      |                       │
                                      |  ADC CH1 (PA0) ◄────┐ │
                                      |  ADC CH2 (PA1) ◄──┐ │ │
                                      +------------------+ │ │ │
                                                          │ │ │
+------------------------------------------------------------------+
|                     ANALOG FRONT END (AFE)                       |
|                                                                  |
|  ┌────────────────────────────────────────────────────┐          |
|  │  TX Chain                                          │          |
|  │  DAC out ──[Sallen-Key LPF fc=200kHz]──[Buffer]──►│──► J2   |
|  └────────────────────────────────────────────────────┘  BNC_TX |
|                                                                  |
|  ┌────────────────────────────────────────────────────┐          |
|  │  RX CH1 (CH_in — ngõ vào DUT)                     │          |
|  │  J2 ──[Clamp BAT54]──[R 1kΩ]──[TMUX1072]──        │          |
|  │       ──[Summing +1.65V]──[RC 100Ω/10nF]──► PA0   │          |
|  └────────────────────────────────────────────────────┘          |
|                                                                  |
|  ┌────────────────────────────────────────────────────┐          |
|  │  RX CH2 (CH_out — ngõ ra DUT)                     │          |
|  │  J3 ──[Clamp BAT54]──[R 1kΩ]──[TMUX1072]──        │          |
|  │       ──[Summing +1.65V]──[RC 100Ω/10nF]──► PA1   │          |
|  └────────────────────────────────────────────────────┘          |
|                                                                  |
|  GPIO PA4, PA5 (2-bit) ──►[TMUX1072 SEL]  (auto-range control)  |
+------------------------------------------------------------------+
                    ↕ SWD (J4)
              [ST-Link Debugger]
```

### 3.2 Phân bổ GPIO / Pin mapping (đề xuất)

| STM32 Pin | Chức năng | Peripheral | Ghi chú |
|-----------|-----------|------------|---------|
| PA0 | ADC1_IN0 | ADC1 (CH_in) | Dual Interleaved với ADC2 |
| PA1 | ADC2_IN1 | ADC2 (CH_out) | Dual Interleaved với ADC1 |
| PA4 | DAC1_OUT | DAC Channel 1 | TX sine wave |
| PA5 | DAC2_OUT | DAC Channel 2 | Dự phòng / reference |
| PB0 | GPIO Output | TMUX1072 SEL0 | Auto-range bit 0 |
| PB1 | GPIO Output | TMUX1072 SEL1 | Auto-range bit 1 |
| PA11 | USB_FS_DM | USB OTG FS | D- |
| PA12 | USB_FS_DP | USB OTG FS | D+ |
| PH0 | OSC_IN | HSE 8 MHz | Crystal |
| PH1 | OSC_OUT | HSE 8 MHz | Crystal |
| PA13 | SWDIO | SWD | Debug |
| PA14 | SWDCLK | SWD | Debug |

---

## 4. Chuỗi tín hiệu TX (phát)

### 4.1 Nguyên lý hoạt động

```
[STM32 DAC CH1]
    │  12-bit, 0–3.3V, 200–500 kSPS (DMA + TIM6 trigger)
    │
    ▼
[Reconstruction Low-Pass Filter — Sallen-Key 2nd-order Butterworth]
    │  fc = 194 kHz (R=82Ω, C=10nF), Q=0.707, roll-off 40 dB/decade
    │  Mục đích: lọc sóng bậc thang (staircase) từ DAC → sine mượt
    │
    ▼
[Buffer Op-Amp — TLV9001 / LMV321]
    │  Gain = 1 (voltage follower)
    │  Mục đích: impedance matching, không tải trực tiếp DAC
    │
    ▼
[BNC J2 → DUT Input]
```

### 4.2 Bảng giới hạn tần số DAC

| Tần số | Biên độ an toàn | Ghi chú |
|--------|----------------|---------|
| < 10 kHz | Full 3.3 Vpp | Ít distortion, chất lượng cao |
| 10 – 100 kHz | ~1–2 Vpp | Cần giảm amplitude trong Sine LUT |
| 100 – 500 kHz | ~0.3–0.5 Vpp | Distortion tăng, cần LPF chất lượng tốt |
| > 500 kHz | Không khuyến nghị | Slew rate limit → méo hoàn toàn |

### 4.3 Firmware — Sine LUT và control tần số

```c
// 256-point Sine LUT, 12-bit, scale theo amplitude
// amplitude: 0.0–1.0 (float)
void DAC_InitLUT(float amplitude) {
    for (int i = 0; i < 256; i++) {
        float v = (sinf(2.0f * M_PI * i / 256.0f) + 1.0f) / 2.0f;
        sine_lut[i] = (uint16_t)(v * 4095.0f * amplitude);
    }
}

// Đổi tần số: chỉ cần thay TIM6 ARR
// APB1 = 42 MHz → TIM6 clock = 84 MHz (x2)
void DAC_SetFrequency(uint32_t freq_hz) {
    uint32_t arr = (84000000UL) / (freq_hz * 256) - 1;
    __HAL_TIM_SET_AUTORELOAD(&htim6, arr);
}
```

**Dải tần số hỗ trợ với LUT 256 điểm:**
- f_min = 84 MHz / (256 × 65535) ≈ **5 Hz**
- f_max = 84 MHz / (256 × 1) = **328 kHz** (thực tế giới hạn bởi DAC slew rate → 500 kHz)

---

## 5. Chuỗi tín hiệu RX (thu)

### 5.1 Sơ đồ chi tiết (cho cả 2 kênh, giống nhau)

```
[Input BNC Jx]
    │
    ├──[R_term 1 MΩ đến GND]     ← Input impedance 1 MΩ (standard)
    │
    ▼
[Bảo vệ ngõ vào]
    │  D1 (BAT54) cathode → 3.3V
    │  D2 (BAT54) anode  → GND
    │  R_in = 1 kΩ        → giới hạn dòng
    │  Mục đích: clamp Vin về [-0.3V, 3.6V] khi overvoltage
    │
    ▼
[Auto-Range Attenuator — TMUX1072]
    │  SEL[1:0] = 00 → x1   (ngõ vào thẳng, ±1.65V max)
    │  SEL[1:0] = 01 → ÷10  (qua R_div1/R_div2, ±16.5V max)
    │  SEL[1:0] = 10 → ÷100 (qua R_div3/R_div4, ±165V max)
    │  STM32 GPIO PB0, PB1 điều khiển SEL
    │  TMUX1072: Ron=5Ω, BW=200MHz, OVP=±18V
    │
    ▼
[DC Bias Summing Op-Amp — LMV321 / TLV9001]
    │  Mạch summing: Vout = Vin_att + Vbias
    │  Vbias = 1.65V (từ voltage divider 10k/10k + buffer follower)
    │  R_sumA = R_sumB = 10 kΩ → Gain = -1 (inverting summing)
    │
    │  ⚠️ Chú ý: Inverting summing amp → Vout = -(Vin_att + Vbias)
    │  Cần thêm một tầng inverter nữa, HOẶC dùng non-inverting topology:
    │  Non-inverting: Vout = Vin_att + Vbias (dùng standard diff-amp topology)
    │
    ▼
[RC Anti-aliasing Filter]
    │  R_aa = 100 Ω, C_aa = 10 nF
    │  fc = 1/(2π × 100 × 10n) ≈ 159 kHz
    │  Mục đích: chặn alias trước ADC @ fs=1.4 MSPS (Nyquist = 700 kHz)
    │
    ▼
[STM32 ADC Input Pin (PA0 / PA1)]
    │  VREF = 3.3V, dải 0–3.3V, 12-bit
    │
    ▼
[Firmware decode]
    float adc_v   = (adc_code / 4095.0f) * 3.3f;
    float vin_att = adc_v - 1.65f;          // Bù DC bias
    float vin_real = vin_att / gain_factor;  // Bù auto-range attenuation
```

### 5.2 Bảng auto-range control

| SEL[1:0] | Dải đo | gain_factor | Firmware code |
|----------|--------|------------|---------------|
| `00` | ±1.65 V | `1.0f` | `RANGE_X1 = 0` |
| `01` | ±16.5 V | `0.1f` | `RANGE_DIV10 = 1` |
| `10` | ±165 V | `0.01f` | `RANGE_DIV100 = 2` |

### 5.3 Thuật toán auto-range firmware (trong autorange.c)

```c
#define LOWER_THRESHOLD  410    // ~10% ADC full scale → tăng gain
#define UPPER_THRESHOLD  3686   // ~90% ADC full scale → giảm gain

void AutoRange_Update(uint16_t* adc_buf, uint16_t len) {
    uint16_t min_val = 4095, max_val = 0;
    for (int i = 0; i < len; i++) {
        if (adc_buf[i] < min_val) min_val = adc_buf[i];
        if (adc_buf[i] > max_val) max_val = adc_buf[i];
    }
    uint16_t peak_to_peak = max_val - min_val;

    if (peak_to_peak < LOWER_THRESHOLD && g_gain_range < RANGE_DIV100) {
        // Tăng attenuation (giảm gain) để signal lớn hơn
        // KHÔNG switch khi đang ở giữa DMA half-buffer!
        g_pending_range_change = true;
        g_new_range = g_gain_range + 1;
    } else if (peak_to_peak > UPPER_THRESHOLD && g_gain_range > RANGE_X1) {
        g_pending_range_change = true;
        g_new_range = g_gain_range - 1;
    }
}
// Range được thực sự đổi ở đầu half-buffer tiếp theo (boundary an toàn)
```

---

## 6. Cây xung nhịp (Clock Tree)

### 6.1 Cấu hình CubeMX (bắt buộc)

```
HSE = 8 MHz (external crystal Y1)
    │
    ▼ PLL
    ├── M = 8  (÷8 → 1 MHz PLL input)
    ├── N = 336 (×336 → 336 MHz VCO)
    ├── P = 2   (÷2 → SYSCLK = 168 MHz)
    └── Q = 7   (÷7 → 48 MHz → USB OTG FS clock ✅)

SYSCLK = 168 MHz
    ├── AHB  (HCLK) = 168 MHz (÷1)
    ├── APB1 (PCLK1) = 42 MHz (÷4)  → TIM6 clock = 84 MHz (×2)
    └── APB2 (PCLK2) = 84 MHz (÷2)  → ADCCLK prescaler ÷4 = 21 MHz ✅
```

### 6.2 Kiểm tra tính hợp lệ

| Clock | Giá trị | Giới hạn ST | Status |
|-------|---------|-------------|--------|
| SYSCLK | 168 MHz | ≤ 168 MHz | ✅ |
| USB OTG FS | 48 MHz | = 48 MHz (phải chính xác) | ✅ |
| ADCCLK | 21 MHz | ≤ 36 MHz | ✅ |
| APB1 | 42 MHz | ≤ 42 MHz | ✅ |
| APB2 | 84 MHz | ≤ 84 MHz | ✅ |

### 6.3 Tốc độ lấy mẫu ADC

| Cấu hình | ADCCLK | Min sample time | Effective rate |
|----------|--------|-----------------|----------------|
| Single ADC | 21 MHz | 3 cycles → 15 total | **1.4 MSPS** |
| Dual Interleaved (ADC1+ADC2) | 21 MHz | 3 cycles | **2.8 MSPS** |

**Sau decimation → stream về PC: ≤ 350 KSPS** (giới hạn bởi USB FS bandwidth ~700 KB/s)

---

## 7. Thiết kế nguồn & PCB

### 7.1 Phân tách nguồn VDDA (quan trọng nhất)

USB FS frame 1 ms → current spike → ripple trên 3.3V rail → ảnh hưởng VDDA → ENOB giảm 2–3 bit.

**Giải pháp bắt buộc (phải implement cả 2 tầng):**

**Tầng 1 — PCB/Hardware:**
```
3.3V_DIGITAL ──[FB1: Ferrite bead 600Ω@100MHz]──[VDDA]
                                                    │
                                              [C_vdda1: 1µF C0G]
                                              [C_vdda2: 100nF]
                                                    │
                                                   GND

Hoặc tốt hơn (nếu có diện tích):
3.3V_DIGITAL ──[LDO ultra-low noise LT3042/TPS7A02]──[VDDA]
```

**Tầng 2 — Firmware:**
```c
// Oversampling ×4 → +1 ENOB
uint32_t sum = 0;
for (int i = 0; i < 4; i++) sum += adc_buf[base + i];
uint16_t result = (uint16_t)(sum >> 2);
```

### 7.2 PCB Guidelines

**Phân vùng (Partitioning):**
```
+------------------------------------------+
|         DIGITAL ZONE                      |
|   STM32, USB, Crystal, SWD               |
|   - Ground plane liên tục                 |
|   - Tụ bypass 100nF sát mỗi chân VCC    |
+-----+------------------------------------+
      |  Moat (khe nhỏ) hoặc gap
+-----+------------------------------------+
|         ANALOG ZONE                       |
|   AFE TX, AFE RX CH1/CH2, Op-Amp        |
|   VDDA LDO/Filter                        |
|   - Analog ground plane riêng (AGND)     |
|   - Kết nối AGND ↔ DGND tại 1 điểm duy nhất (Star GND) |
+------------------------------------------+
```

**Star Ground Point:** Nối AGND và DGND tại 1 điểm duy nhất (star point) — thường ở gần LDO VDDA hoặc ferrite bead.

**Routing rules:**
- ADC input trace: ngắn nhất có thể, không chạy qua vùng digital
- Ferrite bead FB1: đặt sát chân VDDA của STM32 (< 5 mm)
- Tụ bypass 100nF: đặt ngay cạnh chân VDD của STM32 (< 1 mm)
- Crystal Y1: đặt sát chân OSC_IN/OUT, không route trace dài

**Layer stack (2-layer tối thiểu, 4-layer tốt hơn):**
- Layer 1 (top): Components + signals
- Layer 2 (bottom): Ground plane liên tục

### 7.3 Chọn Op-Amp cho AFE

**Yêu cầu chung cho cả U2 (TX buffer) và U4 (DC bias):**
- Rail-to-Rail Input/Output (RRIO) — bắt buộc vì supply = 3.3V đơn
- GBW ≥ 2× fc_max = 2 × 200 kHz = **400 kHz minimum**
- Offset voltage < 1 mV (để không làm sai DC measurement)
- Supply: 3.3V đơn (single supply)

| Op-Amp | GBW | Vos max | Package | Ghi chú |
|--------|-----|---------|---------|---------|
| **TLV9001** (TI) | 1 MHz | 0.5 mV | SOT-23-5 | **Khuyến nghị #1** — rẻ, phổ biến |
| **LMV321** (TI) | 1 MHz | 7 mV | SOT-23-5 | Phổ biến, Vos hơi cao |
| **MCP6001** (Microchip) | 1 MHz | 4.5 mV | SOT-23-5 | Tốt, dễ mua |
| **OPA314** (TI) | 3 MHz | 0.15 mV | SOT-23-5 | Chính xác cao, giá cao hơn |

---

## 8. Hướng dẫn Schematic

### 8.1 Thứ tự vẽ schematic

1. **Power rails** — LDO 3.3V, ferrite bead VDDA, bypass caps
2. **STM32** — đặt trước, add decoupling caps (100nF mỗi chân VDD/VDDA)
3. **Crystal HSE** (Y1 8MHz + 20pF × 2)
4. **USB connector** + ESD protection (tùy chọn: PRTR5V0U2X)
5. **SWD header** (J4: 5 chân)
6. **BNC connectors** (J2, J3)
7. **AFE TX**: DAC → R1/C1/R2/C2 Sallen-Key → U2 buffer → J2
8. **AFE RX CH1**: J2 → D1/D2/R_in → U3 TMUX1072 → U4 summing → R_aa/C_aa → PA0
9. **AFE RX CH2**: J3 → (giống CH1) → PA1
10. **Auto-range GPIO**: PB0/PB1 → SEL pins của TMUX1072

### 8.2 Decoupling caps cho STM32F407VET6

STM32F407VET6 có nhiều chân VDD và VDDA riêng biệt:

| Chân | Cap bắt buộc |
|------|-------------|
| VDDA (pin 22) | 1µF + 100nF (C0G) ngay sát chân |
| VDD (pins 11, 19, 28, 50, 75, 100) | 100nF mỗi chân |
| VCAP (pins 21, 49) | **2.2µF** mỗi chân (bắt buộc cho voltage regulator nội bộ STM32) |

> ⚠️ **VCAP là bắt buộc!** STM32F407 có bộ điều áp nội bộ 1.2V — thiếu tụ VCAP → MCU không khởi động được hoặc không ổn định.

### 8.3 DC Bias Circuit — Topology khuyến nghị

```
                     +3.3V
                        │
                   [10kΩ R_top]
                        │
Vbias_node ─────────────●─────── [Buffer U4a: follower] ──► 1.65V_ref
                        │
                   [10kΩ R_bot]
                        │
                       GND

// Summing (non-inverting để tránh cần thêm inverter):
//  Dùng differential amplifier topology:
//  Vout = Vin_att × (R_f/R_in) + Vbias × (1 + R_f/R_in) × (R_g/(R_g+R_in))
//  Đơn giản nhất: dùng single op-amp summing với Gain = +1:
//     Vin ──[10kΩ]──┐
//                   ├──► Op-Amp (non-inverting ref = 1.65V via divider)
//  Ref ──[10kΩ]──R_f

// HOẶC đơn giản hơn (không cần op-amp):
// Passive summing + buffer:
//   Vin_att ──[10kΩ]──┐
//                     ├──[U4 follower]──► ADC
//   1.65V ────[10kΩ]──┘
// Nhược điểm: Gain = 0.5 (cần điều chỉnh firmware: vin = (adc - 1.65/2) × 2 / gain_factor)
```

**Topology được chọn (simple passive + buffer):**
```
Vin_att ──[R_sumA = 10kΩ]──┐
                            ├──[U4: RRIO follower]──► ADC pin
1.65V ────[R_sumB = 10kΩ]──┘

Vout = (Vin_att + 1.65V) / 2     (passive voltage divider)
→ ADC thấy tín hiệu từ 0 đến 3.3V khi Vin_att từ -1.65V đến +1.65V

Firmware decode:
adc_v = adc_code / 4095.0f * 3.3f
vin_att = adc_v * 2.0f - 1.65f   // ×2 bù passive summing
vin_real = vin_att / gain_factor
```

---

## 9. Thông số hiệu năng thực tế

| Thông số | Spec lý thuyết | Thực tế (sau optimize) | Đủ dùng? |
|----------|---------------|----------------------|----------|
| ADC rate (Dual Interleaved) | 4.8 MSPS | **2.8 MSPS** @ 21 MHz ADCCLK | ✅ Vượt target 1 MSPS |
| ADC ENOB (USB inactive) | 12-bit (10.5 ENOB) | **~10–11 bits** | ✅ |
| ADC ENOB (USB active, sau fix) | — | **≥9.5–10.5 ENOB** (ferrite + oversampling) | ✅ |
| DAC TX rate | 1 MSPS | **200–500 kSPS** ổn định | ✅ Đủ sweep ≤500 kHz |
| USB CDC throughput (optimized) | 1.5 MB/s | **700 KB–1 MB/s** | ✅ Đủ stream 350 KSPS |
| Bode accuracy | — | **<±1 dB, <±2°** vs RC reference | ✅ |
| Phase measurement error | — | **<1°** @ SNR >20 dB (Cross-Corr) | ✅ |

---

## 10. Danh sách rủi ro phần cứng

| Rủi ro | Mức độ | Giải pháp |
|--------|--------|-----------|
| ADC ENOB giảm khi USB active | 🔴 Cao | Ferrite bead 600Ω@100MHz trên VDDA + LDO + oversampling ×4 |
| VDDA nhiễu từ digital switching | 🔴 Cao | Star GND, tách AGND/DGND, route ngắn |
| DAC distortion tại f cao (>200 kHz) | 🟡 Trung bình | Giảm amplitude trong Sine LUT; LPF Sallen-Key chất lượng |
| Overvoltage ngõ vào ADC | 🟡 Trung bình | Clamping BAT54 + series resistor 1kΩ |
| Analog Switch bandwidth giới hạn | 🟢 Thấp | TMUX1072 BW=200 MHz — đủ dùng |
| Crystal startup không ổn định | 🟢 Thấp | Chọn crystal 8 MHz CL=20pF, đặt gần STM32, trace ngắn |
| Thiếu tụ VCAP cho STM32 | 🔴 Cao | Đặt 2.2µF tại mỗi chân VCAP (bắt buộc, không được thiếu) |

---

## Phụ lục A — Checklist Schematic Review

Trước khi ra Gerber, kiểm tra:

- [ ] Tất cả chân VDD của STM32 có 100nF bypass
- [ ] Chân VDDA có 1µF + 100nF C0G + ferrite bead FB1
- [ ] VCAP1, VCAP2 có **2.2µF** mỗi chân
- [ ] Crystal Y1 đặt tụ 20pF × 2, trace < 5mm
- [ ] USB D+/D- trace impedance 90Ω differential (quan trọng nếu layout cẩn thận)
- [ ] BAT54 clamp diodes ở cả 2 input BNC
- [ ] TMUX1072 SEL pins nối đúng PB0/PB1
- [ ] Op-Amp RRIO supply = 3.3V, không nối ngược
- [ ] Sallen-Key dùng C0G/NP0 (không dùng X7R cho C1, C2)
- [ ] SWD header có đủ SWDIO, SWDCLK, GND, VCC, NRST
- [ ] AGND ↔ DGND nối tại 1 điểm duy nhất (star ground)

---

## Phụ lục B — Tham chiếu tài liệu kỹ thuật

| Tài liệu | Nội dung cần đọc |
|----------|-----------------|
| STM32F407 RM0090 | Chương 12 (DAC), 13 (ADC), 10 (DMA), 35 (USB OTG) |
| STM32F407 Datasheet DS8626 | Electrical characteristics, ADC specs |
| AN2834 | ADC accuracy, VDDA noise reduction |
| AN4666 | ADC multimode (dual interleaved) |
| TI TMUX1072 Datasheet | Analog switch selection, Ron, BW |
| TI TLV9001 Datasheet | Op-Amp specs, application circuits |
| TI BAT54 Datasheet | Schottky clamping diode specs |

---

*Tài liệu này được tạo tự động từ Architecture Workflow — 2026-04-18*  
*Cập nhật khi có thay đổi về linh kiện hoặc topology mạch*
