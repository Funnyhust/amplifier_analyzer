"""
Module: frame_parser
Mục đích: State machine phân tích binary frame từ raw byte stream (HUNT→TYPE→LEN→PAYLOAD→CRC)
Sections:
  - IMPORTS
  - PARSEDFRAME NAMEDTUPLE
  - CLASS FrameParser
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import logging
from collections import namedtuple
from PyQt6.QtCore import QObject, pyqtSignal
from config import HEADER_BYTE_1, HEADER_BYTE_2, PROTOCOL_HEADER_SIZE, PROTOCOL_CRC_SIZE

logger = logging.getLogger(__name__)

# ===== PARSEDFRAME NAMEDTUPLE =====
ParsedFrame = namedtuple('ParsedFrame', [
    'frame_type',   # 0x01, 0x02, 0x03
    'payload',      # raw bytes
])

# ===== CLASS FrameParser =====
class FrameParser(QObject):
    """
    Bộ phân tích gói tin sử dụng State Machine.
    Giúp xử lý stream dữ liệu liên tục không bị mất đồng bộ.
    """
    frame_complete = pyqtSignal(object)  # Phát ra ParsedFrame khi nhận đủ

    STATE_HUNT_1 = 0    # Tìm 0xAA
    STATE_HUNT_2 = 1    # Tìm 0xBB
    STATE_TYPE   = 2    # Đọc loại frame
    STATE_LEN    = 3    # Đọc độ dài (2 bytes)
    STATE_DATA   = 4    # Đọc dữ liệu payload
    STATE_CRC    = 5    # Kiểm tra CRC

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = self.STATE_HUNT_1
        self._buffer = bytearray()
        
        self._curr_type = 0
        self._curr_len = 0
        self._payload = bytearray()
        self._len_bytes = bytearray()

    def feed(self, data: bytes):
        """Hàm nhận raw bytes từ SerialReader và đưa vào máy trạng thái."""
        for b in data:
            if self._state == self.STATE_HUNT_1:
                if b == HEADER_BYTE_1:
                    self._state = self.STATE_HUNT_2
                    
            elif self._state == self.STATE_HUNT_2:
                if b == HEADER_BYTE_2:
                    self._state = self.STATE_TYPE
                else:
                    self._state = self.STATE_HUNT_1 if b != HEADER_BYTE_1 else self.STATE_HUNT_2

            elif self._state == self.STATE_TYPE:
                self._curr_type = b
                self._len_bytes.clear()
                self._state = self.STATE_LEN

            elif self._state == self.STATE_LEN:
                self._len_bytes.append(b)
                if len(self._len_bytes) == 2:
                    # Chuyển 2 byte thành int (Big Endian hoặc Little Endian tùy firmware)
                    # Ở đây giả định Big Endian (MSB first)
                    self._curr_len = int.from_bytes(self._len_bytes, byteorder='big')
                    self._payload.clear()
                    if self._curr_len > 0:
                        self._state = self.STATE_DATA
                    else:
                        self._state = self.STATE_CRC

            elif self._state == self.STATE_DATA:
                self._payload.append(b)
                if len(self._payload) == self._curr_len:
                    self._state = self.STATE_CRC

            elif self._state == self.STATE_CRC:
                # TODO: Thực hiện kiểm tra checksum thực tế ở đây
                # Hiện tại tạm thời chấp nhận mọi CRC để test protocol
                frame = ParsedFrame(self._curr_type, bytes(self._payload))
                self.frame_complete.emit(frame)
                self._state = self.STATE_HUNT_1
