"""
Module: config
Mục đích: Hằng số cấu hình toàn cục — protocol bytes, màu sắc UI, simulation flag
Sections:
  - IMPORTS
  - SIMULATION MODE
  - PROTOCOL CONSTANTS
  - UI COLORS (Catppuccin Mocha)
  - QUEUE SETTINGS
Tác giả: Truong pc
"""

# ===== SIMULATION MODE =====
SIMULATION_MODE: bool = True  # True = không cần phần cứng

# ===== PROTOCOL CONSTANTS =====
HEADER_BYTE_1 = 0xAA
HEADER_BYTE_2 = 0xBB

FRAME_TYPE_OSC_STREAM  = 0x01  # Streaming liên tục, decimated
FRAME_TYPE_BODE        = 0x02  # Một điểm dữ liệu Bode
FRAME_TYPE_OSC_CAPTURE = 0x03  # Single-shot capture toàn tốc

# Gain range mapping (từ firmware)
GAIN_RANGE_X1    = 0   # gain_factor = 1.0
GAIN_RANGE_DIV10  = 1   # gain_factor = 0.1
GAIN_RANGE_DIV100 = 2   # gain_factor = 0.01

# ===== UI COLORS (Catppuccin Mocha) =====
COLORS = {
    'background': '#1e1e2e',  # Crust/Base
    'surface':    '#313244',  # Surface0
    'text':       '#cdd6f4',  # Text
    'blue':       '#89b4fa',  # Blue (primary, CH1)
    'green':      '#a6e3a1',  # Green (secondary, CH2)
    'red':        '#f38ba8',  # Red (error/warning)
    'yellow':     '#f9e2af',  # Yellow (warning highlight)
}

# ===== QUEUE SETTINGS =====
QUEUE_MAX_SIZE = 32  # ~0.5s buffer @ 60 FPS trước khi drop oldest
