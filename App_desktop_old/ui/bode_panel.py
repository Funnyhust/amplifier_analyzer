"""
Module: bode_panel
Mục đích: Panel Bode Plot — Magnitude (dB) + Phase (°) plots theo tần số log-scale.
          Hiển thị kết quả sweep từ Presenter.
Sections:
  - IMPORTS
  - CLASS BodePanel
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from config import COLORS

# ===== CLASS BodePanel =====
class BodePanel(QWidget):
    """
    Panel Bode Plot — Magnitude + Phase side by side trên log-scale.
    Passive View: nhận data từ Presenter qua method update_bode().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Thiết lập 2 plot: Magnitude (trên) + Phase (dưới)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ─── Plot Bode Magnitude ───
        self.plot_mag = pg.PlotWidget(title="Bode — Magnitude (dB)")
        self.plot_mag.setBackground(COLORS['background'])
        self.plot_mag.showGrid(x=True, y=True, alpha=0.15)
        self.plot_mag.setLabel('left', 'Gain', 'dB',
                               color=COLORS['text'], size='11pt')
        self.plot_mag.setLabel('bottom', 'Frequency', 'Hz',
                               color=COLORS['text'], size='11pt')
        self.plot_mag.setLogMode(x=True, y=False)  # Trục X log-scale
        self.plot_mag.getAxis('left').setPen(COLORS['text'])
        self.plot_mag.getAxis('bottom').setPen(COLORS['text'])
        self.plot_mag.getAxis('left').setTextPen(COLORS['text'])
        self.plot_mag.getAxis('bottom').setTextPen(COLORS['text'])

        # Đường -3dB marker
        self.hline_3db = pg.InfiniteLine(
            pos=-3, angle=0,
            pen=pg.mkPen(COLORS['red'], width=1, style=Qt.PenStyle.DashLine),
            label='-3 dB', labelOpts={'color': COLORS['red']}
        )
        self.plot_mag.addItem(self.hline_3db)

        # Curve sweep — màu xanh lá
        self.curve_mag = self.plot_mag.plot(
            pen=pg.mkPen(COLORS['green'], width=2.5),
            symbol='o', symbolSize=5,
            symbolBrush=COLORS['green'], symbolPen=None
        )
        layout.addWidget(self.plot_mag, stretch=1)

        # ─── Plot Bode Phase ───
        self.plot_phase = pg.PlotWidget(title="Bode — Phase (°)")
        self.plot_phase.setBackground(COLORS['background'])
        self.plot_phase.showGrid(x=True, y=True, alpha=0.15)
        self.plot_phase.setLabel('left', 'Phase', '°',
                                 color=COLORS['text'], size='11pt')
        self.plot_phase.setLabel('bottom', 'Frequency', 'Hz',
                                 color=COLORS['text'], size='11pt')
        self.plot_phase.setLogMode(x=True, y=False)
        self.plot_phase.getAxis('left').setPen(COLORS['text'])
        self.plot_phase.getAxis('bottom').setPen(COLORS['text'])
        self.plot_phase.getAxis('left').setTextPen(COLORS['text'])
        self.plot_phase.getAxis('bottom').setTextPen(COLORS['text'])

        # Curve phase — màu cam
        self.curve_phase = self.plot_phase.plot(
            pen=pg.mkPen(COLORS['yellow'], width=2.5),
            symbol='o', symbolSize=5,
            symbolBrush=COLORS['yellow'], symbolPen=None
        )
        layout.addWidget(self.plot_phase, stretch=1)

        # ─── Progress bar sweep ───
        progress_row = QHBoxLayout()
        self.lbl_sweep_status = QLabel("Ready — Press 'Start Sweep' to begin")
        self.lbl_sweep_status.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 11px;"
        )
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumHeight(12)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['surface']};
                border-radius: 6px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['blue']};
                border-radius: 6px;
            }}
        """)
        progress_row.addWidget(self.lbl_sweep_status, stretch=2)
        progress_row.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(progress_row)

    # ─── Public API cho Presenter ───
    def update_bode(self, freqs: np.ndarray, gains_db: np.ndarray, phases_deg: np.ndarray):
        """Cập nhật 2 Bode plots. Gọi từ Presenter sau khi sweep xong."""
        self.curve_mag.setData(freqs, gains_db)
        self.curve_phase.setData(freqs, phases_deg)
        self.lbl_sweep_status.setText(
            f"Sweep complete — {len(freqs)} points"
        )

    def update_progress(self, value: int):
        """Cập nhật progress bar khi đang sweep."""
        self.progress_bar.setValue(value)
        self.lbl_sweep_status.setText(f"Sweeping... {value}%")
