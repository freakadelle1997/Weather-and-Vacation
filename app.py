# app.py
from __future__ import annotations
import sys
from PyQt6 import QtWidgets
from main_window import MainWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Wetterdaten")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()