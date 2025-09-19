# app.py
from __future__ import annotations
import sys, os
from PyQt6 import QtWidgets
from single_instance import acquire_single_instance_lock
from logging_excepthook import install_excepthook
from main_window import MainWindow

def main():
    lock_fd = acquire_single_instance_lock()
    if lock_fd is None:
        return

    install_excepthook()
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("DWD Regions")
    w = MainWindow()
    w.show()
    code = app.exec()

    try:
        os.close(lock_fd)
    except Exception:
        pass
    sys.exit(code)

if __name__ == "__main__":
    main()
