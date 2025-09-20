# region_card.py
from __future__ import annotations
from typing import List, Optional, Set
from PyQt6 import QtCore, QtGui, QtWidgets
from style_utils import mac_default_font
from color_config import color_for_temp_hex, load_config

COLOR_GREY = "#6E6E73"
COLOR_HOLIDAY = "#FF9500"
COLOR_VACATION = "#FF3B30"

def _fmt_pct_de(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:.1f}".replace(".", ",") + " %"

def _q(hex_str: str) -> QtGui.QColor:
    c = QtGui.QColor()
    c.setNamedColor(hex_str)
    return c

def _with_alpha(c: QtGui.QColor, a: int) -> QtGui.QColor:
    out = QtGui.QColor(c); out.setAlpha(max(0, min(255, a))); return out

def _mix(c1: QtGui.QColor, c2: QtGui.QColor, t: float) -> QtGui.QColor:
    t = max(0.0, min(1.0, t))
    return QtGui.QColor(
        int(round(c1.red()*(1-t)+c2.red()*t)),
        int(round(c1.green()*(1-t)+c2.green()*t)),
        int(round(c1.blue()*(1-t)+c2.blue()*t)),
    )

def _lighten(c: QtGui.QColor, factor: float = 0.25) -> QtGui.QColor:
    return _mix(c, QtGui.QColor(255, 255, 255), factor)


class RegionCard(QtWidgets.QFrame):
    """Karte zeichnet (Gradient + Sparkline) im paintEvent und respektiert Farbeingaben aus settings.json."""
    def __init__(
        self,
        region: str,
        states: List[str],
        temp_mean: Optional[float],
        precip_sum: Optional[float],
        stations_day_max: int,
        stations_total: int,
        population_share_pct: Optional[float] = None,
        vacation_states: Optional[Set[str]] = None,
        holiday_states: Optional[Set[str]] = None,
        spark_values: Optional[List[float]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("RegionCard")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)

        # Daten
        self.region = region
        self.states = states
        self.temp_mean = float(temp_mean) if temp_mean is not None else None
        self.precip_sum = float(precip_sum) if precip_sum is not None else None
        self.stations_day_max = int(stations_day_max or 0)
        self.stations_total = int(stations_total or 0)
        self.population_share_pct = population_share_pct
        self.vacation_states = set(vacation_states or set())
        self.holiday_states = set(holiday_states or set())
        self.spark_values: List[float] = [float(v) for v in (spark_values or []) if v is not None]

        # Farben aus Config
        cfg = load_config()
        base_hex = color_for_temp_hex(self.temp_mean, cfg)
        self.base_bottom = _q(base_hex)                     # Kartenfarbe unten
        self.base_top = _lighten(self.base_bottom, 0.25)    # oben heller
        self.border_color = self.base_bottom.darker(115)

        # Sparkline in gleicher Farbe, „umgedrehter“ Verlauf, Linie etwas dunkler
        self.spark_line_color = self.base_bottom.darker(130)
        self.spark_fill_top = _with_alpha(self.base_bottom.darker(140), 170)  # oben dunkler/kräftig
        self.spark_fill_mid = _with_alpha(self.base_bottom, 90)
        self.spark_fill_bot = _with_alpha(self.base_bottom, 25)               # unten transparent

        # Layout (Inhalte)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14); root.setSpacing(10)

        top = QtWidgets.QHBoxLayout(); top.setSpacing(18)

        left = QtWidgets.QVBoxLayout(); left.setSpacing(6)
        title = QtWidgets.QLabel(region); title.setProperty("cls", "title"); title.setFont(mac_default_font())
        left.addWidget(title)

        big_text = "—" if self.temp_mean is None else f"{self.temp_mean:.1f} °C"
        big = QtWidgets.QLabel(big_text)
        big.setFont(mac_default_font())
        big.setStyleSheet("font-size:26px; font-weight:800; color:#FFFFFF;")
        left.addWidget(big)

        if self.precip_sum is None or float(self.precip_sum) <= 0.0:
            sub_text = "Σ Niederschlag: —"
            sub_style = "color:#FFFFFF;"
        else:
            sub_text = f"Σ Niederschlag: {self.precip_sum:.2f} mm"
            sub_style = "color:#0A84FF; font-weight:600;"
        sub = QtWidgets.QLabel(sub_text); sub.setStyleSheet(sub_style); sub.setFont(mac_default_font())
        left.addWidget(sub)

        line1 = QtWidgets.QLabel(f"max. Stationsanzahl/Tag: {self.stations_day_max}")
        line1.setProperty("cls", "line"); line1.setFont(mac_default_font()); left.addWidget(line1)
        line2 = QtWidgets.QLabel(f"berücksichtigte Stationen: {self.stations_total}")
        line2.setProperty("cls", "line"); line2.setFont(mac_default_font()); left.addWidget(line2)
        left.addStretch(1)

        right = QtWidgets.QVBoxLayout(); right.setSpacing(6)
        fragments = []
        for s in self.states:
            if s in self.vacation_states:
                color = "#FF3B30"
            elif s in self.holiday_states:
                color = "#FF9500"
            else:
                color = "#EAEAEA"  # hellgrau auf dunklem BG
            fragments.append(f'<span style="color:{color};">{s}</span>')
        html = "<br>".join(fragments) if fragments else "—"
        bl_list = QtWidgets.QLabel()
        bl_list.setTextFormat(QtCore.Qt.TextFormat.RichText)
        bl_list.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.NoTextInteraction)
        bl_list.setText(f'<div style="text-align:right;">{html}</div>')
        bl_list.setFont(mac_default_font())
        bl_list.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignRight)
        bl_list.setWordWrap(True)
        right.addWidget(bl_list, 1)

        pct = QtWidgets.QLabel(f"≈ {_fmt_pct_de(self.population_share_pct)} der Bevölkerung")
        pct.setFont(mac_default_font()); pct.setStyleSheet("color:#FFFFFF;")
        pct.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom)
        right.addWidget(pct, 0, QtCore.Qt.AlignmentFlag.AlignRight)

        top.addLayout(left, 2); top.addLayout(right, 1)
        root.addLayout(top)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18); shadow.setOffset(0, 3); shadow.setColor(QtGui.QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(f"""
            QFrame#RegionCard {{
                border: 1px solid {self.border_color.name()};
                border-radius: 14px;
            }}
            QLabel[cls="title"] {{ color:#FFFFFF; font-weight:700; }}
            QLabel[cls="line"]  {{ color:#FFFFFF; }}
        """)

    def set_spark_values(self, values: List[float] | None):
        self.spark_values = [float(v) for v in (values or []) if v is not None]
        self.update()

    def paintEvent(self, e: QtGui.QPaintEvent) -> None:
        super().paintEvent(e)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        r = self.rect().adjusted(1, 1, -1, -1)
        rf = QtCore.QRectF(r)
        radius = 14.0

        # Hintergrund: oben heller → unten Basisfarbe
        bg_path = QtGui.QPainterPath()
        bg_path.addRoundedRect(rf, radius, radius)
        grad_bg = QtGui.QLinearGradient(rf.topLeft(), rf.bottomLeft())
        grad_bg.setColorAt(0.0, self.base_top)
        grad_bg.setColorAt(1.0, self.base_bottom)
        p.fillPath(bg_path, grad_bg)

        # Sparkline unten randlos
        spark_h = max(64, int(rf.height() * 0.22))
        sr = QtCore.QRectF(rf.left(), rf.bottom() - spark_h, rf.width(), float(spark_h))

        p.save(); p.setClipPath(bg_path)
        if len(self.spark_values) >= 2:
            vals = self.spark_values[-30:]
            vmin, vmax = min(vals), max(vals)
            if abs(vmax - vmin) < 1e-6:
                vmax = vmin + 1.0
            step = sr.width() / (len(vals) - 1)

            line_path = QtGui.QPainterPath()
            for i, v in enumerate(vals):
                x = sr.left() + i * step
                y = sr.bottom() - (v - vmin) / (vmax - vmin) * sr.height()
                if i == 0: line_path.moveTo(x, y)
                else:      line_path.lineTo(x, y)

            fill_path = QtGui.QPainterPath(line_path)
            fill_path.lineTo(sr.right(), sr.bottom())
            fill_path.lineTo(sr.left(), sr.bottom())
            fill_path.closeSubpath()

            grad_fill = QtGui.QLinearGradient(sr.topLeft(), sr.bottomLeft())
            # „umgedrehter“ Verlauf: oben dunkler → unten transparenter (in Kartenfarbe)
            grad_fill.setColorAt(0.00, self.spark_fill_top)
            grad_fill.setColorAt(0.60, self.spark_fill_mid)
            grad_fill.setColorAt(1.00, self.spark_fill_bot)
            p.fillPath(fill_path, grad_fill)

            pen = QtGui.QPen(self.spark_line_color, 2.0)
            p.setPen(pen)
            p.drawPath(line_path)
        else:
            pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 140), 2.0)
            p.setPen(pen)
            midy = sr.center().y()
            p.drawLine(QtCore.QPointF(sr.left(), midy), QtCore.QPointF(sr.right(), midy))
        p.restore()
