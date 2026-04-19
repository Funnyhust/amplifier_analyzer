"""
Module: frame_parser
Mục đích: State machine phân tích binary frame từ raw byte stream (HUNT→HEADER→PAYLOAD→CRC)
Sections:
  - IMPORTS
  - PARSEDFRAME NAMEDTUPLE
  - CLASS FrameParser
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from collections import namedtuple
from PyQt6.QtCore import QObject, pyqtSignal

# ===== PARSEDFRAME NAMEDTUPLE =====
ParsedFrame = namedtuple('ParsedFrame', [
    'frame_type',   # int: 0x01=OSC_STREAM, 0x02=BODE, 0x03=OSC_CAPTURE
    'payload',      # bytes: raw payload chưa decode
    'gain_factor',  # float: auto-range gain factor (0→1.0, 1→0.1, 2→0.01)
    'timestamp_ms', # int: thời điểm nhận frame (ms từ đầu ngày)
])

# ===== CLASS FrameParser =====
class FrameParser(QObject):
    """
    Phân tích byte stream thành ParsedFrame namedtuples.
    Sẽ implement đầy đủ ở Story 2.1 với 4-state machine + 5 edge cases.
    """
    frame_complete = pyqtSignal(object)  # Emit ParsedFrame khi đủ 1 frame

    def __init__(self, parent=None):
        super().__init__(parent)

    def feed(self, data: bytes):
        """Nhận raw bytes, xử lý qua state machine. Stub — sẽ implement ở Story 2.1."""
        pass
