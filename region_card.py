# region_card.py
from __future__ import annotations
from typing import Iterable, List, Optional, Set
from PyQt6 import QtCore, QtGui, QtWidgets

from color_config import color_for_temp_hex


def _fmt_temp(v: Optional[float]) -> str:
    return "" if v is None else f"{v:.1f} °C"

def _fmt_precip(v: Optional[float]) -> str:
    return "" if v is None else f"{v:.2f}"

def _fmt_pct_de(v: Optional[float]) -> str:
    return "" if v is None else f"{v:.1f} %"


class RegionCard(QtWidgets.QFrame):
    """Kachel pro Region mit Gradient, Sparkline, Texten und BL-Liste (Ferien/Feiertag farblich)."""

    def __init__(
        self,
        region: str,
        states: Iterable[str],
        temp_mean: Optional[float],
        precip_sum: Optional[float],
        stations_day_max: int,
        stations_total: int,
        population_share_pct: Optional[float],
        vacation_states: Set[str],
        holiday_states: Set[str],
        spark_values: List[float],
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("RegionCard")
        self.setMinimumHeight(200)
        self.setMaximumHeight(240)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        self.region = region
        self.states = list(states)
        self.temp_mean = temp_mean
        self.precip_sum = precip_sum
        self.stations_day_max = int(stations_day_max or 0)
        self.stations_total = int(stations_total or 0)
        self.population_share_pct = population_share_pct
        self.vacation_states = set(vacation_states)
        self.holiday_states = set(holiday_states)
        self.spark_values = list(spark_values or [])

        self.setStyleSheet("""
            QFrame#RegionCard {
                border-radius: 14px;
                background: transparent;
            }
            QLabel { color: #FFFFFF; }
        """)

        # Layout-Inhalte
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(6)

        # Titel links oben
        title = QtWidgets.QLabel(f"{region}")
        f = title.font(); f.setPointSize(f.pointSize() + 2); f.setBold(True); title.setFont(f)

        # Bundesländer rechts oben (RichText, farbig je Status)
        bl = QtWidgets.QLabel(self._states_richtext())
        bl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop)
        bl.setTextFormat(QtCore.Qt.TextFormat.RichText)

        # Kennzahlen links
        temp_lbl = QtWidgets.QLabel("Ø Temperatur")
        temp_val = QtWidgets.QLabel(_fmt_temp(self.temp_mean))

        prec_lbl = QtWidgets.QLabel("Σ Niederschlag")
        prec_val = QtWidgets.QLabel(_fmt_precip(self.precip_sum))

        st_lbl = QtWidgets.QLabel("max. Stationen/Tag")
        st_val = QtWidgets.QLabel(str(self.stations_day_max))

        st2_lbl = QtWidgets.QLabel("berücksichtigte Stationen")
        st2_val = QtWidgets.QLabel(str(self.stations_total))

        # Bevölkerung unten rechts
        pct = QtWidgets.QLabel(f"≈ {_fmt_pct_de(self.population_share_pct)} der Bevölkerung")
        pf = pct.font(); pf.setBold(True); pct.setFont(pf)
        pct.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom)

        # Grid:
        # Zeile 0: Titel (links), Bundesländer (rechts)
        layout.addWidget(title, 0, 0, 1, 2)
        layout.addWidget(bl,    0, 2, 2, 1)

        # Zeilen 1..: Kennzahlen links, rechts bleibt BL / unten rechts Population
        layout.addWidget(temp_lbl, 1, 0); layout.addWidget(temp_val, 1, 1)
        layout.addWidget(prec_lbl, 2, 0); layout.addWidget(prec_val, 2, 1)
        layout.addWidget(st_lbl,   3, 0); layout.addWidget(st_val,   3, 1)
        layout.addWidget(st2_lbl,  4, 0); layout.addWidget(st2_val,  4, 1)

        layout.addWidget(pct, 4, 2, 1, 1)

    def _states_richtext(self) -> str:
        # Ferien > Feiertag > neutral
        lines = []
        for s in self.states:
            if s in self.vacation_states:
                color = "#FF3B30"  # Rot
            elif s in self.holiday_states:
                color = "#FF9F0A"  # Orange
            else:
                color = "#D1D1D1"  # Hellgrau
            lines.append(f'<span style="color:{color}">{QtGui.QGuiApplication.translate("", s)}</span>')
        return "<br/>".join(lines)

    # ---- Zeichenlogik ----
    def paintEvent(self, e: QtGui.QPaintEvent):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        r = self.rect().adjusted(1, 1, -1, -1)
        radius = 14

        # Farben aus Temperatur ableiten
        base_hex = color_for_temp_hex(self.temp_mean)
        base = QtGui.QColor(base_hex)

        # Unterkante (volle Sättigung), nach oben heller Verlauf
        top = QtGui.QColor(base); top.setAlpha(220)
        bottom = QtGui.QColor(base); bottom.setAlpha(255)

        grad_bg = QtGui.QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        grad_bg.setColorAt(0.0, top.lighter(120))
        grad_bg.setColorAt(1.0, bottom)

        brush_bg = QtGui.QBrush(grad_bg)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(r), radius, radius)
        p.fillPath(path, brush_bg)

        # Sparkline Fläche und Linie – volle Breite
        if self.spark_values:
            spark_rect = QtCore.QRectF(r.left() + 8, r.top() + 64, r.width() - 16, r.height() - 92)

            vals = self.spark_values[:]
            vmin = min(vals); vmax = max(vals)
            if abs(vmax - vmin) < 1e-9:
                vmax = vmin + 1.0  # degeneriert → flache Linie

            # Umgekehrter Verlauf: oben dunkler → unten heller
            fill_top = QtGui.QColor(base.darker(130)); fill_top.setAlpha(120)
            fill_bottom = QtGui.QColor(base.lighter(130)); fill_bottom.setAlpha(80)

            grad_fill = QtGui.QLinearGradient(spark_rect.left(), spark_rect.top(), spark_rect.left(), spark_rect.bottom())
            grad_fill.setColorAt(0.0, fill_top)
            grad_fill.setColorAt(1.0, fill_bottom)

            line_color = QtGui.QColor(base.darker(140)); line_color.setAlpha(220)

            n = len(vals)
            if n == 1:
                xs = [spark_rect.left(), spark_rect.right()]
                y = spark_rect.bottom() - (vals[0] - vmin) / (vmax - vmin) * spark_rect.height()
                ys = [y, y]
            else:
                xs = [spark_rect.left() + i * (spark_rect.width() / (n - 1)) for i in range(n)]
                ys = [spark_rect.bottom() - (v - vmin) / (vmax - vmin) * spark_rect.height() for v in vals]

            # Fläche
            poly = QtGui.QPolygonF()
            if n == 1:
                poly.append(QtCore.QPointF(xs[0], ys[0]))
                poly.append(QtCore.QPointF(xs[1], ys[1]))
                poly.append(QtCore.QPointF(xs[1], spark_rect.bottom()))
                poly.append(QtCore.QPointF(xs[0], spark_rect.bottom()))
            else:
                for x, y in zip(xs, ys):
                    poly.append(QtCore.QPointF(x, y))
                poly.append(QtCore.QPointF(spark_rect.right(), spark_rect.bottom()))
                poly.append(QtCore.QPointF(spark_rect.left(), spark_rect.bottom()))
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QBrush(grad_fill))
            p.drawPolygon(poly)

            # Linie
            pen = QtGui.QPen(line_color, 2)
            p.setPen(pen)
            if n == 1:
                p.drawLine(int(xs[0]), int(ys[0]), int(xs[1]), int(ys[1]))
            else:
                path_line = QtGui.QPainterPath(QtCore.QPointF(xs[0], ys[0]))
                for i in range(1, n):
                    path_line.lineTo(QtCore.QPointF(xs[i], ys[i]))
                p.drawPath(path_line)

        # dünne innere Kontur
        pen_border = QtGui.QPen(QtGui.QColor(255, 255, 255, 50), 1)
        p.setPen(pen_border)
        p.drawRoundedRect(r, radius, radius)

        super().paintEvent(e)
