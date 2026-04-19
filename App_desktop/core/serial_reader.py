"""
Module: serial_reader
Mục đích: QThread đọc dữ liệu từ cổng serial thực hoặc tạo synthetic frames khi SIMULATION_MODE=True
Sections:
  - IMPORTS
  - CLASS SerialReader
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import queue
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from config import SIMULATION_MODE, QUEUE_MAX_SIZE

logger = logging.getLogger(__name__)

# ===== CLASS SerialReader =====
class SerialReader(QThread):
    """
    QThread quản lý việc đọc dữ liệu serial.
    Emit raw bytes qua signal — KHÔNG giả thiết frame structure ở đây.
    Sẽ implement đầy đủ ở Story 1.3.
    """
    data_received = pyqtSignal(bytes)  # Emitted mỗi khi có raw bytes

    def __init__(self, parent=None):
        super().__init__(parent)
        # Queue bounded — sẽ dùng trong Story 1.3
        self.data_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX_SIZE)
        self._running = False

    def run(self):
        """Vòng lặp chính của thread — stub, sẽ implement ở Story 1.3."""
        self._running = True
        logger.debug("SerialReader thread bắt đầu (stub)")
        while self._running:
            self.msleep(16)  # Chờ, avoid busy loop

    def stop(self):
        """Dừng thread an toàn."""
        self._running = False
        self.wait()
