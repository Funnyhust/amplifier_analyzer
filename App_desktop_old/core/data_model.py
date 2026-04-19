"""
Module: data_model
Mục đích: Pre-allocated NumPy arrays, filter state (zi), calibration loader từ disk
Sections:
  - IMPORTS
  - CONSTANTS
  - CLASS DataModel
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import os
import json
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ===== CONSTANTS =====
CAL_FILE = os.path.join(os.getenv('APPDATA', ''), 'AplifierAnalyze', 'calibration.json')

# ===== CLASS DataModel =====
class DataModel:
    """
    Giữ trạng thái data: pre-allocated arrays, filter zi, calibration.
    Sẽ implement đầy đủ ở Story 2.3/4.3.
    """

    def __init__(self):
        # Calibration defaults — sẽ override khi load file
        self.dc_offset_mv: float = 0.0
        self.gain_correction: dict = {
            'range_x1': 1.0,
            'range_div10': 1.0,
            'range_div100': 1.0,
        }
        logger.debug("DataModel khởi tạo với calibration mặc định")
