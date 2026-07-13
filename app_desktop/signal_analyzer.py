import sys
import os
import csv
import json
import numpy as np
import pyqtgraph as pg
from scipy import signal

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton, 
                             QGroupBox, QFormLayout, QGridLayout, QTabWidget, QProgressBar,
                             QColorDialog, QComboBox, QLineEdit, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

# Try to import serial for USB CDC communication
SERIAL_AVAILABLE = False
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    pass

# ==========================================
# 1. HÀM TẠO DỮ LIỆU & DSP (CORE MODULE)
# ==========================================

def generate_analyzer_signals(freq, amplitude, sampling_time_ms, sim_gain, sim_phase_deg, time_offset=0.0):
    sampling_time_s = sampling_time_ms / 1000.0
    sample_rate = max(100000, int(freq * 50)) 
    t_raw = np.arange(0, sampling_time_s, 1 / sample_rate)
    t_running = t_raw + time_offset 
    
    omega = 2 * np.pi * freq
    v_in_clean = amplitude * np.sin(omega * t_running)
    phase_shift_rad = np.deg2rad(sim_phase_deg)
    
    v_out_clean = sim_gain * amplitude * np.sin(omega * t_running + phase_shift_rad)
    v_out_clean += (sim_gain * amplitude * 0.05) * np.sin(2 * omega * t_running + phase_shift_rad) # Harmonic noise
    
    ch1 = v_in_clean + np.random.normal(0, amplitude * 0.01, len(t_raw))
    ch2 = v_out_clean + np.random.normal(0, sim_gain * amplitude * 0.01, len(t_raw))
    return t_raw, ch1, ch2, sample_rate

def generate_external_signals(sampling_time_ms, f1, amp1, f2, amp2, time_offset=0.0):
    sampling_time_s = sampling_time_ms / 1000.0
    sample_rate = max(100000, int(max(f1, f2) * 50))
    t_raw = np.arange(0, sampling_time_s, 1 / sample_rate)
    t_running = t_raw + time_offset
    
    ch1 = amp1 * np.sin(2 * np.pi * f1 * t_running) + np.random.normal(0, amp1*0.02, len(t_raw))
    ch2 = amp2 * np.sin(2 * np.pi * f2 * t_running + np.pi/4) + np.random.normal(0, amp2*0.03, len(t_raw))
    return t_raw, ch1, ch2, sample_rate

def measure_frequency(t, v):
    """Estimate signal frequency using zero-crossing method"""
    v_ac = v - np.mean(v)
    crossings = np.where(np.diff(np.sign(v_ac)))[0]
    if len(crossings) > 1:
        dt = t[crossings[-1]] - t[crossings[0]]
        cycles = (len(crossings) - 1) / 2.0
        if dt > 0:
            return cycles / dt
    return 0.0

def calculate_phase(t, v_in, v_out, freq):
    """Calculate phase shift using cross-correlation"""
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

    def __init__(self, parent_app, f_start, f_stop, points, amp):
        super().__init__()
        self.parent_app = parent_app
        self.f_start = f_start
        self.f_stop = f_stop
        self.points = points
        self.amp = amp

    def run(self):
        freqs = np.logspace(np.log10(self.f_start), np.log10(self.f_stop), self.points)
        gains = []
        phases = []
        
        for i, f in enumerate(freqs):
            if self.parent_app.serial_conn and self.parent_app.serial_conn.is_open:
                # Compile parameters and configure hardware
                wave_cmd = f"CONFIG:WAVE=SINE,FREQ={int(f)},AMP_MV={int(self.amp*1000)},OFFSET_MV=0,DAC_GAIN=X2,FS={int(f*10)},SAMPLES=1024\n"
                self.parent_app.serial_send_cmd(wave_cmd)
                self.parent_app.serial_send_cmd("START\n")
                self.msleep(50)
                
                # Fetch result
                res_str = self.parent_app.serial_query("GET_RESULT\n")
                self.parent_app.serial_send_cmd("STOP\n")
                
                # Parse
                try:
                    if res_str.startswith("RESULT:"):
                        data = json.loads(res_str[7:])
                        gains.append(data["gain_db"])
                        phases.append(data["phase_deg"])
                    else:
                        gains.append(-99.0)
                        phases.append(0.0)
                except Exception:
                    gains.append(-99.0)
                    phases.append(0.0)
            else:
                # Simulated sweep
                fc = 50000.0 
                actual_gain = 0.8 / np.sqrt(1 + (f/fc)**2)
                actual_phase = -25.0 - np.rad2deg(np.arctan(f/fc))
                t_ms = max(5.0, (10 / f) * 1000) 
                t, v_in, v_out, _ = generate_analyzer_signals(f, self.amp, t_ms, actual_gain, actual_phase)
                g_db, p_deg = analyze_active(t, v_in, v_out, f)
                gains.append(g_db)
                phases.append(p_deg)
                
            self.progress.emit(int(((i + 1) / self.points) * 100))
            self.msleep(20)
            
        self.result.emit(freqs.tolist(), gains, phases)
        self.finished.emit()

# ==========================================
# 3. GIAO DIỆN CHÍNH (GUI)
# ==========================================
class SignalAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Signal Analyzer Pro - Reorganized Layer PlatformIO")
        self.resize(1300, 900)
        
        self.is_dark_theme = True
        self.time_counter = 0.0
        self.current_live_mode = None 
        
        # Serial variables
        self.serial_conn = None
        self.last_raw_ch1 = np.array([])
        self.last_raw_ch2 = np.array([])
        self.last_raw_time = np.array([])
        
        self.live_timer = QTimer()
        self.live_timer.timeout.connect(self.process_live_data)

        self.initUI()
        self.refresh_com_ports()
        
    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # --- LEFT PANEL: Controls ---
        left_panel = QVBoxLayout()
        left_panel.setContentsMargins(0, 0, 10, 0)
        
        # Theme button & Color Pickers
        top_ctrl_layout = QHBoxLayout()
        self.btn_theme = QPushButton("White Theme ☀")
        self.btn_theme.setStyleSheet("font-weight: bold; height: 30px; background-color: #f0f0f0; color: black;")
        self.btn_theme.clicked.connect(self.toggle_theme)
        top_ctrl_layout.addWidget(self.btn_theme)
        
        self.btn_col_ch1 = QPushButton("CH1 Color")
        self.btn_col_ch1.setStyleSheet("background-color: #ffEB3B; color: black; font-weight: bold; height: 30px;")
        self.btn_col_ch1.clicked.connect(lambda: self.change_channel_color(1))
        
        self.btn_col_ch2 = QPushButton("CH2 Color")
        self.btn_col_ch2.setStyleSheet("background-color: #00E5FF; color: black; font-weight: bold; height: 30px;")
        self.btn_col_ch2.clicked.connect(lambda: self.change_channel_color(2))
        
        top_ctrl_layout.addWidget(self.btn_col_ch1)
        top_ctrl_layout.addWidget(self.btn_col_ch2)
        left_panel.addLayout(top_ctrl_layout)
        
        # ====== DEVICE CONNECTION ======
        conn_group = QGroupBox("Device Connection")
        conn_layout = QGridLayout()
        self.combo_ports = QComboBox()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_com_ports)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.toggle_connection)
        self.btn_connect.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.lbl_conn_status = QLabel("Status: Disconnected (SIMULATION)")
        self.lbl_conn_status.setStyleSheet("color: #ffaa00; font-weight: bold;")
        
        conn_layout.addWidget(QLabel("COM Port:"), 0, 0)
        conn_layout.addWidget(self.combo_ports, 0, 1)
        conn_layout.addWidget(self.btn_refresh, 0, 2)
        conn_layout.addWidget(self.btn_connect, 1, 0, 1, 3)
        conn_layout.addWidget(self.lbl_conn_status, 2, 0, 1, 3)
        conn_group.setLayout(conn_layout)
        left_panel.addWidget(conn_group)
        
        # TAB WIDGETS
        self.ctrl_tabs = QTabWidget()
        
        # ====== TAB 1: NETWORK ANALYZER (CHỦ ĐỘNG) ======
        ana_widget = QWidget()
        ana_layout = QVBoxLayout(ana_widget)
        
        config_group = QGroupBox("Stimulus Signal & Capture Config")
        config_layout = QFormLayout()
        
        self.ana_combo_wave = QComboBox()
        self.ana_combo_wave.addItems(["SINE", "SQUARE", "TRIANGLE", "DC"])
        
        self.ana_spin_freq = QDoubleSpinBox()
        self.ana_spin_freq.setRange(10, 500000)
        self.ana_spin_freq.setValue(20000)
        self.ana_spin_freq.setSuffix(" Hz")
        self.ana_spin_freq.valueChanged.connect(self.update_error_metrics)
        
        self.ana_spin_amp = QDoubleSpinBox()
        self.ana_spin_amp.setRange(0.1, 3.3)
        self.ana_spin_amp.setValue(0.3)
        self.ana_spin_amp.setSuffix(" V")
        
        self.ana_spin_offset = QDoubleSpinBox()
        self.ana_spin_offset.setRange(-1.65, 1.65)
        self.ana_spin_offset.setValue(0.0)
        self.ana_spin_offset.setSuffix(" V")
        
        self.ana_combo_gain = QComboBox()
        self.ana_combo_gain.addItems(["X1 (0-2.048V)", "X2 (0-4.096V)"])
        self.ana_combo_gain.setCurrentIndex(1)
        
        self.ana_spin_fs = QDoubleSpinBox()
        self.ana_spin_fs.setRange(1000, 1000000)
        self.ana_spin_fs.setValue(200000)
        self.ana_spin_fs.setSuffix(" SPS")
        self.ana_spin_fs.valueChanged.connect(self.update_error_metrics)
        
        self.ana_combo_samples = QComboBox()
        self.ana_combo_samples.addItems(["512", "1024", "2048"])
        self.ana_combo_samples.setCurrentIndex(1)

        self.ana_combo_range = QComboBox()
        self.ana_combo_range.addItems([
            "AUTO",
            "MANUAL - 0.3 V",
            "MANUAL - 3.3 V",
            "MANUAL - 10 V",
        ])
        self.lbl_range_status = QLabel("AUTO / 10V (safe startup)")
        
        config_layout.addRow("Waveform Type:", self.ana_combo_wave)
        config_layout.addRow("TX Frequency:", self.ana_spin_freq)
        config_layout.addRow("TX Amplitude:", self.ana_spin_amp)
        config_layout.addRow("TX Offset:", self.ana_spin_offset)
        config_layout.addRow("DAC Gain Bit:", self.ana_combo_gain)
        config_layout.addRow("Sample Rate Fs:", self.ana_spin_fs)
        config_layout.addRow("Capture Samples:", self.ana_combo_samples)
        config_layout.addRow("ADC Input Range:", self.ana_combo_range)
        config_layout.addRow("Active Range:", self.lbl_range_status)
        
        self.btn_ana_apply = QPushButton("Apply Configuration")
        self.btn_ana_apply.clicked.connect(self.apply_device_config)
        self.btn_ana_apply.setStyleSheet("font-weight: bold; background-color: #00796B; color: white;")
        config_layout.addRow(self.btn_ana_apply)
        config_group.setLayout(config_layout)
        ana_layout.addWidget(config_group)
        
        # ERROR ESTIMATES PANEL
        err_group = QGroupBox("Signal Error Analysis")
        err_layout = QFormLayout()
        self.lbl_samples_cycle = QLabel("10.0")
        self.lbl_peak_err = QLabel("4.89%")
        self.lbl_zoh_droop = QLabel("1.64%")
        self.lbl_settling_margin = QLabel("5.00 µs (OK)")
        
        err_layout.addRow("Samples per cycle (N):", self.lbl_samples_cycle)
        err_layout.addRow("Peak sampling error:", self.lbl_peak_err)
        err_layout.addRow("DAC ZOH droop:", self.lbl_zoh_droop)
        err_layout.addRow("DAC Settling Margin:", self.lbl_settling_margin)
        err_group.setLayout(err_layout)
        ana_layout.addWidget(err_group)
        
        # START/STOP RUNTIME
        run_layout = QHBoxLayout()
        self.btn_ana_live = QPushButton("Start Test")
        self.btn_ana_live.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; height: 35px;")
        self.btn_ana_live.clicked.connect(lambda: self.toggle_live('ANALYZER'))
        
        self.btn_export = QPushButton("Export CSV/JSON")
        self.btn_export.clicked.connect(self.export_report)
        self.btn_export.setStyleSheet("background-color: #E65100; color: white; font-weight: bold; height: 35px;")
        
        run_layout.addWidget(self.btn_ana_live)
        run_layout.addWidget(self.btn_export)
        ana_layout.addLayout(run_layout)
        
        # PASS/FAIL CRITERIA
        pf_group = QGroupBox("Pass/Fail Tolerance")
        pf_layout = QGridLayout()
        
        self.spin_target_gain = QDoubleSpinBox(); self.spin_target_gain.setRange(-50, 50); self.spin_target_gain.setValue(-2.0); self.spin_target_gain.setSuffix(" dB")
        self.spin_tol_gain = QDoubleSpinBox(); self.spin_tol_gain.setRange(0.1, 10); self.spin_tol_gain.setValue(1.5); self.spin_tol_gain.setSuffix(" dB")
        self.lbl_pf_status = QLabel("STATUS: IDLE")
        self.lbl_pf_status.setStyleSheet("font-size: 16px; font-weight: bold; color: gray; qproperty-alignment: AlignCenter;")
        
        pf_layout.addWidget(QLabel("Target Gain:"), 0, 0)
        pf_layout.addWidget(self.spin_target_gain, 0, 1)
        pf_layout.addWidget(QLabel("Gain Tol +/-:"), 1, 0)
        pf_layout.addWidget(self.spin_tol_gain, 1, 1)
        pf_layout.addWidget(self.lbl_pf_status, 2, 0, 1, 2)
        pf_group.setLayout(pf_layout)
        ana_layout.addWidget(pf_group)
        
        ana_layout.addStretch()
        self.ctrl_tabs.addTab(ana_widget, "Network Analyzer")
        
        # ====== TAB 2: BODE SWEEP CONTROL ======
        sweep_widget = QWidget()
        sweep_layout = QVBoxLayout(sweep_widget)
        
        sweep_group = QGroupBox("Bode Plot Settings")
        sweep_form = QFormLayout()
        self.sweep_start = QDoubleSpinBox(); self.sweep_start.setRange(10, 100000); self.sweep_start.setValue(100); self.sweep_start.setSuffix(" Hz")
        self.sweep_stop = QDoubleSpinBox(); self.sweep_stop.setRange(1000, 1000000); self.sweep_stop.setValue(250000); self.sweep_stop.setSuffix(" Hz")
        self.sweep_pts = QDoubleSpinBox(); self.sweep_pts.setRange(5, 200); self.sweep_pts.setValue(30)
        
        sweep_form.addRow("Start Freq:", self.sweep_start)
        sweep_form.addRow("Stop Freq:", self.sweep_stop)
        sweep_form.addRow("Sweep Points:", self.sweep_pts)
        
        self.btn_sweep = QPushButton("Run Bode Sweep")
        self.btn_sweep.setStyleSheet("background-color: #00897B; color: white; font-weight: bold; height: 35px;")
        self.btn_sweep.clicked.connect(self.run_sweep)
        sweep_form.addRow(self.btn_sweep)
        
        self.progress_bar = QProgressBar(); self.progress_bar.setValue(0)
        sweep_form.addRow(self.progress_bar)
        sweep_group.setLayout(sweep_form)
        sweep_layout.addWidget(sweep_group)
        
        # Bode Results display
        res_ana_group = QGroupBox("Analyzer Results")
        res_ana_layout = QGridLayout()
        self.lbl_ana_gain = QLabel("0.00 dB"); self.lbl_ana_phase = QLabel("0.00 °")
        for lbl in [self.lbl_ana_gain, self.lbl_ana_phase]:
            lbl.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 15px;"); lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        res_ana_layout.addWidget(QLabel("Measured Gain:"), 0, 0); res_ana_layout.addWidget(self.lbl_ana_gain, 0, 1)
        res_ana_layout.addWidget(QLabel("Phase Shift:"), 1, 0); res_ana_layout.addWidget(self.lbl_ana_phase, 1, 1)
        res_ana_group.setLayout(res_ana_layout)
        sweep_layout.addWidget(res_ana_group)
        
        sweep_layout.addStretch()
        self.ctrl_tabs.addTab(sweep_widget, "Bode Sweep")
        
        # ====== TAB 3: CALIBRATION UI ======
        calib_widget = QWidget()
        calib_layout = QVBoxLayout(calib_widget)
        calib_form = QFormLayout()
        
        self.cal_dac_a = QLineEdit("1.000000")
        self.cal_dac_b = QLineEdit("0.000000")
        self.cal_adc1_m0 = QLineEdit("1.000000")
        self.cal_adc1_c0 = QLineEdit("0.000000")
        self.cal_adc1_m1 = QLineEdit("10.000000")
        self.cal_adc1_c1 = QLineEdit("0.000000")
        self.cal_adc1_m2 = QLineEdit("100.000000")
        self.cal_adc1_c2 = QLineEdit("0.000000")
        self.cal_adc2_m0 = QLineEdit("1.000000")
        self.cal_adc2_c0 = QLineEdit("0.000000")
        self.cal_adc2_m1 = QLineEdit("10.000000")
        self.cal_adc2_c1 = QLineEdit("0.000000")
        self.cal_adc2_m2 = QLineEdit("100.000000")
        self.cal_adc2_c2 = QLineEdit("0.000000")
        
        calib_form.addRow("DAC Gain X2 Scale (a):", self.cal_dac_a)
        calib_form.addRow("DAC Offset (b):", self.cal_dac_b)
        calib_form.addRow("ADC1 0.3V Gain/Scale:", self.cal_adc1_m0)
        calib_form.addRow("ADC1 0.3V Offset:", self.cal_adc1_c0)
        calib_form.addRow("ADC1 3.3V Gain/Scale:", self.cal_adc1_m1)
        calib_form.addRow("ADC1 3.3V Offset:", self.cal_adc1_c1)
        calib_form.addRow("ADC1 10V Gain/Scale:", self.cal_adc1_m2)
        calib_form.addRow("ADC1 10V Offset:", self.cal_adc1_c2)
        calib_form.addRow("ADC2 0.3V Gain/Scale:", self.cal_adc2_m0)
        calib_form.addRow("ADC2 0.3V Offset:", self.cal_adc2_c0)
        calib_form.addRow("ADC2 3.3V Gain/Scale:", self.cal_adc2_m1)
        calib_form.addRow("ADC2 3.3V Offset:", self.cal_adc2_c1)
        calib_form.addRow("ADC2 10V Gain/Scale:", self.cal_adc2_m2)
        calib_form.addRow("ADC2 10V Offset:", self.cal_adc2_c2)
        
        btn_read_calib = QPushButton("Read Calib from Dev")
        btn_read_calib.clicked.connect(self.read_calibration_from_device)
        btn_write_calib = QPushButton("Write Calib to Dev")
        btn_write_calib.clicked.connect(self.write_calibration_to_device)
        btn_write_calib.setStyleSheet("background-color: #00796B; color: white; font-weight: bold;")
        btn_reset_calib = QPushButton("Reset Defaults")
        btn_reset_calib.clicked.connect(self.reset_calibration_device)
        
        calib_form.addRow(btn_read_calib)
        calib_form.addRow(btn_write_calib)
        calib_form.addRow(btn_reset_calib)
        
        calib_group = QGroupBox("Hardware Coefficients Calibration")
        calib_group.setLayout(calib_form)
        calib_layout.addWidget(calib_group)
        calib_layout.addStretch()
        self.ctrl_tabs.addTab(calib_widget, "Calibration")
        
        # ====== TAB 4: PASSIVE OSCILLO ======
        osc_widget = QWidget()
        osc_layout = QVBoxLayout(osc_widget)
        
        osc_config = QGroupBox("Oscilloscope Settings")
        osc_config_layout = QFormLayout()
        self.osc_spin_time = QDoubleSpinBox(); self.osc_spin_time.setRange(1, 5000); self.osc_spin_time.setValue(10.0); self.osc_spin_time.setSuffix(" ms")
        osc_config_layout.addRow("Time/Div (Window):", self.osc_spin_time)
        
        self.btn_osc_live = QPushButton("Start Passive Oscillo (RX Only)")
        self.btn_osc_live.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; height: 35px;")
        self.btn_osc_live.clicked.connect(lambda: self.toggle_live('PASSIVE'))
        osc_config_layout.addRow(self.btn_osc_live)
        osc_config.setLayout(osc_config_layout)
        osc_layout.addWidget(osc_config)
        
        sim_ext_group = QGroupBox("External Signal Sim (For Testing)")
        sim_ext_layout = QFormLayout()
        self.ext_f1 = QDoubleSpinBox(); self.ext_f1.setRange(10, 100000); self.ext_f1.setValue(500); self.ext_f1.setSuffix(" Hz")
        self.ext_f2 = QDoubleSpinBox(); self.ext_f2.setRange(10, 100000); self.ext_f2.setValue(1200); self.ext_f2.setSuffix(" Hz")
        sim_ext_layout.addRow("Sim CH1 Freq:", self.ext_f1)
        sim_ext_layout.addRow("Sim CH2 Freq:", self.ext_f2)
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
        self.ctrl_tabs.addTab(osc_widget, "Passive Oscillo")

        left_panel.addWidget(self.ctrl_tabs)
        main_layout.addLayout(left_panel, stretch=1)
        
        # --- RIGHT PANEL: Plots ---
        self.view_tabs = QTabWidget()
        
        # VIEW TAB 1: OSCILLOSCOPE MONITOR
        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        self.plot_osc = pg.PlotWidget(title="Time Domain Waveform (Double-click to Maximize)")
        self.plot_osc.showGrid(x=True, y=True); self.plot_osc.addLegend()
        self.plot_osc.setLabel('left', 'Voltage', 'V'); self.plot_osc.setLabel('bottom', 'Time', 's')
        self.curve_ch1 = self.plot_osc.plot(pen=pg.mkPen('#ffEB3B', width=2), name="CH1 (Vin)")
        self.curve_ch2 = self.plot_osc.plot(pen=pg.mkPen('#00E5FF', width=2), name="CH2 (Vout)")
        tab1_layout.addWidget(self.plot_osc)
        self.view_tabs.addTab(tab1, "Oscilloscope Monitor")
        
        self.plot_osc.setProperty("is_maximized", False)
        self.plot_osc.scene().sigMouseClicked.connect(lambda evt: self.toggle_maximize(self.plot_osc) if evt.double() else None)
        
        # VIEW TAB 2: BODE PLOT
        tab2 = QWidget()
        tab2_layout = QVBoxLayout(tab2)
        self.plot_bode_gain = pg.PlotWidget(title="Bode Plot: Magnitude (Double-click to Maximize)")
        self.plot_bode_gain.showGrid(x=True, y=True); self.plot_bode_gain.setLogMode(x=True, y=False)
        self.plot_bode_gain.setLabel('left', 'Gain', 'dB'); self.plot_bode_gain.setLabel('bottom', 'Frequency', 'Hz')
        self.curve_bode_gain = self.plot_bode_gain.plot(pen=pg.mkPen('#4CAF50', width=3), symbol='o')
        
        self.plot_bode_phase = pg.PlotWidget(title="Bode Plot: Phase (Double-click to Maximize)")
        self.plot_bode_phase.showGrid(x=True, y=True); self.plot_bode_phase.setLogMode(x=True, y=False)
        self.plot_bode_phase.setLabel('left', 'Phase', 'Deg'); self.plot_bode_phase.setLabel('bottom', 'Frequency', 'Hz')
        self.curve_bode_phase = self.plot_bode_phase.plot(pen=pg.mkPen('#FF9800', width=3), symbol='o')
        
        tab2_layout.addWidget(self.plot_bode_gain); tab2_layout.addWidget(self.plot_bode_phase)
        self.view_tabs.addTab(tab2, "Frequency Sweep (Bode)")
        
        self.plot_bode_gain.setProperty("is_maximized", False); self.plot_bode_phase.setProperty("is_maximized", False)
        self.plot_bode_gain.scene().sigMouseClicked.connect(lambda evt: self.toggle_maximize(self.plot_bode_gain) if evt.double() else None)
        self.plot_bode_phase.scene().sigMouseClicked.connect(lambda evt: self.toggle_maximize(self.plot_bode_phase) if evt.double() else None)

        main_layout.addWidget(self.view_tabs, stretch=3)
        self.all_plots = [self.plot_osc, self.plot_bode_gain, self.plot_bode_phase]
        
        self.update_error_metrics()

    # --- SERIAL PORTS SCAN ---
    def refresh_com_ports(self):
        self.combo_ports.clear()
        self.combo_ports.addItem("SIMULATE")
        if SERIAL_AVAILABLE:
            ports = serial.tools.list_ports.comports()
            for p in ports:
                self.combo_ports.addItem(p.device)
                
    # --- CONFIGURE DEVICE PARAMETERS ---
    def apply_device_config(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            QMessageBox.information(self, "Simulation Mode", "No device connected. Settings applied to Simulator.")
            return
            
        wave_str = self.ana_combo_wave.currentText()
        freq = int(self.ana_spin_freq.value())
        amp_mv = int(self.ana_spin_amp.value() * 1000)
        offset_mv = int(self.ana_spin_offset.value() * 1000)
        dac_gain = "X1" if self.ana_combo_gain.currentIndex() == 0 else "X2"
        fs = int(self.ana_spin_fs.value())
        samples = int(self.ana_combo_samples.currentText())

        if not self.apply_range_config():
            QMessageBox.critical(self, "Error", "Failed to configure the ADC input range.")
            return
        
        cmd = f"CONFIG:WAVE={wave_str},FREQ={freq},AMP_MV={amp_mv},OFFSET_MV={offset_mv},DAC_GAIN={dac_gain},FS={fs},SAMPLES={samples}\n"
        if self.serial_send_cmd(cmd):
            QMessageBox.information(self, "Success", "Configuration applied successfully to device!")

    def apply_range_config(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            return True

        commands = [
            "SET_RANGE:AUTO\n",
            "SET_RANGE:0.3V\n",
            "SET_RANGE:3.3V\n",
            "SET_RANGE:10V\n",
        ]
        if not self.serial_send_cmd(commands[self.ana_combo_range.currentIndex()]):
            return False

        self.refresh_range_status()
        return True

    def refresh_range_status(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            return

        response = self.serial_query("GET_RANGE\n")
        if not response.startswith("DATA:"):
            return

        values = {}
        for item in response[5:].split(','):
            key, separator, value = item.partition('=')
            if separator:
                values[key] = value

        mode = values.get("mode", "UNKNOWN")
        active_range = values.get("range", "UNKNOWN")
        self.lbl_range_status.setText(f"{mode} / {active_range}")
            
    # --- PING / PONG SERIAL COMMANDS ---
    def serial_send_cmd(self, cmd):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write(cmd.encode('utf-8'))
                res = self.serial_conn.readline().decode('utf-8').strip()
                if res == "OK":
                    return True
                else:
                    print(f"Error response: {res}")
            except Exception as e:
                print(f"Serial send error: {e}")
        return False
        
    def serial_query(self, cmd):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write(cmd.encode('utf-8'))
                res = self.serial_conn.readline().decode('utf-8').strip()
                return res
            except Exception as e:
                print(f"Serial query error: {e}")
        return ""

    # --- TOGGLE SERIAL CONNECTION ---
    def toggle_connection(self):
        port = self.combo_ports.currentText()
        if port == "SIMULATE":
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.serial_conn = None
            self.lbl_conn_status.setText("Status: Disconnected (SIMULATION)")
            self.lbl_conn_status.setStyleSheet("color: #ffaa00; font-weight: bold;")
            self.btn_connect.setText("Connect")
            self.btn_connect.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
            return
            
        if self.serial_conn and self.serial_conn.is_open:
            # Disconnect
            try:
                self.serial_conn.write(b"STOP\n")
            except Exception:
                pass
            self.serial_conn.close()
            self.serial_conn = None
            self.lbl_conn_status.setText("Status: Disconnected (SIMULATION)")
            self.lbl_conn_status.setStyleSheet("color: #ffaa00; font-weight: bold;")
            self.btn_connect.setText("Connect")
            self.btn_connect.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        else:
            # Connect
            try:
                self.serial_conn = serial.Serial(port, 115200, timeout=1.0)
                # Verify identity
                self.serial_conn.write(b"PING\n")
                res = self.serial_conn.readline().decode('utf-8').strip()
                if res == "OK":
                    info = self.serial_query("INFO\n")
                    self.lbl_conn_status.setText(f"Status: Connected ({info})")
                    self.lbl_conn_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    self.btn_connect.setText("Disconnect")
                    self.btn_connect.setStyleSheet("background-color: #F44336; color: white; font-weight: bold;")
                    self.refresh_range_status()
                else:
                    self.serial_conn.close()
                    self.serial_conn = None
                    QMessageBox.critical(self, "Error", "Connected device did not reply properly to PING.")
            except Exception as e:
                self.serial_conn = None
                QMessageBox.critical(self, "Error", f"Failed to connect to port {port}.\nDetails: {e}")

    # --- MATH FORMULAS FOR SAMPLING ISSUES ---
    def update_error_metrics(self):
        fs = self.ana_spin_fs.value()
        f_sig = self.ana_spin_freq.value()
        
        N = fs / f_sig
        self.lbl_samples_cycle.setText(f"{N:.2f}")
        
        # Peak sampling error = 1 - cos(pi / N)
        if N > 0:
            peak_err = (1 - np.cos(np.pi / N)) * 100
            self.lbl_peak_err.setText(f"{peak_err:.3f} %")
            
            # ZOH Droop = 1 - sin(pi / N) / (pi / N)
            zoh_droop = (1 - (np.sin(np.pi / N) / (np.pi / N))) * 100
            self.lbl_zoh_droop.setText(f"{zoh_droop:.3f} %")
        else:
            self.lbl_peak_err.setText("N/A")
            self.lbl_zoh_droop.setText("N/A")
            
        # DAC Settling margin warning
        sample_interval_us = 1000000.0 / fs
        if sample_interval_us < 4.5:
            self.lbl_settling_margin.setText(f"{sample_interval_us:.2f} µs (WARNING: Settling time limit)")
            self.lbl_settling_margin.setStyleSheet("color: #FF5252; font-weight: bold;")
        else:
            self.lbl_settling_margin.setText(f"{sample_interval_us:.2f} µs (OK)")
            self.lbl_settling_margin.setStyleSheet("color: #4CAF50; font-weight: bold;")

    # --- DARK / LIGHT THEME TOGGLE ---
    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        bg_color, fg_color = ('k', 'w') if self.is_dark_theme else ('w', 'k')
        self.btn_theme.setText("White Theme ☀" if self.is_dark_theme else "Dark Theme 🌙")
        self.btn_theme.setStyleSheet(f"font-weight: bold; height: 30px; background-color: {'#f0f0f0' if self.is_dark_theme else '#333333'}; color: {'black' if self.is_dark_theme else 'white'};")
        for p in self.all_plots:
            p.setBackground(bg_color)
            p.getAxis('bottom').setPen(fg_color)
            p.getAxis('bottom').setTextPen(fg_color)
            p.getAxis('left').setPen(fg_color)
            p.getAxis('left').setTextPen(fg_color)

    def change_channel_color(self, channel):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            text_color = 'white' if color.lightness() < 128 else 'black'
            if channel == 1:
                self.curve_ch1.setPen(pg.mkPen(color=hex_color, width=2))
                self.btn_col_ch1.setStyleSheet(f"background-color: {hex_color}; color: {text_color}; font-weight: bold; height: 30px;")
            else:
                self.curve_ch2.setPen(pg.mkPen(color=hex_color, width=2))
                self.btn_col_ch2.setStyleSheet(f"background-color: {hex_color}; color: {text_color}; font-weight: bold; height: 30px;")

    def toggle_maximize(self, clicked_widget):
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

    def toggle_live(self, mode):
        if self.live_timer.isActive():
            self.live_timer.stop()
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_send_cmd("STOP\n")
            self.btn_ana_live.setText("Start Test")
            self.btn_ana_live.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; height: 35px;")
            self.btn_osc_live.setText("Start Passive Oscillo (RX Only)")
            self.btn_osc_live.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; height: 35px;")
            self.ctrl_tabs.setTabEnabled(0, True); self.ctrl_tabs.setTabEnabled(1, True); self.ctrl_tabs.setTabEnabled(2, True)
            self.lbl_pf_status.setText("STATUS: IDLE")
            self.lbl_pf_status.setStyleSheet("font-size: 16px; font-weight: bold; color: gray; qproperty-alignment: AlignCenter;")
        else:
            self.current_live_mode = mode
            self.view_tabs.setCurrentIndex(0)
            
            if self.serial_conn and self.serial_conn.is_open:
                # Apply current parameters
                self.apply_device_config()
                self.serial_send_cmd("START\n")
                
            self.live_timer.start(50) # 20fps
            
            if mode == 'ANALYZER':
                self.btn_ana_live.setText("STOP Test")
                self.btn_ana_live.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; height: 35px;")
                self.ctrl_tabs.setTabEnabled(1, False)
                self.ctrl_tabs.setTabEnabled(2, False)
                self.ctrl_tabs.setTabEnabled(3, False)
            else:
                self.btn_osc_live.setText("STOP Passive Oscillo")
                self.btn_osc_live.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; height: 35px;")
                self.ctrl_tabs.setTabEnabled(0, False)
                self.ctrl_tabs.setTabEnabled(1, False)
                self.ctrl_tabs.setTabEnabled(2, False)

    # --- PROCESS REALTIME SERIAL / SIMULATOR DATA ---
    def process_live_data(self):
        self.time_counter += 0.005
        
        if self.serial_conn and self.serial_conn.is_open:
            # Query measurement result
            res_str = self.serial_query("GET_RESULT\n")
            if res_str.startswith("RESULT:"):
                try:
                    data = json.loads(res_str[7:])
                    gain = data["gain_db"]
                    phase = data["phase_deg"]
                    vin_vpp = data["vin_vpp"]
                    vout_vpp = data["vout_vpp"]
                    if "range_name" in data and "range_mode" in data:
                        self.lbl_range_status.setText(
                            f"{data['range_mode']} / {data['range_name']}"
                        )
                    
                    if self.current_live_mode == 'ANALYZER':
                        self.lbl_ana_gain.setText(f"{gain:.2f} dB")
                        self.lbl_ana_phase.setText(f"{phase:.2f} °")
                        
                        # Evaluate PASS / FAIL
                        target = self.spin_target_gain.value()
                        tol = self.spin_tol_gain.value()
                        if abs(gain - target) <= tol:
                            self.lbl_pf_status.setText("STATUS: PASS")
                            self.lbl_pf_status.setStyleSheet("font-size: 18px; font-weight: bold; color: #4CAF50; qproperty-alignment: AlignCenter;")
                        else:
                            self.lbl_pf_status.setText("STATUS: FAIL (OutOfTolerance)")
                            self.lbl_pf_status.setStyleSheet("font-size: 18px; font-weight: bold; color: #FF5252; qproperty-alignment: AlignCenter;")
                except Exception as e:
                    print(f"Result parse err: {e}")
            
            # Query binary raw samples
            try:
                self.serial_conn.write(b"GET_SAMPLES\n")
                
                # Parse binary custom frame format:
                # Header: 0xAA 0xBB (2 bytes)
                # Type: 0x03 (1 byte)
                # Length: uint16 (2 bytes, Big Endian)
                hdr = self.serial_conn.read(2)
                if hdr == b"\xaa\xbb":
                    frame_type = ord(self.serial_conn.read(1))
                    length_bytes = self.serial_conn.read(2)
                    length = (length_bytes[0] << 8) | length_bytes[1]
                    
                    payload = self.serial_conn.read(length)
                    crc = ord(self.serial_conn.read(1))
                    
                    # Unpack payload as interleaved uint16
                    raw_data = np.frombuffer(payload, dtype='>u2') # big endian uint16
                    if len(raw_data) >= 2:
                        ch1_raw = raw_data[0::2]
                        ch2_raw = raw_data[1::2]
                        
                        # Convert to physical voltage (-1.65 to 1.65V)
                        ch1 = (ch1_raw / 4095.0) * 3.3 - 1.65
                        ch2 = (ch2_raw / 4095.0) * 3.3 - 1.65
                        
                        fs = self.ana_spin_fs.value()
                        t = np.arange(0, len(ch1)) / fs
                        
                        self.curve_ch1.setData(t, ch1)
                        self.curve_ch2.setData(t, ch2)
                        
                        # Save local copy for exporting
                        self.last_raw_ch1 = ch1
                        self.last_raw_ch2 = ch2
                        self.last_raw_time = t
            except Exception as e:
                print(f"Error reading binary samples: {e}")
                
        else:
            # SIMULATION MODE fallback
            if self.current_live_mode == 'ANALYZER':
                freq = self.ana_spin_freq.value()
                t, ch1, ch2, _ = generate_analyzer_signals(freq, self.ana_spin_amp.value(), 5.0, 0.8, -25.0, self.time_counter)
                gain, phase = analyze_active(t, ch1, ch2, freq)
                
                self.lbl_ana_gain.setText(f"{gain:.2f} dB")
                self.lbl_ana_phase.setText(f"{phase:.2f} °")
                
                # Evaluate PASS / FAIL
                target = self.spin_target_gain.value()
                tol = self.spin_tol_gain.value()
                if abs(gain - target) <= tol:
                    self.lbl_pf_status.setText("STATUS: PASS")
                    self.lbl_pf_status.setStyleSheet("font-size: 18px; font-weight: bold; color: #4CAF50; qproperty-alignment: AlignCenter;")
                else:
                    self.lbl_pf_status.setText("STATUS: FAIL (OutOfTolerance)")
                    self.lbl_pf_status.setStyleSheet("font-size: 18px; font-weight: bold; color: #FF5252; qproperty-alignment: AlignCenter;")
                
                self.curve_ch1.setData(t, ch1)
                self.curve_ch2.setData(t, ch2)
                self.last_raw_ch1 = ch1
                self.last_raw_ch2 = ch2
                self.last_raw_time = t
                
            elif self.current_live_mode == 'PASSIVE':
                t, ch1, ch2, _ = generate_external_signals(
                    self.osc_spin_time.value(), 
                    self.ext_f1.value(), 2.0,  
                    self.ext_f2.value(), 1.5,  
                    self.time_counter
                )
                f1, v1_pp, f2, v2_pp = analyze_passive(t, ch1, ch2)
                
                self.lbl_osc_f1.setText(f"{f1:.1f} Hz")
                self.lbl_osc_v1.setText(f"{v1_pp:.2f} Vpp")
                self.lbl_osc_f2.setText(f"{f2:.1f} Hz")
                self.lbl_osc_v2.setText(f"{v2_pp:.2f} Vpp")
                
                self.curve_ch1.setData(t, ch1)
                self.curve_ch2.setData(t, ch2)
                self.last_raw_ch1 = ch1
                self.last_raw_ch2 = ch2
                self.last_raw_time = t

    # --- SWEEP BODE ---
    def run_sweep(self):
        self.view_tabs.setCurrentIndex(1) 
        if self.serial_conn and self.serial_conn.is_open and not self.apply_range_config():
            QMessageBox.critical(self, "Error", "Failed to configure the ADC input range.")
            return
        self.btn_sweep.setEnabled(False)
        self.worker = SweepWorker(
            self,
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

    # --- CALIBRATION INTERFACE METHODS ---
    def read_calibration_from_device(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            QMessageBox.warning(self, "Warning", "Device is not connected.")
            return
            
        res = self.serial_query("GET_CALIB\n")
        if res.startswith("DATA:"):
            params = res[5:].split(',')
            for p in params:
                kv = p.split('=')
                if len(kv) == 2:
                    k, v = kv[0], kv[1]
                    if k == "dac_x2_a": self.cal_dac_a.setText(v)
                    elif k == "dac_x2_b": self.cal_dac_b.setText(v)
                    elif k == "adc1_r0_m": self.cal_adc1_m0.setText(v)
                    elif k == "adc1_r0_c": self.cal_adc1_c0.setText(v)
                    elif k == "adc1_r1_m": self.cal_adc1_m1.setText(v)
                    elif k == "adc1_r1_c": self.cal_adc1_c1.setText(v)
                    elif k == "adc1_r2_m": self.cal_adc1_m2.setText(v)
                    elif k == "adc1_r2_c": self.cal_adc1_c2.setText(v)
                    elif k == "adc2_r0_m": self.cal_adc2_m0.setText(v)
                    elif k == "adc2_r0_c": self.cal_adc2_c0.setText(v)
                    elif k == "adc2_r1_m": self.cal_adc2_m1.setText(v)
                    elif k == "adc2_r1_c": self.cal_adc2_c1.setText(v)
                    elif k == "adc2_r2_m": self.cal_adc2_m2.setText(v)
                    elif k == "adc2_r2_c": self.cal_adc2_c2.setText(v)
            QMessageBox.information(self, "Success", "Calibration read successfully from hardware Flash!")

    def write_calibration_to_device(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            QMessageBox.warning(self, "Warning", "Device is not connected.")
            return
            
        # Send calibration coefficients one by one
        success = True
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=dac_x2_a,VALUE={self.cal_dac_a.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=dac_x2_b,VALUE={self.cal_dac_b.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc1_r0_m,VALUE={self.cal_adc1_m0.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc1_r0_c,VALUE={self.cal_adc1_c0.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc1_r1_m,VALUE={self.cal_adc1_m1.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc1_r1_c,VALUE={self.cal_adc1_c1.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc1_r2_m,VALUE={self.cal_adc1_m2.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc1_r2_c,VALUE={self.cal_adc1_c2.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc2_r0_m,VALUE={self.cal_adc2_m0.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc2_r0_c,VALUE={self.cal_adc2_c0.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc2_r1_m,VALUE={self.cal_adc2_m1.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc2_r1_c,VALUE={self.cal_adc2_c1.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc2_r2_m,VALUE={self.cal_adc2_m2.text()}\n")
        success &= self.serial_send_cmd(f"SET_CALIB:KEY=adc2_r2_c,VALUE={self.cal_adc2_c2.text()}\n")
        
        # Save to device Flash memory
        success &= self.serial_send_cmd("SAVE_CALIB\n")
        
        if success:
            QMessageBox.information(self, "Success", "Calibration coefficients saved into hardware Flash!")
        else:
            QMessageBox.critical(self, "Error", "Failed to save calibration coefficients to device.")

    def reset_calibration_device(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            QMessageBox.warning(self, "Warning", "Device is not connected.")
            return
            
        if self.serial_send_cmd("RESET_CALIB\n") and self.serial_send_cmd("SAVE_CALIB\n"):
            self.cal_dac_a.setText("1.000000")
            self.cal_dac_b.setText("0.000000")
            self.cal_adc1_m0.setText("1.000000")
            self.cal_adc1_c0.setText("0.000000")
            self.cal_adc1_m1.setText("10.000000")
            self.cal_adc1_c1.setText("0.000000")
            self.cal_adc1_m2.setText("100.000000")
            self.cal_adc1_c2.setText("0.000000")
            self.cal_adc2_m0.setText("1.000000")
            self.cal_adc2_c0.setText("0.000000")
            self.cal_adc2_m1.setText("10.000000")
            self.cal_adc2_c1.setText("0.000000")
            self.cal_adc2_m2.setText("100.000000")
            self.cal_adc2_c2.setText("0.000000")
            QMessageBox.information(self, "Success", "Calibration reset to defaults and saved to Flash.")

    # --- REPORT EXPORTS ---
    def export_report(self):
        if len(self.last_raw_ch1) == 0:
            QMessageBox.warning(self, "Warning", "No raw wave data available to export. Run a live test first.")
            return
            
        # Export CSV Raw samples
        try:
            csv_path = "amplifier_test_samples.csv"
            with open(csv_path, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Time (s)", "CH1 Vin (V)", "CH2 Vout (V)"])
                for i in range(len(self.last_raw_ch1)):
                    writer.writerow([self.last_raw_time[i], self.last_raw_ch1[i], self.last_raw_ch2[i]])
            
            # Export JSON summary report
            summary_path = "amplifier_test_summary.json"
            summary_data = {
                "tester": "PyQt6 Signal Analyzer Pro",
                "frequency_hz": self.ana_spin_freq.value(),
                "fs_sps": self.ana_spin_fs.value(),
                "samples_per_cycle": float(self.lbl_samples_cycle.text()),
                "est_peak_sampling_error": self.lbl_peak_err.text(),
                "est_zoh_droop": self.lbl_zoh_droop.text(),
                "gain_db": self.lbl_ana_gain.text(),
                "phase_deg": self.lbl_ana_phase.text(),
                "status": self.lbl_pf_status.text()
            }
            with open(summary_path, mode='w') as fj:
                json.dump(summary_data, fj, indent=4)
                
            QMessageBox.information(self, "Export Successful", f"Saved raw data to: {csv_path}\nSaved summary details to: {summary_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save reports.\nDetails: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Custom premium Dark Style Sheets
    app.setStyleSheet("""
        QMainWindow { background-color: #121212; }
        QWidget { color: #E0E0E0; font-family: 'Outfit', 'Inter', sans-serif; font-size: 12px; }
        QGroupBox { font-weight: bold; border: 1px solid #2D2D2D; border-radius: 6px; margin-top: 10px; padding-top: 10px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
        QPushButton { border: 1px solid #3A3A3A; border-radius: 4px; padding: 6px 12px; min-height: 20px; background-color: #1E1E1E; }
        QPushButton:hover { background-color: #2D2D2D; border-color: #4A4A4A; }
        QDoubleSpinBox, QComboBox, QLineEdit { border: 1px solid #2D2D2D; border-radius: 4px; padding: 4px; background-color: #181818; selection-background-color: #333; }
        QTabWidget::pane { border: 1px solid #2D2D2D; background-color: #121212; }
        QTabBar::tab { background: #1E1E1E; border: 1px solid #2D2D2D; padding: 6px 12px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
        QTabBar::tab:selected { background: #121212; border-bottom-color: #121212; }
    """)
    
    window = SignalAnalyzerApp()
    window.show()
    sys.exit(app.exec())
