---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - '_bmad-output/planning-artifacts/research/technical-aplifier-analyze-research-2026-04-18.md'
  - '_bmad-output/planning-artifacts/sprint-roadmap.md'
  - '_bmad-output/project-context.md'
workflowType: 'architecture'
lastStep: 8
status: 'complete'
project_name: 'Aplifier_Analyze'
user_name: 'Truong pc'
date: '2026-04-18'
completedAt: '2026-04-18'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

| ID | Requirement | Architectural Impact |
|---|---|---|
| FR-01 | Phát tín hiệu sine via STM32 DAC 12-bit nội bộ, sweep 100 Hz–500 kHz (Bode mode) | DAC DMA + TIM6 frequency control; Reconstruction LPF Sallen-Key fc=200 kHz |
| FR-02 | Thu 2 kênh ADC Dual Interleaved 2.8 MSPS, auto-range 3 dải ×1/÷10/÷100 | Analog Switch TMUX1072 GPIO-controlled; gain_factor phải embed trong mỗi data frame |
| FR-03 | Oscilloscope mode — realtime waveform ≥60 FPS, 2-channel | QTimer 16ms; pre-allocated NumPy buffers; trigger specification cần định nghĩa rõ |
| FR-04 | Bode plot — 50-step sweep, Gain (RMS) + Phase (FFT method), <±1 dB & <±2° | TIM2 interrupt-driven step scheduling (không HAL_Delay); calibration workflow cần thiết |
| FR-05 | Binary comm protocol Firmware→PC + ASCII command PC→Firmware | Frame schema: [0xAA 0xBB][Type:1B][Len:2B LE][Payload:N B][CRC8:1B]; gain_factor là field bắt buộc trong Oscilloscope frame |
| FR-06 | Desktop PyQt6 GUI — OSC + Bode panels, CSV export, standalone .exe | MVP pattern; PyInstaller packaging |
| FR-07 | Simulation mode (SIMULATION_MODE flag) — độc lập với hardware | SerialReader phải xử lý 2 mode trong cùng class |
| FR-08 ⚠️ | **[Mới — Party Mode]** Display unit conventions: V/mV auto-scale, Hz/kHz X-axis, phase -180°→+180° | DSP layer & UI layer phải dùng chung unit convention |
| FR-09 ⚠️ | **[Mới — Party Mode]** Calibration mode: open-circuit / short-circuit baseline capture | Cần calibration workflow và file lưu offset/gain trên disk |
| FR-10 ⚠️ | **[Mới — Party Mode]** Trigger specification: software edge trigger, configurable threshold, pre-trigger buffer % | Firmware scans DMA buffer for threshold crossing; pre-trigger buffer size cần define |

**Non-Functional Requirements:**

| NFR | Yêu cầu | Mức độ |
|---|---|---|
| PERF | CPU <30%, GUI ≥60 FPS, USB stream ổn định >30s không drop frame | 🔴 Critical |
| ACCURACY | ENOB ≥9.5 bit khi USB active; Phase <±2°; Gain <±1 dB | 🔴 Critical |
| REALTIME | Hard deadline: ADC DMA callback xử lý xong trước khi DMA fill buffer kế | 🔴 Hard real-time |
| RELIABILITY | Frame sync recovery tự động; USB CDC no-deadlock (không `while(USBD_BUSY)`) | 🟡 High |
| MAINTAINABILITY | Strict layered architecture firmware; không trộn HAL/LL cùng peripheral | 🟡 High |
| TESTABILITY | Simulation mode preserved; FrameParser unit tests không cần hardware | 🟢 Medium |
| PORTABILITY | Desktop .exe chạy không cần install Python | 🟢 Medium |

**Scale & Complexity:**

- Primary domain: **Embedded / Instrument / Desktop (triple-domain)**
- Complexity level: **HIGH**
- Architectural components: ~20 modules spanning 3 layers + 4 hardware subcircuits

---

### Technical Constraints & Dependencies

| Constraint | Detail | Impact |
|---|---|---|
| STM32 Clock Tree | SYSCLK=168 MHz → ADCCLK=21 MHz (÷4 từ 84 MHz APB2) | Max 2.8 MSPS Dual Interleaved — không thể tăng thêm |
| USB FS Bandwidth | Max ~1 MB/s optimized → phải decimate ADC trước khi gửi | Stream rate ≤350 KSPS; chunk size ≥512 bytes/TX call |
| DAC Slew Rate | Giới hạn thực tế ≤500 kHz | Distortion tăng theo tần số; amplitude cần giảm trong LUT |
| VDDA Noise | USB frame 1ms gây ripple → ENOB giảm 2–3 bits | Ferrite bead + LDO dedicated + oversampling ×4 bắt buộc |
| Qt Thread Safety | Tuyệt đối không gọi Qt widget từ bất kỳ non-main thread | Chỉ emit pyqtSignal từ QThread; dùng queue.Queue bounded |
| queue.Queue size | Unbounded queue → RAM leak khi DSP không kịp | Dùng `Queue(maxsize=N)` + drop-oldest policy; drain loop trong QTimer |

---

### Cross-Cutting Concerns Identified

1. **Gain Factor Synchronization** — `gain_factor` từ auto-range PHẢI là field trong mỗi data frame. Không được switch range trong khi DMA half-buffer đang active. Đây là inter-layer contract quan trọng nhất.

2. **Timing & Synchronization** — DMA ping-pong timing, USB frame 1ms, QTimer 16ms, TIM2 Bode step ISR — tất cả phải không xung đột.

3. **Data Integrity** — CRC8 frame validation; FrameParser HUNT-state recovery; `volatile` cho mọi ISR-shared variable.

4. **Voltage Domain** — ADC 0–3.3V; DC bias +1.65V; firmware decode: `vin = (adc/4095*3.3 - 1.65) / gain_factor`.

5. **Simulation/Hardware Duality** — `SerialReader` xử lý 2 mode trong cùng class; `SIMULATION_MODE` flag trong `config.py`.

6. **Error Recovery** — `SYS_ERROR` state cần transition `ERROR → IDLE` khi USB reconnect (không cần hard reset).

7. **FrameParser Emission Contract** — Phải định nghĩa trước: emit `pyqtSignal(bytes)` hay `pyqtSignal(ParsedFrame)` namedtuple. Quyết định này ảnh hưởng `AppPresenter` và tests.

8. **Filter State Re-init** — `lfilter_zi` phải được reinit khi sample rate hoặc cutoff thay đổi; `AppPresenter.on_config_change()` phải own trách nhiệm này.

---

### Open Architectural Questions (để giải quyết ở các bước tiếp theo)

| # | Câu hỏi | Priority |
|---|---|---|
| Q1 | Oscilloscope mode: **streaming** (liên tục ≤350 KSPS) hay **capture** (single-shot 2.8 MSPS → burst)? | 🔴 Critical |
| Q2 | Trigger: firmware edge trigger (threshold scan trong DMA callback) hay software trigger (PC side)? | 🔴 Critical |
| Q3 | FrameParser emit: raw `bytes` hay `ParsedFrame` namedtuple? | 🟡 High |
| Q4 | Calibration file format và storage location? | 🟡 High |
| Q5 | Bode sweep: TIM2 ISR scheduling hay main-loop với `uwTick` comparison? | 🟡 High |

---

## Starter Template Evaluation

### Primary Technology Domain

**Triple-domain:** Embedded Instrument (STM32 Firmware / C) + Desktop Application (Python / PyQt6)  
Không có single "starter template" phù hợp — mỗi layer có scaffolding strategy riêng.

### Starter Strategy: Manual Scaffold

**Rationale:** Module structure đã được fully specified trong Technical Research. Dùng scaffold CLI nặng sẽ tạo ra nhiều file cần xóa hơn file giữ lại. Manual scaffold là lựa chọn đúng đắn nhất cho dự án embedded instrument quy mô này.

---

### Layer 1 — Firmware Scaffold: STM32CubeMX

**Initialization:**
```
STM32CubeMX → New Project → STM32F407VETx → Generate Code → Open in STM32CubeIDE
```

**Peripherals cần configure trong CubeMX:**

| Peripheral | Mode | Ghi chú |
|---|---|---|
| ADC1 + ADC2 | Dual Interleaved, DMA Circular, Half-Word | ADCCLK = 21 MHz (APB2÷4) |
| DAC CH1 | DMA, triggered by TIM6 | 12-bit right-aligned |
| TIM6 | Internal clock, auto-reload | ARR = f(freq_hz, 256 LUT points) |
| TIM2 | Internal clock, ISR | Bode sweep step scheduling |
| USB_OTG_FS | CDC Device mode | PLLQ → 48 MHz |
| GPIO | Output Push-Pull | TMUX1072 select pins (2-bit auto-range) |

**Rule bắt buộc:** Commit file `.ioc` vào Git cùng với mọi thay đổi peripheral config.

---

### Layer 2 — Desktop Scaffold: Python Manual

**Initialization:**
```bash
mkdir App_desktop && cd App_desktop
# Tạo requirements.txt:
pyqt6>=6.0
pyqtgraph>=0.13
numpy
scipy
pyserial>=3.0
pyinstaller
```

---

### Defined Module Structure

```
Aplifier_Analyze/
├── App_desktop/
│   ├── main.py              ← QApplication entry, AppPresenter init
│   ├── config.py            ← COLORS (Catppuccin Mocha), SIMULATION_MODE, protocol constants
│   ├── ui/
│   │   ├── main_window.py   ← QMainWindow, layout, passive View
│   │   ├── osc_panel.py     ← QGroupBox oscilloscope controls
│   │   └── bode_panel.py    ← QGroupBox Bode plot controls
│   ├── core/
│   │   ├── serial_reader.py ← QThread + pyserial, emit raw bytes only
│   │   ├── frame_parser.py  ← FrameParser state machine (HUNT→HEADER→PAYLOAD→CRC)
│   │   ├── app_presenter.py ← MVP Presenter: wire View↔Model, own DSP calls
│   │   ├── dsp.py           ← Pure functions: compute_fft(), compute_phase_fft(), compute_gain_rms()
│   │   └── data_model.py    ← Pre-allocated NumPy arrays, filter state zi
│   └── requirements.txt
│
└── Firmware_STM32/
    ├── Aplifier_Analyze.ioc  ← CubeMX config (commit vào Git)
    ├── Core/
    │   ├── Src/
    │   │   ├── main.c
    │   │   ├── state_machine.c   ← App layer: enum SystemState_t, StateMachine_Run()
    │   │   ├── adc_engine.c      ← Service: ADC DMA init, ping-pong callbacks, decimation
    │   │   ├── dac_engine.c      ← Service: Sine LUT, DAC_SetFrequency(), DMA start
    │   │   ├── usb_tx.c          ← Service: FIFO 8KB, CDC_TransmitCplt_FS chain
    │   │   ├── autorange.c       ← Service: peak-to-peak detect, GPIO switch control
    │   │   └── cmd_parser.c      ← Service: parse ASCII commands từ CDC_Receive_FS
    │   └── Inc/
    │       ├── state_machine.h
    │       ├── adc_engine.h
    │       ├── dac_engine.h
    │       ├── usb_tx.h
    │       ├── autorange.h
    │       └── cmd_parser.h
    ├── USB_DEVICE/           ← CubeMX generated — không sửa tay
    └── Drivers/              ← CubeMX generated HAL — không sửa tay
```

**Architectural Decisions Established by Scaffold:**
- Language: C (Firmware), Python 3.10+ (Desktop) — không thay đổi
- USB middleware: ST HAL USB CDC stack — không viết lại từ đầu
- HAL generation: CubeMX — mọi peripheral init qua `.ioc`
- Build: STM32CubeIDE (firmware), pip + PyInstaller (desktop)
- Pattern: App→Service→HAL (firmware), MVP (desktop) — hardcoded trong scaffold

**Note:** Story đầu tiên trong Epic 1 sẽ là tạo project scaffold theo structure này.

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation — phải xong trước khi code):**
- D1: Oscilloscope acquisition mode → Cả hai (Stream + Capture)
- D2: Trigger mechanism → Firmware-side software trigger
- D3: FrameParser emission contract → ParsedFrame namedtuple

**Important Decisions (Shape Architecture):**
- D4: Bode sweep step scheduling → Main loop + `uwTick` comparison
- D5: Calibration file location → `AppData/Roaming/AplifierAnalyze/calibration.json`
- D6: queue.Queue maxsize → 32 (drop-oldest, ~0.5s buffer @ 60 FPS)

**Deferred Decisions (Post-MVP):**
- Trigger mode: Level trigger, Pre-trigger % configurable (v2)
- Export format: CSV first; Excel (openpyxl) là stretch goal
- Multi-language UI support (N/A — Vietnamese comments, UI in English)

---

### D1 — Oscilloscope Acquisition Mode

| Field | Value |
|---|---|
| **Decision** | Hỗ trợ **cả hai mode**: Streaming liên tục (≤350 KSPS) và Single-Shot Capture (2.8 MSPS burst) |
| **Toggle** | PC gửi command để chọn mode; Firmware chuyển state tương ứng |
| **Affects** | Firmware state machine, Frame Type table, Desktop display logic |

**Firmware State Machine (updated với SYS_CAPTURE):**
```
IDLE ──(CMD:START_OSC_STREAM)──→ CONFIGURING ──→ OSC_STREAM
IDLE ──(CMD:START_OSC_CAPTURE)─→ CONFIGURING ──→ OSC_CAPTURE ──(done)──→ IDLE
IDLE ──(CMD:START_SWEEP)───────→ CONFIGURING ──→ BODE_SWEEP  ──(done)──→ IDLE

       (CMD:STOP)
OSC_STREAM ────────────────────→ IDLE
Any state ──(USB disconnect)───→ ERROR ──(USB reconnect)──→ IDLE
```

```c
typedef enum {
    SYS_IDLE         = 0,
    SYS_CONFIGURING  = 1,
    SYS_OSC_STREAM   = 2,   // Liên tục, decimated, ≤350 KSPS
    SYS_OSC_CAPTURE  = 3,   // Single-shot, 2.8 MSPS → burst TX
    SYS_BODE_SWEEP   = 4,
    SYS_ERROR        = 5
} SystemState_t;
```

**Frame Type Table (updated):**

| Type Byte | Tên | Payload |
|---|---|---|
| `0x01` | OSC_STREAM frame | Interleaved CH1+CH2 uint16_t, decimated |
| `0x02` | BODE_RESULT frame | freq(float32) + gain_db(float32) + phase_deg(float32) |
| `0x03` | OSC_CAPTURE frame | Full-rate CH1+CH2 uint16_t, single snapshot |

**Error Recovery (Winston's concern — resolved):**  
`SYS_ERROR → SYS_IDLE` transition xảy ra khi USB reconnect được phát hiện (poll `hUsbDevice.dev_state == USBD_STATE_CONFIGURED`). Không cần hard reset.

---

### D2 — Trigger Mechanism

| Field | Value |
|---|---|
| **Decision** | **Firmware-side software trigger** — firmware scan DMA buffer tìm threshold crossing |
| **Scope** | Chỉ áp dụng cho `OSC_CAPTURE` mode; `OSC_STREAM` chạy free-running |
| **Pre-trigger** | 50% frame size (512 samples pre-trigger trong buffer 1024 samples) |
| **Affects** | cmd_parser.c, adc_engine.c, OSC_CAPTURE state logic |

**Command added:**
```
<CMD:SET_TRIGGER, EDGE:RISING, LEVEL:2048>\n
```
*(LEVEL: raw ADC code 0–4095; EDGE: RISING hoặc FALLING)*

**Firmware trigger algorithm (trong adc_engine.c):**
```c
// Sau khi DMA fill đủ pre-trigger buffer:
bool trigger_detect(uint16_t* buf, uint16_t len, uint16_t level, bool rising) {
    for (int i = 1; i < len; i++) {
        if (rising  && buf[i-1] < level && buf[i] >= level) return true;
        if (!rising && buf[i-1] > level && buf[i] <= level) return true;
    }
    return false;
}
// Khi trigger: gửi [pre_trigger_buf | post_trigger_buf] dưới dạng TYPE 0x03 frame
```

---

### D3 — FrameParser Emission Contract

| Field | Value |
|---|---|
| **Decision** | FrameParser emit `pyqtSignal(object)` với `ParsedFrame` namedtuple |
| **Rationale** | Separation of concerns — FrameParser hoàn toàn độc lập với DSP/GUI |
| **Affects** | frame_parser.py, app_presenter.py, unit tests |

**ParsedFrame definition (trong frame_parser.py):**
```python
from collections import namedtuple

ParsedFrame = namedtuple('ParsedFrame', [
    'frame_type',    # int: 0x01=OSC_STREAM, 0x02=BODE, 0x03=OSC_CAPTURE
    'payload',       # bytes: raw payload (chưa decode)
    'gain_factor',   # float: auto-range gain factor (embed trong payload header)
    'timestamp_ms',  # int: QTime.currentTime().msecsSinceStartOfDay() khi nhận
])

# FrameParser signal:
class FrameParser(QObject):
    frame_complete = pyqtSignal(object)   # emit ParsedFrame
```

**Payload schema cho OSC_STREAM / OSC_CAPTURE (TYPE 0x01, 0x03):**
```
[gain_range: 1B] [reserved: 1B] [num_samples: 2B LE] [CH1_0: 2B] [CH2_0: 2B] ... [CH1_N: 2B] [CH2_N: 2B]
```
*(gain_range: 0=×1, 1=÷10, 2=÷100 → Desktop tính gain_factor tương ứng)*

**Payload schema cho BODE_RESULT (TYPE 0x02):**
```
[freq_hz: 4B float32 LE] [gain_db: 4B float32 LE] [phase_deg: 4B float32 LE]
```
*(Mỗi frame = 1 Bode data point; 50 frames = 1 full sweep)*

---

### D4 — Bode Sweep Step Scheduling

| Field | Value |
|---|---|
| **Decision** | **Main loop + `HAL_GetTick()` comparison** (`uwTick`-based) |
| **Rationale** | 50 steps × 5ms/step = 250ms total — không cần precision của TIM2 ISR |
| **TIM2 freed** | TIM2 có thể dùng cho mục đích khác nếu cần (trigger timing, v.v.) |
| **Affects** | state_machine.c (SYS_BODE_SWEEP handler), dac_engine.c |

**Pattern trong state_machine.c:**
```c
case SYS_BODE_SWEEP:
    if ((HAL_GetTick() - bode_last_tick) >= BODE_STEP_INTERVAL_MS) {
        bode_last_tick = HAL_GetTick();
        DAC_SetFrequency(bode_freq_table[bode_step_idx]);
        // Wait 2ms settle (HAL_GetTick based, không blocking)
        if (bode_settled) {
            adc_capture_bode_step();    // Capture CH_in + CH_out
            compute_and_send_bode();    // Pack TYPE 0x02 frame, enqueue FIFO
            bode_step_idx++;
        }
    }
    if (bode_step_idx >= BODE_TOTAL_STEPS) g_sys_state = SYS_IDLE;
    break;
```

---

### D5 — Calibration File & Persistence

| Field | Value |
|---|---|
| **Decision** | `%APPDATA%\AplifierAnalyze\calibration.json` |
| **Rationale** | Chuẩn Windows app — không bị overwrite khi update .exe, không cần admin rights |
| **Affects** | app_presenter.py (load/save cal), FR-09 Calibration mode |

**File format:**
```json
{
  "version": 1,
  "date": "2026-04-18T00:00:00",
  "dc_offset_mv": 12.5,
  "gain_correction": {
    "range_x1":    1.0023,
    "range_div10": 0.9987,
    "range_div100": 1.0011
  }
}
```

**Python path resolution:**
```python
import os
CAL_FILE = os.path.join(os.getenv('APPDATA'), 'AplifierAnalyze', 'calibration.json')
os.makedirs(os.path.dirname(CAL_FILE), exist_ok=True)
```

---

### D6 — Desktop Queue Size & Drop Policy

| Field | Value |
|---|---|
| **Decision** | `queue.Queue(maxsize=32)` với **drop-oldest** policy |
| **Rationale** | ~0.5s buffer @ 60 FPS — đủ absorb DSP spike, không để RAM leak vô hạn |
| **Affects** | serial_reader.py (producer), app_presenter.py (consumer drain loop) |

**Pattern:**
```python
# serial_reader.py — Producer
self.data_queue = queue.Queue(maxsize=32)

def _enqueue(self, frame: ParsedFrame):
    if self.data_queue.full():
        try:
            self.data_queue.get_nowait()   # Drop oldest
        except queue.Empty:
            pass
    self.data_queue.put_nowait(frame)

# app_presenter.py — Consumer (gọi bởi QTimer 16ms)
def update_display(self):
    processed = 0
    while not self.data_queue.empty() and processed < 4:  # Max 4 frames/tick
        frame = self.data_queue.get_nowait()
        self._process_frame(frame)
        processed += 1
    self.view.refresh()  # Chỉ update GUI 1 lần/tick dù process nhiều frames
```

---

### Decision Impact Analysis

**Implementation Sequence (bắt buộc theo thứ tự):**
1. Protocol spec (frame types 0x01/0x02/0x03 + payload schema) → **Phải xong trước mọi thứ**
2. FrameParser (ParsedFrame emission) → Desktop có thể test với mock data
3. Firmware state machine (5 states) + cmd_parser → Firmware base
4. adc_engine (Dual Interleaved DMA ping-pong) → Data acquisition
5. usb_tx (FIFO 8KB + CDC callback chain) → Data transport
6. dac_engine (Sine LUT + TIM6) → Signal generation
7. autorange (TMUX1072 GPIO control) → Auto-ranging
8. Desktop MVP (SerialReader → Queue → Presenter → View) → End-to-end integration
9. DSP functions (FFT, lfilter, Cross-Corr, phase) → Signal processing
10. Bode sweep coordinator → Full Bode plot
11. Trigger logic (OSC_CAPTURE mode) → Advanced capture
12. Calibration workflow → Accuracy refinement

**Cross-Component Dependencies:**
- `gain_factor` (autorange.c) → embedded trong OSC frame payload → decoded trong app_presenter.py
- `ParsedFrame.frame_type` → routing logic trong `AppPresenter._process_frame()`
- `SIMULATION_MODE` flag → SerialReader chọn `_run_simulation()` vs `_run_hardware()`
- Calibration `gain_correction` → apply trong `dsp.py` sau khi giải mã gain_factor

---

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Python (Desktop) — bắt buộc cho mọi file:**

| Loại | Convention | Ví dụ |
|---|---|---|
| Functions / variables | `snake_case` | `compute_gain_rms()`, `gain_factor`, `frame_type` |
| Classes | `PascalCase` | `FrameParser`, `AppPresenter`, `DataModel` |
| Constants (module-level) | `UPPER_SNAKE_CASE` | `SIMULATION_MODE`, `HEADER_BYTE_1 = 0xAA` |
| pyqtSignal names | `snake_case` | `data_received`, `frame_complete`, `connection_error` |
| Files | `snake_case.py` | `serial_reader.py`, `frame_parser.py`, `dsp.py` |

**C (Firmware) — bắt buộc cho mọi file:**

| Loại | Convention | Ví dụ |
|---|---|---|
| Local variables | `camelCase` | `adcBufIdx`, `gainFactor`, `bodeLastTick` |
| `#define` constants | `UPPER_SNAKE_CASE` | `ADC_HALF_SIZE`, `USB_TX_FIFO_SIZE 8192` |
| Typedef structs/enums | `PascalCase_t` | `SystemState_t`, `BodeResult_t`, `OscFrameHeader_t` |
| Functions | `Module_Action()` | `ADC_StartDMA()`, `USB_EnqueueFrame()`, `DAC_SetFrequency()` |
| Global volatile vars | `g_` prefix | `g_sys_state`, `g_gain_factor`, `g_stop_requested` |

---

### Code Structure Patterns

**Python file header (bắt buộc đầu mọi `.py` file):**
```python
"""
Module: <tên module>
Mục đích: <mô tả ngắn bằng Tiếng Việt>
Sections:
  - IMPORTS
  - CONSTANTS
  - CLASS / FUNCTIONS
Tác giả: Truong pc
"""
```

**C file header (bắt buộc đầu mọi `.c` / `.h` file):**
```c
/**
 * @file    adc_engine.c
 * @brief   Mô tả ngắn bằng tiếng Việt
 * @author  Truong pc
 */
```

**Section separator (Python) — dùng ASCII banner:**
```python
# ===== CONSTANTS =====
# ===== SERIAL COMMUNICATION =====
# ===== DSP PROCESSING =====
```

**Inline comments:** **Tiếng Việt** trong toàn bộ codebase (Python + C). Không được dùng tiếng Anh cho inline comments.

---

### Protocol Encoding Patterns

**Python — struct packing (bắt buộc little-endian `'<'`):**
```python
import struct
# Unpack OSC frame header (TYPE 0x01 / 0x03):
gain_range, reserved, num_samples = struct.unpack_from('<BBH', payload, 0)
data_start = 4  # bytes
# Unpack interleaved samples:
samples = struct.unpack_from(f'<{num_samples * 2}H', payload, data_start)

# Unpack Bode point (TYPE 0x02):
freq_hz, gain_db, phase_deg = struct.unpack_from('<fff', payload, 0)
```

**C — payload packing (phải khớp Python struct format ở trên):**
```c
// Phải dùng __attribute__((packed)) để tránh padding
typedef struct __attribute__((packed)) {
    uint8_t  gain_range;    // 0=x1, 1=div10, 2=div100
    uint8_t  reserved;      // 0x00
    uint16_t num_samples;   // số cặp CH1/CH2
} OscFrameHeader_t;

typedef struct __attribute__((packed)) {
    float freq_hz;
    float gain_db;
    float phase_deg;
} BodeResultFrame_t;
```

> ⚠️ **CRITICAL RULE:** Khi thay đổi payload schema → phải update **cả hai** C và Python trong **cùng một commit**. Không được tách ra 2 commits.

---

### Error Handling Patterns

**Python — logging (không dùng `print()` trong production code):**
```python
import logging
logger = logging.getLogger(__name__)  # Mỗi module có logger riêng

# Levels:
logger.debug("Nhận được frame type=0x{:02X}".format(frame.frame_type))
logger.warning("Queue đầy — drop oldest frame")
logger.error(f"Lỗi CRC: expected={expected:#04x}, got={got:#04x}")
logger.critical("Mất kết nối USB — stop acquisition")
```

**Firmware — Error state (không dùng `while(1)` halt):**
```c
// Mọi lỗi nghiêm trọng → set SYS_ERROR, ghi error code
typedef enum {
    ERR_NONE          = 0,
    ERR_USB_TIMEOUT   = 1,
    ERR_ADC_OVERFLOW  = 2,
    ERR_FIFO_FULL     = 3,
} ErrorCode_t;

void Error_Set(ErrorCode_t code) {
    g_error_code = code;
    g_sys_state  = SYS_ERROR;
    // Không NVIC_SystemReset() — chờ USB reconnect để recover
}
```

---

### Testing Patterns

**Python unit tests — pytest + unittest.mock (không cần hardware):**
```python
from unittest.mock import MagicMock, patch
from core.frame_parser import FrameParser, ParsedFrame

def test_frame_parser_split_mid_payload():
    """Kiểm tra FrameParser xử lý đúng khi frame bị split giữa payload."""
    parser = FrameParser()
    received = []
    parser.frame_complete.connect(lambda f: received.append(f))
    # Tạo frame hợp lệ rồi split:
    full = b'\xAA\xBB\x01\x04\x00\x01\x02\x03\x04\xXX'  # CRC placeholder
    parser.feed(full[:5])   # split mid-payload
    parser.feed(full[5:])
    assert len(received) == 1
    assert isinstance(received[0], ParsedFrame)
```

**Bắt buộc test 5 edge cases (Amelia's list — không được bỏ qua):**
1. ✅ Perfect stream → emit đúng ParsedFrame
2. ✅ Split mid-header (sau byte 3/5)
3. ✅ Split mid-payload
4. ✅ Bad CRC → HUNT recovery (không crash, không emit)
5. ✅ Consecutive false sync: `0xAA 0xAA 0xBB` → recover đúng

---

### UI Display Patterns

**Unit conventions (FR-08 — bắt buộc):**

| Đại lượng | Rule | Ví dụ |
|---|---|---|
| Voltage | Auto-scale: <0.1V → dùng mV | `"12.5 mV"` / `"1.24 V"` |
| Frequency (Bode X) | <1000 Hz → `Hz`; ≥1000 → `kHz` | `"500 Hz"` / `"10.0 kHz"` |
| Phase | Luôn -180° → +180°, 1 decimal | `"-45.3°"` |
| Gain | Luôn `dB`, 1 decimal | `"-6.0 dB"` |

**pyqtgraph performance rules (KHÔNG ĐƯỢC vi phạm):**
```python
# ✅ ĐÚNG — reuse PlotDataItem trong update loop:
self.ch1_curve.setData(time_arr, ch1_arr)
self.fft_curve.setData(freq_arr, fft_arr)

# ❌ SAI — tạo PlotDataItem mới mỗi tick (cực kỳ chậm):
self.osc_plot.plot(time_arr, ch1_arr)  # KHÔNG BAO GIỜ trong QTimer callback
```

---

### Enforcement Guidelines

**All AI Agents MUST:**

- Đọc file `_bmad-output/project-context.md` trước bất kỳ bước implement nào
- Đọc section **Protocol Encoding Patterns** trước khi viết bất kỳ code serial/USB nào
- Kiểm tra `SIMULATION_MODE` flag trước khi thêm bất kỳ hardware-specific call nào
- Dùng `logger` thay `print()` trong mọi Python production code
- Không sửa code ngoài `/* USER CODE BEGIN */` blocks trong CubeMX-generated files
- Commit `.ioc` file cùng với mọi thay đổi peripheral trong CubeMX

**Anti-Patterns (KHÔNG BAO GIỜ làm):**

| Anti-pattern | Vì sao sai | Thay bằng |
|---|---|---|
| `serial.readline()` cho binary | `0x0A` trong payload bị cắt | `serial.read(n)` theo Length field |
| `filtfilt()` trong streaming | Cần full signal — offline only | `lfilter(b, a, chunk, zi=zi)` |
| `QTimer.start()` trước khi port mở | Exception ngay tick đầu | Check `serial.is_open` trước |
| `while(CDC_Transmit_FS() == USBD_BUSY)` | Deadlock ngay lập tức | `CDC_TransmitCplt_FS` callback chain |
| Trộn HAL + LL cùng 1 peripheral | Undefined behavior | Chọn 1 abstraction level, giữ nhất quán |
| `np.plot()` / tạo array mới trong loop | RAM spike, GC pressure | Slice assignment `arr[:] = new_data` |

---

## Project Structure & Boundaries

### Complete Project Directory Structure

```
Aplifier_Analyze/
│
├── README.md
├── .gitignore
│
├── App_desktop/                         ← Desktop layer (Python/PyQt6)
│   ├── main.py                          ← QApplication entry; khởi tạo AppPresenter
│   ├── config.py                        ← SIMULATION_MODE, COLORS (Catppuccin), protocol consts
│   ├── requirements.txt
│   │
│   ├── ui/                              ← VIEW layer (passive — chỉ hiển thị, emit events)
│   │   ├── main_window.py               ← QMainWindow; layout tổng thể; connect signals
│   │   ├── osc_panel.py                 ← QGroupBox: chọn kênh, timebase, trigger controls
│   │   └── bode_panel.py                ← QGroupBox: f_start/f_stop/steps; Mag+Phase plots
│   │
│   ├── core/                            ← Business logic (không import từ ui/)
│   │   ├── app_presenter.py             ← MVP Presenter: wire View↔Model; QTimer 16ms
│   │   ├── serial_reader.py             ← QThread + pyserial; emit raw bytes; SIMULATION aware
│   │   ├── frame_parser.py              ← FrameParser SM + ParsedFrame namedtuple
│   │   ├── dsp.py                       ← Pure functions: FFT, phase, gain, filter (no Qt)
│   │   └── data_model.py                ← Pre-allocated NumPy arrays; filter zi; cal loader
│   │
│   └── tests/
│       ├── test_frame_parser.py         ← 5 edge cases bắt buộc (Amelia's list)
│       ├── test_dsp.py                  ← compute_phase_fft, gain_rms, lfilter state
│       └── test_data_model.py           ← pre-alloc, slice-assign correctness
│
├── Firmware_STM32/                      ← Firmware layer (C / STM32F407VET6)
│   ├── Aplifier_Analyze.ioc             ← CubeMX config (COMMIT với mọi peripheral change)
│   │
│   ├── Core/
│   │   ├── Src/
│   │   │   ├── main.c                   ← HAL_Init, clock config, gọi StateMachine_Run()
│   │   │   ├── state_machine.c          ← App layer: enum 5 states; transitions
│   │   │   ├── adc_engine.c             ← Service: Dual Interleaved DMA; ping-pong; trigger
│   │   │   ├── dac_engine.c             ← Service: Sine LUT 256pt; TIM6 DMA; freq sweep
│   │   │   ├── usb_tx.c                 ← Service: FIFO 8KB; frame packer; CDC chain
│   │   │   ├── autorange.c              ← Service: peak-to-peak; TMUX1072 GPIO
│   │   │   └── cmd_parser.c             ← Service: parse ASCII cmds; set g_cmd_* flags
│   │   │
│   │   └── Inc/
│   │       ├── state_machine.h          ← SystemState_t; ErrorCode_t; g_sys_state extern
│   │       ├── adc_engine.h
│   │       ├── dac_engine.h
│   │       ├── usb_tx.h                 ← OscFrameHeader_t; BodeResultFrame_t; FIFO API
│   │       ├── autorange.h
│   │       └── cmd_parser.h
│   │
│   ├── USB_DEVICE/                      ← CubeMX generated — KHÔNG sửa tay
│   └── Drivers/                         ← CubeMX HAL — KHÔNG sửa tay
│
└── Hardware/                            ← Hardware design files
    ├── schematic/                       ← KiCad / EasyEDA project
    └── docs/
        ├── BOM.csv                      ← Bill of Materials (TMUX1072, LMV321, BAT54, ferrite)
        └── circuit_notes.md             ← AFE design notes, component values, clock tree
```

---

### Architectural Boundaries (Layer Rules)

| From | To | Mechanism | Vi phạm bị cấm |
|---|---|---|---|
| `ui/` → `core/` | Signal-Slot only | `pyqtSignal` + `.connect()` | Direct call từ View sang Presenter |
| `serial_reader` → `frame_parser` | `data_received = pyqtSignal(bytes)` | frame_parser import serial_reader |
| `frame_parser` → `app_presenter` | `frame_complete = pyqtSignal(object)` | frame_parser biết về DSP/GUI |
| `dsp.py` | Pure functions, no Qt | Import Qt bất kỳ trong dsp.py |
| Firmware App → HAL | Chỉ qua Service layer | `main.c` gọi thẳng `HAL_ADC_*` |
| Service layer | Chỉ trong `/* USER CODE BEGIN */` | Sửa code ngoài USER CODE block |

---

### FR → File Mapping

| FR | File(s) chiu trách nhiệm |
|---|---|
| FR-01 (DAC TX sine) | `dac_engine.c`, `dac_engine.h` |
| FR-02 (ADC + auto-range) | `adc_engine.c`, `autorange.c`, `autorange.h` |
| FR-03 (Oscilloscope mode) | `state_machine.c`, `adc_engine.c`, `osc_panel.py`, `dsp.py` |
| FR-04 (Bode plot) | `state_machine.c`, `dac_engine.c`, `bode_panel.py`, `dsp.py` |
| FR-05 (Protocol) | `usb_tx.c`, `usb_tx.h`, `frame_parser.py`, `config.py` |
| FR-06 (Desktop GUI) | `main_window.py`, `osc_panel.py`, `bode_panel.py`, `app_presenter.py` |
| FR-07 (Simulation mode) | `serial_reader.py`, `config.py` (`SIMULATION_MODE`) |
| FR-08 (Display units) | `dsp.py` (format helpers), `osc_panel.py`, `bode_panel.py` |
| FR-09 (Calibration) | `data_model.py`, `app_presenter.py`, `%APPDATA%\\AplifierAnalyze\\calibration.json` |
| FR-10 (Trigger) | `adc_engine.c`, `cmd_parser.c`, `osc_panel.py` |

---

### Data Flow (End-to-End)

```
[STM32 ADC Dual Interleaved DMA]
        ↓ (ISR callback — ping-pong)
[adc_engine.c: decimation + gain_range embed]
        ↓
[usb_tx.c: FIFO 8KB → CDC_TransmitCplt_FS chain]
        ↓ (USB FS CDC, binary frames)
[serial_reader.py: QThread, pyserial.read()]
        ↓ pyqtSignal(bytes) — cross-thread safe
[frame_parser.py: HUNT→HEADER→PAYLOAD→CRC]
        ↓ pyqtSignal(ParsedFrame) — cross-thread safe
[app_presenter.py: _enqueue() → Queue(maxsize=32)]
        ↓ QTimer 16ms drain loop (main thread)
[dsp.py: decode → FFT / lfilter / phase / gain]
        ↓
[data_model.py: slice-assign NumPy arrays]
        ↓
[osc_panel.py / bode_panel.py: curve.setData()]
        ↓
[pyqtgraph OpenGL render → screen]
```

---

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
- STM32F407 clock tree: SYSCLK=168 MHz → ADCCLK=21 MHz + USB PLLQ=48 MHz — coexist verified (RM0090)
- USB CDC + ADC DMA: không xung đột DMA channel (ADC1/2 dùng DMA2; USB OTG FS có controller riêng)
- PyQt6 + pyqtgraph + NumPy/SciPy: fully compatible, đã xác nhận trong project-context.md
- `OSC_CAPTURE` (SYS_CAPTURE=3) không xung đột với `OSC_STREAM` (SYS_OSC_STREAM=2) — mutual exclusive states

**Pattern Consistency:**
- MVP pattern ↔ Signal-Slot rule ↔ QThread/Queue/QTimer — consistent chain end-to-end
- `ParsedFrame` namedtuple ↔ FrameParser boundary ↔ AppPresenter — clean handoff, no coupling
- Firmware App→Service→HAL ↔ `/* USER CODE BEGIN */` rule — enforced at code level

**Structure Alignment:**
- `core/` không import từ `ui/` — enforced bởi boundary rule trong Patterns section
- `dsp.py` pure functions, no Qt import — enforced bởi layer rule
- HAL chỉ qua Service layer — enforced bởi firmware architecture

---

### Requirements Coverage Validation ✅

| FR | Kiến trúc hỗ trợ | Status |
|---|---|---|
| FR-01 (DAC TX) | `dac_engine.c` + TIM6 + Sine LUT 256pt | ✅ |
| FR-02 (ADC auto-range) | `adc_engine.c` + `autorange.c` + TMUX1072 GPIO | ✅ |
| FR-03 (Oscilloscope) | `OSC_STREAM` state + `osc_panel.py` + QTimer 16ms | ✅ |
| FR-04 (Bode plot) | `BODE_SWEEP` state + `bode_panel.py` + FFT phase | ✅ |
| FR-05 (Protocol) | Frame spec 0x01/0x02/0x03 + `frame_parser.py` + `usb_tx.c` | ✅ |
| FR-06 (Desktop GUI) | MVP + `main_window.py` + panels + PyInstaller | ✅ |
| FR-07 (Simulation) | `SIMULATION_MODE` + `serial_reader._run_simulation()` | ✅ |
| FR-08 (Display units) | Unit convention table trong Patterns section | ✅ |
| FR-09 (Calibration) | `%APPDATA%\\AplifierAnalyze\\calibration.json` + `data_model.py` | ✅ |
| FR-10 (Trigger) | `OSC_CAPTURE` state + `trigger_detect()` + `SET_TRIGGER` cmd | ✅ |

**Non-Functional Requirements Coverage:**

| NFR | Giải pháp kiến trúc | Status |
|---|---|---|
| PERF (CPU <30%, ≥60 FPS) | QTimer 16ms; max 4 frames/tick; pre-allocated NumPy | ✅ |
| ACCURACY (ENOB ≥9.5 bit) | Ferrite bead VDDA + oversampling ×4 | ✅ HW |
| REALTIME (DMA deadline) | Ping-pong pattern; process in half-callback | ✅ |
| RELIABILITY (sync recovery) | FrameParser HUNT state; Error→IDLE on USB reconnect | ✅ |
| MAINTAINABILITY (layered) | App→Service→HAL; không trộn HAL/LL | ✅ |
| TESTABILITY | Simulation mode + pytest + mock pyserial | ✅ |
| PORTABILITY (.exe) | PyInstaller packaging; `%APPDATA%` cal file | ✅ |

---

### Gap Analysis Results

**Critical Gaps:** ✅ Không có gaps block implementation

**Important Gaps (ghi nhận, giải quyết trong epic tương ứng):**

| Gap | Epic sẽ xử lý |
|---|---|
| `logging.basicConfig()` config chưa định nghĩa format + output file cho .exe | Epic 6 (Export & Polish) |
| PyInstaller `.spec` file template chưa có | Epic 6 (Export & Polish) |
| Hardware BOM chi tiết + giá trị linh kiện | Hardware design phase (ngoài scope software) |

**Minor Gaps (optional, post-MVP):**
- Keyboard shortcuts cho Desktop GUI
- Level trigger với configurable pre-trigger %
- Excel export via openpyxl

---

### Architecture Completeness Checklist

**✅ Requirements Analysis (Step 2)**
- [x] 10 Functional Requirements định nghĩa và map sang kiến trúc
- [x] 7 Non-Functional Requirements + mức độ priority
- [x] 6 Technical constraints & dependencies
- [x] 8 Cross-cutting concerns được xác định
- [x] 5 Open questions được giải quyết trong Step 4

**✅ Architectural Decisions (Step 3+4)**
- [x] 7 ADRs từ Technical Research (ADR-001 → ADR-007)
- [x] 6 New decisions (D1–D6) đưa ra trong workflow này
- [x] Full frame type table (0x01/0x02/0x03) với payload schemas
- [x] State machine 5 states với error recovery `ERROR→IDLE`

**✅ Implementation Patterns (Step 5)**
- [x] Naming conventions (Python + C)
- [x] File header templates (Python + C)
- [x] Protocol encoding patterns (struct little-endian, `__attribute__((packed))`)
- [x] Error handling (logging levels + ErrorCode_t enum)
- [x] 5 bắt buộc FrameParser edge case tests
- [x] UI display unit conventions
- [x] 6 anti-patterns documented

**✅ Project Structure (Step 6)**
- [x] Full directory tree (App_desktop + Firmware_STM32 + Hardware)
- [x] FR → File mapping hoàn chỉnh (10 FRs mapped)
- [x] Layer boundary rules (6 rules)
- [x] End-to-end data flow diagram

---

### Architecture Readiness Assessment

**Overall Status: 🚀 READY FOR IMPLEMENTATION**

**Confidence Level: HIGH**

**Key Strengths:**
1. Binary protocol spec hoàn toàn defined — C struct ↔ Python struct format matched
2. State machine 5 states với error recovery rõ ràng, không cần hard reset
3. Simulation mode preserved — có thể test toàn bộ Desktop pipeline không cần hardware
4. Queue bounded (maxsize=32) + drain loop — không có RAM leak risk
5. Gain factor embedded trong mọi data frame — auto-range sync được đảm bảo

**Areas for Future Enhancement (post-MVP):**
- Level trigger với pre-trigger % configurable
- Excel export (openpyxl)
- Logging file output cho production .exe

---

### Implementation Handoff

**AI Agent Guidelines:**
- Đọc `_bmad-output/project-context.md` + `_bmad-output/planning-artifacts/architecture.md` trước mọi task
- Tham chiếu **Protocol Encoding Patterns** trước khi viết bất kỳ code serial/USB
- Tham chiếu **FR → File Mapping** để biết story nào có liên quan file nào
- Giữ `SIMULATION_MODE` luôn hoạt động xuyữt suốt quá trình implement

**First Implementation Priority — Story 1 (Epic 1):**
```
1. Tạo CubeMX project STM32F407VET6
   → Configure: ADC1+ADC2 Dual Interleaved, DAC CH1 DMA, TIM6, USB OTG FS CDC, GPIO
   → Clock: SYSCLK=168 MHz, ADCCLK=21 MHz, PLLQ→48 MHz
   → Generate Code → STM32CubeIDE
   → Commit .ioc file

2. Tạo App_desktop/ folder structure:
   → ui/ (main_window.py, osc_panel.py, bode_panel.py)
   → core/ (app_presenter.py, serial_reader.py, frame_parser.py, dsp.py, data_model.py)
   → tests/ (test_frame_parser.py, test_dsp.py, test_data_model.py)
   → config.py + main.py + requirements.txt

3. Implement config.py với COLORS dict (Catppuccin Mocha) + SIMULATION_MODE + protocol consts
4. Commit scaffold lên Git
```

**Architecture completed:** 2026-04-18  
**Author:** Truong pc  
**Status:** ✅ COMPLETE — ready for Epic & Story creation phase
