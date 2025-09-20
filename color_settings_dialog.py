# color_settings_dialog.py
from __future__ import annotations
from typing import List, Dict, Any
from PyQt6 import QtCore, QtGui, QtWidgets

from color_config import load_config, save_config, default_config

HEX_RE = QtCore.QRegularExpression(r"^#[0-9A-Fa-f]{6}$")

_LABELS = [
    "−20.0 bis 10.9 °C",
    "11.0 bis 14.9 °C",
    "15.0 bis 19.9 °C",
    "20.0 bis 24.9 °C",
    "25.0 bis 29.9 °C",
    "30.0 bis 34.9 °C",
    "35.0 bis 49.9 °C",
]

class ColorSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Farben einstellen")
        self.setModal(True)
        self.resize(520, 360)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        info = QtWidgets.QLabel("Hex-Farben pro Temperaturbereich (Klick auf Farbfeld öffnet Farbwähler).")
        layout.addWidget(info)

        self.grid = QtWidgets.QGridLayout()
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(6)
        layout.addLayout(self.grid)

        self._rows: List[Dict[str, Any]] = []
        self._build_rows()

        # Bottom Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_reset = QtWidgets.QPushButton("Auf Standard zurücksetzen")
        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_cancel = QtWidgets.QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QtWidgets.QPushButton("Speichern")
        self.btn_save.clicked.connect(self.on_save)
        btn_row.addWidget(self.btn_reset)
        btn_row.addSpacing(6)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

    def _build_rows(self):
        cfg = load_config()
        val = QtGui.QRegularExpressionValidator(HEX_RE, self)
        for i, entry in enumerate(cfg):
            label = QtWidgets.QLabel(_LABELS[i])

            color_edit = QtWidgets.QLineEdit(str(entry["color"]).upper())
            color_edit.setMaxLength(7)
            color_edit.setValidator(val)
            color_edit.setFixedWidth(90)

            color_btn = QtWidgets.QPushButton("")
            color_btn.setFixedSize(42, 22)
            color_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            self._apply_btn_color(color_btn, color_edit.text())

            # Klick → QColorDialog
            color_btn.clicked.connect(lambda _, ed=color_edit, b=color_btn: self.pick_color(ed, b))

            self.grid.addWidget(label, i, 0)
            self.grid.addWidget(color_edit, i, 1)
            self.grid.addWidget(color_btn, i, 2)

            self._rows.append({"edit": color_edit, "btn": color_btn})

    def _apply_btn_color(self, btn: QtWidgets.QPushButton, hex_color: str):
        btn.setStyleSheet(f"QPushButton {{ background: {hex_color}; border-radius: 6px; border:1px solid #999; }}")

    def pick_color(self, edit: QtWidgets.QLineEdit, btn: QtWidgets.QPushButton):
        initial = QtGui.QColor(edit.text()) if edit.text() else QtGui.QColor("#000000")
        col = QtWidgets.QColorDialog.getColor(initial, self, "Farbe wählen")
        if col.isValid():
            h = col.name().upper()
            edit.setText(h)
            self._apply_btn_color(btn, h)

    def on_reset(self):
        defaults = default_config()
        for i, row in enumerate(self._rows):
            h = defaults[i]["color"].upper()
            row["edit"].setText(h)
            self._apply_btn_color(row["btn"], h)

    def on_save(self):
        # Eingaben validieren
        items = load_config()
        for i, row in enumerate(self._rows):
            h = row["edit"].text().upper().strip()
            if not HEX_RE.match(h):
                QtWidgets.QMessageBox.warning(self, "Farbe", f"Ungültige Hexfarbe in Zeile {i+1}: {h}")
                return
            items[i]["color"] = h
        try:
            save_config(items)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Speichern fehlgeschlagen", str(e))
            return
        self.accept()
