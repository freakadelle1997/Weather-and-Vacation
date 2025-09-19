# region_card.py
from __future__ import annotations
from typing import List, Optional
from PyQt6 import QtCore, QtGui, QtWidgets
from style_utils import mac_default_font, gradient_for_temp

class RegionCard(QtWidgets.QFrame):
    def __init__(self, region: str, states: List[str],
                 temp_mean: Optional[float], precip_sum: Optional[float],
                 stations_day_max: int, stations_total: int, parent=None):
        super().__init__(parent)
        self.setObjectName("RegionCard")
        c1, c2, c_border = gradient_for_temp(temp_mean)
        self.setStyleSheet(f"""
            QFrame#RegionCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c1}, stop:1 {c2});
                border: 1px solid {c_border};
                border-radius: 14px;
            }}
            QLabel[cls="title"] {{ color:#1C1C1E; font-weight:700; }}
            QLabel[cls="line"]  {{ color:#0E1116; }}
        """)
        main = QtWidgets.QHBoxLayout(self)
        main.setContentsMargins(16, 14, 16, 14); main.setSpacing(18)

        left = QtWidgets.QVBoxLayout(); left.setSpacing(6)
        right = QtWidgets.QVBoxLayout(); right.setSpacing(6)

        title = QtWidgets.QLabel(region); title.setProperty("cls", "title"); title.setFont(mac_default_font())
        left.addWidget(title)

        big_text = "—" if temp_mean is None else f"{float(temp_mean):.1f} °C"
        big = QtWidgets.QLabel(big_text)
        big.setFont(mac_default_font())
        big.setStyleSheet("font-size:26px; font-weight:800; color:#0E1116;")
        left.addWidget(big)

        if precip_sum is None or float(precip_sum) <= 0.0:
            sub_text = "Σ Niederschlag: —"; sub_style = "color:#3A3A3C;"
        else:
            sub_text = f"Σ Niederschlag: {float(precip_sum):.2f} mm"; sub_style = "color:#0A84FF; font-weight:600;"
        sub = QtWidgets.QLabel(sub_text); sub.setStyleSheet(sub_style); sub.setFont(mac_default_font())
        left.addWidget(sub)

        line1 = QtWidgets.QLabel(f"max. Stationsanzahl/Tag: {int(stations_day_max or 0)}")
        line1.setProperty("cls", "line"); line1.setFont(mac_default_font()); left.addWidget(line1)
        line2 = QtWidgets.QLabel(f"berücksichtigte Stationen: {int(stations_total or 0)}")
        line2.setProperty("cls", "line"); line2.setFont(mac_default_font()); left.addWidget(line2)
        left.addStretch(1)

        bl_text = "\n".join(states) if states else "—"
        bl_list = QtWidgets.QLabel(bl_text)
        bl_list.setFont(mac_default_font())
        bl_list.setStyleSheet("color:#6E6E73;")
        bl_list.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignRight)
        bl_list.setWordWrap(True)
        right.addWidget(bl_list, 1)

        main.addLayout(left, 2); main.addLayout(right, 1)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18); shadow.setOffset(0, 3); shadow.setColor(QtGui.QColor(0,0,0,30))
        self.setGraphicsEffect(shadow)
