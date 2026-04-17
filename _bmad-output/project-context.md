---
project_name: 'Aplifier_Analyze'
user_name: 'Truong pc'
date: '2026-04-18'
sections_completed:
  ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns']
status: 'complete'
rule_count: 28
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Project Overview

**Aplifier_Analyze** is a **Signal Analyzer & Oscilloscope** tool consisting of three tightly coupled layers:

1. **Desktop App (PC)** — Python / PyQt6: Real-time visualization (Time Domain, FFT, Bode Magnitude/Phase).
2. **Firmware (Embedded)** — C / STM32F407VET6: Signal generation (DAC/DDS), high-speed data acquisition (ADC+DMA), USB CDC communication.
3. **Hardware** — STM32F407VET6 @ 168 MHz, dual-channel ADC, optional external DDS (AD9833), log-amp (AD8307).

> **Key integration point:** The binary communication protocol between Firmware ↔ Desktop is the most critical design decision in this project. All other components depend on it.

---

## Technology Stack & Versions

| Layer | Technology | Notes |
|---|---|---|
| **Desktop GUI** | Python 3.10+ / PyQt6 6.x | `QMainWindow`-based OOP architecture |
| **Real-time Plotting** | pyqtgraph 0.13.x | Use `PlotDataItem.setData()`, NOT re-create |
| **DSP / Math** | NumPy, SciPy | FFT via `np.fft`, filters via `scipy.signal` |
| **Serial Comms** | pyserial 3.x | Non-blocking, polled via `QTimer` |
| **Distribution** | PyInstaller | Package into single `.exe` for lab use |
| **Firmware MCU** | STM32F407VET6 (ARM Cortex-M4 @ 168 MHz) | HAL or LL depending on performance need |
| **Firmware IDE** | STM32CubeIDE / CubeMX | HAL generated via CubeMX, manually optimized |
| **ADC Strategy** | Dual/Triple Interleaved or Simultaneous | Target ≥ 1 MSPS per channel effective rate |
| **Data Transfer** | USB CDC (Virtual COM Port) | Higher bandwidth than UART, no extra chip |
| **Optional HW** | AD9833 (DDS via SPI), AD8307 (Log Amp) | TBD during architecture phase |

---

## Critical Implementation Rules

### Language-Specific Rules (Python)

- **Non-blocking serial reads:** Always poll `pyserial` inside a `QTimer` callback (e.g., every 30–100 ms). **Never** use a blocking `while True` loop or `time.sleep()` on the main thread — it will freeze the Qt event loop.
- **Thread-safe data handoff:** If a `QThread` or `threading.Thread` is used for serial I/O, pass data back to the main thread via `queue.Queue` and drain it inside the `QTimer` callback. **Never** call any Qt widget method from a non-main thread.
- **Binary protocol parsing:** Use Python's `struct` module for packing/unpacking binary frames. Specify byte order explicitly (`'<'` little-endian to match STM32 ARM). Never use string splitting or `decode()` on raw binary frames.
- **Numpy array reuse:** Pre-allocate NumPy arrays once and update in-place with slice assignment (`arr[:] = new_data`) inside the update loop. Avoid creating new arrays per timer tick.

### Language-Specific Rules (C / STM32 Firmware)

- **DMA Double-Buffering (Ping-Pong):** Configure ADC in DMA circular mode with half-transfer and full-transfer interrupts. Process one half-buffer in the ISR callback while DMA fills the other. **Never** process ADC data directly inside the DMA full-transfer callback if it takes more than a few microseconds.
- **USB CDC flow control:** Check `CDC_Transmit_FS()` return code. If it returns `USBD_BUSY`, queue the data and retry — do not discard silently. USB CDC runs slower than ADC sampling; the firmware **must** implement a software buffer.
- **State Machine mandatory:** All system behavior (IDLE → CONFIGURING → ACQUIRING → TRANSMITTING) must be governed by an explicit `enum`-based state machine in the main loop. No `while(1)` spaghetti logic.
- **Volatile for ISR-shared variables:** Any variable shared between main loop and an ISR (DMA, Timer) **must** be declared `volatile` and accessed with critical sections (`__disable_irq()` / `__enable_irq()`) or CMSIS atomic intrinsics.

---

### Framework-Specific Rules (PyQt6 Desktop)

- **OOP architecture:** All GUI windows inherit from `QMainWindow`. Each logical panel (connection controls, plot area, export controls) is a `QGroupBox` with its own layout. No monolithic flat widget hierarchies.
- **Signal-Slot only for UI wiring:** Connect all user interactions (button clicks, slider changes) exclusively through Qt Signal-Slot mechanism. Do not call UI-update functions directly from business logic — emit a signal instead.
- **`pyqtgraph` performance rules:**
  - Create `PlotWidget` and `PlotDataItem` objects **once** in `setup_ui()`.
  - Update data with `curve.setData(x, y)` in the timer callback.
  - Use `PlotWidget.setDownsampling(auto=True)` and `PlotWidget.setClipToView(True)` for large FFT/Bode datasets.
  - Log-scale X axis for Bode plots: use `setLogMode(x=True)`.
- **Color palette:** Use the **Catppuccin Mocha** palette (as established in `sine_wave_pro.py`). Background `#1e1e2e`, primary text `#cdd6f4`. Do not introduce arbitrary color choices.

---

### Communication Protocol Rules

> This section is **critical** — any agent implementing serial communication or firmware protocol must read this first.

- **Frame format (Firmware → PC):** `[0xAA, 0xBB] [Type:1B] [Length:2B LE] [Payload: N bytes] [CRC8:1B]`
  - `Type` values: `0x01` = Oscilloscope raw ADC frame, `0x02` = Bode result frame.
  - `Length` = byte count of payload only.
  - `CRC8` = XOR checksum of payload bytes.
- **Frame format (PC → Firmware):** `<CMD:NAME, PARAM1:VALUE, PARAM2:VALUE>\n`
  - Example: `<CMD:START_SWEEP, F_START:100, F_STOP:500000, STEPS:50>\n`
  - Firmware parser is line-terminated; always end with `\n`.
- **Sync/recovery:** If the PC parser loses sync (byte count mismatch or bad CRC), it must scan forward byte-by-byte looking for the `0xAA 0xBB` header. Never assume the stream is always aligned.
- **ADC data encoding:** Raw 12-bit ADC values packed as `uint16_t` little-endian. Two channels interleaved: `[CH1_0, CH2_0, CH1_1, CH2_1, ...]`.

---

### Code Quality & Style Rules

- **File header block:** Every `.py` file must start with a triple-quoted docstring block describing the module purpose, main sections, and key function index (see `serial_reader.py` as reference).
- **Section separators:** Use large ASCII comment separators (e.g., `# ===== SECTION NAME =====`) to delimit logical sections within a file. This is an established convention in this codebase.
- **Vietnamese comments:** All inline comments and docstrings are written in **Vietnamese**. New code must maintain this convention consistently.
- **Naming:** Python: `snake_case` for functions/variables, `PascalCase` for classes. C: `camelCase` for local vars, `UPPER_SNAKE_CASE` for `#define` constants, `PascalCase` for typedef structs.
- **No magic numbers:** All protocol constants (header bytes, command strings, buffer sizes, ADC sample rates) must be defined as named constants or `#define` macros, never inline literals.

---

### Testing Rules

- **Manual integration test first:** Before writing automated tests, verify the serial protocol manually: connect STM32, capture raw bytes with a logic analyzer or terminal, confirm frame structure matches protocol spec.
- **Simulate before hardware:** Use the existing `generate_signals()` / simulated data path (do not delete it yet) as a test harness for desktop DSP logic. Keep simulation mode accessible via a CLI flag or config variable.
- **Serial port mock for unit tests:** Unit tests for the Python parser must mock `pyserial.Serial` using `unittest.mock.MagicMock`. Do not require physical hardware to run unit tests.
- **Edge cases to always test:** Zero-length payload, CRC mismatch, partial frame (stream cut mid-packet), max buffer size overflow, frequency sweep with `F_START == F_STOP`.

---

### Development Workflow Rules

- **Branch naming:** `feature/[short-description]` for new features, `fix/[short-description]` for bug fixes, `hw/[short-description]` for hardware-specific firmware branches.
- **Do not delete simulation mode:** The `generate_signals()` path in the desktop app must be preserved (gated by a flag) throughout all firmware integration work. It is the regression baseline.
- **CubeMX `.ioc` file must be committed:** Any STM32 peripheral configuration change must be done via CubeMX and the `.ioc` project file committed alongside the generated HAL code. Do not hand-edit CubeMX-generated files.
- **Phase gate:** Do not start Phase 2 (Protocol Implementation) until the binary frame format is formally defined and reviewed in the Architecture document.

---

### Critical Don't-Miss Rules (Anti-Patterns)

- ❌ **Do NOT call `QTimer.start()` before `serial.Serial()` succeeds.** Starting the read timer before the port is open causes immediate exceptions on the first tick.
- ❌ **Do NOT use `serial.readline()` for binary protocols.** Binary frames may contain `0x0A` (newline) bytes in data payload. Always use `serial.read(n)` after parsing the `Length` field.
- ❌ **Do NOT use `filtfilt()` on real-time streaming data.** `scipy.signal.filtfilt()` requires the full signal and is only valid for post-processing. For real-time filtering use `lfilter()` with a state variable (`zi`).
- ❌ **Do NOT mix HAL and LL drivers for the same peripheral.** Choose one abstraction level per peripheral and stay consistent.
- ❌ **Do NOT enable ADC and USB CDC simultaneously without verifying clock tree.** Both use the HSE PLL; verify APB2 (ADC max 42 MHz) and 48 MHz USB clock are correctly configured concurrently in CubeMX.
- ❌ **Do NOT plot raw 12-bit ADC codes directly on the Y-axis.** Always convert to physical voltage: `V = (adc_code / 4095.0) * Vref` before passing to `pyqtgraph`.
- ❌ **Do NOT delete the `COLORS` dict or rename its keys.** The Catppuccin Mocha palette is used across multiple files; any rename breaks the shared style.

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code in this project.
- When implementing serial protocol code (Python or C), always reference the "Communication Protocol Rules" section first.
- When in doubt about styling or conventions, refer to `App_desktop/sine_wave_pro.py` (Python reference) as the canonical example.
- Update this file if new patterns or technology decisions are established.

**For Humans:**
- Update the Technology Stack table immediately when hardware or library decisions change.
- The Protocol Rules section must stay in sync with the Architecture document once it is created.
- Review anti-patterns list after each phase of development.

Last Updated: 2026-04-18
