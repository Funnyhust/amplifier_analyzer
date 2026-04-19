"""
Module: main
Mục đích: Entry point của ứng dụng Aplifier Analyze — khởi tạo QApplication và AppPresenter
Sections:
  - IMPORTS
  - MAIN ENTRY POINT
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import sys
import logging
from PyQt6.QtWidgets import QApplication
from core.app_presenter import AppPresenter

# ===== MAIN ENTRY POINT =====
def main():
    # Khởi tạo Qt application
    app = QApplication(sys.argv)
    presenter = AppPresenter()
    presenter.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
