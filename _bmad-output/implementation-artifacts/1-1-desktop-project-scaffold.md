# Story 1.1: Desktop Project Scaffold

## Story Information

| Field | Value |
|---|---|
| **Story ID** | 1.1 |
| **Story Key** | 1-1-desktop-project-scaffold |
| **Epic** | Epic 1 — Foundation Scaffold: Project Setup & Simulation Mode |
| **Status** | ready-for-dev |
| **Created** | 2026-04-20 |
| **Author** | Truong pc |

---

## User Story

**As a** developer,  
**I want** a complete `App_desktop/` folder structure with all module stubs and configuration,  
**So that** every subsequent story has a consistent foundation to build upon without restructuring.

---

## Acceptance Criteria

> **Tất cả criteria phải pass trước khi story được đánh dấu `done`.**

**AC-1: Cấu trúc thư mục đầy đủ**

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

**AC-2: requirements.txt đầy đủ**

`requirements.txt` phải chứa đủ (exact versions):
```
pyqt6>=6.0
pyqtgraph>=0.13
numpy
scipy
pyserial>=3.0
pyinstaller
```

**AC-3: File header chuẩn**

Mỗi `.py` file (trừ `__init__.py` rỗng) phải có file header đúng format:
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

**AC-4: config.py đúng spec**

`config.py` phải định nghĩa đầy đủ (không thiếu field nào):
- `SIMULATION_MODE: bool = True` ← default phải là `True`
- `HEADER_BYTE_1 = 0xAA`
- `HEADER_BYTE_2 = 0xBB`
- `FRAME_TYPE_OSC_STREAM = 0x01`
- `FRAME_TYPE_BODE = 0x02`
- `FRAME_TYPE_OSC_CAPTURE = 0x03`
- `COLORS` dict với Catppuccin Mocha palette, BẮT BUỘC có các keys: `background`, `surface`, `text`, `blue`, `green`, `red`, `yellow`
- `QUEUE_MAX_SIZE = 32`

**AC-5: Import test**

Lệnh sau chạy thành công không lỗi từ thư mục `App_desktop/`:
```bash
python -c "from config import SIMULATION_MODE, COLORS; print(SIMULATION_MODE)"
# Expected output: True
```

**AC-6: Commit đầu tiên**

Commit đầu tiên vào git phải bao gồm toàn bộ scaffold (tất cả files và thư mục).

---

## Developer Context

### Tổng quan Epic 1

Epic 1 bao gồm 3 stories tuần tự:
1. **Story 1.1 (này):** Desktop scaffold — tạo toàn bộ cấu trúc thư mục + stub files
2. **Story 1.2:** Main Window + Panel Stubs — PyQt6 app chạy được với UI cơ bản
3. **Story 1.3:** Simulation Mode — SerialReader synthetic frames chạy được hoàn toàn không cần hardware

**Story 1.1 là foundation cho toàn bộ project — sai ở đây sẽ ảnh hưởng tất cả 19 stories còn lại.**

### Vị trí trong toàn dự án

Dự án `Aplifier_Analyze` có 3 layer:
- **Desktop (Python/PyQt6)** ← Story này tạo scaffold
- **Firmware (C/STM32)** ← Epic 2, 3 sẽ phát triển
- **Hardware** ← Không nằm trong scope của epics

Story 1.1 chỉ tạo scaffold cho **Desktop layer** (`App_desktop/`). Không chạm vào `Firmware_STM32/`.

---

## Technical Requirements

### Kiến trúc bắt buộc (MVP Pattern)

```
main.py
  └── AppPresenter (core/app_presenter.py)
        ├── View: MainWindow (ui/main_window.py)
        │     ├── OscPanel (ui/osc_panel.py)
        │     └── BodePanel (ui/bode_panel.py)
        ├── SerialReader (core/serial_reader.py)  ← QThread
        ├── FrameParser (core/frame_parser.py)    ← QObject
        ├── DataModel (core/data_model.py)
        └── DSP functions (core/dsp.py)           ← Pure functions
```

**Layer Boundary Rules (CẤM VI PHẠM):**

| Rule | Mô tả |
|---|---|
| `core/` không import từ `ui/` | `core/` là business logic — không được biết về Qt widgets |
| `dsp.py` không import Qt | Pure functions chỉ dùng numpy/scipy |
| `ui/` chỉ giao tiếp via Signal-Slot | Không gọi `core/` method trực tiếp |

### File-by-file Implementation Guide

#### `main.py` — Entry Point
```python
"""
Module: main
Mục đích: Entry point của ứng dụng Aplifier Analyze — khởi tạo QApplication và AppPresenter
Sections:
  - IMPORTS
  - MAIN ENTRY POINT
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import sys
import logging
from PyQt6.QtWidgets import QApplication
from core.app_presenter import AppPresenter

# ===== MAIN ENTRY POINT =====
def main():
    # Khởi tạo Qt application
    app = QApplication(sys.argv)
    presenter = AppPresenter()
    presenter.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
```

#### `config.py` — Constants & Configuration
```python
"""
Module: config
Mục đích: Hằng số cấu hình toàn cục — protocol bytes, màu sắc UI, simulation flag
Sections:
  - IMPORTS
  - SIMULATION MODE
  - PROTOCOL CONSTANTS
  - UI COLORS (Catppuccin Mocha)
  - QUEUE SETTINGS
Tác giả: Truong pc
"""

# ===== SIMULATION MODE =====
SIMULATION_MODE: bool = True  # True = không cần phần cứng

# ===== PROTOCOL CONSTANTS =====
HEADER_BYTE_1 = 0xAA
HEADER_BYTE_2 = 0xBB

FRAME_TYPE_OSC_STREAM  = 0x01  # Streaming liên tục, decimated
FRAME_TYPE_BODE        = 0x02  # Một điểm dữ liệu Bode
FRAME_TYPE_OSC_CAPTURE = 0x03  # Single-shot capture toàn tốc

# Gain range mapping (từ firmware)
GAIN_RANGE_X1    = 0   # gain_factor = 1.0
GAIN_RANGE_DIV10  = 1   # gain_factor = 0.1
GAIN_RANGE_DIV100 = 2   # gain_factor = 0.01

# ===== UI COLORS (Catppuccin Mocha) =====
COLORS = {
    'background': '#1e1e2e',  # Crust/Base
    'surface':    '#313244',  # Surface0
    'text':       '#cdd6f4',  # Text
    'blue':       '#89b4fa',  # Blue (primary, CH1)
    'green':      '#a6e3a1',  # Green (secondary, CH2)
    'red':        '#f38ba8',  # Red (error/warning)
    'yellow':     '#f9e2af',  # Yellow (warning highlight)
}

# ===== QUEUE SETTINGS =====
QUEUE_MAX_SIZE = 32  # ~0.5s buffer @ 60 FPS trước khi drop oldest
```

> ⚠️ **QUAN TRỌNG:** Không được đổi tên keys trong `COLORS` dict. Tất cả modules UI sẽ import dict này bằng key name cố định.

#### `core/app_presenter.py` — Stub
```python
"""
Module: app_presenter
Mục đích: MVP Presenter — kết nối View và Model, điều phối data flow từ SerialReader tới GUI
Sections:
  - IMPORTS
  - CLASS AppPresenter
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from PyQt6.QtCore import QObject, QTimer
from ui.main_window import MainWindow

# ===== CLASS AppPresenter =====
class AppPresenter(QObject):
    """Presenter trong MVP pattern — sẽ được implement đầy đủ ở Story 1.2, 1.3."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Khởi tạo View
        self._view = MainWindow()

    def show(self):
        """Hiển thị cửa sổ chính."""
        self._view.show()
```

#### `core/serial_reader.py` — Stub
```python
"""
Module: serial_reader
Mục đích: QThread đọc dữ liệu từ cổng serial thực hoặc tạo synthetic frames khi SIMULATION_MODE=True
Sections:
  - IMPORTS
  - CLASS SerialReader
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import queue
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from config import SIMULATION_MODE, QUEUE_MAX_SIZE

logger = logging.getLogger(__name__)

# ===== CLASS SerialReader =====
class SerialReader(QThread):
    """
    QThread quản lý việc đọc dữ liệu serial.
    Emit raw bytes qua signal — KHÔNG giả thiết frame structure ở đây.
    Sẽ implement đầy đủ ở Story 1.3.
    """
    data_received = pyqtSignal(bytes)  # Emitted mỗi khi có raw bytes

    def __init__(self, parent=None):
        super().__init__(parent)
        # Queue bounded — sẽ dùng trong Story 1.3
        self.data_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX_SIZE)
        self._running = False

    def run(self):
        """Vòng lặp chính của thread — stub, sẽ implement ở Story 1.3."""
        self._running = True
        logger.debug("SerialReader thread bắt đầu (stub)")
        while self._running:
            self.msleep(16)  # Chờ, avoid busy loop

    def stop(self):
        """Dừng thread an toàn."""
        self._running = False
        self.wait()
```

#### `core/frame_parser.py` — Stub
```python
"""
Module: frame_parser
Mục đích: State machine phân tích binary frame từ raw byte stream (HUNT→HEADER→PAYLOAD→CRC)
Sections:
  - IMPORTS
  - PARSEDFRAME NAMEDTUPLE
  - CLASS FrameParser
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from collections import namedtuple
from PyQt6.QtCore import QObject, pyqtSignal

# ===== PARSEDFRAME NAMEDTUPLE =====
ParsedFrame = namedtuple('ParsedFrame', [
    'frame_type',   # int: 0x01=OSC_STREAM, 0x02=BODE, 0x03=OSC_CAPTURE
    'payload',      # bytes: raw payload chưa decode
    'gain_factor',  # float: auto-range gain factor (0→1.0, 1→0.1, 2→0.01)
    'timestamp_ms', # int: thời điểm nhận frame (ms từ đầu ngày)
])

# ===== CLASS FrameParser =====
class FrameParser(QObject):
    """
    Phân tích byte stream thành ParsedFrame namedtuples.
    Sẽ implement đầy đủ ở Story 2.1 với 4-state machine + 5 edge cases.
    """
    frame_complete = pyqtSignal(object)  # Emit ParsedFrame khi đủ 1 frame

    def __init__(self, parent=None):
        super().__init__(parent)

    def feed(self, data: bytes):
        """Nhận raw bytes, xử lý qua state machine. Stub — sẽ implement ở Story 2.1."""
        pass
```

#### `core/dsp.py` — Stub
```python
"""
Module: dsp
Mục đích: Pure DSP functions — FFT, phase, gain, filter, unit formatting. KHÔNG import Qt.
Sections:
  - IMPORTS
  - SIGNAL DECODE
  - DSP COMPUTATIONS
  - UNIT FORMATTERS
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import numpy as np

# ===== SIGNAL DECODE =====
def decode_osc_payload(payload: bytes, gain_factor: float):
    """
    Giải mã OSC payload thành 2 mảng voltage.
    Sẽ implement đầy đủ ở Story 2.3/4.1.
    Returns: (ch1_V: np.ndarray, ch2_V: np.ndarray)
    """
    raise NotImplementedError("Sẽ implement ở Story 2.3")

# ===== DSP COMPUTATIONS =====
def compute_fft(signal: np.ndarray, sample_rate: float):
    """Tính FFT. Returns: (freq_array, magnitude_dB)"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def compute_gain_rms(ch_in: np.ndarray, ch_out: np.ndarray) -> float:
    """Tính gain theo RMS. Returns: gain_dB (float)"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def compute_phase_fft(ch_in: np.ndarray, ch_out: np.ndarray,
                      freq_hz: float, sample_rate: float) -> float:
    """Tính phase difference. Returns: phase_deg in -180..+180"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def apply_lowpass_filter(signal: np.ndarray, cutoff_hz: float,
                         sample_rate: float, zi: np.ndarray):
    """Lowpass filter real-time với state. Returns: (filtered, zi_new)"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

# ===== UNIT FORMATTERS =====
def format_voltage(v: float) -> str:
    """Auto-scale voltage: <0.1V → mV, >=0.1V → V"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def format_frequency(hz: float) -> str:
    """Auto-scale frequency: <1000 → Hz, >=1000 → kHz"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def format_phase(deg: float) -> str:
    """Format phase degrees."""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def format_gain(db: float) -> str:
    """Format gain dB."""
    raise NotImplementedError("Sẽ implement ở Story 4.1")
```

> ⚠️ **QUAN TRỌNG:** `dsp.py` **tuyệt đối không được import bất kỳ Qt module nào** (PyQt6, PySide6, etc.). Pure Python + NumPy + SciPy only.

#### `core/data_model.py` — Stub
```python
"""
Module: data_model
Mục đích: Pre-allocated NumPy arrays, filter state (zi), calibration loader từ disk
Sections:
  - IMPORTS
  - CONSTANTS
  - CLASS DataModel
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import os
import json
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ===== CONSTANTS =====
CAL_FILE = os.path.join(os.getenv('APPDATA', ''), 'AplifierAnalyze', 'calibration.json')

# ===== CLASS DataModel =====
class DataModel:
    """
    Giữ trạng thái data: pre-allocated arrays, filter zi, calibration.
    Sẽ implement đầy đủ ở Story 2.3/4.3.
    """

    def __init__(self):
        # Calibration defaults — sẽ override khi load file
        self.dc_offset_mv: float = 0.0
        self.gain_correction: dict = {
            'range_x1': 1.0,
            'range_div10': 1.0,
            'range_div100': 1.0,
        }
        logger.debug("DataModel khởi tạo với calibration mặc định")
```

#### `ui/main_window.py` — Stub
```python
"""
Module: main_window
Mục đích: QMainWindow — passive View, chỉ layout và expose signals. Không có business logic.
Sections:
  - IMPORTS
  - CLASS MainWindow
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from config import COLORS

# ===== CLASS MainWindow =====
class MainWindow(QMainWindow):
    """
    Cửa sổ chính của ứng dụng.
    Passive View trong MVP pattern — giao tiếp với Presenter qua Signal-Slot.
    Sẽ hoàn thiện layout ở Story 1.2.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aplifier Analyze")
        self.resize(1200, 800)
        self._setup_ui()

    def _setup_ui(self):
        """Thiết lập layout cơ bản — sẽ bổ sung panels ở Story 1.2."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        # Placeholder — Story 1.2 sẽ thêm OscPanel và BodePanel
```

#### `ui/osc_panel.py` — Stub
```python
"""
Module: osc_panel
Mục đích: Panel Oscilloscope — controls và plot area. Passive View.
Sections:
  - IMPORTS
  - CLASS OscPanel
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel

# ===== CLASS OscPanel =====
class OscPanel(QGroupBox):
    """Panel Oscilloscope — sẽ implement đầy đủ ở Story 1.2."""

    def __init__(self, parent=None):
        super().__init__("Oscilloscope", parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Oscilloscope Panel — stub"))
```

#### `ui/bode_panel.py` — Stub
```python
"""
Module: bode_panel
Mục đích: Panel Bode Plot — Magnitude + Phase plots, sweep controls. Passive View.
Sections:
  - IMPORTS
  - CLASS BodePanel
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel

# ===== CLASS BodePanel =====
class BodePanel(QGroupBox):
    """Panel Bode Plot — sẽ implement đầy đủ ở Story 1.2."""

    def __init__(self, parent=None):
        super().__init__("Bode Plot", parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Bode Panel — stub"))
```

#### `tests/test_frame_parser.py` — Stub
```python
"""
Module: test_frame_parser
Mục đích: Unit tests cho FrameParser — 5 edge cases bắt buộc (Amelia's list)
Sections:
  - IMPORTS
  - TEST CASES (5 bắt buộc)
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import pytest
# from core.frame_parser import FrameParser, ParsedFrame

# ===== TEST CASES =====
# Các test cases sẽ implement ở Story 2.1:
# test_perfect_stream()
# test_split_mid_header()
# test_split_mid_payload()
# test_bad_crc_recovery()
# test_consecutive_false_sync()
```

---

## Architecture Compliance Checklist

> Dev agent phải verify từng điểm này trước khi mark story là done.

| # | Rule | Nguồn |
|---|---|---|
| ✅ | `config.py` có đúng tất cả constants theo spec | architecture.md §D3, §D6 |
| ✅ | `COLORS` dict có đủ 7 keys bắt buộc | architecture.md §UI Display Patterns |
| ✅ | `SIMULATION_MODE = True` là default | epics.md AC Story 1.1 |
| ✅ | Mọi `.py` file có đúng file header format | architecture.md §Code Structure Patterns |
| ✅ | `dsp.py` không import PyQt6/Qt module | architecture.md §Layer Rules |
| ✅ | `core/` không import từ `ui/` | architecture.md §Architectural Boundaries |
| ✅ | `ParsedFrame` namedtuple có đúng 4 fields | architecture.md §D3 |
| ✅ | `queue.Queue(maxsize=32)` trong SerialReader | architecture.md §D6 |
| ✅ | Inline comments bằng **Tiếng Việt** | project-context.md §Code Quality |
| ✅ | `logger = logging.getLogger(__name__)` trong mỗi module | project-context.md §Error Handling |

---

## File Structure Requirements

### Files cần tạo (14 files + 4 thư mục)

```
d:\Duong\Aplifier_Analyze\App_desktop\
├── main.py                     ← PHẢI TẠO
├── config.py                   ← PHẢI TẠO (định nghĩa đầy đủ constants)
├── requirements.txt            ← PHẢI TẠO
├── ui\
│   ├── __init__.py             ← PHẢI TẠO (có thể rỗng)
│   ├── main_window.py          ← PHẢI TẠO (stub)
│   ├── osc_panel.py            ← PHẢI TẠO (stub)
│   └── bode_panel.py           ← PHẢI TẠO (stub)
├── core\
│   ├── __init__.py             ← PHẢI TẠO (có thể rỗng)
│   ├── app_presenter.py        ← PHẢI TẠO (stub)
│   ├── serial_reader.py        ← PHẢI TẠO (stub)
│   ├── frame_parser.py         ← PHẢI TẠO (stub với ParsedFrame namedtuple)
│   ├── dsp.py                  ← PHẢI TẠO (stub với function signatures)
│   └── data_model.py           ← PHẢI TẠO (stub)
└── tests\
    ├── __init__.py             ← PHẢI TẠO (có thể rỗng)
    ├── test_frame_parser.py    ← PHẢI TẠO (stub/placeholder)
    ├── test_dsp.py             ← PHẢI TẠO (stub/placeholder)
    └── test_data_model.py      ← PHẢI TẠO (stub/placeholder)
```

### Files KHÔNG tạo trong story này

- `ui/styles.py` — sẽ tạo ở Story 6.3
- `aplifier_analyze.spec` — sẽ tạo ở Story 6.2
- Bất kỳ firmware file nào trong `Firmware_STM32/`

---

## Testing Requirements

Story 1.1 chủ yếu là scaffold — không có unit tests phức tạp. Verification đơn giản:

```bash
# Từ thư mục App_desktop/:
cd d:\Duong\Aplifier_Analyze\App_desktop

# Test 1: Import config thành công
python -c "from config import SIMULATION_MODE, COLORS, HEADER_BYTE_1; print('OK:', SIMULATION_MODE)"
# Expected: OK: True

# Test 2: Import các module không lỗi
python -c "from core.frame_parser import ParsedFrame; print('ParsedFrame fields:', ParsedFrame._fields)"
# Expected: ParsedFrame fields: ('frame_type', 'payload', 'gain_factor', 'timestamp_ms')

# Test 3: Import dsp không lỗi (verify không có Qt import)
python -c "import core.dsp; print('dsp OK')"
# Expected: dsp OK

# Test 4: pytest chạy không crash (tests có thể skip/pass vì stub)
pytest tests/ -v
```

---

## Latest Technical Information

### PyQt6 + pyqtgraph compatibility (2026)

- **PyQt6 6.7+** yêu cầu `sip >= 6.8`
- **pyqtgraph 0.13.x** hỗ trợ PyQt6 — cần import `import pyqtgraph as pg` sau khi `from PyQt6 import ...`
- **QThread**: dùng `self.msleep(ms)` thay vì `time.sleep()` trong QThread.run()
- **Signal definition**: Trong PyQt6, signals phải khai báo trong class body, không thể gán dynamic

### Python path cho Windows

- `os.getenv('APPDATA')` trả về `C:\Users\<username>\AppData\Roaming` trên Windows
- `os.makedirs(path, exist_ok=True)` để tạo thư mục an toàn
- Dùng `os.path.join()` thay hardcode `\` để cross-platform

### pytest setup (không cần pytest.ini cho story này)

```bash
pip install pytest
pytest tests/ -v  # Từ thư mục App_desktop/
```

---

## Common Mistakes to Prevent

> Đây là những lỗi thường gặp của AI agents khi implement story này:

| ❌ Sai lầm | ✅ Đúng |
|---|---|
| Import PyQt6 trong `dsp.py` | `dsp.py` chỉ import numpy, scipy |
| `SIMULATION_MODE = False` làm default | Default phải là `True` |
| Bỏ sót key trong `COLORS` dict | Phải có đủ 7 keys: background, surface, text, blue, green, red, yellow |
| `ParsedFrame` thiếu field `gain_factor` hoặc `timestamp_ms` | Phải có đúng 4 fields |
| Đặt `core/` import từ `ui/` | Vi phạm layer boundary — cấm |
| Dùng `print()` thay `logger` | Luôn dùng `logging.getLogger(__name__)` |
| Viết inline comments bằng tiếng Anh | Tất cả inline comments phải bằng **Tiếng Việt** |
| Tạo `__init__.py` có content không cần thiết | `__init__.py` có thể rỗng hoàn toàn |
| Quên commit story này sau khi tạo xong | Commit đầu tiên phải có toàn bộ scaffold |

---

## Dev Notes (từ Implementation)

```
# Dev notes từ implementation:
# - Các vấn đề gặp phải:
#   * pytest chưa được cài sẵn → đã pip install pytest
#   * PowerShell không hỗ trợ && → tách 2 lệnh git add và git commit riêng
# - Các quyết định implementation:
#   * Tất cả stub files giữ đúng spec từ architecture doc
#   * __init__.py có comment tối thiểu thay vì hoàn toàn rỗng (để avoid tool error)
#   * dsp.py verified không có bất kỳ Qt import nào
# - Ghi chú cho story kế tiếp (1.2):
#   * ui/main_window.py sẵn sàng thêm OscPanel và BodePanel vào _setup_ui()
#   * AppPresenter._view đã khởi tạo sẵn → story 1.2 chỉ cần thêm panels
#   * COLORS dict đã có đủ keys cho Story 1.2 dùng
```

## Dev Agent Record

### Implementation Plan
- Tạo 14 files + 3 thư mục theo đúng AC-1 spec
- config.py với đủ 7 COLORS keys + tất cả PROTOCOL CONSTANTS
- Validate tất cả AC bằng python import tests
- Git commit toàn bộ scaffold

### Completion Notes
- ✅ AC-1: Cấu trúc thư mục đầy đủ (ui/, core/, tests/ + 14 files)
- ✅ AC-2: requirements.txt có đủ 6 dependencies
- ✅ AC-3: Mọi .py file có file header chuẩn
- ✅ AC-4: config.py có SIMULATION_MODE=True, tất cả PROTOCOL CONSTANTS, COLORS 7 keys, QUEUE_MAX_SIZE=32
- ✅ AC-5: python -c "from config import SIMULATION_MODE, COLORS; print(SIMULATION_MODE)" → True
- ✅ AC-6: Git commit dd4b8b5 bao gồm toàn bộ scaffold (24 files)

## File List

- App_desktop/main.py
- App_desktop/config.py
- App_desktop/requirements.txt
- App_desktop/ui/__init__.py
- App_desktop/ui/main_window.py
- App_desktop/ui/osc_panel.py
- App_desktop/ui/bode_panel.py
- App_desktop/core/__init__.py
- App_desktop/core/app_presenter.py
- App_desktop/core/serial_reader.py
- App_desktop/core/frame_parser.py
- App_desktop/core/dsp.py
- App_desktop/core/data_model.py
- App_desktop/tests/__init__.py
- App_desktop/tests/test_frame_parser.py
- App_desktop/tests/test_dsp.py
- App_desktop/tests/test_data_model.py

## Change Log

- 2026-04-20: Story 1.1 implemented — Desktop scaffold tạo đầy đủ 14 files + 3 thư mục, tất cả AC pass, git commit dd4b8b5

---

## Story Status

| Field | Value |
|---|---|
| **Status** | review |
| **Note** | Story 1.1 implemented — scaffold hoàn chỉnh, tất cả AC pass, git commit dd4b8b5 |
| **Next Story** | 1-2-main-window-and-panel-stubs |
| **Completed** | 2026-04-20 |
