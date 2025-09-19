# style_utils.py
from __future__ import annotations
from typing import Tuple, Optional
from PyQt6 import QtCore, QtGui, QtWidgets

def mac_default_font():
    return QtGui.QFont(".AppleSystemUIFont", 13)

def style_line_edit(le: QtWidgets.QLineEdit):
    # <- HIER war der Fehler: QtWidgets.Qt → QtCore.Qt
    le.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    le.setMinimumWidth(140)
    le.setFont(mac_default_font())
    le.setStyleSheet("""
        QLineEdit {
            border: 1px solid #DADADA;
            border-radius: 10px;
            padding: 6px 12px;
            background: #FBFBFD;
            color: #111111;
            selection-background-color: #0A84FF;
            selection-color: #FFFFFF;
        }
        QLineEdit:focus { border: 1px solid #0A84FF; }
    """)

def autosize_columns(view: QtWidgets.QTableView):
    header = view.horizontalHeader()
    header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
    view.resizeColumnsToContents()
    header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(False)

# ---- Farb-Logik (Gradient je Temperatur) ----

def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)

def _mix_with_white(hex_color: str, factor: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return _rgb_to_hex((r, g, b))

def _base_color_for_temp(temp: Optional[float]) -> str:
    if temp is None:
        return "#6E6E73"
    t = float(temp)
    if t <= 0:   return "#0A84FF"
    if t <= 10:  return "#32ADE6"
    if t <= 20:  return "#34C759"
    if t <= 25:  return "#FF9F0A"
    return "#FF453A"

def gradient_for_temp(temp: Optional[float]) -> tuple[str, str, str]:
    base = _base_color_for_temp(temp)
    start = _mix_with_white(base, 0.75)
    end   = _mix_with_white(base, 0.55)
    border = _mix_with_white(base, 0.35)
    return start, end, border