import sys
import numpy as np
import pyqtgraph as pg
from scipy import signal, fft
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton, 
                             QGroupBox, QFormLayout, QGridLayout, QTabWidget, QProgressBar,
                             QColorDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

# ==========================================
# 1. HÀM TẠO DỮ LIỆU & DSP (CORE MODULE)
# ==========================================

# --- A. Dữ liệu cho Mode Analyzer (CH1 là Vin, CH2 là Vout của cùng 1 hệ thống) ---
def generate_analyzer_signals(freq, amplitude, sampling_time_ms, sim_gain, sim_phase_deg, time_offset=0.0):
    sampling_time_s = sampling_time_ms / 1000.0
    sample_rate = max(100000, int(freq * 50)) 
    t_raw = np.arange(0, sampling_time_s, 1 / sample_rate)
    t_running = t_raw + time_offset 
    
    omega = 2 * np.pi * freq
    v_in_clean = amplitude * np.sin(omega * t_running)
    phase_shift_rad = np.deg2rad(sim_phase_deg)
    
    v_out_clean = sim_gain * amplitude * np.sin(omega * t_running + phase_shift_rad)
    v_out_clean += (sim_gain * amplitude * 0.05) * np.sin(2 * omega * t_running + phase_shift_rad) # Nhiễu hài
    
    ch1 = v_in_clean + np.random.normal(0, amplitude * 0.01, len(t_raw))
    ch2 = v_out_clean + np.random.normal(0, sim_gain * amplitude * 0.01, len(t_raw))
    return t_raw, ch1, ch2, sample_rate

# --- B. Dữ liệu cho Mode Passive Oscillo (CH1 và CH2 là 2 tín hiệu bên ngoài độc lập) ---
def generate_external_signals(sampling_time_ms, f1, amp1, f2, amp2, time_offset=0.0):
    sampling_time_s = sampling_time_ms / 1000.0
    sample_rate = max(100000, int(max(f1, f2) * 50))
    t_raw = np.arange(0, sampling_time_s, 1 / sample_rate)
    t_running = t_raw + time_offset
    
    # Kênh 1: Sóng Sine
    ch1 = amp1 * np.sin(2 * np.pi * f1 * t_running) + np.random.normal(0, amp1*0.02, len(t_raw))
    # Kênh 2: Sóng Sine khác tần số để thấy sự khác biệt
    ch2 = amp2 * np.sin(2 * np.pi * f2 * t_running + np.pi/4) + np.random.normal(0, amp2*0.03, len(t_raw))
    return t_raw, ch1, ch2, sample_rate

# --- C. Các thuật toán đo lường ---
def measure_frequency(t, v):
    """Đo tần số của tín hiệu bất kỳ bằng Zero-crossing (Giống Oscillo thật)"""
    v_ac = v - np.mean(v)
    crossings = np.where(np.diff(np.sign(v_ac)))[0]
    if len(crossings) > 1:
        dt = t[crossings[-1]] - t[crossings[0]]
        cycles = (len(crossings) - 1) / 2.0
        if dt > 0:
            return cycles / dt
    return 0.0

def calculate_phase(t, v_in, v_out, freq):
    v_in_ac = v_in - np.mean(v_in)
    v_out_ac = v_out - np.mean(v_out)
    correlation = signal.correlate(v_out_ac, v_in_ac, mode='full')
    lags = signal.correlation_lags(len(v_out_ac), len(v_in_ac), mode='full')
    lag = lags[np.argmax(correlation)]
    time_delay = lag * (t[1] - t[0])
    phase_deg = time_delay * freq * 360.0
    return (phase_deg + 180.0) % 360.0 - 180.0

def analyze_active(t, v_in, v_out, freq):
    v_in_rms = np.sqrt(np.mean(v_in**2))
    v_out_rms = np.sqrt(np.mean(v_out**2))
    gain_db = 20 * np.log10(v_out_rms / v_in_rms) if v_in_rms > 0 else 0
    phase_deg = calculate_phase(t, v_in, v_out, freq)
    return gain_db, phase_deg

def analyze_passive(t, ch1, ch2):
    f1 = measure_frequency(t, ch1)
    f2 = measure_frequency(t, ch2)
    v1_pp = np.max(ch1) - np.min(ch1)
    v2_pp = np.max(ch2) - np.min(ch2)
    return f1, v1_pp, f2, v2_pp

# ==========================================
# 2. LUỒNG QUÉT TẦN SỐ (SWEEP WORKER)
# ==========================================
class SweepWorker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(list, list, list)
    finished = pyqtSignal()

    def __init__(self, f_start, f_stop, points, amp):
        super().__init__()
        self.f_start = f_start; self.f_stop = f_stop; self.points = points; self.amp = amp

    def run(self):
        freqs = np.logspace(np.log10(self.f_start), np.log10(self.f_stop), self.points)
        gains = []; phases = []
        for i, f in enumerate(freqs):
            fc = 50000.0 
            actual_gain = 0.8 / np.sqrt(1 + (f/fc)**2)
            actual_phase = -25.0 - np.rad2deg(np.arctan(f/fc))
            t_ms = max(5.0, (10 / f) * 1000) 
            t, v_in, v_out, _ = generate_analyzer_signals(f, self.amp, t_ms, actual_gain, actual_phase)
            g_db, p_deg = analyze_active(t, v_in, v_out, f)
            gains.append(g_db); phases.append(p_deg)
            self.progress.emit(int(((i + 1) / self.points) * 100))
            self.msleep(15) 
        self.result.emit(freqs.tolist(), gains, phases)
        self.finished.emit()

# ==========================================
# 3. GIAO DIỆN CHÍNH (GUI)
# ==========================================
class SignalAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Signal Analyzer Pro - Dual Mode")
        self.resize(1300, 850)
        
        self.is_dark_theme = True
        self.time_counter = 0.0
        self.current_live_mode = None # 'ANALYZER' or 'PASSIVE'
        
        self.live_timer = QTimer()
        self.live_timer.timeout.connect(self.process_live_data)

        self.initUI()
        
    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # --- LEFT PANEL: Controls ---
        left_panel = QVBoxLayout()
        left_panel.setContentsMargins(0, 0, 10, 0)
        
        # Global Settings
        self.btn_theme = QPushButton("Switch to White Theme ☀")
        self.btn_theme.setStyleSheet("font-weight: bold; height: 35px; background-color: #f0f0f0; color: black;")
        self.btn_theme.clicked.connect(self.toggle_theme)
        left_panel.addWidget(self.btn_theme)
        
        # Color Pickers
        color_layout = QHBoxLayout()
        self.btn_col_ch1 = QPushButton("CH1 Color")
        self.btn_col_ch1.setStyleSheet("background-color: #ffEB3B; color: black; font-weight: bold; height: 25px;")
        self.btn_col_ch1.clicked.connect(lambda: self.change_channel_color(1))
        
        self.btn_col_ch2 = QPushButton("CH2 Color")
        self.btn_col_ch2.setStyleSheet("background-color: #00E5FF; color: black; font-weight: bold; height: 25px;")
        self.btn_col_ch2.clicked.connect(lambda: self.change_channel_color(2))
        
        color_layout.addWidget(self.btn_col_ch1)
        color_layout.addWidget(self.btn_col_ch2)
        left_panel.addLayout(color_layout)
        
        # TAB ĐIỀU KHIỂN (2 Chế độ)
        self.ctrl_tabs = QTabWidget()
        
        # ====== TAB ĐIỀU KHIỂN 1: ANALYZER (CHỦ ĐỘNG) ======
        ana_widget = QWidget()
        ana_layout = QVBoxLayout(ana_widget)
        
        config_group = QGroupBox("Stimulus Signal (TX)")
        config_layout = QFormLayout()
        self.ana_spin_freq = QDoubleSpinBox(); self.ana_spin_freq.setRange(10, 500000); self.ana_spin_freq.setValue(1000); self.ana_spin_freq.setSuffix(" Hz")
        self.ana_spin_amp = QDoubleSpinBox(); self.ana_spin_amp.setRange(0.1, 20); self.ana_spin_amp.setValue(3.3); self.ana_spin_amp.setSuffix(" V")
        self.ana_spin_time = QDoubleSpinBox(); self.ana_spin_time.setRange(1, 5000); self.ana_spin_time.setValue(5.0); self.ana_spin_time.setSuffix(" ms")
        config_layout.addRow("TX Frequency:", self.ana_spin_freq)
        config_layout.addRow("TX Amplitude:", self.ana_spin_amp)
        config_layout.addRow("Display Time:", self.ana_spin_time)
        
        self.btn_ana_live = QPushButton("Start Live Analyzer")
        self.btn_ana_live.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; height: 35px;")
        self.btn_ana_live.clicked.connect(lambda: self.toggle_live('ANALYZER'))
        config_layout.addRow(self.btn_ana_live)
        config_group.setLayout(config_layout)
        ana_layout.addWidget(config_group)
        
        sweep_group = QGroupBox("Bode Plot Sweep")
        sweep_layout = QFormLayout()
        self.sweep_start = QDoubleSpinBox(); self.sweep_start.setRange(10, 100000); self.sweep_start.setValue(100)
        self.sweep_stop = QDoubleSpinBox(); self.sweep_stop.setRange(1000, 1000000); self.sweep_stop.setValue(500000)
        self.sweep_pts = QDoubleSpinBox(); self.sweep_pts.setRange(10, 500); self.sweep_pts.setValue(50)
        sweep_layout.addRow("Start (Hz):", self.sweep_start)
        sweep_layout.addRow("Stop (Hz):", self.sweep_stop)
        sweep_layout.addRow("Points:", self.sweep_pts)
        
        self.btn_sweep = QPushButton("Start Sweep")
        self.btn_sweep.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; height: 35px;")
        self.btn_sweep.clicked.connect(self.run_sweep)
        sweep_layout.addRow(self.btn_sweep)
        self.progress_bar = QProgressBar(); self.progress_bar.setValue(0)
        sweep_layout.addRow(self.progress_bar)
        sweep_group.setLayout(sweep_layout)
        ana_layout.addWidget(sweep_group)
        
        res_ana_group = QGroupBox("Analyzer Results")
        res_ana_layout = QGridLayout()
        self.lbl_ana_gain = QLabel("0.00 dB"); self.lbl_ana_phase = QLabel("0.00 °")
        for lbl in [self.lbl_ana_gain, self.lbl_ana_phase]:
            lbl.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 15px;"); lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        res_ana_layout.addWidget(QLabel("Measured Gain:"), 0, 0); res_ana_layout.addWidget(self.lbl_ana_gain, 0, 1)
        res_ana_layout.addWidget(QLabel("Phase Shift:"), 1, 0); res_ana_layout.addWidget(self.lbl_ana_phase, 1, 1)
        res_ana_group.setLayout(res_ana_layout)
        ana_layout.addWidget(res_ana_group)
        ana_layout.addStretch()
        self.ctrl_tabs.addTab(ana_widget, "Network Analyzer")
        
        # ====== TAB ĐIỀU KHIỂN 2: PASSIVE OSCILLO (THỤ ĐỘNG) ======
        osc_widget = QWidget()
        osc_layout = QVBoxLayout(osc_widget)
        
        osc_config = QGroupBox("Oscilloscope Settings")
        osc_config_layout = QFormLayout()
        self.osc_spin_time = QDoubleSpinBox(); self.osc_spin_time.setRange(1, 5000); self.osc_spin_time.setValue(10.0); self.osc_spin_time.setSuffix(" ms")
        osc_config_layout.addRow("Time/Div (Window):", self.osc_spin_time)
        
        self.btn_osc_live = QPushButton("Start Passive Oscillo (RX Only)")
        self.btn_osc_live.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; height: 40px;")
        self.btn_osc_live.clicked.connect(lambda: self.toggle_live('PASSIVE'))
        osc_config_layout.addRow(self.btn_osc_live)
        osc_config.setLayout(osc_config_layout)
        osc_layout.addWidget(osc_config)
        
        # Giả lập môi trường ngoài (chỉ để test)
        sim_ext_group = QGroupBox("External Signal Sim (For Testing)")
        sim_ext_layout = QFormLayout()
        self.ext_f1 = QDoubleSpinBox(); self.ext_f1.setRange(10, 100000); self.ext_f1.setValue(500); self.ext_f1.setSuffix(" Hz")
        self.ext_f2 = QDoubleSpinBox(); self.ext_f2.setRange(10, 100000); self.ext_f2.setValue(1200); self.ext_f2.setSuffix(" Hz")
        sim_ext_layout.addRow("Unknown CH1 Freq:", self.ext_f1)
        sim_ext_layout.addRow("Unknown CH2 Freq:", self.ext_f2)
        sim_ext_group.setLayout(sim_ext_layout)
        osc_layout.addWidget(sim_ext_group)
        
        res_osc_group = QGroupBox("Oscilloscope Measurements")
        res_osc_layout = QGridLayout()
        self.lbl_osc_f1 = QLabel("0.0 Hz"); self.lbl_osc_v1 = QLabel("0.0 Vpp")
        self.lbl_osc_f2 = QLabel("0.0 Hz"); self.lbl_osc_v2 = QLabel("0.0 Vpp")
        for lbl in [self.lbl_osc_f1, self.lbl_osc_v1, self.lbl_osc_f2, self.lbl_osc_v2]:
            lbl.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 14px;"); lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        res_osc_layout.addWidget(QLabel("CH1 Measured Freq:"), 0, 0); res_osc_layout.addWidget(self.lbl_osc_f1, 0, 1)
        res_osc_layout.addWidget(QLabel("CH1 Vpp:"), 1, 0); res_osc_layout.addWidget(self.lbl_osc_v1, 1, 1)
        res_osc_layout.addWidget(QLabel("CH2 Measured Freq:"), 2, 0); res_osc_layout.addWidget(self.lbl_osc_f2, 2, 1)
        res_osc_layout.addWidget(QLabel("CH2 Vpp:"), 3, 0); res_osc_layout.addWidget(self.lbl_osc_v2, 3, 1)
        res_osc_group.setLayout(res_osc_layout)
        osc_layout.addWidget(res_osc_group)
        osc_layout.addStretch()
        self.ctrl_tabs.addTab(osc_widget, "Passive Oscilloscope")
        
        left_panel.addWidget(self.ctrl_tabs)
        main_layout.addLayout(left_panel, stretch=1)
        
        # --- RIGHT PANEL: Plots ---
        self.view_tabs = QTabWidget()
        
        # ================= VIEW TAB 1: OSCILLOSCOPE & FFT =================
        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        self.plot_osc = pg.PlotWidget(title="Time Domain (Double-click to Maximize)")
        self.plot_osc.showGrid(x=True, y=True); self.plot_osc.addLegend()
        self.plot_osc.setLabel('left', 'Voltage', 'V'); self.plot_osc.setLabel('bottom', 'Time', 's')
        self.curve_ch1 = self.plot_osc.plot(pen=pg.mkPen('#ffEB3B', width=2), name="CH1")
        self.curve_ch2 = self.plot_osc.plot(pen=pg.mkPen('#00E5FF', width=2), name="CH2")
        tab1_layout.addWidget(self.plot_osc)
        self.view_tabs.addTab(tab1, "Live Monitor")
        
        self.plot_osc.setProperty("is_maximized", False)
        self.plot_osc.scene().sigMouseClicked.connect(lambda evt: self.toggle_maximize(self.plot_osc) if evt.double() else None)
        
        # ================= VIEW TAB 2: BODE PLOT =================
        tab2 = QWidget()
        tab2_layout = QVBoxLayout(tab2)
        self.plot_bode_gain = pg.PlotWidget(title="Bode Plot: Magnitude (Double-click to Maximize)")
        self.plot_bode_gain.showGrid(x=True, y=True); self.plot_bode_gain.setLogMode(x=True, y=False)
        self.curve_bode_gain = self.plot_bode_gain.plot(pen=pg.mkPen('#4CAF50', width=3), symbol='o')
        self.plot_bode_phase = pg.PlotWidget(title="Bode Plot: Phase (Double-click to Maximize)")
        self.plot_bode_phase.showGrid(x=True, y=True); self.plot_bode_phase.setLogMode(x=True, y=False)
        self.curve_bode_phase = self.plot_bode_phase.plot(pen=pg.mkPen('#FF9800', width=3), symbol='o')
        tab2_layout.addWidget(self.plot_bode_gain); tab2_layout.addWidget(self.plot_bode_phase)
        self.view_tabs.addTab(tab2, "Frequency Sweep (Bode)")
        
        self.plot_bode_gain.setProperty("is_maximized", False); self.plot_bode_phase.setProperty("is_maximized", False)
        self.plot_bode_gain.scene().sigMouseClicked.connect(lambda evt: self.toggle_maximize(self.plot_bode_gain) if evt.double() else None)
        self.plot_bode_phase.scene().sigMouseClicked.connect(lambda evt: self.toggle_maximize(self.plot_bode_phase) if evt.double() else None)

        main_layout.addWidget(self.view_tabs, stretch=3)
        self.all_plots = [self.plot_osc, self.plot_bode_gain, self.plot_bode_phase]

    # --- ĐỔI MÀU NỀN ---
    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        bg_color, fg_color = ('k', 'w') if self.is_dark_theme else ('w', 'k')
        self.btn_theme.setText("Switch to White Theme ☀" if self.is_dark_theme else "Switch to Dark Theme 🌙")
        self.btn_theme.setStyleSheet(f"font-weight: bold; height: 35px; background-color: {'#f0f0f0' if self.is_dark_theme else '#333333'}; color: {'black' if self.is_dark_theme else 'white'};")
        for p in self.all_plots:
            p.setBackground(bg_color)
            p.getAxis('bottom').setPen(fg_color); p.getAxis('bottom').setTextPen(fg_color)
            p.getAxis('left').setPen(fg_color); p.getAxis('left').setTextPen(fg_color)

    # --- ĐỔI MÀU TÍN HIỆU ---
    def change_channel_color(self, channel):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            # Cân bằng độ sáng của chữ để dễ đọc
            text_color = 'white' if color.lightness() < 128 else 'black'
            
            if channel == 1:
                self.curve_ch1.setPen(pg.mkPen(color=hex_color, width=2))
                self.btn_col_ch1.setStyleSheet(f"background-color: {hex_color}; color: {text_color}; font-weight: bold; height: 25px;")
            else:
                self.curve_ch2.setPen(pg.mkPen(color=hex_color, width=2))
                self.btn_col_ch2.setStyleSheet(f"background-color: {hex_color}; color: {text_color}; font-weight: bold; height: 25px;")

    # --- PHÓNG TO / THU NHỎ ---
    def toggle_maximize(self, clicked_widget):
        # Đơn giản hóa: Phóng to widget trong Parent layout của nó
        parent_layout = clicked_widget.parentWidget().layout()
        if clicked_widget.property("is_maximized"):
            for i in range(parent_layout.count()):
                parent_layout.itemAt(i).widget().show()
            clicked_widget.setProperty("is_maximized", False)
        else:
            for i in range(parent_layout.count()):
                w = parent_layout.itemAt(i).widget()
                if w != clicked_widget: w.hide()
            clicked_widget.show()
            clicked_widget.setProperty("is_maximized", True)

    # --- START/STOP LIVE MONITOR ---
    def toggle_live(self, mode):
        if self.live_timer.isActive():
            self.live_timer.stop()
            self.btn_ana_live.setText("Start Live Analyzer")
            self.btn_ana_live.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; height: 35px;")
            self.btn_osc_live.setText("Start Passive Oscillo (RX Only)")
            self.btn_osc_live.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; height: 40px;")
            self.ctrl_tabs.setTabEnabled(0, True); self.ctrl_tabs.setTabEnabled(1, True)
        else:
            self.current_live_mode = mode
            self.view_tabs.setCurrentIndex(0)
            self.live_timer.start(50) # 20fps
            
            if mode == 'ANALYZER':
                self.btn_ana_live.setText("STOP Analyzer")
                self.btn_ana_live.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; height: 35px;")
                self.ctrl_tabs.setTabEnabled(1, False) # Khóa tab kia
            else:
                self.btn_osc_live.setText("STOP Passive Oscillo")
                self.btn_osc_live.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; height: 40px;")
                self.ctrl_tabs.setTabEnabled(0, False)

    # --- XỬ LÝ DỮ LIỆU THỜI GIAN THỰC ---
    def process_live_data(self):
        self.time_counter += 0.001 
        
        if self.current_live_mode == 'ANALYZER':
            freq = self.ana_spin_freq.value()
            t, ch1, ch2, _ = generate_analyzer_signals(freq, self.ana_spin_amp.value(), self.ana_spin_time.value(), 0.8, -25.0, self.time_counter)
            gain, phase = analyze_active(t, ch1, ch2, freq)
            
            self.lbl_ana_gain.setText(f"{gain:.2f} dB")
            self.lbl_ana_phase.setText(f"{phase:.2f} °")
            
        elif self.current_live_mode == 'PASSIVE':
            # Giả lập đọc tín hiệu bên ngoài
            t, ch1, ch2, _ = generate_external_signals(
                self.osc_spin_time.value(), 
                self.ext_f1.value(), 2.0,  # CH1 giả lập 2V
                self.ext_f2.value(), 1.5,  # CH2 giả lập 1.5V
                self.time_counter
            )
            f1, v1_pp, f2, v2_pp = analyze_passive(t, ch1, ch2)
            
            self.lbl_osc_f1.setText(f"{f1:.1f} Hz")
            self.lbl_osc_v1.setText(f"{v1_pp:.2f} Vpp")
            self.lbl_osc_f2.setText(f"{f2:.1f} Hz")
            self.lbl_osc_v2.setText(f"{v2_pp:.2f} Vpp")

        self.curve_ch1.setData(t, ch1)
        self.curve_ch2.setData(t, ch2)

    # --- SWEEP BODE ---
    def run_sweep(self):
        self.view_tabs.setCurrentIndex(1) 
        self.btn_sweep.setEnabled(False)
        self.worker = SweepWorker(
            self.sweep_start.value(), self.sweep_stop.value(),
            int(self.sweep_pts.value()), self.ana_spin_amp.value()
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.result.connect(self.update_bode_plot)
        self.worker.finished.connect(lambda: self.btn_sweep.setEnabled(True))
        self.worker.start()

    def update_bode_plot(self, freqs, gains, phases):
        self.curve_bode_gain.setData(freqs, gains)
        self.curve_bode_phase.setData(freqs, phases)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SignalAnalyzerApp()
    window.show()
    sys.exit(app.exec())