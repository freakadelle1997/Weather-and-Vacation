# stations_dialog.py
from __future__ import annotations
import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets
from pandas_model import PandasModel
from style_utils import mac_default_font, autosize_columns

class StationsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Verwendete Stationen")
        self.resize(900, 600)
        self.setFont(mac_default_font())

        v = QtWidgets.QVBoxLayout(self)
        self.view = QtWidgets.QTableView()
        self.view.verticalHeader().setVisible(False)
        self.view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(self.view)

        self.model = PandasModel(pd.DataFrame(), formatters={
            "temp_mean_C_period": lambda x: f"{float(x):.1f} °C" if pd.notna(x) else "",
            "precip_sum_mm_period": lambda x: f"{float(x):.2f}" if pd.notna(x) else "",
        })
        self.view.setModel(self.model)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject); btns.accepted.connect(self.accept)
        v.addWidget(btns)

    def set_dataframe(self, df: pd.DataFrame):
        self.model.setDataFrame(df)
        autosize_columns(self.view)