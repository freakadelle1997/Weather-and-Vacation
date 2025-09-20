# settings_dialog.py
from __future__ import annotations
from typing import Dict
from PyQt6 import QtCore, QtGui, QtWidgets
from color_config import get_ranges_meta, load_config, save_config, HEX_RE


class SettingsDialog(QtWidgets.QDialog):
    settings_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen – Farben nach Temperatur")
        self.setModal(True)
        self.setMinimumWidth(520)

        self.inputs: Dict[str, QtWidgets.QLineEdit] = {}
        self.previews: Dict[str, QtWidgets.QLabel] = {}

        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)

        info = QtWidgets.QLabel("Lege die Farben (HEX) für die Temperaturbereiche fest. "
                                "Sparkline und Kartenverlauf passen sich automatisch an.")
        info.setWordWrap(True)
        vbox.addWidget(info)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        vbox.addLayout(grid)

        self.cfg = load_config()
        meta = get_ranges_meta()
        for row, (label, key, lo, hi) in enumerate(meta):
            lbl = QtWidgets.QLabel(label)
            grid.addWidget(lbl, row, 0)

            line = QtWidgets.QLineEdit(self.cfg.get(key, "#FFFFFF"))
            line.setMaxLength(7)
            line.setText(self.cfg.get(key, "#FFFFFF"))
            line.setPlaceholderText("#RRGGBB")
            line.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            # Validator
            rx = QtCore.QRegularExpression(HEX_RE.pattern)
            line.setValidator(QtGui.QRegularExpressionValidator(rx, line))
            grid.addWidget(line, row, 1)
            self.inputs[key] = line

            btn = QtWidgets.QPushButton("Wählen…")
            btn.clicked.connect(lambda _=False, k=key: self.pick_color(k))
            grid.addWidget(btn, row, 2)

            prev = QtWidgets.QLabel()
            prev.setFixedSize(54, 20)
            prev.setFrameShape(QtWidgets.QFrame.Shape.Box)
            prev.setLineWidth(1)
            grid.addWidget(prev, row, 3)
            self.previews[key] = prev
            self._update_preview(key, line.text())

            line.textChanged.connect(lambda text, k=key: self._update_preview(k, text))

        # Buttons
        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        save = QtWidgets.QPushButton("Speichern")
        cancel = QtWidgets.QPushButton("Abbrechen")
        save.clicked.connect(self.on_save)
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addWidget(save)
        vbox.addLayout(btns)

    def _update_preview(self, key: str, text: str):
        if HEX_RE.match(text):
            self.previews[key].setStyleSheet(f"background:{text}; border:1px solid #888;")
        else:
            self.previews[key].setStyleSheet("background:#FFFFFF; border:1px solid #f00;")

    def pick_color(self, key: str):
        start = self.inputs[key].text() if HEX_RE.match(self.inputs[key].text()) else "#FFFFFF"
        col = QtGui.QColor(start)
        picked = QtWidgets.QColorDialog.getColor(col, self, "Farbe auswählen",
                                                 QtWidgets.QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if picked.isValid():
            hexv = picked.name().upper()
            self.inputs[key].setText(hexv)

    def on_save(self):
        out = {}
        for key, line in self.inputs.items():
            txt = line.text().strip().upper()
            if not HEX_RE.match(txt):
                QtWidgets.QMessageBox.warning(self, "Ungültige Farbe",
                                              f"Bitte gültige HEX-Farbe für Bereich {key} eingeben.")
                return
            out[key] = txt
        save_config(out)
        self.settings_changed.emit()
        self.accept()
