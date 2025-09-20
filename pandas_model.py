# pandas_model.py
from __future__ import annotations
from typing import Optional, Dict, Any
import pandas as pd
from PyQt6 import QtCore

class PandasModel(QtCore.QAbstractTableModel):
    def __init__(self, df: pd.DataFrame, formatters: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self._df = df.reset_index(drop=True).copy()
        self._formatters = formatters or {}

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            val = self._df.iat[index.row(), index.column()]
            col = self._df.columns[index.column()]
            fmt = self._formatters.get(col)
            if pd.isna(val):
                return ""
            if fmt:
                try:
                    return fmt(val)
                except Exception:
                    return str(val)
            return str(val)
        return None

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        else:
            return str(section + 1)

    def setDataFrame(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.reset_index(drop=True).copy()
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df.copy()