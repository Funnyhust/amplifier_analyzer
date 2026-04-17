"""
=============================================================================
  ỨNG DỤNG VẼ ĐỒ THỊ SÓNG SINE THỜI GIAN THỰC
  Python 3 + PyQt6 + PyQtGraph + NumPy
=============================================================================
  CẤU TRÚC CODE GỒM 3 PHẦN CHÍNH:
    1. PHẦN GIAO DIỆN (UI Layout)       → setup_ui()
    2. PHẦN LOGIC (Functions)            → update_plot(), tính toán sóng sine
    3. PHẦN KẾT NỐI (Signals & Slots)   → Slider thay đổi → cập nhật giá trị
                                           QTimer timeout  → vẽ lại đồ thị
=============================================================================
"""

# ==================== IMPORT THƯ VIỆN ====================
import sys
import numpy as np                      # Thư viện tính toán mảng số học

from PyQt6.QtWidgets import (
    QApplication,                       # Ứng dụng chính
    QMainWindow,                        # Cửa sổ chính
    QWidget,                            # Widget cơ sở
    QVBoxLayout,                        # Layout dọc
    QHBoxLayout,                        # Layout ngang
    QSlider,                            # Thanh trượt
    QLabel,                             # Nhãn văn bản
    QGroupBox,                          # Khung nhóm
)
from PyQt6.QtCore import QTimer, Qt     # Timer và hằng số
from PyQt6.QtGui import QFont

import pyqtgraph as pg                  # Thư viện vẽ đồ thị tốc độ cao


# ==================== LỚP CỬA SỔ CHÍNH ====================
class SineWaveApp(QMainWindow):
    """
    ┌─────────────────────────────────────────┐
    │  Đây là LỚP TẠO RA CỬA SỔ chính.      │
    │  Gồm: Đồ thị + 2 thanh trượt          │
    │  (Tần số & Biên độ)                     │
    └─────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()

        # ===== BIẾN TRẠNG THÁI =====
        self.frequency = 1.0        # Tần số mặc định: 1 Hz
        self.amplitude = 1.0        # Biên độ mặc định: 1.0
        self.phase_offset = 0.0     # Pha dịch chuyển (tạo hiệu ứng sóng chạy)

        # ===== TẠO GIAO DIỆN =====
        self.setup_ui()

        # ===== TẠO TIMER CẬP NHẬT ĐỒ THỊ =====
        # ┌──────────────────────────────────────────────────────┐
        # │  QTimer hoạt động như một "đồng hồ báo thức lặp lại"│
        # │  Mỗi 30ms, nó phát tín hiệu timeout.               │
        # │  Ta kết nối tín hiệu đó với hàm update_plot().      │
        # │  → Kết quả: hàm update_plot() được gọi 33 lần/giây │
        # │    (≈ 33 FPS), tạo hiệu ứng sóng chạy mượt mà.    │
        # └──────────────────────────────────────────────────────┘
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)  # Timer hết giờ → gọi update_plot()
        self.timer.start(30)                          # Bắt đầu: lặp mỗi 30ms

    # ==========================================================================
    #  PHẦN 1: GIAO DIỆN (UI Layout)
    # ==========================================================================
    def setup_ui(self):
        """Tạo toàn bộ giao diện người dùng."""

        # --- Cửa sổ chính ---
        self.setWindowTitle("🌊 Đồ Thị Sóng Sine Thời Gian Thực")
        self.setMinimumSize(900, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ───────────────────────────────────────────
        #  VÙNG ĐỒ THỊ (PyQtGraph PlotWidget)
        # ───────────────────────────────────────────
        # PyQtGraph sử dụng OpenGL → vẽ đồ thị cực nhanh,
        # phù hợp cho hiển thị thời gian thực.
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e2e')       # Màu nền tối
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)  # Lưới mờ
        self.plot_widget.setLabel('left', 'Biên độ (Amplitude)')
        self.plot_widget.setLabel('bottom', 'Thời gian (s)')
        self.plot_widget.setTitle('Sóng Sine: y = A · sin(2π · f · t)', color='#cdd6f4', size='14pt')
        self.plot_widget.setYRange(-5.5, 5.5)           # Cố định trục Y
        self.plot_widget.setXRange(0, 4)                 # Hiển thị 4 giây

        # Tạo đường cong (curve) để vẽ sóng
        pen = pg.mkPen(color='#89b4fa', width=2.5)      # Bút vẽ: màu xanh, dày 2.5px
        self.curve = self.plot_widget.plot(pen=pen)

        main_layout.addWidget(self.plot_widget, stretch=3)  # Đồ thị chiếm 3 phần

        # ───────────────────────────────────────────
        #  KHUNG ĐIỀU KHIỂN (Control Panel)
        # ───────────────────────────────────────────
        control_group = QGroupBox("🎛 Điều chỉnh thông số")
        control_layout = QVBoxLayout()

        # --- Thanh trượt TẦN SỐ ---
        freq_layout = QHBoxLayout()

        freq_label = QLabel("📶 Tần số (Hz):")
        freq_label.setMinimumWidth(120)
        freq_layout.addWidget(freq_label)

        self.slider_freq = QSlider(Qt.Orientation.Horizontal)
        self.slider_freq.setMinimum(1)       # Min: 0.1 Hz (chia 10)
        self.slider_freq.setMaximum(100)     # Max: 10.0 Hz (chia 10)
        self.slider_freq.setValue(10)        # Mặc định: 1.0 Hz
        self.slider_freq.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_freq.setTickInterval(10)
        freq_layout.addWidget(self.slider_freq, stretch=1)

        self.label_freq_value = QLabel("1.0 Hz")
        self.label_freq_value.setMinimumWidth(80)
        self.label_freq_value.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.label_freq_value.setStyleSheet("color: #f9e2af;")
        freq_layout.addWidget(self.label_freq_value)

        control_layout.addLayout(freq_layout)

        # --- Thanh trượt BIÊN ĐỘ ---
        amp_layout = QHBoxLayout()

        amp_label = QLabel("📊 Biên độ:")
        amp_label.setMinimumWidth(120)
        amp_layout.addWidget(amp_label)

        self.slider_amp = QSlider(Qt.Orientation.Horizontal)
        self.slider_amp.setMinimum(1)        # Min: 0.1 (chia 10)
        self.slider_amp.setMaximum(50)       # Max: 5.0 (chia 10)
        self.slider_amp.setValue(10)         # Mặc định: 1.0
        self.slider_amp.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_amp.setTickInterval(5)
        amp_layout.addWidget(self.slider_amp, stretch=1)

        self.label_amp_value = QLabel("1.0")
        self.label_amp_value.setMinimumWidth(80)
        self.label_amp_value.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.label_amp_value.setStyleSheet("color: #a6e3a1;")
        amp_layout.addWidget(self.label_amp_value)

        control_layout.addLayout(amp_layout)

        # --- Công thức hiển thị ---
        self.label_formula = QLabel("y = 1.0 · sin(2π · 1.0 · t)")
        self.label_formula.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_formula.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        self.label_formula.setStyleSheet("color: #89b4fa; padding: 5px;")
        control_layout.addWidget(self.label_formula)

        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group, stretch=1)  # Điều khiển chiếm 1 phần

        # ───────────────────────────────────────────
        #  PHẦN 3: KẾT NỐI SIGNALS & SLOTS
        #  → "Khi kéo thanh trượt thì cập nhật giá trị"
        # ───────────────────────────────────────────
        self.slider_freq.valueChanged.connect(self.on_freq_changed)   # Kéo slider tần số → cập nhật
        self.slider_amp.valueChanged.connect(self.on_amp_changed)     # Kéo slider biên độ → cập nhật

        # ───────────────────────────────────────────
        #  STYLESHEET
        # ───────────────────────────────────────────
        self.setStyleSheet("""
            QMainWindow {
                background-color: #313244;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #cdd6f4;
                border: 2px solid #45475a;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #1e1e2e;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QLabel {
                font-size: 12px;
                color: #cdd6f4;
            }
            QSlider::groove:horizontal {
                border: 1px solid #45475a;
                height: 8px;
                background: #313244;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #89b4fa;
                border: 2px solid #74c7ec;
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #74c7ec;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #89b4fa, stop:1 #74c7ec);
                border-radius: 4px;
            }
        """)

    # ==========================================================================
    #  PHẦN 2: LOGIC (Functions)
    # ==========================================================================

    def on_freq_changed(self, value):
        """Khi thanh trượt Tần số thay đổi."""
        self.frequency = value / 10.0  # Chia 10 để có giá trị thập phân
        self.label_freq_value.setText(f"{self.frequency:.1f} Hz")
        self.update_formula_label()

    def on_amp_changed(self, value):
        """Khi thanh trượt Biên độ thay đổi."""
        self.amplitude = value / 10.0
        self.label_amp_value.setText(f"{self.amplitude:.1f}")
        self.update_formula_label()

    def update_formula_label(self):
        """Cập nhật nhãn công thức hiển thị."""
        self.label_formula.setText(
            f"y = {self.amplitude:.1f} · sin(2π · {self.frequency:.1f} · t)"
        )

    def update_plot(self):
        """
        ┌─────────────────────────────────────────────────────────┐
        │  ★★★ HÀM VẼ ĐỒ THỊ - Được QTimer gọi mỗi 30ms ★★★  │
        │                                                         │
        │  Cách hoạt động:                                        │
        │  1. Tạo mảng thời gian t = [0, 0.001, 0.002, ..., 4]  │
        │  2. Tính y = A · sin(2π · f · t + phase)               │
        │  3. Tăng phase_offset để sóng "chạy" sang trái         │
        │  4. Cập nhật dữ liệu lên đường cong (curve)            │
        │                                                         │
        │  QTimer gọi hàm này 33 lần/giây → sóng chạy mượt mà!  │
        └─────────────────────────────────────────────────────────┘
        """
        # Bước 1: Tạo mảng thời gian (4000 điểm trong 4 giây)
        t = np.linspace(0, 4, 4000)

        # Bước 2: Tính sóng Sine với công thức y = A · sin(2π · f · t + phase)
        y = self.amplitude * np.sin(2 * np.pi * self.frequency * t + self.phase_offset)

        # Bước 3: Tăng pha để sóng "chạy" (dịch sang trái mỗi frame)
        self.phase_offset += 0.1

        # Bước 4: Cập nhật dữ liệu lên đồ thị
        self.curve.setData(t, y)


# ==============================================================================
#  PHẦN KHỞI CHẠY ỨNG DỤNG
# ==============================================================================
if __name__ == "__main__":
    # ★ TẠO ỨNG DỤNG
    app = QApplication(sys.argv)

    # ★ TẠO CỬA SỔ CHÍNH → Dòng code này tạo ra cửa sổ
    window = SineWaveApp()
    window.show()

    # ★ CHẠY VÒNG LẶP SỰ KIỆN
    sys.exit(app.exec())
