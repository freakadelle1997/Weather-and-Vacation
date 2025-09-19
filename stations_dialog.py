# stations_dialog.py
from __future__ import annotations
import pandas as pd
from PyQt6 import QtWidgets
from pandas_model import PandasModel
from style_utils import autosize_columns

class StationsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verwendete Stationen")
        self.resize(920, 620)

        vbox = QtWidgets.QVBoxLayout(self)
        vbox.setContentsMargins(12, 12, 12, 12); vbox.setSpacing(8)

        self.table = QtWidgets.QTableView(self)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        vbox.addWidget(self.table, 1)

        btn_row = QtWidgets.QHBoxLayout(); btn_row.addStretch(1)
        self.btn_export = QtWidgets.QPushButton("CSV exportieren")
        self.btn_close = QtWidgets.QPushButton("Schließen")
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_export); btn_row.addWidget(self.btn_close)
        vbox.addLayout(btn_row)

        self.model = PandasModel(pd.DataFrame())
        self.table.setModel(self.model)
        self.btn_export.clicked.connect(self._export_csv)

    def set_dataframe(self, df: pd.DataFrame):
        self.model.setDataFrame(df)
        autosize_columns(self.table)

    def _export_csv(self):
        df = self.model.dataframe()
        if df.empty:
            QtWidgets.QMessageBox.information(self, "Export", "Keine Stationenliste vorhanden.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "CSV speichern", "stationen_mit_werten.csv", "CSV (*.csv)"
        )
        if path:
            df.to_csv(path, index=False)
