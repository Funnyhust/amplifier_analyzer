"""
=============================================================================
  ỨNG DỤNG ĐỌC DỮ LIỆU UART SERIAL - Python + PyQt6
=============================================================================
  Tác giả: AI Assistant
  Mô tả: Ứng dụng Desktop đơn giản để đọc dữ liệu từ cổng UART (Serial).
  
  CẤU TRÚC CODE GỒM 3 PHẦN CHÍNH:
    1. PHẦN GIAO DIỆN (UI Layout)  → Dòng 50-130
    2. PHẦN LOGIC (Functions)      → Dòng 135-250
    3. PHẦN KẾT NỐI (Signals)     → Dòng 115-125
=============================================================================
"""

# ==================== IMPORT THƯ VIỆN ====================
import sys
import serial                          # Thư viện giao tiếp Serial (pyserial)
import serial.tools.list_ports          # Liệt kê các cổng COM có sẵn
from datetime import datetime

from PyQt6.QtWidgets import (           # Các widget giao diện PyQt6
    QApplication,                       # Ứng dụng chính
    QMainWindow,                        # Cửa sổ chính
    QWidget,                            # Widget cơ sở
    QVBoxLayout,                        # Layout theo chiều dọc
    QHBoxLayout,                        # Layout theo chiều ngang
    QComboBox,                          # Hộp chọn (dropdown)
    QPushButton,                        # Nút nhấn
    QTextEdit,                          # Ô văn bản nhiều dòng
    QLabel,                             # Nhãn văn bản
    QGroupBox,                          # Khung nhóm
)
from PyQt6.QtCore import QTimer, Qt     # Timer và các hằng số
from PyQt6.QtGui import QFont, QColor, QTextCursor  # Font, màu sắc


# ==================== LỚP CỬA SỔ CHÍNH ====================
class SerialReaderApp(QMainWindow):
    """
    ┌─────────────────────────────────────────┐
    │  Đây là LỚP TẠO RA CỬA SỔ chính.      │
    │  Mọi thứ bạn thấy trên màn hình đều    │
    │  được định nghĩa bên trong lớp này.     │
    └─────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()

        # Biến lưu đối tượng serial (ban đầu chưa kết nối)
        self.serial_port = None

        # ===== GỌI HÀM TẠO GIAO DIỆN =====
        self.setup_ui()

        # ===== TẠO TIMER ĐỌC DỮ LIỆU =====
        # Timer sẽ tự động gọi hàm read_data() mỗi 100ms
        self.read_timer = QTimer()
        self.read_timer.timeout.connect(self.read_data)  # Kết nối: Timer hết giờ → gọi read_data()

        # ===== QUÉT CỔNG COM LẦN ĐẦU =====
        self.scan_ports()

    # ==========================================================================
    #  PHẦN 1: GIAO DIỆN (UI Layout)
    #  → Định nghĩa các nút bấm, ô văn bản nằm ở đâu trên cửa sổ
    # ==========================================================================
    def setup_ui(self):
        """Tạo toàn bộ giao diện người dùng."""

        # --- Thiết lập cửa sổ chính ---
        self.setWindowTitle("📡 Đọc Dữ Liệu UART Serial")
        self.setMinimumSize(650, 500)

        # Widget trung tâm (bắt buộc với QMainWindow)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout chính theo chiều dọc
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # ───────────────────────────────────────────
        #  KHUNG KẾT NỐI (Connection Group)
        # ───────────────────────────────────────────
        connection_group = QGroupBox("🔌 Kết nối Serial")
        connection_layout = QHBoxLayout()

        # Label "Cổng COM:"
        self.label_port = QLabel("Cổng COM:")
        connection_layout.addWidget(self.label_port)

        # ComboBox chọn cổng COM
        self.combo_ports = QComboBox()
        self.combo_ports.setMinimumWidth(200)
        self.combo_ports.setToolTip("Chọn cổng COM để kết nối")
        connection_layout.addWidget(self.combo_ports)

        # Nút Quét lại cổng
        self.btn_scan = QPushButton("🔄 Quét")
        self.btn_scan.setToolTip("Quét lại danh sách cổng COM")
        connection_layout.addWidget(self.btn_scan)

        # Nút Kết nối / Ngắt kết nối
        self.btn_connect = QPushButton("▶ Kết nối")
        self.btn_connect.setToolTip("Kết nối hoặc ngắt kết nối cổng Serial")
        connection_layout.addWidget(self.btn_connect)

        # ComboBox chọn Baudrate
        self.label_baud = QLabel("Baudrate:")
        connection_layout.addWidget(self.label_baud)

        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.combo_baud.setCurrentText("115200")  # Mặc định 115200
        connection_layout.addWidget(self.combo_baud)

        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)

        # ───────────────────────────────────────────
        #  KHUNG HIỂN THỊ DỮ LIỆU (Display Group)
        # ───────────────────────────────────────────
        display_group = QGroupBox("📋 Dữ liệu nhận được")
        display_layout = QVBoxLayout()

        # Ô văn bản hiển thị dữ liệu (chỉ đọc, không cho gõ vào)
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setFont(QFont("Consolas", 10))  # Font monospace dễ đọc
        self.text_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #a6e3a1;
                border: 1px solid #45475a;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        display_layout.addWidget(self.text_display)

        # Hàng nút bên dưới ô hiển thị
        button_layout = QHBoxLayout()

        # Label trạng thái
        self.label_status = QLabel("⚪ Chưa kết nối")
        self.label_status.setStyleSheet("color: #888; font-weight: bold;")
        button_layout.addWidget(self.label_status)

        button_layout.addStretch()  # Đẩy nút sang phải

        # Nút Xóa màn hình
        self.btn_clear = QPushButton("🗑 Xóa màn hình")
        self.btn_clear.setToolTip("Xóa toàn bộ dữ liệu hiển thị")
        button_layout.addWidget(self.btn_clear)

        display_layout.addLayout(button_layout)
        display_group.setLayout(display_layout)
        main_layout.addWidget(display_group)

        # ───────────────────────────────────────────
        #  PHẦN 3: KẾT NỐI SIGNALS & SLOTS
        #  → "Khi bấm nút này thì chạy hàm kia"
        # ───────────────────────────────────────────
        self.btn_scan.clicked.connect(self.scan_ports)         # Bấm Quét     → gọi scan_ports()
        self.btn_connect.clicked.connect(self.toggle_connect)  # Bấm Kết nối  → gọi toggle_connect()
        self.btn_clear.clicked.connect(self.clear_display)     # Bấm Xóa      → gọi clear_display()

        # ───────────────────────────────────────────
        #  ÁP DỤNG STYLESHEET CHO TOÀN BỘ ỨNG DỤNG
        # ───────────────────────────────────────────
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #ccc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2a5f9e;
            }
            QComboBox {
                padding: 5px 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 12px;
            }
            QLabel {
                font-size: 12px;
            }
        """)

    # ==========================================================================
    #  PHẦN 2: LOGIC (Functions) - Các hàm xử lý
    # ==========================================================================

    def scan_ports(self):
        """
        ┌─────────────────────────────────────────┐
        │  QUÉT CỔNG COM                          │
        │  Liệt kê tất cả cổng Serial có trên    │
        │  máy tính và đưa vào ComboBox.          │
        └─────────────────────────────────────────┘
        """
        self.combo_ports.clear()
        ports = serial.tools.list_ports.comports()
        if ports:
            for port in ports:
                # Hiển thị tên cổng + mô tả (ví dụ: "COM3 - USB Serial Device")
                self.combo_ports.addItem(f"{port.device} - {port.description}", port.device)
            self.log_message("🔍 Đã quét cổng COM. Tìm thấy: " + ", ".join([p.device for p in ports]))
        else:
            self.combo_ports.addItem("Không tìm thấy cổng COM")
            self.log_message("⚠️ Không tìm thấy cổng COM nào!")

    def toggle_connect(self):
        """
        ┌─────────────────────────────────────────┐
        │  KẾT NỐI / NGẮT KẾT NỐI               │
        │  Nếu đang ngắt → kết nối.               │
        │  Nếu đang kết nối → ngắt.               │
        └─────────────────────────────────────────┘
        """
        if self.serial_port is None or not self.serial_port.is_open:
            self.connect_serial()
        else:
            self.disconnect_serial()

    def connect_serial(self):
        """
        ┌─────────────────────────────────────────┐
        │  MỞ CỔNG SERIAL                         │
        │  Lấy tên cổng COM từ ComboBox, tạo      │
        │  đối tượng Serial và bắt đầu Timer      │
        │  để đọc dữ liệu mỗi 100ms.             │
        └─────────────────────────────────────────┘
        """
        # Lấy tên cổng COM từ ComboBox (dữ liệu ẩn - userData)
        port_name = self.combo_ports.currentData()
        if port_name is None:
            self.log_message("❌ Chưa chọn cổng COM!")
            return

        # Lấy baudrate từ ComboBox
        baudrate = int(self.combo_baud.currentText())

        try:
            # ★★★ DÒNG CODE MỞ CỔNG SERIAL ★★★
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                timeout=0.1         # Timeout đọc 100ms (không block)
            )

            # Bắt đầu Timer: đọc dữ liệu mỗi 100ms
            self.read_timer.start(100)

            # Cập nhật giao diện
            self.btn_connect.setText("⏹ Ngắt kết nối")
            self.btn_connect.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #c0392b; }
            """)
            self.label_status.setText(f"🟢 Đã kết nối: {port_name} @ {baudrate}")
            self.label_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.combo_ports.setEnabled(False)
            self.combo_baud.setEnabled(False)
            self.btn_scan.setEnabled(False)

            self.log_message(f"✅ Đã kết nối thành công: {port_name} @ {baudrate} baud")

        except serial.SerialException as e:
            self.log_message(f"❌ Lỗi kết nối: {str(e)}")
            self.serial_port = None

    def disconnect_serial(self):
        """
        ┌─────────────────────────────────────────┐
        │  ĐÓNG CỔNG SERIAL                       │
        │  Dừng Timer, đóng cổng, cập nhật UI.    │
        └─────────────────────────────────────────┘
        """
        # Dừng Timer
        self.read_timer.stop()

        # Đóng cổng Serial
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

        self.serial_port = None

        # Cập nhật giao diện về trạng thái ban đầu
        self.btn_connect.setText("▶ Kết nối")
        self.btn_connect.setStyleSheet("")  # Reset về style mặc định
        self.label_status.setText("⚪ Chưa kết nối")
        self.label_status.setStyleSheet("color: #888; font-weight: bold;")
        self.combo_ports.setEnabled(True)
        self.combo_baud.setEnabled(True)
        self.btn_scan.setEnabled(True)

        self.log_message("🔌 Đã ngắt kết nối.")

    def read_data(self):
        """
        ┌─────────────────────────────────────────────────────┐
        │  ★★★ DÒNG CODE XỬ LÝ VIỆC ĐỌC SERIAL ★★★         │
        │                                                     │
        │  Hàm này được QTimer gọi TỰ ĐỘNG mỗi 100ms.       │
        │  Nó kiểm tra xem có dữ liệu mới từ cổng Serial    │
        │  không, nếu có thì đọc ra và hiển thị lên màn hình.│
        └─────────────────────────────────────────────────────┘
        """
        if self.serial_port and self.serial_port.is_open:
            try:
                # Kiểm tra có bao nhiêu byte đang chờ đọc
                bytes_waiting = self.serial_port.in_waiting

                if bytes_waiting > 0:
                    # ★ ĐỌC DỮ LIỆU TỪ SERIAL ★
                    raw_data = self.serial_port.read(bytes_waiting)

                    # Chuyển bytes thành chuỗi text (UTF-8, bỏ qua lỗi mã hóa)
                    text_data = raw_data.decode('utf-8', errors='replace')

                    # Hiển thị dữ liệu lên ô văn bản
                    self.text_display.insertPlainText(text_data)

                    # Tự động cuộn xuống cuối
                    self.text_display.moveCursor(QTextCursor.MoveOperation.End)

            except serial.SerialException as e:
                self.log_message(f"❌ Lỗi đọc dữ liệu: {str(e)}")
                self.disconnect_serial()
            except Exception as e:
                self.log_message(f"⚠️ Lỗi không xác định: {str(e)}")

    def clear_display(self):
        """Xóa toàn bộ nội dung trong ô văn bản."""
        self.text_display.clear()
        self.log_message("🗑 Đã xóa màn hình.")

    def log_message(self, message):
        """Ghi một dòng thông báo hệ thống vào ô hiển thị (có kèm timestamp)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_display.append(f"[{timestamp}] {message}")
        self.text_display.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event):
        """
        Hàm này được gọi tự động khi người dùng đóng cửa sổ (bấm X).
        Đảm bảo cổng Serial được đóng an toàn trước khi thoát.
        """
        if self.serial_port and self.serial_port.is_open:
            self.read_timer.stop()
            self.serial_port.close()
        event.accept()


# ==============================================================================
#  PHẦN KHỞI CHẠY ỨNG DỤNG
#  → Đây là nơi Python bắt đầu chạy chương trình
# ==============================================================================
if __name__ == "__main__":
    # ★ TẠO ỨNG DỤNG (bắt buộc, chỉ cần 1 QApplication duy nhất)
    app = QApplication(sys.argv)

    # ★ TẠO CỬA SỔ CHÍNH → Dòng code này tạo ra cửa sổ bạn nhìn thấy
    window = SerialReaderApp()
    window.show()

    # ★ CHẠY VÒNG LẶP SỰ KIỆN (giữ cửa sổ mở cho đến khi người dùng đóng)
    sys.exit(app.exec())
