"""
Module: main_window
Mục đích: QMainWindow — passive View, layout chính Left Panel + Right Panel theo demo signal_analyzer.
          Left Panel: Control tabs (Network Analyzer / Passive Oscilloscope)
          Right Panel: Plot tabs (Live Monitor / Bode Sweep)
Sections:
  - IMPORTS
  - CLASS MainWindow
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTabWidget, QPushButton, QLabel, QGroupBox, QDoubleSpinBox, QGridLayout
)
from PyQt6.QtCore import pyqtSignal
from config import COLORS
from ui.osc_panel import OscPanel
from ui.bode_panel import BodePanel

# ===== CLASS MainWindow =====
class MainWindow(QMainWindow):
    """
    Cửa sổ chính của ứng dụng.
    Passive View trong MVP pattern — layout: Left controls | Right plots.
    Giao tiếp với Presenter qua Signal-Slot.
    """

    # Signals gửi về Presenter
    sig_toggle_analyzer = pyqtSignal()       # Bấm nút Start/Stop Analyzer
    sig_toggle_oscilloscope = pyqtSignal()   # Bấm nút Start/Stop Oscilloscope
    sig_run_sweep = pyqtSignal()             # Bấm nút Start Sweep

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aplifier Analyze — Signal Analyzer Pro")
        self.resize(1300, 850)
        self._setup_ui()
        self._apply_stylesheet()

    def _setup_ui(self):
        """Thiết lập layout chính: Left Panel (controls) + Right Panel (plots)."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ─────────────────────────────────────────
        #  LEFT PANEL: bảng điều khiển (stretch=1)
        # ─────────────────────────────────────────
        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)

        # Tiêu đề
        title_label = QLabel("⚡ Aplifier Analyze")
        title_label.setStyleSheet(
            f"color: {COLORS['blue']}; font-size: 16px; font-weight: bold; padding: 4px;"
        )
        left_panel.addWidget(title_label)

        # TODO (Story 1.3): Nút theme toggle sẽ thêm ở đây

        # Tab điều khiển — 2 tab: Analyzer & Oscilloscope
        self.ctrl_tabs = QTabWidget()
        self.ctrl_tabs.setObjectName("ctrlTabs")

        # Tab 1: Network Analyzer
        ana_widget = QWidget()
        ana_layout = QVBoxLayout(ana_widget)
        
        ana_config_group = QGroupBox("Signal Stimulus")
        ana_form = QGridLayout()
        
        self.ana_spin_freq = QDoubleSpinBox()
        self.ana_spin_freq.setRange(1, 100000)
        self.ana_spin_freq.setValue(1000)
        self.ana_spin_freq.setSuffix(" Hz")
        
        self.ana_spin_amp = QDoubleSpinBox()
        self.ana_spin_amp.setRange(0.1, 5.0)
        self.ana_spin_amp.setValue(1.0)
        self.ana_spin_amp.setSuffix(" V")
        
        ana_form.addWidget(QLabel("Frequency:"), 0, 0)
        ana_form.addWidget(self.ana_spin_freq, 0, 1)
        ana_form.addWidget(QLabel("Amplitude:"), 1, 0)
        ana_form.addWidget(self.ana_spin_amp, 1, 1)
        
        ana_config_group.setLayout(ana_form)
        ana_layout.addWidget(ana_config_group)
        
        # Bode Sweep Group
        sweep_group = QGroupBox("Bode Sweep Settings")
        sweep_form = QGridLayout()
        self.btn_sweep = QPushButton("🚀 Start Sweep")
        self.btn_sweep.clicked.connect(self.sig_run_sweep)
        sweep_form.addWidget(self.btn_sweep, 0, 0, 1, 2)
        sweep_group.setLayout(sweep_form)
        ana_layout.addWidget(sweep_group)
        
        self.btn_ana_live = QPushButton("▶ Start Live Analyzer")
        self.btn_ana_live.setObjectName("btnAnaLive")
        self.btn_ana_live.setStyleSheet(f"background-color: {COLORS['green']}; color: {COLORS['background']};")
        self.btn_ana_live.clicked.connect(self.sig_toggle_analyzer)
        ana_layout.addWidget(self.btn_ana_live)
        
        ana_layout.addStretch()
        self.ctrl_tabs.addTab(ana_widget, "Network Analyzer")

        # Tab 2: Passive Oscilloscope
        osc_ctrl_widget = QWidget()
        osc_ctrl_layout = QVBoxLayout(osc_ctrl_widget)
        
        osc_config_group = QGroupBox("Oscilloscope Settings")
        osc_form = QGridLayout()
        self.osc_spin_time = QDoubleSpinBox()
        self.osc_spin_time.setRange(1, 1000)
        self.osc_spin_time.setValue(10)
        self.osc_spin_time.setSuffix(" ms")
        osc_form.addWidget(QLabel("Time Window:"), 0, 0)
        osc_form.addWidget(self.osc_spin_time, 0, 1)
        osc_config_group.setLayout(osc_form)
        osc_ctrl_layout.addWidget(osc_config_group)
        
        self.btn_osc_live = QPushButton("▶ Start Passive Oscillo")
        self.btn_osc_live.setObjectName("btnOscLive")
        self.btn_osc_live.clicked.connect(self.sig_toggle_oscilloscope)
        osc_ctrl_layout.addWidget(self.btn_osc_live)
        
        osc_ctrl_layout.addStretch()
        self.ctrl_tabs.addTab(osc_ctrl_widget, "Passive Oscilloscope")

        left_panel.addWidget(self.ctrl_tabs)

        left_wrapper = QWidget()
        left_wrapper.setLayout(left_panel)
        left_wrapper.setMaximumWidth(320)
        main_layout.addWidget(left_wrapper, stretch=1)

        # ─────────────────────────────────────────
        #  RIGHT PANEL: đồ thị (stretch=3)
        # ─────────────────────────────────────────
        self.view_tabs = QTabWidget()
        self.view_tabs.setObjectName("viewTabs")

        # View Tab 1: Live Monitor — OscPanel (Time Domain)
        self.osc_panel = OscPanel()
        self.view_tabs.addTab(self.osc_panel, "📺 Live Monitor")

        # View Tab 2: Bode Sweep — BodePanel
        self.bode_panel = BodePanel()
        self.view_tabs.addTab(self.bode_panel, "📈 Frequency Sweep (Bode)")

        main_layout.addWidget(self.view_tabs, stretch=3)

    def _apply_stylesheet(self):
        """Áp dụng Catppuccin Mocha stylesheet cho toàn bộ cửa sổ."""
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }}
            QTabWidget::pane {{
                border: 1px solid #45475a;
                border-radius: 6px;
                background-color: {COLORS['background']};
            }}
            QTabBar::tab {{
                background-color: #181825;
                color: #6c7086;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{
                background-color: #313244;
                color: {COLORS['text']};
            }}
            QPushButton {{
                background-color: {COLORS['blue']};
                color: {COLORS['background']};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #74c7ec;
            }}
            QPushButton:pressed {{
                background-color: #89dceb;
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 12px;
                color: {COLORS['text']};
                border: 1px solid #45475a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                background-color: {COLORS['surface']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: {COLORS['blue']};
            }}
        """)
