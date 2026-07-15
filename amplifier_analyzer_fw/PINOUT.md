# Pinout firmware production — STM32F103C8T6

Đây là bảng chân đang được firmware `production` sử dụng, được đối chiếu với
schematic và mã nguồn hiện tại. Không dùng bảng pinout cũ trong
`docs/hardware-design.md` vì bảng đó thuộc kiến trúc ADC/DAC nội trước đây.

| STM32 | Net / thiết bị | Chức năng | Hướng MCU | Ghi chú |
|---|---|---|---|---|
| PA3 | MCP4822 LDAC1 | LDAC | Output | Active-low, firmware giữ mức thấp |
| PA4 | MCP4822 NSS1/CS | SPI1 CS | Output | Inactive-high |
| PA5 | MCP4822 SCK1 | SPI1 SCK | Output | SPI mode 0 |
| PA7 | MCP4822 MOSI1/SDI | SPI1 MOSI | Output | Dữ liệu DAC 16-bit, MSB trước |
| PA8 | ADS7861 RD/CONVST | Bắt đầu chuyển đổi/đọc | Output | RD và CONVST dùng chung |
| PB0 | ADS7861 M0 | Chọn mode | Output | Mode II: mức thấp |
| PB1 | ADS7861 A0 | Chọn cặp kênh | Output | Chọn A0/B0: mức thấp |
| PB10 | ADS7861 BUSY2 | Trạng thái chuyển đổi | Input | BUSY active-high |
| PB11 | ADS7861 M1 | Chọn mode | Output | Mode II: mức cao |
| PB12 | ADS7861 CS2 | Chip select | Output | Inactive-high |
| PB13 | ADS7861 CLK2 | SPI2 SCK | Output | SPI mode 1: CPOL=0, lấy mẫu cạnh thứ hai; bring-up 1,125 MHz |
| PB14 | ADS7861 MISO2/SDA | Serial Data A | Input | Hai kết quả đọc tuần tự |
| PA15 | Relay 0.3 | Chọn range 0,3 V | Output | Active-high |
| PB3 | Relay 3.3 | Chọn range 3,3 V | Output | Active-high |
| PB4 | Relay 10 | Chọn range 10 V | Output | Active-high |
| PA11 | USB DM | USB D- | USB | USB CDC Full Speed |
| PA12 | USB DP | USB D+ | USB | USB CDC Full Speed |
| PA13 | SWDIO | Nạp/debug | Bidirectional | Không được dùng làm GPIO |
| PA14 | SWCLK | Nạp/debug | Input clock | Không được dùng làm GPIO |
| NRST | RST | Reset | Input | Nên nối J-Link RESET |
| PD0/OSC_IN | OSC_IN | HSE 8 MHz | Clock | Thạch anh ngoài |
| PD1/OSC_OUT | OSC_OUT | HSE 8 MHz | Clock | Thạch anh ngoài |

## Quy ước điện áp DAC

- MCP4822 là DAC đơn cực. Firmware production cộng bias `1650 mV` vào
  biên độ/offset tín hiệu trước khi đổi sang DAC code.
- Tầng analog TX phải trừ lại bias này để tạo tín hiệu lưỡng cực
  quanh 0 V. Có thể đổi `DAC_OUTPUT_BIAS_MV` trong `Core/Inc/config.h`.
- Calibration `dac_a`, `dac_b` hiện là hệ số cho X2. X1 tạm thời
  dùng scale bằng một nửa X2.

## Chân SPI được HAL cấu hình nhưng không cần nối ngoại vi

- PA6 được cấu hình SPI1 MISO nhưng MCP4822 chỉ cần MOSI.
- PB15 được cấu hình SPI2 MOSI để SPI master phát dummy clock, nhưng ADS7861
  không nhận dữ liệu trên chân này; không cần nối vào ADS7861.

## Nguồn định nghĩa trong firmware

- MCP4822: `Core/Src/mcp4822.c`
- ADS7861: `Core/Src/ads7861.c`
- Relay range: `Core/Src/range_control.c`
- GPIO, SPI và clock: `Core/Src/main.c`, `Core/Src/stm32f1xx_hal_msp.c`
- USB CDC: `Core/Src/usbd_conf.c`
