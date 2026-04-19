"""
Module: app_presenter
Mục đích: MVP Presenter — kết nối View và Model, điều phối simulation data tới GUI (Story 1.2/1.3)
Sections:
  - IMPORTS
  - SIMULATION HELPERS
  - CLASS AppPresenter
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import numpy as np
from scipy import signal as scipy_signal
from PyQt6.QtCore import QObject, QTimer, QThread, pyqtSignal
from ui.main_window import MainWindow
from config import SIMULATION_MODE

# ===== SIMULATION HELPERS =====
def _gen_analyzer_signals(freq, amp, t_ms, gain, phase_deg, offset=0.0):
    """Tạo tín hiệu CH1/CH2 giả lập cho Network Analyzer mode."""
    sr = max(100_000, int(freq * 50))
    t = np.arange(0, t_ms / 1000.0, 1 / sr)
    t_run = t + offset
    omega = 2 * np.pi * freq
    ch1 = amp * np.sin(omega * t_run) + np.random.normal(0, amp * 0.01, len(t))
    ch2 = gain * amp * np.sin(omega * t_run + np.deg2rad(phase_deg))
    ch2 += (gain * amp * 0.05) * np.sin(2 * omega * t_run)
    ch2 += np.random.normal(0, gain * amp * 0.01, len(t))
    return t, ch1, ch2

def _calc_gain_db(ch1, ch2):
    """Tính gain theo RMS."""
    rms1 = np.sqrt(np.mean(ch1 ** 2))
    rms2 = np.sqrt(np.mean(ch2 ** 2))
    return 20 * np.log10(rms2 / rms1) if rms1 > 0 else 0.0

def _calc_phase(t, ch1, ch2, freq):
    """Tính phase shift bằng cross-correlation."""
    c = scipy_signal.correlate(ch2 - ch2.mean(), ch1 - ch1.mean(), mode='full')
    lags = scipy_signal.correlation_lags(len(ch2), len(ch1), mode='full')
    lag = lags[np.argmax(c)]
    delay = lag * (t[1] - t[0])
    deg = (delay * freq * 360.0 + 180.0) % 360.0 - 180.0
    return deg

# ===== SWEEP WORKER (SIMULATION) =====
class SweepWorkerSim(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(np.ndarray, np.ndarray, np.ndarray)

    def run(self):
        freqs = np.logspace(1, 5, 50) # 10Hz to 100kHz
        gains = []
        phases = []
        for i, f in enumerate(freqs):
            # Giả lập Low-pass filter với cutoff 5kHz
            fc = 5000.0
            g = 0.8 / np.sqrt(1 + (f/fc)**2)
            p = -np.rad2deg(np.arctan(f/fc))
            gains.append(20 * np.log10(g))
            phases.append(p)
            self.progress.emit(int((i+1)/len(freqs) * 100))
            self.msleep(20)
        self.result.emit(freqs, np.array(gains), np.array(phases))

# ===== CLASS AppPresenter =====
class AppPresenter(QObject):
    """
    Presenter trong MVP pattern.
    Điều phối data flow: SerialReader (hoặc simulation) → FrameParser → GUI panels.
    Story 1.2: chạy simulation timer để demo giao diện.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = MainWindow()

        # Trạng thái simulation
        self._time_offset = 0.0
        self._live_running = False
        self._live_mode = None  # 'ANALYZER' | 'PASSIVE'

        # Timer live update mỗi 50ms (~20 FPS)
        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._on_live_tick)

        # Kết nối signals từ View
        self._view.sig_toggle_analyzer.connect(
            lambda: self._toggle_live('ANALYZER')
        )
        self._view.sig_toggle_oscilloscope.connect(
            lambda: self._toggle_live('PASSIVE')
        )
        self._view.sig_run_sweep.connect(self._start_sweep)

        # Khởi động simulation ngay nếu SIMULATION_MODE để demo
        if SIMULATION_MODE:
            self._toggle_live('ANALYZER')

    def show(self):
        """Hiển thị cửa sổ chính."""
        self._view.show()

    # ─── Sweep Bode ───
    def _start_sweep(self):
        self._worker = SweepWorkerSim()
        self._worker.progress.connect(self._view.bode_panel.update_progress)
        self._worker.result.connect(self._view.bode_panel.update_bode)
        self._worker.start()
        self._view.view_tabs.setCurrentIndex(1) # Chuyển sang tab Bode

    # ─── Live timer ───
    def _toggle_live(self, mode: str):
        """Bật/tắt live simulation."""
        if self._live_running and self._live_mode == mode:
            self._live_timer.stop()
            self._live_running = False
            self._live_mode = None
            self._view.btn_ana_live.setText("▶ Start Live Analyzer")
            self._view.btn_osc_live.setText("▶ Start Passive Oscillo")
        else:
            self._live_mode = mode
            self._live_running = True
            self._time_offset = 0.0
            self._live_timer.start(50)
            self._view.view_tabs.setCurrentIndex(0)  # Chuyển sang Live Monitor
            if mode == 'ANALYZER':
                self._view.btn_ana_live.setText("⏹ Stop Analyzer")
            else:
                self._view.btn_osc_live.setText("⏹ Stop Oscilloscope")

    def _on_live_tick(self):
        """Mỗi 50ms: tạo data simulation và cập nhật View."""
        self._time_offset += 0.002

        if self._live_mode == 'ANALYZER':
            freq = self._view.ana_spin_freq.value()
            amp = self._view.ana_spin_amp.value()
            
            # Giả lập gain/phase phụ thuộc tần số (giống filter thật)
            fc = 5000.0
            sim_gain = 0.8 / np.sqrt(1 + (freq/fc)**2)
            sim_phase = -np.rad2deg(np.arctan(freq/fc))

            t, ch1, ch2 = _gen_analyzer_signals(
                freq, amp,
                10.0, sim_gain, sim_phase,
                self._time_offset
            )
            gain_db = _calc_gain_db(ch1, ch2)
            phase_deg = _calc_phase(t, ch1, ch2, freq)
            vpp1 = float(ch1.max() - ch1.min())
            vpp2 = float(ch2.max() - ch2.min())

            self._view.osc_panel.update_plot(t, ch1, ch2)
            self._view.osc_panel.update_measurements(
                freq, gain_db, phase_deg, vpp1, vpp2
            )

        elif self._live_mode == 'PASSIVE':
            t_ms = self._view.osc_spin_time.value()
            sr = 100_000
            t = np.arange(0, t_ms/1000.0, 1 / sr)
            t_run = t + self._time_offset
            ch1 = 1.5 * np.sin(2 * np.pi * 500 * t_run) + np.random.normal(0, 0.03, len(t))
            ch2 = 1.0 * np.sin(2 * np.pi * 1200 * t_run + 0.4) + np.random.normal(0, 0.03, len(t))

            self._view.osc_panel.update_plot(t, ch1, ch2)
            self._view.osc_panel.update_measurements(
                500.0, 0.0, 0.0,
                float(ch1.max() - ch1.min()),
                float(ch2.max() - ch2.min())
            )
