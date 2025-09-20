# region_card.py
from __future__ import annotations
from typing import Iterable, List, Optional, Set
from PyQt6 import QtCore, QtGui, QtWidgets

from color_config import color_for_temp_hex

# Fixe Puffer (einheitliches Layout)
TOP_PAD = 88        # Platz oben: Titel + große Temperatur + Niederschlag
BOTTOM_PAD = 66     # unten: 2 Stationszeilen + Bevölkerungs-Text
SIDE_PAD = 16       # Innenabstand links/rechts

def _fmt_temp(v: Optional[float]) -> str:
    return "" if v is None else f"{v:.1f} °C"

def _fmt_precip(v: Optional[float]) -> str:
    return "" if v is None else f"{v:.2f}"

def _fmt_pct_de(v: Optional[float]) -> str:
    return "" if v is None else f"{v:.1f} %"


class RegionCard(QtWidgets.QFrame):
    """
    Linke Spalte: Titel, Ø Temp (groß), Σ Niederschlag, unten links 2 Stationszeilen
    Rechte Seite: BL-Liste (oben rechts, Overlay), Bevölkerungs-Hinweis (unten rechts, Overlay)
    Sparkline: zwischen TOP_PAD und BOTTOM_PAD über die volle Breite
    """
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
        self.setMinimumHeight(210)
        self.setMaximumHeight(250)
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

        # Linke Spalte (im Layout)
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(SIDE_PAD, SIDE_PAD, SIDE_PAD, SIDE_PAD)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(2)

        title = QtWidgets.QLabel(self.region)
        f = title.font(); f.setPointSize(f.pointSize() + 2); f.setBold(True)
        title.setFont(f)

        temp_big = QtWidgets.QLabel(_fmt_temp(self.temp_mean))
        tf = temp_big.font(); tf.setPointSize(tf.pointSize() + 8); tf.setBold(True)
        temp_big.setFont(tf)

        prec_row = QtWidgets.QHBoxLayout(); prec_row.setSpacing(6)
        prec_lbl = QtWidgets.QLabel("Σ Niederschlag")
        prec_val = QtWidgets.QLabel(_fmt_precip(self.precip_sum))
        prec_row.addWidget(prec_lbl); prec_row.addWidget(prec_val); prec_row.addStretch(1)

        st_row1 = QtWidgets.QHBoxLayout(); st_row1.setSpacing(6)
        st1_lbl = QtWidgets.QLabel("max. Stationen/Tag")
        st1_val = QtWidgets.QLabel(str(self.stations_day_max))
        st_row1.addWidget(st1_lbl); st_row1.addWidget(st1_val); st_row1.addStretch(1)

        st_row2 = QtWidgets.QHBoxLayout(); st_row2.setSpacing(6)
        st2_lbl = QtWidgets.QLabel("berücksichtigte Stationen")
        st2_val = QtWidgets.QLabel(str(self.stations_total))
        st_row2.addWidget(st2_lbl); st_row2.addWidget(st2_val); st_row2.addStretch(1)

        layout.addWidget(title,     0, 0, 1, 1)
        layout.addWidget(temp_big,  1, 0, 1, 1)
        layout.addLayout(prec_row,  2, 0, 1, 1)
        layout.setRowStretch(3, 1)
        layout.addLayout(st_row1,   4, 0, 1, 1)
        layout.addLayout(st_row2,   5, 0, 1, 1)

        # Rechte Seite (Overlay-Labels, beeinflussen Layout nicht)
        self.bl_label = QtWidgets.QLabel(self._states_richtext(), self)
        self.bl_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop)
        self.bl_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.bl_label.setWordWrap(True)
        self.bl_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.pct_label = QtWidgets.QLabel(f"≈ {_fmt_pct_de(self.population_share_pct)} der Bevölkerung", self)
        pf = self.pct_label.font(); pf.setBold(True); self.pct_label.setFont(pf)
        self.pct_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom)
        self.pct_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _states_richtext(self) -> str:
        lines = []
        for s in self.states:
            if s in self.vacation_states:
                color = "#FF3B30"  # Ferien → Rot
            elif s in self.holiday_states:
                color = "#FF9F0A"  # Feiertag → Orange
            else:
                color = "#D1D1D1"  # neutral
            lines.append(f'<span style="color:{color}">{s}</span>')
        return "<br/>".join(lines)

    # Hintergrund + Sparkline
    def paintEvent(self, e: QtGui.QPaintEvent):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        r = self.rect().adjusted(1, 1, -1, -1)
        radius = 14

        base_hex = color_for_temp_hex(self.temp_mean)
        base = QtGui.QColor(base_hex)

        top = QtGui.QColor(base); top.setAlpha(220)
        bottom = QtGui.QColor(base); bottom.setAlpha(255)
        grad_bg = QtGui.QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        grad_bg.setColorAt(0.0, top.lighter(120))
        grad_bg.setColorAt(1.0, bottom)

        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(r), radius, radius)
        p.fillPath(path, QtGui.QBrush(grad_bg))

        # Sparkline
        if self.spark_values:
            spark_rect = QtCore.QRectF(
                r.left() + SIDE_PAD - 8,
                r.top() + TOP_PAD,
                r.width() - 2 * (SIDE_PAD - 8),
                r.height() - TOP_PAD - BOTTOM_PAD
            )
            vals = self.spark_values[:]
            vmin = min(vals); vmax = max(vals)
            if abs(vmax - vmin) < 1e-9:
                vmax = vmin + 1.0

            fill_top = QtGui.QColor(base.darker(130)); fill_top.setAlpha(120)
            fill_bottom = QtGui.QColor(base.lighter(130)); fill_bottom.setAlpha(80)
            grad_fill = QtGui.QLinearGradient(
                spark_rect.left(), spark_rect.top(), spark_rect.left(), spark_rect.bottom()
            )
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

            poly = QtGui.QPolygonF()
            if n == 1:
                poly.append(QtCore.QPointF(xs[0], ys[0])); poly.append(QtCore.QPointF(xs[1], ys[1]))
                poly.append(QtCore.QPointF(xs[1], spark_rect.bottom())); poly.append(QtCore.QPointF(xs[0], spark_rect.bottom()))
            else:
                for x, y in zip(xs, ys): poly.append(QtCore.QPointF(x, y))
                poly.append(QtCore.QPointF(spark_rect.right(), spark_rect.bottom()))
                poly.append(QtCore.QPointF(spark_rect.left(), spark_rect.bottom()))
            p.setPen(QtCore.Qt.PenStyle.NoPen); p.setBrush(QtGui.QBrush(grad_fill)); p.drawPolygon(poly)

            pen = QtGui.QPen(line_color, 2); p.setPen(pen)
            if n == 1:
                p.drawLine(int(xs[0]), int(ys[0]), int(xs[1]), int(ys[1]))
            else:
                path_line = QtGui.QPainterPath(QtCore.QPointF(xs[0], ys[0]))
                for i in range(1, n): path_line.lineTo(QtCore.QPointF(xs[i], ys[i]))
                p.drawPath(path_line)

        pen_border = QtGui.QPen(QtGui.QColor(255, 255, 255, 50), 1)
        p.setPen(pen_border); p.drawRoundedRect(r, radius, radius)
        super().paintEvent(e)

    # Overlays platzieren (entkoppelt vom Layout)
    def resizeEvent(self, e: QtGui.QResizeEvent):
        r = self.rect().adjusted(SIDE_PAD, SIDE_PAD, -SIDE_PAD, -SIDE_PAD)

        # BL-Box oben rechts – max. 40% Breite, 2 Zeilen Höhe genügt (WordWrap)
        w = max(160, int(r.width() * 0.38))
        self.bl_label.setFixedWidth(w)
        h = self.bl_label.sizeHint().height()
        self.bl_label.setGeometry(r.right() - w, r.top(), w, h)

        s = self.pct_label.sizeHint()
        self.pct_label.setGeometry(r.right() - s.width(), r.bottom() - s.height(), s.width(), s.height())

        super().resizeEvent(e)