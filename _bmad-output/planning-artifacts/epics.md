---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - '_bmad-output/planning-artifacts/architecture.md'
  - '_bmad-output/planning-artifacts/sprint-roadmap.md'
  - '_bmad-output/project-context.md'
workflowType: 'epics-and-stories'
status: 'complete'
project_name: 'Aplifier_Analyze'
user_name: 'Truong pc'
date: '2026-04-20'
completedAt: '2026-04-20'
---

# Aplifier_Analyze - Epic Breakdown

## Overview

Tài liệu này phân rã toàn bộ requirements từ Architecture.md thành các Epics và Stories có thể implement tuần tự. Mỗi Epic mang lại một giá trị độc lập, cho phép kiểm thử end-to-end ngay cả khi các Epic sau chưa hoàn thành.

---

## Requirements Inventory

### Functional Requirements

| ID | Requirement | File chịu trách nhiệm |
|---|---|---|
| FR-01 | Phát tín hiệu sine via STM32 DAC 12-bit nội bộ, sweep 100 Hz–500 kHz (Bode mode) | `dac_engine.c`, `dac_engine.h` |
| FR-02 | Thu 2 kênh ADC Dual Interleaved 2.8 MSPS, auto-range 3 dải ×1/÷10/÷100 | `adc_engine.c`, `autorange.c` |
| FR-03 | Oscilloscope mode — realtime waveform ≥60 FPS, 2-channel | `state_machine.c`, `osc_panel.py`, `dsp.py` |
| FR-04 | Bode plot — 50-step sweep, Gain (RMS) + Phase (FFT), <±1 dB & <±2° | `state_machine.c`, `bode_panel.py`, `dsp.py` |
| FR-05 | Binary comm protocol Firmware→PC + ASCII command PC→Firmware | `usb_tx.c`, `frame_parser.py`, `config.py` |
| FR-06 | Desktop PyQt6 GUI — OSC + Bode panels, CSV export, standalone .exe | `main_window.py`, `app_presenter.py` |
| FR-07 | Simulation mode (SIMULATION_MODE flag) — độc lập với hardware | `serial_reader.py`, `config.py` |
| FR-08 | Display unit conventions: V/mV auto-scale, Hz/kHz X-axis, phase -180°→+180° | `dsp.py`, `osc_panel.py`, `bode_panel.py` |
| FR-09 | Calibration mode: open-circuit/short-circuit baseline capture | `data_model.py`, `app_presenter.py` |
| FR-10 | Trigger: software edge trigger, configurable threshold, pre-trigger buffer 50% | `adc_engine.c`, `cmd_parser.c`, `osc_panel.py` |

### Non-Functional Requirements

| ID | Requirement | Mức độ |
|---|---|---|
| NFR-PERF | CPU <30%, GUI ≥60 FPS, USB stream ổn định >30s không drop frame | 🔴 Critical |
| NFR-ACCURACY | ENOB ≥9.5 bit khi USB active; Phase <±2°; Gain <±1 dB | 🔴 Critical |
| NFR-REALTIME | Hard deadline: ADC DMA callback xử lý xong trước khi DMA fill buffer kế | 🔴 Hard real-time |
| NFR-RELIABILITY | Frame sync recovery tự động; USB CDC no-deadlock | 🟡 High |
| NFR-MAINTAINABILITY | Strict layered architecture firmware; không trộn HAL/LL | 🟡 High |
| NFR-TESTABILITY | Simulation mode preserved; FrameParser unit tests không cần hardware | 🟢 Medium |
| NFR-PORTABILITY | Desktop .exe chạy không cần install Python | 🟢 Medium |

### Additional Requirements (từ Architecture)

- **Scaffold chiến lược:** Manual scaffold — không dùng CLI tool nặng; STM32CubeMX cho firmware
- **Build toolchain:** STM32CubeIDE (firmware), pip + PyInstaller (desktop)
- **Pattern bắt buộc:** MVP (desktop), App→Service→HAL (firmware); `core/` không import từ `ui/`
- **`dsp.py`:** Pure functions — tuyệt đối không import Qt
- **`.ioc` commit rule:** Commit file `.ioc` cùng với mọi thay đổi peripheral trong CubeMX
- **Protocol sync rule:** Khi thay đổi payload schema → update cả C lẫn Python trong cùng một commit
- **Queue bounded:** `queue.Queue(maxsize=32)` + drop-oldest policy
- **Calibration storage:** `%APPDATA%\AplifierAnalyze\calibration.json`
- **Inline comments:** Tiếng Việt cho toàn bộ codebase (Python + C)
- **Logging:** Dùng `logging` module — không dùng `print()` trong production

### UX Design Requirements

_Không có tài liệu UX Design riêng. UI requirements được tích hợp trong Architecture (FR-06, FR-08) và implementation patterns._

- **UX-01:** Oscilloscope panel với controls riêng biệt (channel select, timebase, trigger)
- **UX-02:** Bode panel với Magnitude + Phase plots trên 2 sub-plot riêng
- **UX-03:** Auto-scale voltage (V/mV) và frequency (Hz/kHz) trên tất cả plots
- **UX-04:** Màu sắc Catppuccin Mocha (dark mode) cho toàn bộ UI
- **UX-05:** Status bar hiển thị connection state, sample rate, error code

### FR Coverage Map

| FR | Epic | Story |
|---|---|---|
| FR-01 (DAC sine) | Epic 3 — Firmware Signal Generation | Story 3.1, 3.2 |
| FR-02 (ADC auto-range) | Epic 3 — Firmware Signal Generation | Story 3.3, 3.4 |
| FR-03 (Oscilloscope) | Epic 2 — Binary Protocol & Desktop Pipeline | Story 2.3, 2.4 |
| FR-04 (Bode plot) | Epic 4 — Bode Plot & DSP | Story 4.1, 4.2, 4.3 |
| FR-05 (Protocol) | Epic 1 — Foundation Scaffold, Epic 2 | Story 1.3, 2.1, 2.2 |
| FR-06 (Desktop GUI) | Epic 1 — Foundation Scaffold | Story 1.2 |
| FR-07 (Simulation) | Epic 1 — Foundation Scaffold | Story 1.3 |
| FR-08 (Display units) | Epic 4 — Bode Plot & DSP | Story 4.2 |
| FR-09 (Calibration) | Epic 5 — Integration & Calibration | Story 5.2 |
| FR-10 (Trigger) | Epic 5 — Integration & Calibration | Story 5.1 |

---

## Epic List

### Epic 1: Foundation Scaffold — Project Setup & Simulation Mode
Thiết lập toàn bộ cấu trúc project (Desktop + Firmware), đảm bảo Desktop chạy được với Simulation Mode hoàn chỉnh (không cần hardware).
**FRs covered:** FR-06, FR-07
**NFRs covered:** NFR-TESTABILITY, NFR-PORTABILITY

### Epic 2: Binary Protocol & Desktop Data Pipeline
Implement binary communication protocol end-to-end: FrameParser (desktop) + USB TX packer (firmware), kết nối qua SerialReader → Queue → AppPresenter. Desktop có thể nhận và hiển thị waveform thực từ firmware.
**FRs covered:** FR-03 (streaming), FR-05
**NFRs covered:** NFR-RELIABILITY, NFR-REALTIME, NFR-PERF

### Epic 3: Firmware Core — ADC Acquisition & DAC Signal Generation
Implement toàn bộ lớp Firmware Service: ADC Dual Interleaved DMA ping-pong, DAC sine LUT, auto-range TMUX1072, state machine 5 states. Firmware sẵn sàng thu phát tín hiệu thực.
**FRs covered:** FR-01, FR-02
**NFRs covered:** NFR-REALTIME, NFR-ACCURACY, NFR-MAINTAINABILITY

### Epic 4: Bode Plot & DSP
Implement Bode sweep end-to-end: firmware HAL_GetTick scheduling, desktop DSP (FFT phase + gain RMS), Bode panel visualization với unit conventions. User có thể đo Gain/Phase response của DUT.
**FRs covered:** FR-04, FR-08
**NFRs covered:** NFR-ACCURACY, NFR-PERF

### Epic 5: Integration, Trigger & Calibration
Implement trigger cứng (OSC_CAPTURE mode), calibration workflow, và end-to-end integration test toàn hệ thống. Hệ thống đạt trạng thái MVP hoàn chỉnh.
**FRs covered:** FR-09, FR-10
**NFRs covered:** NFR-ACCURACY, NFR-RELIABILITY

### Epic 6: Export & Polish
CSV export, PyInstaller packaging, logging config cho .exe, UI polish (Catppuccin theme hoàn chỉnh, status bar, keyboard shortcuts). Hệ thống sẵn sàng phát hành.
**FRs covered:** FR-06 (export, .exe)
**NFRs covered:** NFR-PORTABILITY

---

## Epic 1: Foundation Scaffold — Project Setup & Simulation Mode

**Goal:** Thiết lập cấu trúc thư mục đầy đủ cho cả Desktop (Python/PyQt6) và Firmware (STM32CubeMX), implement `config.py` với Simulation Mode, và đảm bảo Desktop app chạy được hoàn toàn không cần hardware.

---

### Story 1.1: Desktop Project Scaffold

As a developer,
I want a complete App_desktop/ folder structure with all module stubs and configuration,
So that every subsequent story has a consistent foundation to build upon without restructuring.

**Acceptance Criteria:**

**Given** thư mục `App_desktop/` chưa tồn tại
**When** developer tạo scaffold theo architecture spec
**Then** cấu trúc thư mục sau phải tồn tại đầy đủ:
```
App_desktop/
├── main.py
├── config.py
├── requirements.txt
├── ui/
│   ├── __init__.py
│   ├── main_window.py
│   └── osc_panel.py
│   └── bode_panel.py
├── core/
│   ├── __init__.py
│   ├── app_presenter.py
│   ├── serial_reader.py
│   ├── frame_parser.py
│   ├── dsp.py
│   └── data_model.py
└── tests/
    ├── __init__.py
    ├── test_frame_parser.py
    ├── test_dsp.py
    └── test_data_model.py
```

**And** `requirements.txt` phải chứa đủ: `pyqt6>=6.0`, `pyqtgraph>=0.13`, `numpy`, `scipy`, `pyserial>=3.0`, `pyinstaller`

**And** mỗi `.py` file phải có file header đúng format (module docstring với Module, Mục đích, Sections, Tác giả)

**And** `config.py` phải định nghĩa:
- `SIMULATION_MODE: bool = True` (default bật simulation)
- `HEADER_BYTE_1 = 0xAA`, `HEADER_BYTE_2 = 0xBB`
- `FRAME_TYPE_OSC_STREAM = 0x01`, `FRAME_TYPE_BODE = 0x02`, `FRAME_TYPE_OSC_CAPTURE = 0x03`
- `COLORS` dict với Catppuccin Mocha palette (ít nhất: background, surface, text, blue, green, red, yellow)
- `QUEUE_MAX_SIZE = 32`

**And** `python -c "from config import SIMULATION_MODE, COLORS; print(SIMULATION_MODE)"` chạy thành công không lỗi

**And** commit đầu tiên phải bao gồm toàn bộ scaffold này

---

### Story 1.2: Main Window & Panel Stubs (PyQt6 App chạy được)

As a developer,
I want a PyQt6 MainWindow with OSC panel and Bode panel stubs that launches successfully,
So that the UI framework is verified and subsequent stories can add real functionality.

**Acceptance Criteria:**

**Given** Story 1.1 đã hoàn thành (scaffold tồn tại)
**When** chạy `python main.py`
**Then** một cửa sổ PyQt6 hiện ra với:
- Title: "Aplifier Analyze"
- Layout 2 panel: Oscilloscope panel (trái/trên) và Bode panel (phải/dưới)
- Background màu Catppuccin Mocha (`#1e1e2e` hoặc tương đương)
- Mỗi panel có placeholder text hiển thị tên panel

**And** `main_window.py` phải là passive View — không chứa business logic, chỉ layout và expose signals

**And** `osc_panel.py` phải chứa QGroupBox "Oscilloscope" với stub controls: Channel select (CH1/CH2), Start/Stop button

**And** `bode_panel.py` phải chứa QGroupBox "Bode Plot" với stub controls: Start Sweep button, F_start và F_stop inputs

**And** `app_presenter.py` phải khởi tạo từ `main.py` và hold reference tới view (MainWindow)

**And** App không crash khi đóng cửa sổ (QApplication.exec() exit sạch)

**And** `ui/` không được import bất kỳ module nào từ `core/` trực tiếp (chỉ qua signals)

---

### Story 1.3: Simulation Mode Waveform Generator

As a developer,
I want SerialReader to generate realistic synthetic waveforms when SIMULATION_MODE=True,
So that the entire Desktop pipeline can be tested end-to-end without any hardware.

**Acceptance Criteria:**

**Given** `SIMULATION_MODE = True` trong `config.py`
**When** `SerialReader.start()` được gọi
**Then** SerialReader chạy trong QThread riêng và emit `data_received = pyqtSignal(bytes)` với synthetic frames hợp lệ

**And** Synthetic OSC_STREAM frames (TYPE 0x01) phải:
- Có header `[0xAA][0xBB][0x01][Len: 2B LE][Payload][CRC8]` đúng format
- Payload: `[gain_range=0][reserved=0][num_samples=256 LE][CH1_0..CH1_255 + CH2_0..CH2_255 interleaved]`
- CH1 là sóng sine 1kHz, CH2 là sóng sine 2kHz (giá trị ADC 12-bit: 0–4095)
- Emit rate: ~60 Hz (1 frame mỗi 16ms)

**And** Khi `SIMULATION_MODE = False`, SerialReader phải dùng `pyserial` mở real COM port (code path khác biệt nhưng cùng class)

**And** `queue.Queue(maxsize=32)` được dùng để truyền frames từ SerialReader thread sang main thread

**And** `AppPresenter` kết nối signal `data_received` vào `frame_parser`, sau đó drain queue bằng QTimer 16ms

**And** Chạy `python main.py` với `SIMULATION_MODE=True` → waveform data được log ở `DEBUG` level mà không crash

---

## Epic 2: Binary Protocol & Desktop Data Pipeline

**Goal:** Implement FrameParser state machine hoàn chỉnh + USB TX packer phía firmware, kết nối end-to-end để Desktop có thể parse và hiển thị waveform thực từ STM32.

---

### Story 2.1: FrameParser State Machine (Desktop)

As a developer,
I want a robust FrameParser that converts raw byte streams into ParsedFrame namedtuples,
So that the rest of the desktop pipeline can work with structured data regardless of USB chunking.

**Acceptance Criteria:**

**Given** `frame_parser.py` được implement
**When** `FrameParser.feed(data: bytes)` được gọi với bất kỳ chunk size nào
**Then** `ParsedFrame` namedtuple phải được emit qua `frame_complete = pyqtSignal(object)` khi đủ 1 frame hoàn chỉnh

**And** `ParsedFrame` phải có đúng 4 fields: `frame_type` (int), `payload` (bytes), `gain_factor` (float), `timestamp_ms` (int)

**And** `gain_factor` phải được tính từ `gain_range` byte trong payload: `0→1.0`, `1→0.1`, `2→0.01`

**And** State machine phải có đúng 4 states: `HUNT → HEADER → PAYLOAD → CRC`

**And** **5 edge cases bắt buộc phải pass** (Amelia's list):
1. Perfect stream → emit đúng 1 ParsedFrame
2. Split mid-header (sau byte 3/5) → recover và emit đúng
3. Split mid-payload → buffer đúng, emit khi đủ
4. Bad CRC → HUNT recovery, không crash, không emit
5. Consecutive false sync `[0xAA][0xAA][0xBB]` → recover đúng, emit 1 frame

**And** Test file `tests/test_frame_parser.py` phải có đủ 5 test cases trên và tất cả pass: `pytest tests/test_frame_parser.py -v`

**And** CRC8 phải dùng polynomial `0x07` (CRC-8/SMBUS), tính trên toàn bộ bytes từ Type đến cuối Payload

---

### Story 2.2: Firmware USB TX Service (`usb_tx.c`)

As a firmware developer,
I want a USB TX service with an 8KB FIFO and CDC callback chain,
So that ADC data can be reliably streamed to PC without blocking or deadlocking.

**Acceptance Criteria:**

**Given** STM32CubeMX project đã generate USB_OTG_FS CDC code
**When** `USB_EnqueueFrame(frame_type, payload, len)` được gọi từ service layer
**Then** frame được pack với header `[0xAA][0xBB][Type][Len LE 2B][Payload][CRC8]` và enqueue vào FIFO 8KB

**And** FIFO phải là circular buffer 8192 bytes (`USB_TX_FIFO_SIZE 8192`) — không dùng `malloc`

**And** Truyền CDC phải dùng callback chain: `CDC_TransmitCplt_FS` → dequeue next chunk → `CDC_Transmit_FS` — **tuyệt đối không `while(CDC_Transmit_FS() == USBD_BUSY)`**

**And** Khi FIFO đầy, `USB_EnqueueFrame` phải return `ERR_FIFO_FULL` và set `g_error_code = ERR_FIFO_FULL` — không drop silent

**And** `OscFrameHeader_t` và `BodeResultFrame_t` phải dùng `__attribute__((packed))` đúng như architecture spec

**And** Code chỉ được viết trong `/* USER CODE BEGIN */` blocks — không sửa ngoài

**And** Commit phải bao gồm cả file `.ioc` nếu có thay đổi peripheral config

---

### Story 2.3: Oscilloscope Waveform Display (Real-time Streaming)

As an engineer,
I want to see real-time waveforms from both ADC channels on the Oscilloscope panel at ≥60 FPS,
So that I can observe and analyze signals from my DUT in real time.

**Acceptance Criteria:**

**Given** AppPresenter nhận `ParsedFrame` type `0x01` từ FrameParser
**When** QTimer 16ms tick (drain loop)
**Then** `data_model.py` pre-allocated NumPy arrays được update bằng slice-assign (`arr[:] = new_data`)

**And** `osc_panel.py` update pyqtgraph curves bằng `curve.setData()` — **tuyệt đối không** `plot()` mới trong QTimer callback

**And** Voltage axis phải auto-scale: giá trị <0.1V hiển thị `mV`, ≥0.1V hiển thị `V`

**And** `dsp.py` phải có function `decode_osc_payload(payload: bytes, gain_factor: float) -> tuple[np.ndarray, np.ndarray]` trả về (ch1_V, ch2_V) đã áp dụng gain_factor và DC bias removal (`vin = (adc/4095*3.3 - 1.65) / gain_factor`)

**And** Khi `SIMULATION_MODE=True`, streaming hoạt động với synthetic frames từ Story 1.3

**And** Ở hardware mode, GUI không drop frame khi USB stream liên tục >30 seconds

**And** CPU usage phải <30% khi streaming (đo bằng Windows Task Manager hoặc `psutil`)

---

### Story 2.4: Firmware State Machine & Command Parser

As a firmware developer,
I want a 5-state system state machine with ASCII command parser,
So that the PC can control acquisition mode and the firmware transitions cleanly between states.

**Acceptance Criteria:**

**Given** `state_machine.c` và `cmd_parser.c` được implement
**When** USB CDC nhận ASCII command
**Then** `cmd_parser.c` parse đúng các commands sau:
- `<CMD:START_OSC_STREAM>\n` → set `g_cmd_start_osc_stream = true`
- `<CMD:START_OSC_CAPTURE>\n` → set `g_cmd_start_osc_capture = true`
- `<CMD:START_SWEEP>\n` → set `g_cmd_start_sweep = true`
- `<CMD:STOP>\n` → set `g_cmd_stop = true`
- `<CMD:SET_TRIGGER, EDGE:RISING, LEVEL:2048>\n` → set trigger params

**And** State machine phải implement đúng 5 states với transitions theo architecture spec:
```
IDLE → (CMD:START_OSC_STREAM) → CONFIGURING → OSC_STREAM
IDLE → (CMD:START_OSC_CAPTURE) → CONFIGURING → OSC_CAPTURE → (done) → IDLE
IDLE → (CMD:START_SWEEP) → CONFIGURING → BODE_SWEEP → (done) → IDLE
Any state → (USB disconnect) → ERROR → (USB reconnect) → IDLE
```

**And** Error recovery: `SYS_ERROR → SYS_IDLE` khi `hUsbDevice.dev_state == USBD_STATE_CONFIGURED` — không cần hard reset

**And** Tất cả global shared variables phải có `volatile` qualifier (vd: `volatile SystemState_t g_sys_state`)

**And** `StateMachine_Run()` phải được gọi từ main loop, không từ ISR

**And** Không có `HAL_Delay()` trong bất kỳ đường nào của state machine

---

## Epic 3: Firmware Core — ADC Acquisition & DAC Signal Generation

**Goal:** Implement lớp Firmware Service hoàn chỉnh: ADC Dual Interleaved DMA ping-pong, DAC sine LUT với TIM6, và auto-range TMUX1072. Firmware sẵn sàng thu phát tín hiệu thực ở full spec.

---

### Story 3.1: DAC Sine Wave Generator (`dac_engine.c`)

As a firmware developer,
I want a DAC sine LUT driver with TIM6-controlled frequency,
So that the STM32 can output a clean sine wave at any frequency from 100 Hz to 500 kHz for Bode analysis.

**Acceptance Criteria:**

**Given** CubeMX đã configure DAC CH1 + TIM6 DMA
**When** `DAC_SetFrequency(uint32_t freq_hz)` được gọi
**Then** TIM6 ARR và PSC được tính lại để output đúng tần số từ 256-point LUT: `ARR = (SYSCLK / (freq_hz * 256)) - 1`

**And** Sine LUT phải là 256 điểm, 12-bit right-aligned (`uint16_t sine_lut[256]`), giá trị 0–4095

**And** DAC DMA phải chạy Circular mode — không restart thủ công sau mỗi period

**And** `DAC_Start()` và `DAC_Stop()` phải là safe to call từ state machine context

**And** Distortion phải ≤3% THD tại tần số ≤100 kHz (kiểm tra bằng FFT trên desktop hoặc oscilloscope thực)

**And** Commit bao gồm file `.ioc` updated với DAC + TIM6 config

---

### Story 3.2: Bode Sweep Scheduler (Firmware)

As a firmware developer,
I want a Bode sweep scheduler using HAL_GetTick() that steps through 50 frequency points,
So that the firmware can perform a complete Bode sweep autonomously and send results to PC.

**Acceptance Criteria:**

**Given** State machine ở trạng thái `SYS_BODE_SWEEP`
**When** `StateMachine_Run()` được gọi liên tục từ main loop
**Then** Mỗi step của Bode sweep diễn ra theo pattern:
1. `HAL_GetTick()` check interval (≥5ms từ step trước)
2. `DAC_SetFrequency(bode_freq_table[bode_step_idx])`
3. Settle delay (2ms non-blocking via `HAL_GetTick`)
4. `ADC_CaptureBodeStep()` → lấy RMS CH_in và CH_out
5. Tính `gain_db = 20*log10f(rms_out/rms_in)` và `phase_deg` (FFT cross-correlation hoặc zero-crossing)
6. `USB_EnqueueFrame(FRAME_TYPE_BODE, &result, sizeof(BodeResultFrame_t))`
7. `bode_step_idx++`

**And** `bode_freq_table[50]` phải là log-spaced từ 100 Hz đến 500 kHz

**And** Khi `bode_step_idx >= BODE_TOTAL_STEPS`, transition về `SYS_IDLE`

**And** Không có `HAL_Delay()` — tất cả timing phải dùng `HAL_GetTick()` comparison

**And** 50 BODE_RESULT frames (TYPE 0x02) phải được gửi lên PC, mỗi frame 3×float32 LE đúng schema

---

### Story 3.3: ADC Dual Interleaved DMA Ping-Pong (`adc_engine.c`)

As a firmware developer,
I want ADC1+ADC2 Dual Interleaved DMA with ping-pong buffers and decimation,
So that 2-channel high-speed ADC data is acquired reliably at up to 2.8 MSPS without CPU bottleneck.

**Acceptance Criteria:**

**Given** CubeMX đã configure ADC1+ADC2 Dual Interleaved, DMA2 Circular Half-Word
**When** `ADC_StartDMA()` được gọi từ state machine
**Then** DMA chạy Circular mode với buffer `uint32_t adc_dma_buf[ADC_BUF_SIZE]` (mỗi word = [CH2_raw<<16 | CH1_raw])

**And** `HAL_ADCEx_InjectedConvCpltCallback` (Half-Complete) và `HAL_ADC_ConvCpltCallback` (Full-Complete) phải:
- Xử lý nửa buffer không đang fill (ping-pong)
- Decimation: avg 8 samples liên tiếp → 1 output sample (tốc độ output ≤350 KSPS)
- Embed `g_gain_range` vào OscFrameHeader
- Gọi `USB_EnqueueFrame(FRAME_TYPE_OSC_STREAM, ...)`

**And** Không được switch gain range (`autorange.c`) trong khi DMA half-buffer đang active

**And** `ADCCLK = 21 MHz (APB2÷4)` phải được verify trong clock tree (không thay đổi prescaler)

**And** `volatile` qualifier bắt buộc cho: `g_gain_range`, `g_adc_buf_ready`, tất cả ISR-shared variables

**And** Commit bao gồm file `.ioc` updated với ADC1, ADC2, DMA2 config

---

### Story 3.4: Auto-Range Control (`autorange.c`)

As a firmware developer,
I want automatic range switching via TMUX1072 GPIO control,
So that the ADC always operates at optimal range regardless of input signal amplitude.

**Acceptance Criteria:**

**Given** GPIO pins đã configure cho TMUX1072 (2 output pins: SEL0, SEL1)
**When** `AutoRange_Update()` được gọi sau mỗi ADC block
**Then** Peak-to-peak của block hiện tại được tính: `pp = max(block) - min(block)`

**And** Switch logic theo ngưỡng:
- `pp > 3800` (gần saturation): giảm range (×1 → ÷10 → ÷100)
- `pp < 400` (quá nhỏ): tăng range (÷100 → ÷10 → ×1)
- Hysteresis: không switch nếu không đủ 3 lần liên tiếp out-of-range (anti-chatter)

**And** GPIO output cho TMUX1072:
- Range ×1: `SEL1=0, SEL0=0`
- Range ÷10: `SEL1=0, SEL0=1`
- Range ÷100: `SEL1=1, SEL0=0`

**And** `g_gain_range` (global volatile uint8_t) phải được update **sau** khi GPIO đã set, chỉ khi DMA callback không đang active

**And** `AutoRange_GetGainFactor()` trả về `float`: `1.0f`, `0.1f`, hoặc `0.01f` tương ứng

---

## Epic 4: Bode Plot & DSP

**Goal:** Implement Bode sweep end-to-end: DSP functions (FFT phase + gain RMS), Bode panel visualization với unit conventions chuẩn. User đo được Gain/Phase response của DUT.

---

### Story 4.1: DSP Core Functions (`dsp.py`)

As a developer,
I want pure DSP functions for FFT, phase, gain, and filtering,
So that the desktop can compute and display accurate signal measurements from raw ADC data.

**Acceptance Criteria:**

**Given** `dsp.py` implement đúng các functions
**When** functions được gọi từ `app_presenter.py`
**Then** các functions sau phải tồn tại và hoạt động đúng:

- `decode_osc_payload(payload: bytes, gain_factor: float) → tuple[np.ndarray, np.ndarray]`
  - Unpack CH1+CH2 interleaved uint16_t, convert sang Volt: `vin = (adc/4095*3.3 - 1.65) / gain_factor`
  - Return `(ch1_V, ch2_V)` as float64 arrays

- `compute_fft(signal: np.ndarray, sample_rate: float) → tuple[np.ndarray, np.ndarray]`
  - Return `(freq_array, magnitude_array_dB)` using `np.fft.rfft` + `np.fft.rfftfreq`

- `compute_gain_rms(ch_in: np.ndarray, ch_out: np.ndarray) → float`
  - Return `20 * log10(rms(ch_out) / rms(ch_in))` in dB

- `compute_phase_fft(ch_in: np.ndarray, ch_out: np.ndarray, freq_hz: float, sample_rate: float) → float`
  - Return phase difference in degrees, normalized to -180°→+180°

- `apply_lowpass_filter(signal: np.ndarray, cutoff_hz: float, sample_rate: float, zi: np.ndarray) → tuple[np.ndarray, np.ndarray]`
  - Dùng `scipy.signal.lfilter` (không `filtfilt`), return `(filtered, zi_new)`

**And** `dsp.py` không được import bất kỳ Qt module nào

**And** `pytest tests/test_dsp.py -v` phải pass với tests: sine accuracy, phase at known offset, gain at 0 dB (equal signals), filter state continuity

**And** Unit format helpers phải có trong `dsp.py`:
- `format_voltage(v: float) → str`: `v < 0.1 → f"{v*1000:.1f} mV"`, else `f"{v:.3f} V"`
- `format_frequency(hz: float) → str`: `hz < 1000 → f"{hz:.0f} Hz"`, else `f"{hz/1000:.1f} kHz"`
- `format_phase(deg: float) → str`: `f"{deg:.1f}°"`
- `format_gain(db: float) → str`: `f"{db:.1f} dB"`

---

### Story 4.2: Bode Panel Visualization

As an engineer,
I want a Bode plot panel with Magnitude and Phase sub-plots that updates live during sweep,
So that I can see gain and phase response of my circuit across the full frequency range.

**Acceptance Criteria:**

**Given** `bode_panel.py` được implement với pyqtgraph
**When** AppPresenter nhận `ParsedFrame` type `0x02` (BODE_RESULT)
**Then** Magnitude plot update với điểm mới `(freq_hz, gain_db)` bằng `curve.setData()`

**And** Phase plot update với điểm mới `(freq_hz, phase_deg)` bằng `curve.setData()`

**And** X-axis (Frequency) phải là log scale, auto-label dùng `format_frequency()`: hiển thị `"100 Hz"`, `"10.0 kHz"`, `"500 kHz"`

**And** Y-axis Magnitude: label `"Gain (dB)"`, range auto-fit

**And** Y-axis Phase: label `"Phase (°)"`, range `-180` đến `+180` cố định

**And** Control inputs trong panel:
- F_start (spinbox, Hz, default=100)
- F_stop (spinbox, Hz, default=500000)
- Steps (spinbox, default=50)
- "Start Sweep" button → emit signal sang AppPresenter → gửi `<CMD:START_SWEEP>\n`

**And** Màu sắc curve phải dùng Catppuccin Mocha: Magnitude = blue (`#89b4fa`), Phase = green (`#a6e3a1`)

**And** Sau khi toàn bộ 50 points nhận xong, hiển thị toast/status "Sweep complete"

---

### Story 4.3: Calibration-Corrected Gain Display

As an engineer,
I want gain measurements corrected by calibration data loaded from disk,
So that Bode plot results account for circuit offsets and show accurate absolute gain values.

**Acceptance Criteria:**

**Given** `%APPDATA%\AplifierAnalyze\calibration.json` tồn tại với schema đúng
**When** AppPresenter khởi động
**Then** `data_model.py` load calibration file: `CAL_FILE = os.path.join(os.getenv('APPDATA'), 'AplifierAnalyze', 'calibration.json')`

**And** Nếu file không tồn tại, dùng default values: `dc_offset_mv=0.0`, `gain_correction={range_x1:1.0, range_div10:1.0, range_div100:1.0}`

**And** `compute_gain_rms()` trong AppPresenter phải nhân kết quả với `gain_correction[current_range]`

**And** `decode_osc_payload()` phải trừ `dc_offset_mv / 1000.0` từ voltage trước khi return

**And** Schema calibration.json phải đúng format trong architecture spec (version, date, dc_offset_mv, gain_correction dict)

**And** `DataModel.save_calibration(dc_offset_mv, gain_correction)` method phải ghi atomically (write to temp file rồi rename)

---

## Epic 5: Integration, Trigger & Calibration

**Goal:** Implement OSC_CAPTURE mode với firmware trigger, calibration capture workflow, và end-to-end integration test toàn hệ thống để đạt MVP hoàn chỉnh.

---

### Story 5.1: Firmware Trigger & OSC_CAPTURE Mode

As an engineer,
I want to capture a single high-resolution waveform triggered by a signal edge,
So that I can analyze transient responses and fast signals at full 2.8 MSPS resolution.

**Acceptance Criteria:**

**Given** State machine ở `SYS_OSC_CAPTURE` (sau `CMD:START_OSC_CAPTURE`)
**When** `<CMD:SET_TRIGGER, EDGE:RISING, LEVEL:2048>\n` đã được gửi từ PC
**Then** `adc_engine.c` fill pre-trigger circular buffer liên tục (512 samples = 50% of 1024)

**And** `trigger_detect()` scan buffer tìm edge crossing đúng algorithm:
```c
bool trigger_detect(uint16_t* buf, uint16_t len, uint16_t level, bool rising) {
    for (int i = 1; i < len; i++) {
        if (rising  && buf[i-1] < level && buf[i] >= level) return true;
        if (!rising && buf[i-1] > level && buf[i] <= level) return true;
    }
    return false;
}
```

**And** Khi trigger detected: gửi 1 OSC_CAPTURE frame (TYPE 0x03) chứa [pre_trigger_buf | post_trigger_buf] = 1024 samples

**And** Sau khi gửi xong, state machine tự transition về `SYS_IDLE`

**And** Desktop AppPresenter parse TYPE 0x03 frame và hiển thị trên Oscilloscope panel (code path khác với TYPE 0x01 streaming)

**And** Osc Panel phải có UI control: "Single Capture" button, Trigger Level slider (0–3.3V), Edge dropdown (Rising/Falling)

**And** Timeout: nếu không có trigger sau 5 giây, firmware gửi lại `SYS_IDLE` và PC hiển thị "Trigger timeout"

---

### Story 5.2: Calibration Workflow

As an engineer,
I want a calibration procedure that captures open-circuit and short-circuit baselines,
So that DC offset and gain errors are corrected and measurements are accurate.

**Acceptance Criteria:**

**Given** Calibration mode được trigger từ GUI (menu hoặc button "Run Calibration")
**When** User làm theo 2-step procedure
**Then** Step 1: "Open circuit" — capture 1000 samples với input không nối → tính `dc_offset_mv = mean(ch1_V) * 1000`

**And** Step 2: "Short circuit" (hoặc bypass với unity gain path) — capture và tính `gain_correction` cho từng range

**And** GUI phải hiển thị step-by-step instructions cho user (dialog box)

**And** Sau khi hoàn thành, kết quả được ghi vào `%APPDATA%\AplifierAnalyze\calibration.json` với timestamp

**And** Calibration được load tự động mỗi lần app khởi động

**And** Khi calibration thành công, status bar hiển thị: "Calibration loaded: [date]"

---

### Story 5.3: End-to-End Integration Test

As a developer,
I want an automated integration test that verifies the full data pipeline from simulation to display,
So that regressions are caught before hardware testing and the MVP is verifiable without hardware.

**Acceptance Criteria:**

**Given** `SIMULATION_MODE = True`
**When** `pytest tests/` chạy
**Then** Tất cả unit tests pass: `test_frame_parser.py` (5 cases), `test_dsp.py`, `test_data_model.py`

**And** Integration test `test_integration_simulation.py` phải test end-to-end:
1. SerialReader simulation generate frames
2. Frames đi qua FrameParser → ParsedFrame
3. AppPresenter decode → DataModel update
4. DSP functions return valid arrays

**And** Không có test nào cần real hardware hay real COM port

**And** `pytest tests/ -v --tb=short` phải in kết quả pass/fail rõ ràng

**And** Code coverage phải ≥70% cho `core/frame_parser.py` và `core/dsp.py` (đo bằng `pytest --cov`)

---

## Epic 6: Export & Polish

**Goal:** CSV export, PyInstaller packaging, logging config, UI polish hoàn chỉnh (Catppuccin theme, status bar, keyboard shortcuts). Hệ thống sẵn sàng phát hành.

---

### Story 6.1: CSV Data Export

As an engineer,
I want to export oscilloscope and Bode plot data to CSV files,
So that I can analyze measurements in Excel or other tools after the session.

**Acceptance Criteria:**

**Given** Có waveform data hoặc Bode data trong DataModel
**When** User click "Export CSV" (menu File → Export)
**Then** File dialog mở để chọn save location

**And** OSC export CSV format:
```
time_s,ch1_V,ch2_V
0.000000,1.235,0.423
...
```

**And** Bode export CSV format:
```
freq_hz,gain_db,phase_deg
100,0.1,-0.5
...
```

**And** Nếu không có data, hiển thị warning dialog: "No data to export"

**And** Export không block UI thread (dùng `QThread` hoặc Python `threading` nếu file lớn)

**And** Sau export thành công, status bar hiển thị "Exported to: [filepath]"

---

### Story 6.2: Logging Config & PyInstaller Packaging

As a developer,
I want proper logging configuration and a PyInstaller spec file,
So that the app can be distributed as a standalone .exe with crash logs accessible.

**Acceptance Criteria:**

**Given** App chuẩn bị release
**When** `main.py` khởi động
**Then** `logging.basicConfig()` được configure với:
- Level: `DEBUG` khi `SIMULATION_MODE=True`, `INFO` khi `False`
- File handler: `%APPDATA%\AplifierAnalyze\app.log` (rotating, max 1MB, 3 backups)
- Console handler: stderr, level INFO
- Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

**And** `aplifier_analyze.spec` file tồn tại và build thành công: `pyinstaller aplifier_analyze.spec --clean`

**And** `.spec` phải include: tất cả `ui/` và `core/` modules, `config.py`, không include `tests/`

**And** Generated `.exe` trong `dist/` phải chạy trên Windows 10+ mà không cần install Python

**And** `.exe` phải start trong <5 giây trên machine không có Python

**And** App log phải ghi dòng đầu tiên: `"Aplifier Analyze vX.X started — SIMULATION_MODE={value}"`

---

### Story 6.3: UI Polish & Status Bar

As an engineer,
I want a polished UI with status bar, keyboard shortcuts, and complete Catppuccin Mocha theming,
So that the application feels professional and is efficient to use in lab sessions.

**Acceptance Criteria:**

**Given** App đang chạy
**When** User mở app
**Then** Status bar hiển thị:
- Connection state: "Disconnected" / "Connected: COM3 @ 115200" / "Simulation Mode"
- Current mode: "Streaming" / "Idle" / "Sweep in progress"
- Last calibration date hoặc "Not calibrated"

**And** Keyboard shortcuts phải hoạt động:
- `Space`: Start/Stop streaming
- `B`: Start Bode sweep
- `S`: Single capture trigger
- `Ctrl+E`: Export CSV
- `Ctrl+Q`: Quit

**And** Toàn bộ UI áp dụng Catppuccin Mocha palette nhất quán:
- Background: `#1e1e2e`
- Surface: `#313244`
- Text: `#cdd6f4`
- Blue (primary): `#89b4fa`
- Green (secondary): `#a6e3a1`
- Red (error/CH2): `#f38ba8`
- Yellow (warning): `#f9e2af`

**And** Toàn bộ QSS stylesheet phải được define trong 1 file `ui/styles.py` — không hardcode trong từng widget

**And** Không có placeholder text còn sót lại từ Story 1.2

**And** App resize-responsive: tất cả panels co giãn đúng khi resize window

---

## Summary

| Epic | Stories | FRs covered | Deliverable |
|---|---|---|---|
| Epic 1: Foundation Scaffold | 3 stories | FR-06, FR-07 | Desktop app chạy với Simulation Mode |
| Epic 2: Binary Protocol & Pipeline | 4 stories | FR-03, FR-05 | End-to-end waveform streaming |
| Epic 3: Firmware Core | 4 stories | FR-01, FR-02 | Firmware thu phát tín hiệu thực |
| Epic 4: Bode Plot & DSP | 3 stories | FR-04, FR-08 | Bode analysis hoàn chỉnh |
| Epic 5: Integration & Calibration | 3 stories | FR-09, FR-10 | MVP hoàn chỉnh với trigger + calibration |
| Epic 6: Export & Polish | 3 stories | FR-06 (export/.exe) | Productionized release |
| **Tổng** | **20 stories** | **10 FRs** | **Full MVP** |
