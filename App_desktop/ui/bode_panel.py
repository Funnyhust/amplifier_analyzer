"""
Module: bode_panel
Mục đích: Panel Bode Plot — Magnitude + Phase plots, sweep controls. Passive View.
Sections:
  - IMPORTS
  - CLASS BodePanel
Tác giả: Truong pc
"""

# ===== IMPORTS =====
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QLabel

# ===== CLASS BodePanel =====
class BodePanel(QGroupBox):
    """Panel Bode Plot — sẽ implement đầy đủ ở Story 1.2."""

    def __init__(self, parent=None):
        super().__init__("Bode Plot", parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Bode Panel — stub"))
