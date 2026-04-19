"""
Module: osc_panel
Mục đích: Panel Oscilloscope — Time Domain plot với CH1 (vàng) và CH2 (cyan), live simulation.
Sections:
  - IMPORTS
  - CLASS OscPanel
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from config import COLORS

# ===== CLASS OscPanel =====
class OscPanel(QWidget):
    """
    Panel Oscilloscope — hiển thị Time Domain plot với CH1 và CH2.
    Passive View: nhận data từ Presenter qua method update_plot().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Thiết lập layout: plot time domain + measurement readouts."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ─── Plot Time Domain ───
        self.plot_time = pg.PlotWidget()
        self.plot_time.setBackground(COLORS['background'])
        self.plot_time.showGrid(x=True, y=True, alpha=0.15)
        self.plot_time.setLabel('left', 'Voltage', 'V',
                                color=COLORS['text'], size='11pt')
        self.plot_time.setLabel('bottom', 'Time', 's',
                                color=COLORS['text'], size='11pt')
        self.plot_time.addLegend(offset=(10, 10))
        self.plot_time.getAxis('left').setPen(COLORS['text'])
        self.plot_time.getAxis('bottom').setPen(COLORS['text'])
        self.plot_time.getAxis('left').setTextPen(COLORS['text'])
        self.plot_time.getAxis('bottom').setTextPen(COLORS['text'])

        # Đường CH1 — màu vàng
        self.curve_ch1 = self.plot_time.plot(
            pen=pg.mkPen(COLORS['yellow'], width=2), name="CH1 (Vin)"
        )
        # Đường CH2 — màu cyan/teal
        self.curve_ch2 = self.plot_time.plot(
            pen=pg.mkPen(COLORS['green'], width=2), name="CH2 (Vout)"
        )
        layout.addWidget(self.plot_time, stretch=3)

        # ─── Readouts đo lường ───
        readout_group = QGroupBox("📊 Measurements")
        readout_layout = QGridLayout(readout_group)
        readout_layout.setSpacing(8)

        def _make_readout(label_text, value_color):
            """Tạo cặp label: tên + giá trị."""
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
            val = QLabel("---")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
            val.setStyleSheet(f"color: {value_color}; font-size: 13px;")
            return lbl, val

        lbl_freq, self.val_freq = _make_readout("Frequency:", COLORS['yellow'])
        lbl_gain, self.val_gain = _make_readout("Gain:", COLORS['green'])
        lbl_phase, self.val_phase = _make_readout("Phase:", '#cba6f7')   # mauve
        lbl_vpp1, self.val_vpp1 = _make_readout("CH1 Vpp:", COLORS['yellow'])
        lbl_vpp2, self.val_vpp2 = _make_readout("CH2 Vpp:", COLORS['green'])

        readout_layout.addWidget(lbl_freq, 0, 0); readout_layout.addWidget(self.val_freq, 0, 1)
        readout_layout.addWidget(lbl_gain, 0, 2); readout_layout.addWidget(self.val_gain, 0, 3)
        readout_layout.addWidget(lbl_phase, 1, 0); readout_layout.addWidget(self.val_phase, 1, 1)
        readout_layout.addWidget(lbl_vpp1, 1, 2); readout_layout.addWidget(self.val_vpp1, 1, 3)
        readout_layout.addWidget(lbl_vpp2, 2, 0); readout_layout.addWidget(self.val_vpp2, 2, 1)

        layout.addWidget(readout_group, stretch=1)

    # ─── Public API cho Presenter ───
    def update_plot(self, t: np.ndarray, ch1: np.ndarray, ch2: np.ndarray):
        """Cập nhật đường sóng time domain. Gọi từ Presenter mỗi timer tick."""
        self.curve_ch1.setData(t, ch1)
        self.curve_ch2.setData(t, ch2)

    def update_measurements(self, freq: float, gain_db: float,
                            phase_deg: float, vpp1: float, vpp2: float):
        """Cập nhật các giá trị đo lường. Gọi từ Presenter."""
        self.val_freq.setText(f"{freq:.1f} Hz")
        self.val_gain.setText(f"{gain_db:+.2f} dB")
        self.val_phase.setText(f"{phase_deg:.1f} °")
        self.val_vpp1.setText(f"{vpp1:.3f} V")
        self.val_vpp2.setText(f"{vpp2:.3f} V")
