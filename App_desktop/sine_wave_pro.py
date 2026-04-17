"""
=============================================================================
  ỨNG DỤNG PHÂN TÍCH TÍN HIỆU SÓNG SINE - PHIÊN BẢN PRO
  Python 3 + PyQt6 + PyQtGraph + NumPy + SciPy
=============================================================================
  Gồm 4 đồ thị:
    1. Sóng Sine miền thời gian (Time Domain)
    2. Phổ tần số FFT (Frequency Spectrum)
    3. Bode Magnitude (Biên độ theo tần số)
    4. Bode Phase (Pha theo tần số)
  
  Điều khiển:
    - Tần số & Biên độ sóng Sine
    - Tần số cắt bộ lọc thông thấp (Low-pass filter)
=============================================================================
"""

import sys
import numpy as np
from scipy import signal as scipy_signal  # Tạo hàm truyền cho Bode plot

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QSlider, QLabel, QGroupBox, QCheckBox,
    QComboBox, QPushButton, QFrame,
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont

import pyqtgraph as pg


# ====================== CATPPUCCIN MOCHA COLOR PALETTE ======================
COLORS = {
    'bg':        '#1e1e2e',
    'surface':   '#313244',
    'overlay':   '#45475a',
    'text':      '#cdd6f4',
    'subtext':   '#a6adc8',
    'blue':      '#89b4fa',
    'green':     '#a6e3a1',
    'yellow':    '#f9e2af',
    'red':       '#f38ba8',
    'peach':     '#fab387',
    'mauve':     '#cba6f7',
    'teal':      '#94e2d5',
    'sky':       '#89dceb',
    'pink':      '#f5c2e7',
}


class SignalAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # ===== BIẾN TRẠNG THÁI =====
        self.frequency_1 = 2.0          # Tần số sóng chính (Hz)
        self.amplitude_1 = 1.0          # Biên độ sóng chính
        self.frequency_2 = 8.0          # Tần số sóng phụ (Hz)
        self.amplitude_2 = 0.0          # Biên độ sóng phụ (mặc định tắt)
        self.cutoff_freq = 5.0          # Tần số cắt bộ lọc (Hz)
        self.filter_order = 2           # Bậc bộ lọc
        self.phase_offset = 0.0         # Pha dịch (sóng chạy)
        self.show_filtered = False      # Hiển thị tín hiệu sau lọc

        self.sample_rate = 1000         # Tần số lấy mẫu (Hz)
        self.duration = 2.0             # Thời gian hiển thị (giây)

        self.setup_ui()

        # Timer cập nhật đồ thị mỗi 30ms (~33 FPS)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_all_plots)
        self.timer.start(30)

    def setup_ui(self):
        self.setWindowTitle("📊 Phân Tích Tín Hiệu - Sóng Sine | FFT | Bode Plot")
        self.setMinimumSize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ═══════════════════════════════════════════
        #  4 ĐỒ THỊ (2x2 Grid)
        # ═══════════════════════════════════════════
        plots_layout = QGridLayout()
        plots_layout.setSpacing(8)

        # --- 1. Đồ thị Sóng Sine (Time Domain) ---
        self.plot_time = pg.PlotWidget(title="🌊 Miền Thời Gian (Time Domain)")
        self.plot_time.setBackground(COLORS['bg'])
        self.plot_time.showGrid(x=True, y=True, alpha=0.2)
        self.plot_time.setLabel('left', 'Biên độ')
        self.plot_time.setLabel('bottom', 'Thời gian (s)')
        self.plot_time.setYRange(-3, 3)
        self.plot_time.addLegend(offset=(10, 10))
        self.curve_time = self.plot_time.plot(
            pen=pg.mkPen(COLORS['blue'], width=2), name='Tín hiệu gốc'
        )
        self.curve_time_filtered = self.plot_time.plot(
            pen=pg.mkPen(COLORS['green'], width=2, style=Qt.PenStyle.DashLine),
            name='Sau lọc'
        )
        plots_layout.addWidget(self.plot_time, 0, 0)

        # --- 2. Phổ FFT (Frequency Spectrum) ---
        self.plot_fft = pg.PlotWidget(title="📡 Phổ Tần Số (FFT Spectrum)")
        self.plot_fft.setBackground(COLORS['bg'])
        self.plot_fft.showGrid(x=True, y=True, alpha=0.2)
        self.plot_fft.setLabel('left', '|Biên độ|')
        self.plot_fft.setLabel('bottom', 'Tần số (Hz)')
        self.plot_fft.setXRange(0, 50)
        self.plot_fft.addLegend(offset=(10, 10))
        self.curve_fft = self.plot_fft.plot(
            pen=pg.mkPen(COLORS['yellow'], width=2), name='FFT gốc',
            fillLevel=0, fillBrush=pg.mkBrush(COLORS['yellow'] + '30')
        )
        self.curve_fft_filtered = self.plot_fft.plot(
            pen=pg.mkPen(COLORS['green'], width=2), name='FFT sau lọc'
        )
        plots_layout.addWidget(self.plot_fft, 0, 1)

        # --- 3. Bode Magnitude ---
        self.plot_bode_mag = pg.PlotWidget(title="📈 Bode - Biên Độ (Magnitude)")
        self.plot_bode_mag.setBackground(COLORS['bg'])
        self.plot_bode_mag.showGrid(x=True, y=True, alpha=0.2)
        self.plot_bode_mag.setLabel('left', 'Magnitude (dB)')
        self.plot_bode_mag.setLabel('bottom', 'Tần số (Hz)')
        self.plot_bode_mag.setLogMode(x=True, y=False)
        self.curve_bode_mag = self.plot_bode_mag.plot(
            pen=pg.mkPen(COLORS['peach'], width=2.5)
        )
        # Đường tần số cắt (vertical line)
        self.vline_cutoff_mag = pg.InfiniteLine(
            pos=np.log10(self.cutoff_freq), angle=90,
            pen=pg.mkPen(COLORS['red'], width=1.5, style=Qt.PenStyle.DashLine)
        )
        self.plot_bode_mag.addItem(self.vline_cutoff_mag)
        # Đường -3dB (horizontal line)
        self.hline_3db = pg.InfiniteLine(
            pos=-3, angle=0,
            pen=pg.mkPen(COLORS['subtext'], width=1, style=Qt.PenStyle.DotLine)
        )
        self.plot_bode_mag.addItem(self.hline_3db)
        plots_layout.addWidget(self.plot_bode_mag, 1, 0)

        # --- 4. Bode Phase ---
        self.plot_bode_phase = pg.PlotWidget(title="📉 Bode - Pha (Phase)")
        self.plot_bode_phase.setBackground(COLORS['bg'])
        self.plot_bode_phase.showGrid(x=True, y=True, alpha=0.2)
        self.plot_bode_phase.setLabel('left', 'Pha (°)')
        self.plot_bode_phase.setLabel('bottom', 'Tần số (Hz)')
        self.plot_bode_phase.setLogMode(x=True, y=False)
        self.curve_bode_phase = self.plot_bode_phase.plot(
            pen=pg.mkPen(COLORS['mauve'], width=2.5)
        )
        self.vline_cutoff_phase = pg.InfiniteLine(
            pos=np.log10(self.cutoff_freq), angle=90,
            pen=pg.mkPen(COLORS['red'], width=1.5, style=Qt.PenStyle.DashLine)
        )
        self.plot_bode_phase.addItem(self.vline_cutoff_phase)
        plots_layout.addWidget(self.plot_bode_phase, 1, 1)

        main_layout.addLayout(plots_layout, stretch=4)

        # ═══════════════════════════════════════════
        #  BẢNG ĐIỀU KHIỂN
        # ═══════════════════════════════════════════
        controls = QGroupBox("🎛 Bảng Điều Khiển")
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(20)

        # ─── Cột 1: Sóng chính ───
        col1 = QVBoxLayout()
        col1_title = QLabel("🔵 Sóng chính")
        col1_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col1_title.setStyleSheet(f"color: {COLORS['blue']};")
        col1.addWidget(col1_title)

        col1.addLayout(self._make_slider(
            "Tần số:", "Hz", 1, 200, 20,
            COLORS['blue'], 'freq1'
        ))
        col1.addLayout(self._make_slider(
            "Biên độ:", "", 1, 30, 10,
            COLORS['blue'], 'amp1'
        ))
        controls_layout.addLayout(col1)

        # ─── Separator ───
        controls_layout.addWidget(self._make_separator())

        # ─── Cột 2: Sóng phụ (trộn thêm) ───
        col2 = QVBoxLayout()
        col2_title = QLabel("🟡 Sóng phụ (trộn)")
        col2_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col2_title.setStyleSheet(f"color: {COLORS['yellow']};")
        col2.addWidget(col2_title)

        col2.addLayout(self._make_slider(
            "Tần số:", "Hz", 1, 200, 80,
            COLORS['yellow'], 'freq2'
        ))
        col2.addLayout(self._make_slider(
            "Biên độ:", "", 0, 30, 0,
            COLORS['yellow'], 'amp2'
        ))
        controls_layout.addLayout(col2)

        # ─── Separator ───
        controls_layout.addWidget(self._make_separator())

        # ─── Cột 3: Bộ lọc Low-pass ───
        col3 = QVBoxLayout()
        col3_title = QLabel("🔴 Bộ lọc thông thấp")
        col3_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col3_title.setStyleSheet(f"color: {COLORS['red']};")
        col3.addWidget(col3_title)

        col3.addLayout(self._make_slider(
            "Tần số cắt:", "Hz", 1, 200, 50,
            COLORS['red'], 'cutoff'
        ))
        col3.addLayout(self._make_slider(
            "Bậc lọc:", "", 1, 8, 2,
            COLORS['red'], 'order'
        ))

        self.chk_show_filtered = QCheckBox("Hiển thị tín hiệu sau lọc")
        self.chk_show_filtered.setStyleSheet(f"color: {COLORS['green']}; font-size: 12px;")
        self.chk_show_filtered.stateChanged.connect(self.on_filter_toggle)
        col3.addWidget(self.chk_show_filtered)

        controls_layout.addLayout(col3)

        # ─── Separator ───
        controls_layout.addWidget(self._make_separator())

        # ─── Cột 4: Công thức & thông tin ───
        col4 = QVBoxLayout()
        self.label_formula = QLabel()
        self.label_formula.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.label_formula.setStyleSheet(f"color: {COLORS['sky']};")
        self.label_formula.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col4.addWidget(self.label_formula)

        self.label_info = QLabel()
        self.label_info.setFont(QFont("Consolas", 10))
        self.label_info.setStyleSheet(f"color: {COLORS['subtext']};")
        self.label_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col4.addWidget(self.label_info)

        controls_layout.addLayout(col4)

        controls.setLayout(controls_layout)
        main_layout.addWidget(controls, stretch=1)

        self._update_labels()
        self._apply_stylesheet()

    # ─────────── HELPER: Tạo Slider ───────────
    def _make_slider(self, label_text, unit, min_val, max_val, default, color, tag):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(75)
        layout.addWidget(label)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        layout.addWidget(slider, stretch=1)

        value_label = QLabel()
        value_label.setMinimumWidth(70)
        value_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(value_label)

        # Lưu reference và kết nối signal
        setattr(self, f'slider_{tag}', slider)
        setattr(self, f'label_{tag}', value_label)

        slider.valueChanged.connect(lambda v, t=tag, u=unit: self._on_slider_changed(t, u))
        # Set initial text
        self._set_slider_text(tag, unit, default)

        return layout

    def _set_slider_text(self, tag, unit, value):
        label = getattr(self, f'label_{tag}')
        if tag in ('freq1', 'freq2', 'cutoff'):
            label.setText(f"{value / 10:.1f} {unit}")
        elif tag == 'order':
            label.setText(f"{value}")
        else:
            label.setText(f"{value / 10:.1f} {unit}")

    def _on_slider_changed(self, tag, unit):
        slider = getattr(self, f'slider_{tag}')
        value = slider.value()
        self._set_slider_text(tag, unit, value)

        if tag == 'freq1':
            self.frequency_1 = value / 10.0
        elif tag == 'amp1':
            self.amplitude_1 = value / 10.0
        elif tag == 'freq2':
            self.frequency_2 = value / 10.0
        elif tag == 'amp2':
            self.amplitude_2 = value / 10.0
        elif tag == 'cutoff':
            self.cutoff_freq = value / 10.0
        elif tag == 'order':
            self.filter_order = value

        self._update_labels()
        self.update_bode_plot()  # Bode chỉ cần cập nhật khi thay đổi bộ lọc

    def _make_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['overlay']};")
        return sep

    def _update_labels(self):
        parts = [f"{self.amplitude_1:.1f}·sin(2π·{self.frequency_1:.1f}·t)"]
        if self.amplitude_2 > 0:
            parts.append(f"{self.amplitude_2:.1f}·sin(2π·{self.frequency_2:.1f}·t)")
        self.label_formula.setText("y = " + " + ".join(parts))
        self.label_info.setText(
            f"Fs = {self.sample_rate} Hz | "
            f"Bộ lọc: fc = {self.cutoff_freq:.1f} Hz, bậc {self.filter_order}"
        )

    def on_filter_toggle(self, state):
        self.show_filtered = bool(state)

    # ==========================================================================
    #  PHẦN LOGIC: CẬP NHẬT ĐỒ THỊ
    # ==========================================================================

    def update_all_plots(self):
        """Được QTimer gọi mỗi 30ms → cập nhật sóng + FFT."""
        N = int(self.sample_rate * self.duration)
        t = np.linspace(0, self.duration, N, endpoint=False)

        # ── Tạo tín hiệu tổng hợp ──
        y = self.amplitude_1 * np.sin(2 * np.pi * self.frequency_1 * t + self.phase_offset)
        if self.amplitude_2 > 0:
            y += self.amplitude_2 * np.sin(2 * np.pi * self.frequency_2 * t + self.phase_offset * 1.5)

        self.phase_offset += 0.08  # Sóng chạy

        # ── Lọc tín hiệu (nếu bật) ──
        y_filtered = None
        if self.show_filtered:
            try:
                nyq = self.sample_rate / 2.0
                norm_cutoff = min(self.cutoff_freq / nyq, 0.99)
                b, a = scipy_signal.butter(self.filter_order, norm_cutoff, btype='low')
                y_filtered = scipy_signal.filtfilt(b, a, y)
            except Exception:
                y_filtered = y.copy()

        # ── 1. Cập nhật đồ thị Time Domain ──
        self.curve_time.setData(t, y)
        if y_filtered is not None:
            self.curve_time_filtered.setData(t, y_filtered)
            self.curve_time_filtered.setVisible(True)
        else:
            self.curve_time_filtered.setVisible(False)

        # Tự động scale trục Y
        max_amp = max(self.amplitude_1 + self.amplitude_2, 0.5)
        self.plot_time.setYRange(-max_amp * 1.3, max_amp * 1.3)

        # ── 2. Cập nhật đồ thị FFT ──
        fft_vals = np.fft.fft(y)
        fft_freq = np.fft.fftfreq(N, 1.0 / self.sample_rate)

        # Lấy nửa phổ dương
        pos_mask = fft_freq >= 0
        fft_magnitude = 2.0 / N * np.abs(fft_vals[pos_mask])
        fft_freqs_pos = fft_freq[pos_mask]

        self.curve_fft.setData(fft_freqs_pos, fft_magnitude)

        if y_filtered is not None:
            fft_filt = np.fft.fft(y_filtered)
            fft_mag_filt = 2.0 / N * np.abs(fft_filt[pos_mask])
            self.curve_fft_filtered.setData(fft_freqs_pos, fft_mag_filt)
            self.curve_fft_filtered.setVisible(True)
        else:
            self.curve_fft_filtered.setVisible(False)

    def update_bode_plot(self):
        """Cập nhật đồ thị Bode khi thay đổi thông số bộ lọc."""
        try:
            nyq = self.sample_rate / 2.0
            norm_cutoff = min(self.cutoff_freq / nyq, 0.99)

            # Tạo hàm truyền bộ lọc Butterworth
            b, a = scipy_signal.butter(self.filter_order, norm_cutoff, btype='low')

            # Tính đáp ứng tần số
            w, h = scipy_signal.freqz(b, a, worN=2000, fs=self.sample_rate)

            # Loại bỏ tần số 0 (log(0) = lỗi)
            mask = w > 0
            freqs = w[mask]
            magnitude_db = 20 * np.log10(np.maximum(np.abs(h[mask]), 1e-10))
            phase_deg = np.degrees(np.angle(h[mask]))

            # Vẽ Bode Magnitude
            self.curve_bode_mag.setData(freqs, magnitude_db)
            self.plot_bode_mag.setYRange(-80, 5)
            self.vline_cutoff_mag.setValue(np.log10(max(self.cutoff_freq, 0.1)))

            # Vẽ Bode Phase
            self.curve_bode_phase.setData(freqs, phase_deg)
            self.plot_bode_phase.setYRange(-200, 10)
            self.vline_cutoff_phase.setValue(np.log10(max(self.cutoff_freq, 0.1)))

        except Exception as e:
            pass  # Bỏ qua lỗi khi giá trị chưa hợp lệ

    def _apply_stylesheet(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['surface']};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {COLORS['text']};
                border: 2px solid {COLORS['overlay']};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: {COLORS['bg']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }}
            QLabel {{
                font-size: 11px;
                color: {COLORS['text']};
            }}
            QCheckBox {{
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {COLORS['overlay']};
                border-radius: 4px;
                background: {COLORS['surface']};
            }}
            QCheckBox::indicator:checked {{
                background: {COLORS['green']};
                border-color: {COLORS['green']};
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {COLORS['overlay']};
                height: 6px;
                background: {COLORS['surface']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {COLORS['blue']};
                border: 2px solid {COLORS['sky']};
                width: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {COLORS['sky']};
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['blue']}, stop:1 {COLORS['sky']});
                border-radius: 3px;
            }}
        """)


# ==============================================================================
#  KHỞI CHẠY
# ==============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SignalAnalyzerApp()
    window.show()
    # Vẽ Bode lần đầu
    window.update_bode_plot()
    sys.exit(app.exec())
