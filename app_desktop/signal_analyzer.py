import sys
import os
import csv
import json
import pickle
import socket
import struct
import subprocess
import time
from collections import deque
from datetime import datetime, timezone
import numpy as np
import pyqtgraph as pg
from scipy import signal

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton, 
                             QGroupBox, QFormLayout, QGridLayout, QTabWidget, QProgressBar,
                             QColorDialog, QComboBox, QLineEdit, QMessageBox,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QFileDialog, QCheckBox, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

from signal_analysis import (
    analyze_channel,
    analyze_dut,
    calculate_sampling_quality,
    convert_measurement_channels,
    downsample_extrema_indices,
    evaluate_pass_fail,
)

APP_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_settings.json")
SERIAL_RX_BUFFER_BYTES = 4 * 1024 * 1024
SERIAL_TX_BUFFER_BYTES = 64 * 1024
PLOT_MAX_POINTS = 20000


def configure_serial_driver_buffers(serial_conn):
    """Give Windows CDC enough queueing headroom for temporary GUI stalls."""
    try:
        serial_conn.set_buffer_size(
            rx_size=SERIAL_RX_BUFFER_BYTES,
            tx_size=SERIAL_TX_BUFFER_BYTES,
        )
        return True
    except (AttributeError, NotImplementedError, OSError):
        return False


DEFAULT_APP_SETTINGS = {
    "language": "vi",
    "theme": "dark",
    "adc_input_range": "10V",
    "ch1_color": "#FFEB3B",
    "ch2_color": "#00E5FF",
    "show_grid": True,
    "auto_scale": True,
    "line_width": 2,
}

# English source text is used as the stable translation key. Technical units,
# protocol names and short metric names intentionally remain unchanged.
VI_TRANSLATIONS = {
    "Device Connection": "Kết nối thiết bị",
    "COM Port:": "Cổng COM:",
    "Refresh": "Làm mới",
    "Connect": "Kết nối",
    "Disconnect": "Ngắt kết nối",
    "Status: Disconnected (SIMULATION)": "Trạng thái: Chưa kết nối (MÔ PHỎNG)",
    "Network Analyzer": "Phân tích mạng",
    "Bode Sweep": "Quét Bode",
    "Calibration": "Hiệu chuẩn",
    "Passive Oscillo": "Dao động ký thụ động",
    "Settings": "Cài đặt",
    "⚙ Settings": "⚙ Cài đặt",
    "Analyzer": "Phân tích",
    "Bode": "Bode",
    "Oscilloscope": "Oscillo",
    "Stimulus Signal & Capture Config": "Cấu hình tín hiệu kích thích và thu mẫu",
    "Waveform Type:": "Dạng sóng:",
    "TX Frequency:": "Tần số phát:",
    "TX Amplitude:": "Biên độ phát:",
    "TX Offset:": "Offset phát:",
    "DAC Gain Bit:": "Hệ số khuếch đại DAC:",
    "Sample Rate Fs:": "Tần số lấy mẫu Fs:",
    "Capture Samples:": "Số mẫu thu:",
    "CH2 Vout / DUT Input Range": "Dải CH2 Vout / đầu ra DUT",
    "CH2 Vout Range:": "Dải CH2 Vout:",
    "Active CH2 Range:": "Dải CH2 đang dùng:",
    "Apply ADC Range": "Áp dụng dải ADC",
    "CH1 Vin Direct Gain Calibration:": "Hiệu chuẩn gain CH1 Vin trực tiếp:",
    "CH1 Vin Direct Offset:": "Offset CH1 Vin trực tiếp:",
    "Apply Configuration": "Áp dụng cấu hình",
    "Signal Error Analysis": "Phân tích sai số tín hiệu",
    "Signal period:": "Chu kỳ tín hiệu:",
    "Sample interval:": "Khoảng lấy mẫu:",
    "Samples per cycle (N):": "Số mẫu mỗi chu kỳ (N):",
    "Peak sampling error:": "Sai số bắt hụt đỉnh:",
    "DAC ZOH droop:": "Suy hao ZOH của DAC:",
    "DAC settling time:": "Thời gian xác lập DAC:",
    "DAC Settling Margin:": "Biên xác lập DAC:",
    "Measurement quality:": "Chất lượng phép đo:",
    "Start Test": "Bắt đầu đo",
    "STOP Test": "DỪNG phép đo",
    "Export CSV/JSON": "Xuất CSV/JSON",
    "Follow live data": "Bám theo dữ liệu mới",
    "View window:": "Cửa sổ hiển thị:",
    "Include raw samples": "Kèm mẫu thô",
    "Pass/Fail Tolerance": "Dung sai đánh giá đạt/không đạt",
    "Target Gain:": "Gain mục tiêu:",
    "Gain Tol +/-:": "Dung sai gain +/-:",
    "Frequency Tol +/-:": "Dung sai tần số +/-:",
    "Input Amplitude Tol +/-:": "Dung sai biên độ vào +/-:",
    "STATUS: IDLE": "TRẠNG THÁI: CHỜ",
    "Bode Plot Settings": "Cấu hình đồ thị Bode",
    "Start Freq:": "Tần số bắt đầu:",
    "Stop Freq:": "Tần số kết thúc:",
    "Sweep Points:": "Số điểm quét:",
    "Run Bode Sweep": "Chạy quét Bode",
    "Analyzer Results": "Kết quả phân tích",
    "Measured Gain:": "Gain đo được:",
    "Phase Shift:": "Độ lệch pha:",
    "Hardware Coefficients Calibration": "Hiệu chuẩn hệ số phần cứng",
    "Calibration status:": "Trạng thái hiệu chuẩn:",
    "DAC Gain X2 Scale (a):": "Hệ số tỷ lệ DAC Gain X2 (a):",
    "DAC Offset (b):": "Offset DAC (b):",
    "ADC1 0.3V Gain/Scale:": "ADC1 0.3V Gain/Tỷ lệ:",
    "ADC1 0.3V Offset:": "ADC1 0.3V Offset:",
    "ADC1 3.3V Gain/Scale:": "ADC1 3.3V Gain/Tỷ lệ:",
    "ADC1 3.3V Offset:": "ADC1 3.3V Offset:",
    "ADC1 10V Gain/Scale:": "ADC1 10V Gain/Tỷ lệ:",
    "ADC1 10V Offset:": "ADC1 10V Offset:",
    "ADC2 0.3V Gain/Scale:": "ADC2 0.3V Gain/Tỷ lệ:",
    "ADC2 0.3V Offset:": "ADC2 0.3V Offset:",
    "ADC2 3.3V Gain/Scale:": "ADC2 3.3V Gain/Tỷ lệ:",
    "ADC2 3.3V Offset:": "ADC2 3.3V Offset:",
    "ADC2 10V Gain/Scale:": "ADC2 10V Gain/Tỷ lệ:",
    "ADC2 10V Offset:": "ADC2 10V Offset:",
    "AUTO / 10V (safe startup)": "TỰ ĐỘNG / 10V (khởi động an toàn)",
    "Read Calib from Dev": "Đọc hiệu chuẩn từ thiết bị",
    "Write Calib to Dev": "Ghi hiệu chuẩn vào thiết bị",
    "Reset Defaults": "Khôi phục mặc định",
    "Export Calib JSON": "Xuất JSON hiệu chuẩn",
    "Import Calib JSON": "Nhập JSON hiệu chuẩn",
    "Oscilloscope Settings": "Cài đặt dao động ký",
    "Time/Div (Window):": "Time/Div (cửa sổ):",
    "Start Passive Oscillo (RX Only)": "Chạy dao động ký (chỉ thu)",
    "STOP Passive Oscillo": "DỪNG dao động ký",
    "External Signal Sim (For Testing)": "Mô phỏng tín hiệu ngoài",
    "Sim CH1 Freq:": "Tần số mô phỏng CH1:",
    "Sim CH2 Freq:": "Tần số mô phỏng CH2:",
    "Oscilloscope Measurements": "Kết quả đo dao động ký",
    "CH1 Measured Freq:": "Tần số CH1:",
    "CH2 Measured Freq:": "Tần số CH2:",
    "Oscilloscope Monitor": "Màn hình dao động ký",
    "Frequency Sweep (Bode)": "Quét tần số (Bode)",
    "Measurements": "Kết quả đo",
    "Channel Measurement": "Thông số từng kênh",
    "DUT Analysis": "Phân tích DUT",
    "Metric": "Thông số",
    "Value": "Giá trị",
    "DUT Metric": "Thông số DUT",
    "Vmean Offset": "Offset trung bình",
    "Frequency": "Tần số",
    "Period": "Chu kỳ",
    "Noise RMS": "Nhiễu RMS",
    "Clipping / Saturation": "Clipping / Bão hòa",
    "Target gain dB": "Gain mục tiêu dB",
    "Gain error dB": "Sai số gain dB",
    "Gain tolerance": "Dung sai gain",
    "Phase shift": "Độ lệch pha",
    "Delay": "Độ trễ",
    "Communication": "Truyền thông",
    "Result / Reasons": "Kết quả / Nguyên nhân",
    "Appearance": "Giao diện",
    "Language:": "Ngôn ngữ:",
    "Theme:": "Chủ đề:",
    "Dark": "Tối",
    "Light": "Sáng",
    "Waveform display": "Hiển thị dạng sóng",
    "CH1 Color": "Màu CH1",
    "CH2 Color": "Màu CH2",
    "Show plot grid": "Hiện lưới đồ thị",
    "Auto scale waveform": "Tự động co giãn dạng sóng",
    "Line width:": "Độ dày nét:",
    "Restore application defaults": "Khôi phục cài đặt mặc định",
    "Settings are saved automatically.": "Cài đặt được tự động lưu.",
    "Time Domain Waveform (Double-click to Maximize)": "Dạng sóng theo thời gian (nhấp đúp để phóng to)",
    "Bode Plot: Magnitude (Double-click to Maximize)": "Bode: Biên độ (nhấp đúp để phóng to)",
    "Bode Plot: Phase (Double-click to Maximize)": "Bode: Pha (nhấp đúp để phóng to)",
    "Voltage": "Điện áp",
    "Time": "Thời gian",
    "Gain": "Gain",
    "Phase": "Pha",
    "Not available": "Chưa có",
    "WARNING / DAC not settled": "CẢNH BÁO / DAC chưa xác lập",
    "WARNING / sampling too low": "CẢNH BÁO / tần số lấy mẫu quá thấp",
    "WARNING / POC only": "CẢNH BÁO / chỉ phù hợp POC",
    "WARNING / settling borderline": "CẢNH BÁO / biên xác lập sát giới hạn",
    "WARNING / limited confidence": "CẢNH BÁO / độ tin cậy hạn chế",
    "Simulation Mode": "Chế độ mô phỏng",
    "No device connected. Settings applied to Simulator.": "Chưa kết nối thiết bị. Cấu hình đã áp dụng cho bộ mô phỏng.",
    "Success": "Thành công",
    "Error": "Lỗi",
    "Warning": "Cảnh báo",
    "Busy": "Đang bận",
    "Wait for the current capture to finish before disconnecting.": "Hãy chờ lần thu mẫu hiện tại hoàn tất trước khi ngắt kết nối.",
    "Failed to configure the ADC input range.": "Không thể cấu hình dải đầu vào ADC.",
    "Configuration applied successfully to device!": "Đã áp dụng cấu hình cho thiết bị.",
    "Connected device did not reply properly to PING.": "Thiết bị đã kết nối không phản hồi PING hợp lệ.",
    "Device configuration failed.": "Cấu hình thiết bị thất bại.",
    "Device did not acknowledge START.": "Thiết bị không xác nhận lệnh START.",
    "Device is not connected.": "Thiết bị chưa được kết nối.",
    "Calibration read successfully from hardware Flash!": "Đã đọc hiệu chuẩn từ Flash của thiết bị.",
    "Calibration coefficients saved into hardware Flash!": "Đã lưu hệ số hiệu chuẩn vào Flash của thiết bị.",
    "Failed to save calibration coefficients to device.": "Không thể lưu hệ số hiệu chuẩn vào thiết bị.",
    "Calibration reset to defaults and saved to Flash.": "Đã khôi phục hiệu chuẩn mặc định và lưu vào Flash.",
    "No raw wave data available to export. Run a live test first.": "Chưa có dữ liệu sóng thô để xuất. Hãy chạy phép đo trước.",
    "Export Successful": "Xuất dữ liệu thành công",
    "Export Error": "Lỗi xuất dữ liệu",
    "Import Error": "Lỗi nhập dữ liệu",
    "default": "mặc định",
    "loaded from device": "đã đọc từ thiết bị",
    "loaded from JSON": "đã đọc từ JSON",
    "saved to device": "đã lưu vào thiết bị",
    "modified but not saved": "đã thay đổi, chưa lưu",
}

DARK_STYLESHEET = """
    QMainWindow, QWidget { background-color: #121212; color: #E0E0E0; }
    QWidget { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 12px; }
    QGroupBox { font-weight: bold; border: 1px solid #3A3A3A; border-radius: 6px; margin-top: 10px; padding-top: 10px; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
    QPushButton { border: 1px solid #454545; border-radius: 4px; padding: 6px 12px; min-height: 20px; background-color: #1E1E1E; }
    QPushButton:hover { background-color: #2D2D2D; border-color: #5A5A5A; }
    QDoubleSpinBox, QComboBox, QLineEdit { border: 1px solid #454545; border-radius: 4px; padding: 4px; background-color: #181818; selection-background-color: #1565C0; }
    QTabWidget::pane { border: 1px solid #3A3A3A; background-color: #121212; }
    QTabBar::tab { background: #1E1E1E; border: 1px solid #3A3A3A; padding: 7px 12px; }
    QTabBar::tab:selected { background: #121212; border-bottom-color: #121212; }
    QTableWidget { background-color: #181818; alternate-background-color: #202020; color: #E0E0E0; gridline-color: #484848; selection-background-color: #1565C0; }
    QHeaderView::section { background-color: #252525; color: #F0F0F0; border: 1px solid #484848; padding: 4px; font-weight: bold; }
    QProgressBar { border: 1px solid #454545; background: #181818; text-align: center; }
    QProgressBar::chunk { background-color: #00897B; }
    QCheckBox::indicator { width: 15px; height: 15px; }
"""

LIGHT_STYLESHEET = """
    QMainWindow, QWidget { background-color: #F4F6F8; color: #202124; }
    QWidget { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 12px; }
    QGroupBox { font-weight: bold; border: 1px solid #B8C0C8; border-radius: 6px; margin-top: 10px; padding-top: 10px; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
    QPushButton { border: 1px solid #AAB2BA; border-radius: 4px; padding: 6px 12px; min-height: 20px; background-color: #FFFFFF; }
    QPushButton:hover { background-color: #E8EDF2; border-color: #7E8994; }
    QDoubleSpinBox, QComboBox, QLineEdit { border: 1px solid #AAB2BA; border-radius: 4px; padding: 4px; background-color: #FFFFFF; selection-background-color: #90CAF9; }
    QTabWidget::pane { border: 1px solid #B8C0C8; background-color: #F4F6F8; }
    QTabBar::tab { background: #E3E8ED; border: 1px solid #B8C0C8; padding: 7px 12px; }
    QTabBar::tab:selected { background: #FFFFFF; border-bottom-color: #FFFFFF; }
    QTableWidget { background-color: #FFFFFF; alternate-background-color: #F5F7F9; color: #202124; gridline-color: #B8C0C8; selection-background-color: #90CAF9; }
    QHeaderView::section { background-color: #E3E8ED; color: #202124; border: 1px solid #B8C0C8; padding: 4px; font-weight: bold; }
    QProgressBar { border: 1px solid #AAB2BA; background: #FFFFFF; text-align: center; }
    QProgressBar::chunk { background-color: #00897B; }
    QCheckBox::indicator { width: 15px; height: 15px; }
"""

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


def generate_configured_signals(freq, amplitude, offset, fs, sample_count,
                                sim_gain=0.8, sim_phase_deg=-25.0,
                                time_offset=0.0):
    """Generate the same finite capture shape used by a connected device."""
    t = np.arange(sample_count, dtype=np.float64) / fs
    running_t = t + time_offset
    omega = 2.0 * np.pi * freq
    ch1 = offset + amplitude * np.sin(omega * running_t)
    ch2 = offset + sim_gain * amplitude * np.sin(
        omega * running_t + np.deg2rad(sim_phase_deg)
    )
    noise_scale = max(amplitude * 0.002, 1e-6)
    ch1 += np.random.normal(0.0, noise_scale, sample_count)
    ch2 += np.random.normal(0.0, noise_scale, sample_count)
    return t, ch1, ch2

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
    fs = 1.0 / (t[1] - t[0]) if len(t) > 1 else 1.0
    ch1_metrics = analyze_channel(v_in, fs, freq)
    ch2_metrics = analyze_channel(v_out, fs, freq)
    dut = analyze_dut(ch1_metrics, ch2_metrics, 0.0, float("inf"), freq)
    return dut.gain_db or 0.0, dut.phase_shift_deg or 0.0

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


class LiveCaptureWorker(QThread):
    """Read one request/response capture without blocking the Qt GUI thread."""

    capture_ready = pyqtSignal(object)
    capture_error = pyqtSignal(str)

    def __init__(self, serial_conn, expected_samples):
        super().__init__()
        self.serial_conn = serial_conn
        self.expected_samples = expected_samples

    def _read_exact(self, size):
        data = bytearray()
        while len(data) < size:
            chunk = self.serial_conn.read(size - len(data))
            if not chunk:
                raise TimeoutError(f"short read: {len(data)}/{size} bytes")
            data.extend(chunk)
        return bytes(data)

    def run(self):
        try:
            # Every live frame is a fresh finite ADC block while the firmware's
            # DAC timer continues independently; repeated blocks drive the UI.
            self.serial_conn.write(b"START\n")
            self.serial_conn.flush()
            start_response = self.serial_conn.readline().decode("utf-8").strip()
            if start_response != "OK":
                raise RuntimeError(
                    f"START failed: {start_response or 'TIMEOUT'}"
                )

            self.serial_conn.write(b"GET_RESULT\n")
            self.serial_conn.flush()
            result_line = self.serial_conn.readline().decode("utf-8").strip()
            device_result = None
            if result_line.startswith("RESULT:"):
                try:
                    device_result = json.loads(result_line[7:])
                except json.JSONDecodeError:
                    device_result = None

            # Leave a small request/response guard for the MCU main-loop parser.
            self.msleep(5)

            self.serial_conn.write(b"GET_SAMPLES\n")
            self.serial_conn.flush()
            header = self._read_exact(5)
            if header[:2] != b"\xaa\xbb":
                raise ValueError(f"invalid frame header: {header.hex(' ')}")
            if header[2] != 0x03:
                raise ValueError(f"unexpected frame type: 0x{header[2]:02X}")
            payload_length = int.from_bytes(header[3:5], "big")
            expected_length = self.expected_samples * 4
            if payload_length != expected_length:
                raise ValueError(
                    f"sample length mismatch: {payload_length}/{expected_length} bytes"
                )
            payload = self._read_exact(payload_length)
            received_crc = self._read_exact(1)[0]
            calculated_crc = 0
            for value in payload:
                calculated_crc ^= value
            if received_crc != calculated_crc:
                raise ValueError(
                    f"CRC mismatch: rx=0x{received_crc:02X}, "
                    f"calc=0x{calculated_crc:02X}"
                )
            raw = np.frombuffer(payload, dtype=">u2").copy()
            self.capture_ready.emit({
                "ch1_raw": raw[0::2],
                "ch2_raw": raw[1::2],
                "device_result": device_result,
                "frame_bytes": payload_length + 6,
            })
        except Exception as exc:
            self.capture_error.emit(str(exc))


class LiveStreamWorker(QThread):
    """Consume sequence-checked continuous ADC frames from firmware."""

    capture_ready = pyqtSignal(object)
    capture_error = pyqtSignal(str)
    capture_warning = pyqtSignal(str)

    # Proven end-to-end with ADC at 140 kSPS and DAC DMA up to 200 kupdate/s.
    STREAM_FS = 140000
    # A 512-sample USB frame arrives about 273 times/s at 140 kSPS. Batch eight
    # losslessly checked frames; the GUI separately throttles expensive DSP and
    # plotting so no individual callback monopolizes the GIL for too long.
    UI_BLOCK_SAMPLES = 4096

    def __init__(self, serial_port):
        super().__init__()
        self.serial_port = serial_port
        self.stop_requested = False
        self.reader_process = None
        self.message_connection = None
        self.message_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.message_listener.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024
        )
        self.message_listener.bind(("127.0.0.1", 0))
        self.message_listener.listen(1)
        self.message_listener.settimeout(5.0)

    @staticmethod
    def _socket_read_exact(connection, size):
        data = bytearray()
        while len(data) < size:
            chunk = connection.recv(size - len(data))
            if not chunk:
                raise EOFError
            data.extend(chunk)
        return bytes(data)

    def request_stop(self):
        self.stop_requested = True
        if self.reader_process is not None:
            try:
                self.reader_process.terminate()
            except Exception:
                pass
        try:
            self.message_listener.close()
            if self.message_connection is not None:
                self.message_connection.close()
        except Exception:
            pass

    def run(self):
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "stream_reader_process.py")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.reader_process = subprocess.Popen(
                [sys.executable, helper, self.serial_port, str(self.STREAM_FS),
                 str(self.message_listener.getsockname()[1])],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=creation_flags,
            )
            self.message_connection, _ = self.message_listener.accept()
            self.message_connection.setsockopt(
                socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024
            )
            while not self.stop_requested:
                try:
                    length = struct.unpack(
                        "<I", self._socket_read_exact(
                            self.message_connection, 4
                        )
                    )[0]
                    message = pickle.loads(self._socket_read_exact(
                        self.message_connection, length
                    ))
                except EOFError:
                    break
                kind = message.get("kind")
                if kind == "capture":
                    self.capture_ready.emit(message["capture"])
                elif kind == "warning":
                    self.capture_warning.emit(message["message"])
                elif kind == "error":
                    raise RuntimeError(message["message"])
            if (not self.stop_requested and self.reader_process.poll() not in
                    (None, 0)):
                error_text = self.reader_process.stderr.read().decode(
                    "utf-8", errors="replace").strip()
                raise RuntimeError(error_text or "stream reader process exited")
        except Exception as exc:
            if not self.stop_requested:
                self.capture_error.emit(str(exc))
        finally:
            if self.reader_process is not None and self.reader_process.poll() is None:
                self.reader_process.terminate()
                try:
                    self.reader_process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self.reader_process.kill()
            try:
                if self.message_connection is not None:
                    self.message_connection.close()
                self.message_listener.close()
            except Exception:
                pass

# ==========================================
# 3. GIAO DIỆN CHÍNH (GUI)
# ==========================================
class SignalAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Signal Analyzer Pro - Reorganized Layer PlatformIO")
        self.resize(1300, 900)

        self.app_settings = self.load_app_settings()
        self.language = self.app_settings["language"]
        self.is_dark_theme = self.app_settings["theme"] == "dark"
        self.ch1_color = self.app_settings["ch1_color"]
        self.ch2_color = self.app_settings["ch2_color"]
        self.i18n_tabs = []
        self.time_counter = 0.0
        self.current_live_mode = None 
        self.detail_view_active = False
        
        # Serial variables
        self.serial_conn = None
        self.streaming_port = None
        self.last_raw_ch1 = np.array([])
        self.last_raw_ch2 = np.array([])
        self.last_raw_time = np.array([])
        self.history_window_s = 20.0
        self.hardware_history = deque()
        self.pending_hardware_captures = deque()
        self.hardware_history_cursor_s = 0.0
        self.last_history_plot_at = 0.0
        self.last_metrics_update_at = 0.0
        self.last_ch1_metrics = None
        self.last_ch2_metrics = None
        self.last_dut_metrics = None
        self.last_evaluation = None
        self.last_sampling_quality = None
        self.analysis_warmed = False
        self.last_communication_ok = True
        self.last_data_complete = True
        self.last_communication_error = ""
        self.last_command_response = ""
        self.device_info = "SIMULATOR"
        self.calibration_status = "default"
        self.capture_worker = None
        self.pending_device_stop = False
        self._closing = False
        
        self.live_timer = QTimer()
        self.live_timer.timeout.connect(self.process_live_data)

        self.initUI()
        self.apply_visual_settings(save=False)
        self.retranslate_ui()
        self.refresh_com_ports()

    @staticmethod
    def load_app_settings():
        settings = DEFAULT_APP_SETTINGS.copy()
        try:
            with open(APP_SETTINGS_PATH, "r", encoding="utf-8") as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                settings.update({key: loaded[key] for key in settings if key in loaded})
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        if settings["language"] not in ("en", "vi"):
            settings["language"] = DEFAULT_APP_SETTINGS["language"]
        if settings["theme"] not in ("dark", "light"):
            settings["theme"] = DEFAULT_APP_SETTINGS["theme"]
        if settings["adc_input_range"] not in ("0.3V", "3.3V", "10V"):
            settings["adc_input_range"] = DEFAULT_APP_SETTINGS["adc_input_range"]
        return settings

    def save_app_settings(self):
        try:
            with open(APP_SETTINGS_PATH, "w", encoding="utf-8") as file:
                json.dump(self.app_settings, file, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"Unable to save application settings: {exc}")

    def tr(self, source_text):
        if self.language == "vi":
            return VI_TRANSLATIONS.get(source_text, source_text)
        return source_text

    @staticmethod
    def make_scrollable(widget):
        """Keep long control tabs usable without forcing a tall main window."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        scroll.setMinimumSize(0, 0)
        scroll.setWidget(widget)
        return scroll

    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # --- LEFT PANEL: Controls ---
        self.left_panel_widget = QWidget()
        left_panel = QVBoxLayout(self.left_panel_widget)
        left_panel.setContentsMargins(0, 0, 10, 0)
        
        # ====== DEVICE CONNECTION ======
        self.conn_group = QGroupBox("Device Connection")
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
        self.conn_group.setLayout(conn_layout)
        left_panel.addWidget(self.conn_group)

        self.btn_open_settings = QPushButton("⚙ Settings")
        self.btn_open_settings.setToolTip(
            "Change language, theme and waveform display preferences"
        )
        self.btn_open_settings.setStyleSheet(
            "font-weight: bold; min-height: 28px; background-color: #455A64; color: white;"
        )
        left_panel.addWidget(self.btn_open_settings)
        
        # TAB WIDGETS
        self.ctrl_tabs = QTabWidget()
        self.btn_open_settings.clicked.connect(
            lambda: self.ctrl_tabs.setCurrentIndex(4)
        )
        
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
        self.ana_spin_freq.valueChanged.connect(
            lambda _value: self.update_error_metrics())
        
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
        self.ana_spin_fs.valueChanged.connect(
            lambda _value: self.update_error_metrics())
        
        self.ana_combo_samples = QComboBox()
        self.ana_combo_samples.addItems(["128", "256", "512"])
        self.ana_combo_samples.setCurrentIndex(0)

        self.ana_combo_range = QComboBox()
        self.ana_combo_range.addItem("0.3 V", "0.3V")
        self.ana_combo_range.addItem("3.3 V", "3.3V")
        self.ana_combo_range.addItem("10 V", "10V")
        selected_range = self.ana_combo_range.findData(
            self.app_settings["adc_input_range"]
        )
        self.ana_combo_range.setCurrentIndex(max(0, selected_range))
        self.lbl_range_status = QLabel(
            f"MANUAL / {self.ana_combo_range.currentData()}"
        )
        self.btn_apply_range = QPushButton("Apply ADC Range")
        self.btn_apply_range.clicked.connect(
            lambda: self.apply_range_config(show_message=True)
        )
        
        config_layout.addRow("Waveform Type:", self.ana_combo_wave)
        config_layout.addRow("TX Frequency:", self.ana_spin_freq)
        config_layout.addRow("TX Amplitude:", self.ana_spin_amp)
        config_layout.addRow("TX Offset:", self.ana_spin_offset)
        config_layout.addRow("DAC Gain Bit:", self.ana_combo_gain)
        config_layout.addRow("Sample Rate Fs:", self.ana_spin_fs)
        config_layout.addRow("Capture Samples:", self.ana_combo_samples)
        
        self.btn_ana_apply = QPushButton("Apply Configuration")
        self.btn_ana_apply.clicked.connect(
            lambda: self.apply_device_config(show_message=True)
        )
        self.btn_ana_apply.setStyleSheet("font-weight: bold; background-color: #00796B; color: white;")
        config_layout.addRow(self.btn_ana_apply)
        config_group.setLayout(config_layout)
        ana_layout.addWidget(config_group)

        range_group = QGroupBox("CH2 Vout / DUT Input Range")
        range_layout = QFormLayout(range_group)
        range_layout.addRow("CH2 Vout Range:", self.ana_combo_range)
        range_layout.addRow("Active CH2 Range:", self.lbl_range_status)
        range_layout.addRow(self.btn_apply_range)
        ana_layout.addWidget(range_group)
        
        # ERROR ESTIMATES PANEL
        err_group = QGroupBox("Signal Error Analysis")
        err_layout = QFormLayout()
        self.lbl_period = QLabel("50.00 µs")
        self.lbl_sample_interval = QLabel("5.00 µs")
        self.lbl_samples_cycle = QLabel("10.0")
        self.lbl_peak_err = QLabel("4.89%")
        self.lbl_zoh_droop = QLabel("1.64%")
        self.lbl_settling_time = QLabel("4.50 µs")
        self.lbl_settling_margin = QLabel("0.50 µs")
        self.lbl_measurement_quality = QLabel("WARNING / POC only")
        
        err_layout.addRow("Signal period:", self.lbl_period)
        err_layout.addRow("Sample interval:", self.lbl_sample_interval)
        err_layout.addRow("Samples per cycle (N):", self.lbl_samples_cycle)
        err_layout.addRow("Peak sampling error:", self.lbl_peak_err)
        err_layout.addRow("DAC ZOH droop:", self.lbl_zoh_droop)
        err_layout.addRow("DAC settling time:", self.lbl_settling_time)
        err_layout.addRow("DAC Settling Margin:", self.lbl_settling_margin)
        err_layout.addRow("Measurement quality:", self.lbl_measurement_quality)
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
        self.chk_export_raw = QCheckBox("Include raw samples")
        self.chk_export_raw.setChecked(True)

        self.chk_follow_stream = QCheckBox("Follow live data")
        self.chk_follow_stream.setChecked(True)
        self.spin_view_window = QDoubleSpinBox()
        self.spin_view_window.setRange(0.05, 20.0)
        self.spin_view_window.setDecimals(2)
        self.spin_view_window.setSingleStep(0.25)
        self.spin_view_window.setValue(2.0)
        self.spin_view_window.setSuffix(" s")

        view_layout = QHBoxLayout()
        view_layout.addWidget(self.chk_follow_stream)
        view_layout.addWidget(QLabel("View window:"))
        view_layout.addWidget(self.spin_view_window)
        ana_layout.addLayout(view_layout)
        
        run_layout.addWidget(self.btn_ana_live)
        run_layout.addWidget(self.btn_export)
        run_layout.addWidget(self.chk_export_raw)
        ana_layout.addLayout(run_layout)
        
        # PASS/FAIL CRITERIA
        pf_group = QGroupBox("Pass/Fail Tolerance")
        pf_layout = QGridLayout()
        
        self.spin_target_gain = QDoubleSpinBox(); self.spin_target_gain.setRange(-50, 50); self.spin_target_gain.setValue(-2.0); self.spin_target_gain.setSuffix(" dB")
        self.spin_tol_gain = QDoubleSpinBox(); self.spin_tol_gain.setRange(0.1, 10); self.spin_tol_gain.setValue(1.5); self.spin_tol_gain.setSuffix(" dB")
        self.spin_tol_freq = QDoubleSpinBox(); self.spin_tol_freq.setRange(0.01, 25); self.spin_tol_freq.setValue(1.0); self.spin_tol_freq.setSuffix(" %")
        self.spin_tol_amp = QDoubleSpinBox(); self.spin_tol_amp.setRange(0.1, 50); self.spin_tol_amp.setValue(5.0); self.spin_tol_amp.setSuffix(" %")
        self.lbl_pf_status = QLabel("STATUS: IDLE")
        self.lbl_pf_status.setStyleSheet("font-size: 16px; font-weight: bold; color: gray; qproperty-alignment: AlignCenter;")
        
        pf_layout.addWidget(QLabel("Target Gain:"), 0, 0)
        pf_layout.addWidget(self.spin_target_gain, 0, 1)
        pf_layout.addWidget(QLabel("Gain Tol +/-:"), 1, 0)
        pf_layout.addWidget(self.spin_tol_gain, 1, 1)
        pf_layout.addWidget(QLabel("Frequency Tol +/-:"), 2, 0)
        pf_layout.addWidget(self.spin_tol_freq, 2, 1)
        pf_layout.addWidget(QLabel("Input Amplitude Tol +/-:"), 3, 0)
        pf_layout.addWidget(self.spin_tol_amp, 3, 1)
        pf_layout.addWidget(self.lbl_pf_status, 4, 0, 1, 2)
        pf_group.setLayout(pf_layout)
        ana_layout.addWidget(pf_group)
        
        ana_layout.addStretch()
        self.ctrl_tabs.addTab(self.make_scrollable(ana_widget), "Analyzer")
        
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
        self.ctrl_tabs.addTab(self.make_scrollable(sweep_widget), "Bode")
        
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

        self.calibration_fields = {
            "dac_x2_a": self.cal_dac_a, "dac_x2_b": self.cal_dac_b,
            "adc1_r0_m": self.cal_adc1_m0, "adc1_r0_c": self.cal_adc1_c0,
            "adc1_r1_m": self.cal_adc1_m1, "adc1_r1_c": self.cal_adc1_c1,
            "adc1_r2_m": self.cal_adc1_m2, "adc1_r2_c": self.cal_adc1_c2,
            "adc2_r0_m": self.cal_adc2_m0, "adc2_r0_c": self.cal_adc2_c0,
            "adc2_r1_m": self.cal_adc2_m1, "adc2_r1_c": self.cal_adc2_c1,
            "adc2_r2_m": self.cal_adc2_m2, "adc2_r2_c": self.cal_adc2_c2,
        }
        for field in self.calibration_fields.values():
            field.textEdited.connect(self.mark_calibration_modified)
        self.lbl_calib_status = QLabel("default")
        self.lbl_calib_status.setStyleSheet("color: #FFB74D; font-weight: bold;")
        
        calib_form.addRow("DAC Gain X2 Scale (a):", self.cal_dac_a)
        calib_form.addRow("DAC Offset (b):", self.cal_dac_b)
        calib_form.addRow("CH1 Vin Direct Gain Calibration:", self.cal_adc1_m0)
        calib_form.addRow("CH1 Vin Direct Offset:", self.cal_adc1_c0)
        calib_form.addRow("ADC2 0.3V Gain/Scale:", self.cal_adc2_m0)
        calib_form.addRow("ADC2 0.3V Offset:", self.cal_adc2_c0)
        calib_form.addRow("ADC2 3.3V Gain/Scale:", self.cal_adc2_m1)
        calib_form.addRow("ADC2 3.3V Offset:", self.cal_adc2_c1)
        calib_form.addRow("ADC2 10V Gain/Scale:", self.cal_adc2_m2)
        calib_form.addRow("ADC2 10V Offset:", self.cal_adc2_c2)
        calib_form.addRow("Calibration status:", self.lbl_calib_status)
        
        btn_read_calib = QPushButton("Read Calib from Dev")
        btn_read_calib.clicked.connect(self.read_calibration_from_device)
        btn_write_calib = QPushButton("Write Calib to Dev")
        btn_write_calib.clicked.connect(self.write_calibration_to_device)
        btn_write_calib.setStyleSheet("background-color: #00796B; color: white; font-weight: bold;")
        btn_reset_calib = QPushButton("Reset Defaults")
        btn_reset_calib.clicked.connect(self.reset_calibration_device)
        btn_export_calib = QPushButton("Export Calib JSON")
        btn_export_calib.clicked.connect(self.export_calibration_json)
        btn_import_calib = QPushButton("Import Calib JSON")
        btn_import_calib.clicked.connect(self.import_calibration_json)
        
        calib_form.addRow(btn_read_calib)
        calib_form.addRow(btn_write_calib)
        calib_form.addRow(btn_reset_calib)
        calib_form.addRow(btn_export_calib, btn_import_calib)
        
        calib_group = QGroupBox("Hardware Coefficients Calibration")
        calib_group.setLayout(calib_form)
        calib_layout.addWidget(calib_group)
        calib_layout.addStretch()
        self.ctrl_tabs.addTab(self.make_scrollable(calib_widget), "Calibration")
        
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
        self.ctrl_tabs.addTab(self.make_scrollable(osc_widget), "Oscilloscope")

        # ====== TAB 5: APPLICATION SETTINGS ======
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)

        appearance_group = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance_group)
        self.combo_language = QComboBox()
        self.combo_language.addItem("Tiếng Việt", "vi")
        self.combo_language.addItem("English", "en")
        self.combo_language.setCurrentIndex(
            max(0, self.combo_language.findData(self.language))
        )
        self.combo_theme = QComboBox()
        self.combo_theme.addItem("Dark", "dark")
        self.combo_theme.addItem("Light", "light")
        self.combo_theme.setCurrentIndex(
            max(0, self.combo_theme.findData(self.app_settings["theme"]))
        )
        appearance_form.addRow("Language:", self.combo_language)
        appearance_form.addRow("Theme:", self.combo_theme)
        settings_layout.addWidget(appearance_group)

        waveform_group = QGroupBox("Waveform display")
        waveform_form = QFormLayout(waveform_group)
        color_buttons = QHBoxLayout()
        self.btn_col_ch1 = QPushButton("CH1 Color")
        self.btn_col_ch2 = QPushButton("CH2 Color")
        self.btn_col_ch1.clicked.connect(lambda: self.change_channel_color(1))
        self.btn_col_ch2.clicked.connect(lambda: self.change_channel_color(2))
        color_buttons.addWidget(self.btn_col_ch1)
        color_buttons.addWidget(self.btn_col_ch2)
        waveform_form.addRow(color_buttons)
        self.chk_show_grid = QCheckBox("Show plot grid")
        self.chk_show_grid.setChecked(bool(self.app_settings["show_grid"]))
        self.chk_auto_scale = QCheckBox("Auto scale waveform")
        self.chk_auto_scale.setChecked(bool(self.app_settings["auto_scale"]))
        self.spin_line_width = QDoubleSpinBox()
        self.spin_line_width.setRange(1, 6)
        self.spin_line_width.setDecimals(0)
        self.spin_line_width.setValue(float(self.app_settings["line_width"]))
        waveform_form.addRow(self.chk_show_grid)
        waveform_form.addRow(self.chk_auto_scale)
        waveform_form.addRow("Line width:", self.spin_line_width)
        settings_layout.addWidget(waveform_group)

        self.btn_restore_app_defaults = QPushButton("Restore application defaults")
        self.lbl_settings_saved = QLabel("Settings are saved automatically.")
        self.lbl_settings_saved.setWordWrap(True)
        settings_layout.addWidget(self.btn_restore_app_defaults)
        settings_layout.addWidget(self.lbl_settings_saved)
        settings_layout.addStretch()
        self.ctrl_tabs.addTab(self.make_scrollable(settings_widget), "Settings")

        self.combo_language.currentIndexChanged.connect(self.change_language)
        self.combo_theme.currentIndexChanged.connect(self.change_theme)
        self.chk_show_grid.toggled.connect(self.update_plot_preferences)
        self.chk_auto_scale.toggled.connect(self.update_plot_preferences)
        self.spin_line_width.valueChanged.connect(self.update_plot_preferences)
        self.btn_restore_app_defaults.clicked.connect(self.restore_app_defaults)

        left_panel.addWidget(self.ctrl_tabs)
        main_layout.addWidget(self.left_panel_widget, stretch=1)
        
        # --- RIGHT PANEL: Plots ---
        self.view_tabs = QTabWidget()
        
        # VIEW TAB 1: OSCILLOSCOPE MONITOR
        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        detail_toolbar = QHBoxLayout()
        detail_toolbar.addStretch()
        self.btn_detail_view = QPushButton("Detail View")
        self.btn_detail_view.setProperty("i18n_source", "Detail View")
        self.btn_detail_view.setToolTip("Hide controls and expand the waveform")
        self.btn_detail_view.clicked.connect(self.toggle_detail_view)
        detail_toolbar.addWidget(self.btn_detail_view)
        tab1_layout.addLayout(detail_toolbar)
        self.plot_osc = pg.PlotWidget(title="Time Domain Waveform (Double-click to Maximize)")
        self.plot_osc.showGrid(x=True, y=True); self.plot_osc.addLegend()
        self.plot_osc.setLabel('left', 'Voltage', 'V'); self.plot_osc.setLabel('bottom', 'Time', 's')
        self.curve_ch1 = self.plot_osc.plot(pen=pg.mkPen(self.ch1_color, width=2), name="CH1 (Vin)")
        self.curve_ch2 = self.plot_osc.plot(pen=pg.mkPen(self.ch2_color, width=2), name="CH2 (Vout)")
        self.curve_ch1.setDownsampling(auto=True, method="peak")
        self.curve_ch2.setDownsampling(auto=True, method="peak")
        self.curve_ch1.setClipToView(True)
        self.curve_ch2.setClipToView(True)
        tab1_layout.addWidget(self.plot_osc)
        self.view_tabs.addTab(tab1, "Oscilloscope Monitor")
        
        self.plot_osc.setProperty("is_maximized", False)
        self.plot_osc.scene().sigMouseClicked.connect(
            lambda evt: self.toggle_detail_view() if evt.double() else None
        )
        
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

        # VIEW TAB 3: CHANNEL AND DUT MEASUREMENTS
        measurement_tab = QWidget()
        measurement_layout = QVBoxLayout(measurement_tab)
        self.channel_metric_names = [
            "Vmax", "Vmin", "Vpp", "Vpeak", "Vrms AC", "Vmean Offset",
            "Frequency", "Period", "Noise RMS", "Clipping / Saturation",
        ]
        self.channel_table = QTableWidget(len(self.channel_metric_names), 3)
        self.channel_table.setHorizontalHeaderLabels(["Metric", "CH1 Vin", "CH2 Vout"])
        self.channel_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.channel_table.verticalHeader().setVisible(False)
        for row, name in enumerate(self.channel_metric_names):
            self.channel_table.setItem(row, 0, QTableWidgetItem(name))
            self.channel_table.setItem(row, 1, QTableWidgetItem("N/A"))
            self.channel_table.setItem(row, 2, QTableWidgetItem("N/A"))
        channel_group = QGroupBox("Channel Measurement")
        channel_group_layout = QVBoxLayout(channel_group)
        channel_group_layout.addWidget(self.channel_table)
        measurement_layout.addWidget(channel_group)

        self.dut_metric_names = [
            "Gain linear", "Gain dB", "Target gain dB", "Gain error dB",
            "Gain tolerance", "Phase shift", "Delay", "Communication",
            "Result / Reasons",
        ]
        self.dut_table = QTableWidget(len(self.dut_metric_names), 2)
        self.dut_table.setHorizontalHeaderLabels(["DUT Metric", "Value"])
        self.dut_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dut_table.verticalHeader().setVisible(False)
        for row, name in enumerate(self.dut_metric_names):
            self.dut_table.setItem(row, 0, QTableWidgetItem(name))
            self.dut_table.setItem(row, 1, QTableWidgetItem("N/A"))
        dut_group = QGroupBox("DUT Analysis")
        dut_group_layout = QVBoxLayout(dut_group)
        dut_group_layout.addWidget(self.dut_table)
        measurement_layout.addWidget(dut_group)
        self.view_tabs.addTab(measurement_tab, "Measurements")

        main_layout.addWidget(self.view_tabs, stretch=3)
        self.all_plots = [self.plot_osc, self.plot_bode_gain, self.plot_bode_phase]
        self.i18n_tabs = [
            (self.ctrl_tabs, 0, "Analyzer"),
            (self.ctrl_tabs, 1, "Bode"),
            (self.ctrl_tabs, 2, "Calibration"),
            (self.ctrl_tabs, 3, "Oscilloscope"),
            (self.ctrl_tabs, 4, "Settings"),
            (self.view_tabs, 0, "Oscilloscope Monitor"),
            (self.view_tabs, 1, "Frequency Sweep (Bode)"),
            (self.view_tabs, 2, "Measurements"),
        ]
        
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
    def apply_device_config(self, show_message=True):
        if not self.serial_conn or not self.serial_conn.is_open:
            if show_message:
                QMessageBox.information(self, self.tr("Simulation Mode"), self.tr("No device connected. Settings applied to Simulator."))
            return True
            
        wave_str = self.ana_combo_wave.currentText()
        freq = int(self.ana_spin_freq.value())
        amp_mv = int(self.ana_spin_amp.value() * 1000)
        offset_mv = int(self.ana_spin_offset.value() * 1000)
        dac_gain = "X1" if self.ana_combo_gain.currentIndex() == 0 else "X2"
        fs = int(self.ana_spin_fs.value())
        samples = int(self.ana_combo_samples.currentText())

        # Match the firmware's biased unipolar MCP4822 output validation.
        excursion_mv = 0 if wave_str == "DC" else amp_mv
        dac_min_mv = 1650 + offset_mv - excursion_mv
        dac_max_mv = 1650 + offset_mv + excursion_mv
        dac_limit_mv = 2047.5 if dac_gain == "X1" else 4095.0
        if dac_min_mv < 0 or dac_max_mv > dac_limit_mv:
            self.last_command_response = (
                f"LOCAL_DAC_RANGE: {dac_min_mv:.1f}..{dac_max_mv:.1f} mV, "
                f"allowed 0..{dac_limit_mv:.1f} mV for {dac_gain}"
            )
            if show_message:
                QMessageBox.critical(
                    self,
                    self.tr("Error"),
                    f"{self.tr('Device configuration failed.')}\n"
                    f"{self.last_command_response}",
                )
            return False

        cmd = f"CONFIG:WAVE={wave_str},FREQ={freq},AMP_MV={amp_mv},OFFSET_MV={offset_mv},DAC_GAIN={dac_gain},FS={fs},SAMPLES={samples}\n"
        if self.serial_send_cmd(cmd):
            if show_message:
                QMessageBox.information(self, self.tr("Success"), self.tr("Configuration applied successfully to device!"))
            return True
        if show_message:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                f"{self.tr('Device configuration failed.')}\n"
                f"Device response: {self.last_command_response}",
            )
        return False

    def apply_range_config(self, show_message=False):
        selected_range = self.ana_combo_range.currentData()
        if selected_range not in ("0.3V", "3.3V", "10V"):
            return False

        if self.serial_conn and self.serial_conn.is_open:
            if not self.serial_send_cmd(f"SET_RANGE:{selected_range}\n"):
                if show_message:
                    QMessageBox.critical(
                        self,
                        self.tr("Error"),
                        f"{self.tr('Failed to configure the ADC input range.')}\n"
                        f"Device response: {self.last_command_response}",
                    )
                return False
            self.refresh_range_status()
        else:
            self.lbl_range_status.setText(f"MANUAL / {selected_range}")

        self.app_settings["adc_input_range"] = selected_range
        self.save_app_settings()
        if show_message:
            QMessageBox.information(
                self,
                self.tr("Success"),
                f"ADC/DUT input range: {selected_range}",
            )
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
                self.serial_conn.flush()
                res = self.serial_conn.readline().decode(
                    'utf-8', errors='replace').strip()
                self.last_command_response = res or "TIMEOUT"
                if res == "OK":
                    return True
                else:
                    print("Error response:", ascii(res))
            except Exception as e:
                self.last_command_response = f"SERIAL_ERROR:{e}"
                print("Serial send error:", ascii(str(e)))
        else:
            self.last_command_response = "PORT_CLOSED"
        return False
        
    def serial_query(self, cmd):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write(cmd.encode('utf-8'))
                res = self.serial_conn.readline().decode('utf-8').strip()
                time.sleep(0.01)
                return res
            except Exception as e:
                print(f"Serial query error: {e}")
        return ""

    def stop_device_safely(self):
        """Stop ADC USB first, then DAC, and discard stale binary frames."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return
        old_timeout = self.serial_conn.timeout
        try:
            self.serial_conn.write(b"ADC_STREAM_STOP\n")
            self.serial_conn.flush()
            self.serial_conn.timeout = 0.05
            deadline = time.monotonic() + 0.3
            drained = bytearray()
            while time.monotonic() < deadline:
                chunk = self.serial_conn.read(256)
                if chunk:
                    drained.extend(chunk)
                    if drained.endswith(b"OK\n"):
                        break
            self.serial_conn.timeout = old_timeout
            self.serial_conn.reset_input_buffer()
        except Exception:
            self.serial_conn.timeout = old_timeout
        self.serial_send_cmd("STOP\n")
        try:
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()
        except Exception:
            pass

    # --- TOGGLE SERIAL CONNECTION ---
    def toggle_connection(self):
        port = self.combo_ports.currentText()
        if port == "SIMULATE":
            if self.capture_worker and self.capture_worker.isRunning():
                QMessageBox.warning(self, self.tr("Busy"), self.tr("Wait for the current capture to finish before disconnecting."))
                return
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.serial_conn = None
            self.lbl_conn_status.setText(self.tr("Status: Disconnected (SIMULATION)"))
            self.lbl_conn_status.setStyleSheet("color: #ffaa00; font-weight: bold;")
            self.btn_connect.setText(self.tr("Connect"))
            self.btn_connect.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
            return
            
        if self.serial_conn and self.serial_conn.is_open:
            # Disconnect
            if self.capture_worker and self.capture_worker.isRunning():
                QMessageBox.warning(self, self.tr("Busy"), self.tr("Wait for the current capture to finish before disconnecting."))
                return
            self.stop_device_safely()
            self.serial_conn.close()
            self.serial_conn = None
            self.lbl_conn_status.setText(self.tr("Status: Disconnected (SIMULATION)"))
            self.lbl_conn_status.setStyleSheet("color: #ffaa00; font-weight: bold;")
            self.btn_connect.setText(self.tr("Connect"))
            self.btn_connect.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        else:
            # Connect
            try:
                # GPIO-clock ADS7861 bring-up can take ~1.7 s for 512 samples.
                self.serial_conn = serial.Serial(port, 115200, timeout=5.0)
                configure_serial_driver_buffers(self.serial_conn)
                time.sleep(0.25)
                self.serial_conn.reset_input_buffer()
                res = ""
                for _ in range(3):
                    self.serial_conn.write(b"PING\n")
                    self.serial_conn.flush()
                    res = self.serial_conn.readline().decode('utf-8').strip()
                    if res == "OK":
                        break
                    time.sleep(0.1)
                if res == "OK":
                    info = self.serial_query("INFO\n")
                    self.device_info = info or "STM32F103 USB CDC"
                    status_prefix = "Trạng thái: Đã kết nối" if self.language == "vi" else "Status: Connected"
                    self.lbl_conn_status.setText(f"{status_prefix} ({info})")
                    self.lbl_conn_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    self.btn_connect.setText(self.tr("Disconnect"))
                    self.btn_connect.setStyleSheet("background-color: #F44336; color: white; font-weight: bold;")
                    # Restore the user's manual DUT input range independently
                    # from every DAC stimulus setting.
                    self.apply_range_config(show_message=False)
                else:
                    self.serial_conn.close()
                    self.serial_conn = None
                    QMessageBox.critical(self, self.tr("Error"), self.tr("Connected device did not reply properly to PING."))
            except Exception as e:
                if self.serial_conn:
                    try:
                        self.serial_conn.close()
                    except Exception:
                        pass
                self.serial_conn = None
                QMessageBox.critical(self, "Error", f"Failed to connect to port {port}.\nDetails: {e}")

    # --- MATH FORMULAS FOR SAMPLING ISSUES ---
    def update_error_metrics(self, fs_override=None):
        fs = (float(fs_override) if fs_override is not None
              else self.ana_spin_fs.value())
        f_sig = self.ana_spin_freq.value()
        quality = calculate_sampling_quality(f_sig, fs)
        self.last_sampling_quality = quality
        self.lbl_period.setText(f"{quality.period_us:.2f} µs")
        self.lbl_sample_interval.setText(f"{quality.sample_interval_us:.2f} µs")
        self.lbl_samples_cycle.setText(f"{quality.samples_per_cycle:.2f}")
        self.lbl_peak_err.setText(f"{quality.peak_sampling_error_pct:.3f} %")
        self.lbl_zoh_droop.setText(f"{quality.zoh_droop_pct:.3f} %")
        self.lbl_settling_time.setText(f"{quality.dac_settling_time_us:.2f} µs")
        self.lbl_settling_margin.setText(f"{quality.settling_margin_us:+.2f} µs")
        self.lbl_measurement_quality.setText(self.tr(quality.summary))
        color = "#4CAF50" if quality.status == "OK" else "#FFB300"
        self.lbl_measurement_quality.setStyleSheet(f"color: {color}; font-weight: bold;")
        margin_color = "#FF5252" if quality.settling_margin_us < 0 else (
            "#FFB300" if quality.settling_margin_us < 1.0 else "#4CAF50"
        )
        self.lbl_settling_margin.setStyleSheet(f"color: {margin_color}; font-weight: bold;")

    # --- APPLICATION SETTINGS / INTERNATIONALIZATION ---
    def retranslate_ui(self):
        translatable_types = (QLabel, QPushButton, QCheckBox)
        for widget_type in translatable_types:
            for widget in self.findChildren(widget_type):
                source = widget.property("i18n_source")
                if not source and widget.text() in VI_TRANSLATIONS:
                    source = widget.text()
                    widget.setProperty("i18n_source", source)
                if source:
                    widget.setText(self.tr(source))

        for group in self.findChildren(QGroupBox):
            source = group.property("i18n_source")
            if not source and group.title() in VI_TRANSLATIONS:
                source = group.title()
                group.setProperty("i18n_source", source)
            if source:
                group.setTitle(self.tr(source))

        for tabs, index, source in self.i18n_tabs:
            tabs.setTabText(index, self.tr(source))

        self.combo_theme.blockSignals(True)
        self.combo_theme.setItemText(0, self.tr("Dark"))
        self.combo_theme.setItemText(1, self.tr("Light"))
        self.combo_theme.blockSignals(False)

        self.channel_table.setHorizontalHeaderLabels([
            self.tr("Metric"), "CH1 Vin", "CH2 Vout"
        ])
        for row, source in enumerate(self.channel_metric_names):
            self.channel_table.setItem(row, 0, QTableWidgetItem(self.tr(source)))
        self.dut_table.setHorizontalHeaderLabels([self.tr("DUT Metric"), self.tr("Value")])
        for row, source in enumerate(self.dut_metric_names):
            self.dut_table.setItem(row, 0, QTableWidgetItem(self.tr(source)))

        self.plot_osc.setTitle(self.tr("Time Domain Waveform (Double-click to Maximize)"))
        self.plot_osc.setLabel('left', self.tr("Voltage"), 'V')
        self.plot_osc.setLabel('bottom', self.tr("Time"), 's')
        self.plot_bode_gain.setTitle(self.tr("Bode Plot: Magnitude (Double-click to Maximize)"))
        self.plot_bode_gain.setLabel('left', self.tr("Gain"), 'dB')
        self.plot_bode_gain.setLabel('bottom', self.tr("Frequency"), 'Hz')
        self.plot_bode_phase.setTitle(self.tr("Bode Plot: Phase (Double-click to Maximize)"))
        self.plot_bode_phase.setLabel('left', self.tr("Phase"), 'Deg')
        self.plot_bode_phase.setLabel('bottom', self.tr("Frequency"), 'Hz')

        if self.live_timer.isActive():
            if self.current_live_mode == 'ANALYZER':
                self.btn_ana_live.setText(self.tr("STOP Test"))
            else:
                self.btn_osc_live.setText(self.tr("STOP Passive Oscillo"))
        else:
            self.btn_ana_live.setText(self.tr("Start Test"))
            self.btn_osc_live.setText(self.tr("Start Passive Oscillo (RX Only)"))

        if self.serial_conn and self.serial_conn.is_open:
            self.btn_connect.setText(self.tr("Disconnect"))
            status_prefix = "Trạng thái: Đã kết nối" if self.language == "vi" else "Status: Connected"
            self.lbl_conn_status.setText(f"{status_prefix} ({self.device_info})")
        else:
            self.btn_connect.setText(self.tr("Connect"))
            self.lbl_conn_status.setText(self.tr("Status: Disconnected (SIMULATION)"))
        self.set_calibration_status(self.calibration_status)
        self.update_error_metrics()

    def change_language(self, _index=None):
        language = self.combo_language.currentData()
        if language not in ("en", "vi"):
            return
        self.language = language
        self.app_settings["language"] = language
        self.save_app_settings()
        self.retranslate_ui()

    def change_theme(self, _index=None):
        theme = self.combo_theme.currentData()
        if theme not in ("dark", "light"):
            return
        self.app_settings["theme"] = theme
        self.is_dark_theme = theme == "dark"
        self.apply_visual_settings()

    def update_plot_preferences(self, _value=None):
        self.app_settings["show_grid"] = self.chk_show_grid.isChecked()
        self.app_settings["auto_scale"] = self.chk_auto_scale.isChecked()
        self.app_settings["line_width"] = int(self.spin_line_width.value())
        self.apply_visual_settings()

    def apply_visual_settings(self, save=True):
        self.is_dark_theme = self.app_settings["theme"] == "dark"
        QApplication.instance().setStyleSheet(
            DARK_STYLESHEET if self.is_dark_theme else LIGHT_STYLESHEET
        )
        bg_color, fg_color = ('#101010', '#E8E8E8') if self.is_dark_theme else ('#FFFFFF', '#202124')
        show_grid = bool(self.app_settings["show_grid"])
        for plot in self.all_plots:
            plot.setBackground(bg_color)
            plot.showGrid(x=show_grid, y=show_grid, alpha=0.3)
            plot.getAxis('bottom').setPen(fg_color)
            plot.getAxis('bottom').setTextPen(fg_color)
            plot.getAxis('left').setPen(fg_color)
            plot.getAxis('left').setTextPen(fg_color)

        width = int(self.app_settings["line_width"])
        self.curve_ch1.setPen(pg.mkPen(color=self.ch1_color, width=width))
        self.curve_ch2.setPen(pg.mkPen(color=self.ch2_color, width=width))
        self.update_color_button_styles()
        if self.app_settings["auto_scale"]:
            self.plot_osc.enableAutoRange(x=True, y=True)
        else:
            self.plot_osc.disableAutoRange()
        if save:
            self.save_app_settings()

    def update_color_button_styles(self):
        for button, color_value in (
            (self.btn_col_ch1, self.ch1_color),
            (self.btn_col_ch2, self.ch2_color),
        ):
            color = QColor(color_value)
            text_color = 'white' if color.lightness() < 128 else 'black'
            button.setStyleSheet(
                f"background-color: {color_value}; color: {text_color}; "
                "font-weight: bold; min-height: 30px;"
            )

    def restore_app_defaults(self):
        self.app_settings = DEFAULT_APP_SETTINGS.copy()
        self.language = self.app_settings["language"]
        self.ch1_color = self.app_settings["ch1_color"]
        self.ch2_color = self.app_settings["ch2_color"]
        for widget in (
            self.combo_language, self.combo_theme, self.chk_show_grid,
            self.chk_auto_scale, self.spin_line_width,
        ):
            widget.blockSignals(True)
        self.combo_language.setCurrentIndex(self.combo_language.findData(self.language))
        self.combo_theme.setCurrentIndex(self.combo_theme.findData(self.app_settings["theme"]))
        self.ana_combo_range.setCurrentIndex(
            self.ana_combo_range.findData(self.app_settings["adc_input_range"])
        )
        self.chk_show_grid.setChecked(self.app_settings["show_grid"])
        self.chk_auto_scale.setChecked(self.app_settings["auto_scale"])
        self.spin_line_width.setValue(self.app_settings["line_width"])
        for widget in (
            self.combo_language, self.combo_theme, self.chk_show_grid,
            self.chk_auto_scale, self.spin_line_width,
        ):
            widget.blockSignals(False)
        self.apply_visual_settings()
        self.retranslate_ui()

    def change_channel_color(self, channel):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            if channel == 1:
                self.ch1_color = hex_color
                self.app_settings["ch1_color"] = hex_color
            else:
                self.ch2_color = hex_color
                self.app_settings["ch2_color"] = hex_color
            self.apply_visual_settings()

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

    def toggle_detail_view(self):
        """Expand the main waveform and always leave an explicit back button."""
        self.detail_view_active = not self.detail_view_active
        self.left_panel_widget.setVisible(not self.detail_view_active)
        self.view_tabs.tabBar().setVisible(not self.detail_view_active)
        source = "Back to Controls" if self.detail_view_active else "Detail View"
        self.btn_detail_view.setProperty("i18n_source", source)
        self.btn_detail_view.setText(self.tr(source))
        QTimer.singleShot(0, self.plot_osc.autoRange)

    def toggle_live(self, mode):
        if self.live_timer.isActive():
            self.live_timer.stop()
            if self.capture_worker and self.capture_worker.isRunning():
                self.pending_device_stop = True
                if isinstance(self.capture_worker, LiveStreamWorker):
                    self.capture_worker.request_stop()
            elif self.serial_conn and self.serial_conn.is_open:
                self.stop_device_safely()
            self.btn_ana_live.setText(self.tr("Start Test"))
            self.btn_ana_live.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; height: 35px;")
            self.btn_osc_live.setText(self.tr("Start Passive Oscillo (RX Only)"))
            self.btn_osc_live.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; height: 35px;")
            for index in range(self.ctrl_tabs.count()):
                self.ctrl_tabs.setTabEnabled(index, True)
            self.lbl_pf_status.setText(self.tr("STATUS: IDLE"))
            self.lbl_pf_status.setStyleSheet("font-size: 16px; font-weight: bold; color: gray; qproperty-alignment: AlignCenter;")
        else:
            self.current_live_mode = mode
            self.view_tabs.setCurrentIndex(0)
            
            if self.serial_conn and self.serial_conn.is_open:
                # Show and configure the end-to-end rate proven by sequence
                # soak testing; 200 kSPS is not supported by this F103 path.
                self.ana_spin_fs.setValue(float(LiveStreamWorker.STREAM_FS))
                if not self.apply_device_config(show_message=False):
                    QMessageBox.critical(
                        self,
                        self.tr("Error"),
                        f"{self.tr('Device configuration failed.')}\n"
                        f"Device response: {self.last_command_response}",
                    )
                    return
                self.warmup_live_analysis()
            self.reset_hardware_history()
            self.pending_device_stop = False
            self.last_communication_ok = True
            self.last_data_complete = True
            self.live_timer.start(50)
            
            if mode == 'ANALYZER':
                self.btn_ana_live.setText(self.tr("STOP Test"))
                self.btn_ana_live.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; height: 35px;")
                self.ctrl_tabs.setTabEnabled(1, False)
                self.ctrl_tabs.setTabEnabled(2, False)
                self.ctrl_tabs.setTabEnabled(3, False)
            else:
                self.btn_osc_live.setText(self.tr("STOP Passive Oscillo"))
                self.btn_osc_live.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; height: 35px;")
                self.ctrl_tabs.setTabEnabled(0, False)
                self.ctrl_tabs.setTabEnabled(1, False)
                self.ctrl_tabs.setTabEnabled(2, False)

    # --- PROCESS REALTIME SERIAL / SIMULATOR DATA ---
    def process_live_data(self):
        if self._closing:
            return
        self.process_pending_hardware_captures()
        if self.capture_worker is not None or self.streaming_port is not None:
            return
        if self.serial_conn and self.serial_conn.is_open:
            port = self.serial_conn.port
            self.serial_conn.close()
            self.serial_conn = None
            self.streaming_port = port
            worker = LiveStreamWorker(port)
            self.capture_worker = worker
            worker.capture_ready.connect(self.handle_hardware_capture)
            worker.capture_error.connect(self.handle_capture_error)
            worker.capture_warning.connect(self.handle_capture_warning)
            worker.finished.connect(self.capture_finished)
            worker.start(QThread.Priority.TimeCriticalPriority)

        else:
            # SIMULATION MODE fallback
            if self.current_live_mode == 'ANALYZER':
                freq = self.ana_spin_freq.value()
                fs = self.ana_spin_fs.value()
                sample_count = int(self.ana_combo_samples.currentText())
                t, ch1, ch2 = generate_configured_signals(
                    freq, self.ana_spin_amp.value(), self.ana_spin_offset.value(),
                    fs, sample_count, time_offset=self.time_counter,
                )
                self.time_counter += sample_count / fs
                self.handle_samples(t, ch1, ch2)
                
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

    def capture_finished(self):
        worker = self.sender()
        if self.capture_worker is worker:
            self.capture_worker = None
        if worker is not None:
            worker.deleteLater()
        self.restore_serial_after_stream()
        if (not self._closing and self.pending_device_stop and
                self.serial_conn and self.serial_conn.is_open):
            self.pending_device_stop = False
            self.stop_device_safely()

    def restore_serial_after_stream(self):
        if self.streaming_port is None:
            return
        port = self.streaming_port
        last_error = None
        for _ in range(10):
            try:
                self.serial_conn = serial.Serial(
                    port, 115200, timeout=5.0, write_timeout=1.0
                )
                configure_serial_driver_buffers(self.serial_conn)
                time.sleep(0.1)
                self.serial_conn.reset_input_buffer()
                self.streaming_port = None
                return
            except Exception as exc:
                last_error = exc
                self.serial_conn = None
                time.sleep(0.1)
        if not self._closing:
            self.handle_capture_error(f"Cannot reopen {port}: {last_error}")

    def handle_capture_error(self, message):
        if self._closing:
            return
        self.live_timer.stop()
        self.last_communication_ok = False
        self.last_data_complete = False
        self.last_communication_error = message
        self.pending_device_stop = True
        self.lbl_conn_status.setText(f"Stream error: {message}")
        self.lbl_conn_status.setStyleSheet(
            "color: #FF5252; font-weight: bold;"
        )
        self.btn_ana_live.setText(self.tr("Start Test"))
        self.btn_osc_live.setText(self.tr("Start Passive Oscillo (RX Only)"))
        for index in range(self.ctrl_tabs.count()):
            self.ctrl_tabs.setTabEnabled(index, True)
        self.lbl_pf_status.setText(
            "TRẠNG THÁI: LỖI / TRUYỀN THÔNG"
            if self.language == "vi" else "STATUS: FAIL / COMMUNICATION"
        )
        self.lbl_pf_status.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #FF5252; "
            "qproperty-alignment: AlignCenter;"
        )
        self.dut_table.setItem(7, 1, QTableWidgetItem(f"ERROR: {message}"))

    def handle_capture_warning(self, message):
        if self._closing:
            return
        self.last_data_complete = False
        self.last_communication_error = message
        self.lbl_conn_status.setText(f"Stream warning: {message}")
        self.lbl_conn_status.setStyleSheet(
            "color: #FFB300; font-weight: bold;"
        )

    def active_range_index(self, device_result=None):
        if device_result and "range" in device_result:
            return max(0, min(2, int(device_result["range"])))
        text = self.lbl_range_status.text()
        if "0.3V" in text:
            return 0
        if "3.3V" in text:
            return 1
        return 2

    def calibration_value(self, key, fallback):
        try:
            return float(self.calibration_fields[key].text())
        except (KeyError, ValueError):
            return fallback

    def reset_hardware_history(self):
        """Start a new contiguous sample-time display without stale captures."""
        self.hardware_history.clear()
        self.pending_hardware_captures.clear()
        self.hardware_history_cursor_s = 0.0
        now = time.monotonic()
        self.last_history_plot_at = now
        self.last_metrics_update_at = now
        self.last_raw_ch1 = np.array([])
        self.last_raw_ch2 = np.array([])
        self.last_raw_time = np.array([])

    def warmup_live_analysis(self):
        """Pay one-time SciPy/FFT cold-start cost before USB streaming."""
        if self.analysis_warmed:
            return
        fs = float(LiveStreamWorker.STREAM_FS)
        frequency = max(1.0, float(self.ana_spin_freq.value()))
        count = 4096
        t = np.arange(count, dtype=np.float64) / fs
        samples = np.sin(2.0 * np.pi * frequency * t)
        raw = np.full(count, 2048, dtype=np.uint16)
        analyze_channel(samples, fs, frequency, raw)
        analyze_channel(samples * 0.5, fs, frequency, raw)
        self.analysis_warmed = True

    def append_hardware_history(self, local_t, ch1, ch2, duration_s=None):
        """Append finite blocks on one contiguous sample-time rolling axis.

        The display intentionally compresses command/USB idle gaps. DSP remains
        based on the newest original contiguous block in handle_samples().
        """
        local_t = np.asarray(local_t, dtype=np.float64)
        ch1 = np.asarray(ch1, dtype=np.float64)
        ch2 = np.asarray(ch2, dtype=np.float64)
        if local_t.size == 0:
            return
        sample_interval = (float(local_t[1] - local_t[0])
                           if local_t.size > 1 else 0.0)
        block_start = self.hardware_history_cursor_s
        absolute_t = local_t + block_start
        self.hardware_history.append((absolute_t, ch1.copy(), ch2.copy()))
        if duration_s is None:
            self.hardware_history_cursor_s = float(absolute_t[-1]) + sample_interval
        else:
            self.hardware_history_cursor_s = block_start + float(duration_s)

        cutoff = self.hardware_history_cursor_s - self.history_window_s
        while (self.hardware_history and
               self.hardware_history[0][0][-1] < cutoff):
            self.hardware_history.popleft()

        if self.hardware_history and self.hardware_history[0][0][0] < cutoff:
            block_t, block_ch1, block_ch2 = self.hardware_history.popleft()
            keep = block_t >= cutoff
            self.hardware_history.appendleft(
                (block_t[keep], block_ch1[keep], block_ch2[keep]))

        now = time.monotonic()
        if now - self.last_history_plot_at < 0.2:
            return
        self.last_history_plot_at = now

        times = [entry[0] for entry in self.hardware_history]
        values1 = [entry[1] for entry in self.hardware_history]
        values2 = [entry[2] for entry in self.hardware_history]
        self.last_raw_time = np.concatenate(times) if times else np.array([])
        self.last_raw_ch1 = np.concatenate(values1) if values1 else np.array([])
        self.last_raw_ch2 = np.concatenate(values2) if values2 else np.array([])

        if times:
            plot_t = self.last_raw_time
            plot_ch1 = self.last_raw_ch1
            plot_ch2 = self.last_raw_ch2
            if plot_t.size > PLOT_MAX_POINTS:
                display_indices = downsample_extrema_indices(
                    (plot_ch1, plot_ch2), PLOT_MAX_POINTS
                )
                plot_t = plot_t[display_indices]
                plot_ch1 = plot_ch1[display_indices]
                plot_ch2 = plot_ch2[display_indices]
            self.curve_ch1.setData(plot_t, plot_ch1)
            self.curve_ch2.setData(plot_t, plot_ch2)
            if self.chk_follow_stream.isChecked():
                right = max(0.1, self.hardware_history_cursor_s)
                window = min(self.history_window_s,
                             float(self.spin_view_window.value()))
                left = max(0.0, right - window)
                self.plot_osc.setXRange(left, right, padding=0.0)

    def handle_hardware_capture(self, capture):
        """Qt signal slot: enqueue only so the serial reader never waits."""
        self.pending_hardware_captures.append(capture)

    def process_pending_hardware_captures(self):
        if not self.pending_hardware_captures:
            return
        captures = []
        while self.pending_hardware_captures:
            captures.append(self.pending_hardware_captures.popleft())
        for capture in captures:
            self.append_raw_capture_history(capture)
        now = time.monotonic()
        if now - self.last_metrics_update_at >= 0.2:
            self.last_metrics_update_at = now
            self.consume_hardware_capture(captures[-1], append_history=False)

    def append_raw_capture_history(self, capture):
        device_result = capture.get("device_result") or {}
        fs = float(device_result.get("fs_actual", self.ana_spin_fs.value()))
        if fs <= 0.0:
            fs = float(self.ana_spin_fs.value())
        ch1_raw = np.asarray(capture["ch1_raw"])
        ch2_raw = np.asarray(capture["ch2_raw"])
        count = ch1_raw.size
        if count == 0:
            return
        target_points = 256
        if count > target_points:
            indices = downsample_extrema_indices(
                (ch1_raw, ch2_raw), target_points
            )
            ch1_raw = ch1_raw[indices]
            ch2_raw = ch2_raw[indices]
        else:
            indices = np.arange(count, dtype=np.int64)
        range_index = self.active_range_index(device_result)
        ch1, ch2 = convert_measurement_channels(
            ch1_raw,
            ch2_raw,
            self.calibration_value("adc1_r0_m", 1.0),
            self.calibration_value("adc1_r0_c", 0.0),
            self.calibration_value(f"adc2_r{range_index}_m", 1.0),
            self.calibration_value(f"adc2_r{range_index}_c", 0.0),
        )
        self.append_hardware_history(
            indices / fs, ch1, ch2, duration_s=count / fs
        )

    def consume_hardware_capture(self, capture, append_history=True):
        device_result = capture.get("device_result") or {}
        if "range_name" in device_result and "range_mode" in device_result:
            self.lbl_range_status.setText(
                f"{device_result['range_mode']} / {device_result['range_name']}"
            )
        range_index = self.active_range_index(device_result)
        ch1_raw = capture["ch1_raw"]
        ch2_raw = capture["ch2_raw"]
        # ADS B0/Vin is wired directly and never passes through the x10/x100
        # output-range relays. It must always use ADC1 range-0 calibration.
        ch1, ch2 = convert_measurement_channels(
            ch1_raw,
            ch2_raw,
            self.calibration_value("adc1_r0_m", 1.0),
            self.calibration_value("adc1_r0_c", 0.0),
            self.calibration_value(f"adc2_r{range_index}_m", 1.0),
            self.calibration_value(f"adc2_r{range_index}_c", 0.0),
        )
        fs = float(device_result.get("fs_actual", self.ana_spin_fs.value()))
        if fs <= 0.0:
            fs = self.ana_spin_fs.value()
        t = np.arange(ch1.size, dtype=np.float64) / fs
        self.last_communication_ok = True
        self.last_data_complete = True
        self.last_communication_error = ""
        streaming = bool(capture.get("streaming"))
        self.handle_samples(t, ch1, ch2, ch1_raw, ch2_raw,
                            update_plot=not streaming)
        if append_history:
            self.append_hardware_history(t, ch1, ch2)

    def handle_samples(self, t, ch1, ch2, ch1_raw=None, ch2_raw=None,
                       update_plot=True):
        fs = (1.0 / (t[1] - t[0])) if len(t) > 1 else self.ana_spin_fs.value()
        target_frequency = self.ana_spin_freq.value()
        self.update_error_metrics(fs)
        ch1_metrics = analyze_channel(ch1, fs, target_frequency, ch1_raw)
        ch2_metrics = analyze_channel(ch2, fs, target_frequency, ch2_raw)
        dut = analyze_dut(
            ch1_metrics, ch2_metrics,
            self.spin_target_gain.value(), self.spin_tol_gain.value(),
            target_frequency,
        )
        evaluation = evaluate_pass_fail(
            self.last_sampling_quality, ch1_metrics, ch2_metrics, dut,
            target_frequency,
            frequency_tolerance_pct=self.spin_tol_freq.value(),
            target_amplitude_vpeak=self.ana_spin_amp.value(),
            amplitude_tolerance_pct=self.spin_tol_amp.value(),
            communication_ok=self.last_communication_ok,
            data_complete=self.last_data_complete,
        )
        self.last_ch1_metrics = ch1_metrics
        self.last_ch2_metrics = ch2_metrics
        self.last_dut_metrics = dut
        self.last_evaluation = evaluation
        if update_plot:
            self.last_raw_ch1 = np.asarray(ch1)
            self.last_raw_ch2 = np.asarray(ch2)
            self.last_raw_time = np.asarray(t)
            self.curve_ch1.setData(t, ch1)
            self.curve_ch2.setData(t, ch2)
        plot_title = "Dạng sóng theo thời gian" if self.language == "vi" else "Time Domain Waveform"
        clipping_text = " — CẢNH BÁO CLIPPING" if self.language == "vi" else " — CLIPPING WARNING"
        self.plot_osc.setTitle(
            plot_title + (clipping_text if ch1_metrics.clipping or ch2_metrics.clipping else "")
        )
        if dut.gain_db is not None:
            self.lbl_ana_gain.setText(f"{dut.gain_db:.2f} dB")
        self.lbl_ana_phase.setText(
            f"{dut.phase_shift_deg:.2f} °" if dut.phase_shift_deg is not None
            else self.tr("Not available")
        )
        status_colors = {"PASS": "#4CAF50", "WARNING": "#FFB300", "FAIL": "#FF5252"}
        status_prefix = "TRẠNG THÁI" if self.language == "vi" else "STATUS"
        self.lbl_pf_status.setText(f"{status_prefix}: {evaluation.status}")
        self.lbl_pf_status.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {status_colors[evaluation.status]}; "
            "qproperty-alignment: AlignCenter;"
        )
        self.update_measurement_tables()

    def format_optional(self, value, suffix="", digits=3):
        return self.tr("Not available") if value is None else f"{value:.{digits}f}{suffix}"

    def update_measurement_tables(self):
        c1, c2 = self.last_ch1_metrics, self.last_ch2_metrics
        if c1 is None or c2 is None:
            return
        rows = [
            (c1.vmax, c2.vmax, " V"), (c1.vmin, c2.vmin, " V"),
            (c1.vpp, c2.vpp, " V"), (c1.vpeak, c2.vpeak, " V"),
            (c1.vrms_ac, c2.vrms_ac, " V"), (c1.vmean, c2.vmean, " V"),
            (c1.frequency_hz, c2.frequency_hz, " Hz"),
            (c1.period_us, c2.period_us, " µs"),
            (c1.noise_rms, c2.noise_rms, " V"),
        ]
        for row, (value1, value2, suffix) in enumerate(rows):
            self.channel_table.setItem(row, 1, QTableWidgetItem(self.format_optional(value1, suffix)))
            self.channel_table.setItem(row, 2, QTableWidgetItem(self.format_optional(value2, suffix)))
        self.channel_table.setItem(9, 1, QTableWidgetItem(
            f"{'YES' if c1.clipping else 'No'} / {'SAT' if c1.saturation else 'No saturation'}"
        ))
        self.channel_table.setItem(9, 2, QTableWidgetItem(
            f"{'YES' if c2.clipping else 'No'} / {'SAT' if c2.saturation else 'No saturation'}"
        ))
        dut, evaluation = self.last_dut_metrics, self.last_evaluation
        values = [
            self.format_optional(dut.gain_linear, " x"),
            self.format_optional(dut.gain_db, " dB"),
            f"{dut.target_gain_db:.3f} dB",
            self.format_optional(dut.gain_error_db, " dB"),
            f"±{dut.gain_tolerance_db:.3f} dB",
            self.format_optional(dut.phase_shift_deg, " °"),
            self.format_optional(dut.delay_us, " µs"),
            "OK" if self.last_communication_ok else f"ERROR: {self.last_communication_error}",
            f"{evaluation.status}: {', '.join(evaluation.reasons)}",
        ]
        for row, value in enumerate(values):
            self.dut_table.setItem(row, 1, QTableWidgetItem(value))

    # --- SWEEP BODE ---
    def run_sweep(self):
        self.view_tabs.setCurrentIndex(1) 
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
    def set_calibration_status(self, status):
        self.calibration_status = status
        self.lbl_calib_status.setText(self.tr(status))
        colors = {
            "default": "#FFB74D",
            "loaded from device": "#4CAF50",
            "loaded from JSON": "#4CAF50",
            "saved to device": "#4CAF50",
            "modified but not saved": "#FF5252",
        }
        self.lbl_calib_status.setStyleSheet(
            f"color: {colors.get(status, '#FFB74D')}; font-weight: bold;"
        )

    def mark_calibration_modified(self, _text=""):
        self.set_calibration_status("modified but not saved")

    def calibration_dict(self):
        values = {}
        for key, field in self.calibration_fields.items():
            values[key] = float(field.text())
        return values

    def export_calibration_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Calibration", "calibration.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump({
                    "format": "signal-analyzer-calibration-v1",
                    "status": self.calibration_status,
                    "coefficients": self.calibration_dict(),
                }, file, indent=2)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, self.tr("Export Error"), str(exc))

    def import_calibration_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Calibration", "", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            coefficients = data.get("coefficients", data)
            missing = set(self.calibration_fields) - set(coefficients)
            if missing:
                raise ValueError(f"Missing calibration keys: {sorted(missing)}")
            for key, field in self.calibration_fields.items():
                field.setText(f"{float(coefficients[key]):.6f}")
            self.set_calibration_status("loaded from JSON")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, self.tr("Import Error"), str(exc))

    def read_calibration_from_device(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Device is not connected."))
            return
            
        res = self.serial_query("GET_CALIB\n")
        if res.startswith("DATA:"):
            params = res[5:].split(',')
            for p in params:
                kv = p.split('=')
                if len(kv) == 2:
                    k, v = kv[0], kv[1]
                    if k in self.calibration_fields:
                        self.calibration_fields[k].setText(v)
            self.set_calibration_status("loaded from device")
            QMessageBox.information(self, self.tr("Success"), self.tr("Calibration read successfully from hardware Flash!"))

    def write_calibration_to_device(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Device is not connected."))
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
            self.set_calibration_status("saved to device")
            QMessageBox.information(self, self.tr("Success"), self.tr("Calibration coefficients saved into hardware Flash!"))
        else:
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to save calibration coefficients to device."))

    def reset_calibration_device(self):
        if not self.serial_conn or not self.serial_conn.is_open:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Device is not connected."))
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
            self.set_calibration_status("default")
            QMessageBox.information(self, self.tr("Success"), self.tr("Calibration reset to defaults and saved to Flash."))

    # --- REPORT EXPORTS ---
    def export_report(self):
        if len(self.last_raw_ch1) == 0:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No raw wave data available to export. Run a live test first."))
            return
            
        try:
            timestamp = datetime.now(timezone.utc).astimezone().isoformat()
            csv_path = "amplifier_test_samples.csv"
            exported_paths = []
            if self.chk_export_raw.isChecked():
                with open(csv_path, mode='w', newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Time (s)", "CH1 Vin (V)", "CH2 Vout (V)"])
                    for i in range(len(self.last_raw_ch1)):
                        writer.writerow([self.last_raw_time[i], self.last_raw_ch1[i], self.last_raw_ch2[i]])
                exported_paths.append(csv_path)
            
            summary_path = "amplifier_test_summary.json"
            summary_data = {
                "tester": "PyQt6 Signal Analyzer Pro",
                "timestamp": timestamp,
                "device_info": self.device_info,
                "waveform_config": {
                    "waveform_type": self.ana_combo_wave.currentText(),
                    "target_frequency_hz": self.ana_spin_freq.value(),
                    "target_amplitude_vpeak": self.ana_spin_amp.value(),
                    "target_offset_v": self.ana_spin_offset.value(),
                    "dac_gain": "X1" if self.ana_combo_gain.currentIndex() == 0 else "X2",
                    "adc_input_range": self.lbl_range_status.text(),
                    "sample_rate_sps": self.ana_spin_fs.value(),
                    "capture_samples": int(self.ana_combo_samples.currentText()),
                },
                "sampling_quality": self.last_sampling_quality.to_dict() if self.last_sampling_quality else None,
                "ch1_metrics": self.last_ch1_metrics.to_dict() if self.last_ch1_metrics else None,
                "ch2_metrics": self.last_ch2_metrics.to_dict() if self.last_ch2_metrics else None,
                "dut_metrics": self.last_dut_metrics.to_dict() if self.last_dut_metrics else None,
                "evaluation": self.last_evaluation.to_dict() if self.last_evaluation else None,
                "communication": {
                    "ok": self.last_communication_ok,
                    "data_complete": self.last_data_complete,
                    "last_error": self.last_communication_error,
                },
                "calibration": {
                    "status": self.calibration_status,
                    "coefficients": self.calibration_dict(),
                },
            }
            if self.chk_export_raw.isChecked():
                summary_data["raw_samples"] = {
                    "time_s": self.last_raw_time.tolist(),
                    "ch1_v": self.last_raw_ch1.tolist(),
                    "ch2_v": self.last_raw_ch2.tolist(),
                }
            with open(summary_path, mode='w', encoding="utf-8") as fj:
                json.dump(summary_data, fj, indent=4)
            exported_paths.append(summary_path)
            QMessageBox.information(
                self, self.tr("Export Successful"),
                ("Đã lưu:\n" if self.language == "vi" else "Saved:\n")
                + "\n".join(exported_paths),
            )
        except Exception as e:
            message = (
                f"Không thể lưu báo cáo.\nChi tiết: {e}"
                if self.language == "vi" else f"Failed to save reports.\nDetails: {e}"
            )
            QMessageBox.critical(self, self.tr("Export Error"), message)

    def closeEvent(self, event):
        self._closing = True
        self.live_timer.stop()
        if self.capture_worker and self.capture_worker.isRunning():
            if isinstance(self.capture_worker, LiveStreamWorker):
                self.capture_worker.request_stop()
            else:
                try:
                    self.serial_conn.cancel_read()
                except (AttributeError, OSError):
                    pass
            # Serial timeout is 5 s; never destroy a running QThread.
            if not self.capture_worker.wait(6000):
                self._closing = False
                event.ignore()
                return
        self.restore_serial_after_stream()
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.stop_device_safely()
            except Exception:
                pass
            self.serial_conn.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = SignalAnalyzerApp()
    window.show()
    sys.exit(app.exec())
