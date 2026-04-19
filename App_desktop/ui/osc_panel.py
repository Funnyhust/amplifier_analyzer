"""
Module: osc_panel
Mục đích: Panel Oscilloscope — controls và plot area. Passive View.
Sections:
  - IMPORTS
  - CLASS OscPanel
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel

# ===== CLASS OscPanel =====
class OscPanel(QGroupBox):
    """Panel Oscilloscope — sẽ implement đầy đủ ở Story 1.2."""

    def __init__(self, parent=None):
        super().__init__("Oscilloscope", parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Oscilloscope Panel — stub"))
