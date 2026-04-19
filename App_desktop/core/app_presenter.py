"""
Module: app_presenter
Mục đích: MVP Presenter — kết nối View và Model, điều phối data flow từ SerialReader tới GUI
Sections:
  - IMPORTS
  - CLASS AppPresenter
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from PyQt6.QtCore import QObject, QTimer
from ui.main_window import MainWindow

# ===== CLASS AppPresenter =====
class AppPresenter(QObject):
    """Presenter trong MVP pattern — sẽ được implement đầy đủ ở Story 1.2, 1.3."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Khởi tạo View
        self._view = MainWindow()

    def show(self):
        """Hiển thị cửa sổ chính."""
        self._view.show()
