"""
Module: main_window
Mục đích: QMainWindow — passive View, chỉ layout và expose signals. Không có business logic.
Sections:
  - IMPORTS
  - CLASS MainWindow
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from config import COLORS

# ===== CLASS MainWindow =====
class MainWindow(QMainWindow):
    """
    Cửa sổ chính của ứng dụng.
    Passive View trong MVP pattern — giao tiếp với Presenter qua Signal-Slot.
    Sẽ hoàn thiện layout ở Story 1.2.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aplifier Analyze")
        self.resize(1200, 800)
        self._setup_ui()

    def _setup_ui(self):
        """Thiết lập layout cơ bản — sẽ bổ sung panels ở Story 1.2."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        # Placeholder — Story 1.2 sẽ thêm OscPanel và BodePanel
