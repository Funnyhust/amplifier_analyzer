# BOM & Schematic — Aplifier_Analyze Hardware

**Phiên bản:** 1.0 | **Ngày:** 2026-04-18 | **Tác giả:** Truong pc

---

## Sơ đồ ASCII chi tiết — Toàn bộ các khối

```
╔══════════════════════════════════════════════════════════════════════════════╗
║             APLIFIER_ANALYZE — FULL HARDWARE SCHEMATIC                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌──────────────────── POWER SUPPLY ─────────────────────────────────────────┐
│                                                                             │
│  +5V_USB ──[LDO 3.3V]─────────── 3.3V_DIGITAL ──[C_bulk 10µF]──► VDDD   │
│                                        │                                   │
│                                  [FB1: Ferrite 600Ω@100MHz]                │
│                                        │                                   │
│                                [C_vdda1: 1µF C0G]                         │
│                                [C_vdda2: 100nF   ]                        │
│                                        │                                   │
│                                      VDDA ─────────────────────► STM32    │
│                                                                             │
│  3.3V─[R_top: 10kΩ]─●─[R_bot: 10kΩ]─GND  [U_bias follower]──► 1.65V_ref │
│                      └─────────────────────────────────────────            │
│                                                                             │
│     STM32: VCAP1─[2.2µF]─GND    VCAP2─[2.2µF]─GND  ← BẮT BUỘC!         │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────┐     USB FS CDC (PA11/PA12)      ┌──────────────────────────────┐
│    PC    │◄══════════════════════════════► │     STM32F407VET6            │
│ Desktop  │  Binary: [AA BB][T][Len][P][CRC]│     LQFP-100, 168 MHz        │
│ PyQt6    │                                 │                              │
└──────────┘                                 │  PA4  ──► DAC CH1 (TX out)  │
                                             │  PA0  ◄── ADC1_IN0 (RX CH1) │
                                             │  PA1  ◄── ADC2_IN1 (RX CH2) │
                                             │  PB0  ──► RANGE_SEL[0]       │
                                             │  PB1  ──► RANGE_SEL[1]       │
                                             │  PH0/1 ── Y1 8MHz Crystal    │
                                             │  PA13/14─ SWD J4             │
                                             └──────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━ TX CHAIN ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STM32 DAC (PA4) ──[12-bit, TIM6 DMA, Sine LUT 256pt]──►

         R1=82Ω       R2=82Ω
  in ──[═══]──●──────[═══]──●──► U2 TLV9001 follower ──► J2 (BNC TX)
              │              │
          C1=10nF(C0G)   C2=10nF(C0G)
              │              │
             GND            GND
  [Sallen-Key 2nd order Butterworth, fc=194kHz, Q=0.707]

━━━━━━━━━━━━━━━━━━━━ RX CH1 (DUT INPUT) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

J2_BNC_RX1 ──┬─[R_term1: 1MΩ]─ GND
             │
             └─[R_in1: 1kΩ]──●──[D1: BAT54 → GND]──[D2: BAT54 → 3.3V]
                              │
                      ┌───────┴──────────────────────────────────┐
                      │  TMUX1072 (U3a) — PB0/PB1 = SEL[1:0]   │
                      │                                          │
                      │  SEL=00 ── DIRECT ──(×1, ±1.65V)──►     │
                      │  SEL=01 ──[90kΩ]──┬─[10kΩ]─GND ──(÷10)►│
                      │  SEL=10 ──[990kΩ]─┴─[10kΩ]─GND ─(÷100)►│
                      └─────────────────────────────────────────┘
                              │
                    [R_sumA1: 10kΩ]──┐
                                     ├── U4a TLV9001 (follower) ──►
                    [R_sumB1: 10kΩ]──┘
                    (from 1.65V_ref)
                              │
                     [R_aa1: 100Ω]──● PA0 (ADC1)
                                    │
                               [C_aa1: 10nF]
                                    │
                                   GND
                     fc_aa = 159kHz

━━━━━━━━━━━━━━━━━━━━ RX CH2 (DUT OUTPUT) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

J3_BNC_RX2 ── (Hoàn toàn giống RX CH1 bên trên) ──► PA1 (ADC2)
[R_term2, R_in2, D3, D4, U3b, R_div1b–4b, U4b, R_sumA2, R_sumB2, R_aa2, C_aa2]
Cùng SEL[1:0] từ PB0/PB1 → auto-range cả 2 kênh đồng thời

━━━━━━━━━━━━━━━━━━━━━━ CRYSTAL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Y1 (8MHz) ──[C_hse1: 20pF]─GND    [C_hse2: 20pF]─GND
             PH0 ─────────────────────────────────── PH1
```

---

## BOM — Danh sách linh kiện đầy đủ

### NHÓM 1: Vi điều khiển

| Ref | Model | Package | Qty | Nhà SX | Ghi chú |
|-----|-------|---------|-----|--------|---------|
| U1 | **STM32F407VET6** | LQFP-100 | 1 | STMicro | MCU chính |

### NHÓM 2: Op-Amp (có thể thay bằng 2× TLV9002 dual)

| Ref | Model | Package | Qty | Chức năng |
|-----|-------|---------|-----|-----------|
| U2 | **TLV9001** (hoặc LMV321) | SOT-23-5 | 1 | Buffer DAC TX |
| U4a | **TLV9001** | SOT-23-5 | 1 | DC bias summing RX CH1 |
| U4b | **TLV9001** | SOT-23-5 | 1 | DC bias summing RX CH2 |
| U_bias | **TLV9001** | SOT-23-5 | 1 | 1.65V Vbias follower |

### NHÓM 3: Analog Switch

| Ref | Model | Package | Qty | Ghi chú |
|-----|-------|---------|-----|---------|
| U3a | **TMUX1072** | SOT-23-8 | 1 | Auto-range RX CH1 |
| U3b | **TMUX1072** | SOT-23-8 | 1 | Auto-range RX CH2 |

### NHÓM 4: Diode

| Ref | Model | Package | Qty | Chức năng |
|-----|-------|---------|-----|-----------|
| D1 | **BAT54** Schottky | SOT-23 | 1 | Clamp CH1 → GND |
| D2 | **BAT54** Schottky | SOT-23 | 1 | Clamp CH1 → 3.3V |
| D3 | **BAT54** Schottky | SOT-23 | 1 | Clamp CH2 → GND |
| D4 | **BAT54** Schottky | SOT-23 | 1 | Clamp CH2 → 3.3V |

### NHÓM 5: Điện trở (tất cả 0402)

| Ref | Giá trị | Dung sai | Qty | Chức năng |
|-----|---------|---------|-----|-----------|
| R1, R2 | **82 Ω** | 1% | 2 | Sallen-Key LPF TX |
| R_term1, R_term2 | **1 MΩ** | 5% | 2 | Input impedance RX |
| R_in1, R_in2 | **1 kΩ** | 1% | 2 | Series protection RX |
| R_div1a, R_div1b | **90 kΩ** | 1% | 2 | Attn ÷10 top CH1/CH2 |
| R_div2a, R_div2b | **10 kΩ** | 1% | 2 | Attn ÷10 bottom CH1/CH2 |
| R_div3a, R_div3b | **990 kΩ** | 1% | 2 | Attn ÷100 top CH1/CH2 |
| R_div4a, R_div4b | **10 kΩ** | 1% | 2 | Attn ÷100 bottom CH1/CH2 |
| R_top, R_bot | **10 kΩ** | 1% | 2 | Vbias 1.65V divider |
| R_sumA1, R_sumB1 | **10 kΩ** | 1% | 2 | Summing CH1 |
| R_sumA2, R_sumB2 | **10 kΩ** | 1% | 2 | Summing CH2 |
| R_aa1, R_aa2 | **100 Ω** | 1% | 2 | Anti-alias RC |
| **TỔNG** | | | **22** | |

### NHÓM 6: Tụ điện

| Ref | Giá trị | Loại | Package | Qty | Ghi chú |
|-----|---------|------|---------|-----|---------|
| C1, C2 | **10 nF** | **C0G/NP0** 50V | 0402 | 2 | Sallen-Key — BẮT BUỘC C0G |
| C_aa1, C_aa2 | **10 nF** | C0G 50V | 0402 | 2 | Anti-alias |
| C_vdda1 | **1 µF** | C0G 10V | 0603 | 1 | VDDA bulk |
| C_vdda2 | **100 nF** | C0G 10V | 0402 | 1 | VDDA HF |
| C_bias | **100 nF** | X7R 10V | 0402 | 1 | Vbias bypass |
| **VCAP1, VCAP2** | **2.2 µF** | X5R 6.3V | 0603 | 2 | STM32 VCAP — **BẮT BUỘC** |
| C_hse1, C_hse2 | **20 pF** | C0G 50V | 0402 | 2 | Crystal load |
| C_vdd_byp | **100 nF** | X7R 10V | 0402 | 6 | Bypass mỗi chân VDD STM32 |
| C_bulk | **10 µF** | X5R 10V | 0805 | 1 | Bulk supply |
| **TỔNG** | | | | **18** | |

### NHÓM 7: Thụ động đặc biệt

| Ref | Linh kiện | Thông số | Package | Qty | Ghi chú |
|-----|-----------|---------|---------|-----|---------|
| FB1 | **Ferrite bead** | 600Ω@100MHz, Imax≥200mA, DCR<0.5Ω | 0402/0603 | 1 | VDDA noise filter |
| Y1 | **Crystal 8MHz** | 8.000MHz, CL=20pF, ESR<100Ω | SMD | 1 | HSE clock |

### NHÓM 8: Connectors

| Ref | Linh kiện | Qty | Ghi chú |
|-----|-----------|-----|---------|
| J1 | **USB Micro-B female** (hoặc Type-C) | 1 | Kết nối PC |
| J2 | **BNC female PCB mount** | 1 | TX Out / RX CH1 |
| J3 | **BNC female PCB mount** | 1 | RX CH2 (DUT Output) |
| J4 | **Pin header 2×5 2.54mm** (SWD) | 1 | Debug/Flash |

---

## Tổng kết BOM

| Nhóm | Qty |
|------|-----|
| MCU | 1 |
| Op-Amp | 4 (hoặc 2× TLV9002) |
| Analog Switch | 2 |
| Diode | 4 |
| Điện trở | 22 |
| Tụ điện | 18 |
| Ferrite bead + Crystal | 2 |
| Connectors | 4 |
| **TỔNG** | **~57 linh kiện** |

---

## ⚠️ Lưu ý bắt buộc

- **VCAP1, VCAP2 = 2.2µF:** Không được thiếu — STM32F407 không boot nếu sai
- **C1, C2 = C0G/NP0:** Không thay bằng X7R — sẽ drift tần số fc theo nhiệt độ/điện áp
- **Star Ground:** AGND ↔ DGND chỉ nối 1 điểm duy nhất gần FB1
- **Payload schema C ↔ Python phải khớp** khi thay đổi gain_factor format
