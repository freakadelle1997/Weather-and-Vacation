# style_utils.py
from __future__ import annotations
from typing import Tuple, Optional
from PyQt6 import QtCore, QtGui, QtWidgets

def mac_default_font():
    return QtGui.QFont(".AppleSystemUIFont", 13)

# --------- Light/Dark-Erkennung ---------
def _is_dark_palette() -> bool:
    app = QtWidgets.QApplication.instance()
    pal = app.palette() if app else QtGui.QPalette()
    bg = pal.color(QtGui.QPalette.ColorRole.Window)
    # Luma nach Rec. 709
    luma = 0.2126 * bg.red() + 0.7152 * bg.green() + 0.0722 * bg.blue()
    return luma < 128

def style_line_edit(le: QtWidgets.QLineEdit):
    """Styling für Datumseingaben – passt sich an Light/Dark an und setzt
    sichtbare Text-/Placeholder-Farben."""
    le.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    if _is_dark_palette():
        # Dark Mode
        le.setStyleSheet("""
            QLineEdit {
                background: #1C1C1E;
                color: #F2F2F7;                 /* Helle Schrift */
                border: 1px solid #3A3A3C;
                border-radius: 10px;
                padding: 6px 12px;
                selection-background-color: #0A84FF;
                selection-color: #FFFFFF;
            }
            QLineEdit:focus {
                border: 1px solid #0A84FF;
            }
            QLineEdit::placeholder {
                color: #8E8E93;                 /* Hellgrau (macOS-like) */
            }
        """)
    else:
        # Light Mode
        le.setStyleSheet("""
            QLineEdit {
                background: #FBFBFD;
                color: #111111;                 /* Dunkle Schrift */
                border: 1px solid #DADADA;
                border-radius: 10px;
                padding: 6px 12px;
                selection-background-color: #0A84FF;
                selection-color: #FFFFFF;
            }
            QLineEdit:focus {
                border: 1px solid #0A84FF;
            }
            QLineEdit::placeholder {
                color: #8E8E93;                 /* Hellgrau (macOS-like) */
            }
        """)

def autosize_columns(view: QtWidgets.QTableView):
    header = view.horizontalHeader()
    header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
    view.resizeColumnsToContents()
    header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(False)

def gradient_for_temp(temp_c: Optional[float]) -> Tuple[str, str, str]:
    """
    Liefert (c1, c2, border) als Farb-Strings je Temperatur.
    Kalt → Blautöne, mild → violett, warm → orange/rot.
    """
    if temp_c is None:
        return ("#F5F5F7", "#FFFFFF", "#E5E5EA")
    t = max(-10.0, min(35.0, float(temp_c)))
    if t <= 0:
        return ("#D6E4FF", "#EAF2FF", "#B3D1FF")
    elif t <= 10:
        return ("#E3D4FF", "#F2E9FF", "#D2BFFF")
    elif t <= 20:
        return ("#FFE9CC", "#FFF2E0", "#FFD6A6")
    elif t <= 28:
        return ("#FFD1B3", "#FFE0CC", "#FFBC8A")
    else:
        return ("#FFC2B8", "#FFD6D1", "#FFA89C")