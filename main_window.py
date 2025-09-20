# main_window.py
from __future__ import annotations

import re
import time
import datetime as dt
from typing import Dict, Optional, List, Tuple, Set

import pandas as pd
from PyQt6 import QtCore, QtGui, QtWidgets

from regions import REGIONS, REGION_ORDER
from style_utils import mac_default_font, style_line_edit, autosize_columns
from pandas_model import PandasModel
from region_card import RegionCard
from stations_dialog import StationsDialog
from fetch_worker import FetchWorker
from population import region_population_share, BUNDESLAND_POP, TOTAL_POP
from holidays_utils import union_affected_states
from color_config import load_config
from settings_dialog import SettingsDialog

DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def parse_german_date(s: str) -> dt.date:
    s = s.strip()
    if not DATE_RE.match(s):
        raise ValueError("Bitte Datum im Format TT.MM.JJJJ eingeben.")
    try:
        return dt.datetime.strptime(s, "%d.%m.%Y").date()
    except Exception:
        raise ValueError("Ungültiges Datum (z. B. 31.02.2023).")


class MainWindow(QtWidgets.QMainWindow):
    finished = QtCore.pyqtSignal()  # optional extern

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DWD Regions")
        self.resize(1100, 820)
        self.setFont(mac_default_font())

        # Thread/Worker Referenzen
        self.worker_thread: Optional[QtCore.QThread] = None
        self.worker: Optional[FetchWorker] = None
        self.stations_dialog: Optional[StationsDialog] = None

        # Letzte Zeitspanne & Ferien/Feiertag-Info
        self.last_start_date: Optional[dt.date] = None
        self.last_end_date: Optional[dt.date] = None
        self._states_with_vacation: Set[str] = set()
        self._states_with_holiday: Set[str] = set()
        self._states_free_union: Set[str] = set()
        self._free_share_pct: float = 0.0

        # Datencontainer
        self.df_summary = pd.DataFrame()
        self.df_daily = pd.DataFrame()
        self.df_stations = pd.DataFrame()
        self.df_spark = pd.DataFrame()   # NEU: 30-Tage-Temps je Region

        # Farbkonfiguration
        self._colors = load_config()

        # Stile
        try:
            from PyQt6.QtWidgets import QStyleFactory
            if "macOS" in QStyleFactory.keys():
                QtWidgets.QApplication.setStyle("macOS")
            else:
                QtWidgets.QApplication.setStyle("Fusion")
        except Exception:
            pass

        # ============= Menüleiste: Einstellungen =============
        menubar = self.menuBar()
        menu_app = menubar.addMenu("DWD Regions")
        act_settings = QtGui.QAction("Einstellungen …", self)
        act_settings.triggered.connect(self.open_settings)
        menu_app.addAction(act_settings)

        # ============= Zentrales Layout =============
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)

        # ---------- Toolbar (Datum + Buttons) ----------
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)

        yesterday_str = (dt.date.today() - dt.timedelta(days=1)).strftime("%d.%m.%Y")

        self.start_input = QtWidgets.QLineEdit()
        self.start_input.setPlaceholderText("TT.MM.JJJJ")
        self.start_input.setText(yesterday_str)
        self.start_input.setInputMask("00.00.0000;_")
        style_line_edit(self.start_input)
        self.start_input.setToolTip("Startdatum (TT.MM.JJJJ)")
        self.start_input.returnPressed.connect(self.on_fetch)

        self.end_input = QtWidgets.QLineEdit()
        self.end_input.setPlaceholderText("TT.MM.JJJJ")
        self.end_input.setText(yesterday_str)
        self.end_input.setInputMask("00.00.0000;_")
        style_line_edit(self.end_input)
        self.end_input.setToolTip("Endedatum (TT.MM.JJJJ)")
        self.end_input.returnPressed.connect(self.on_fetch)

        self.btn_fetch = QtWidgets.QPushButton("Berechnen")
        self.btn_fetch.clicked.connect(self.on_fetch)

        self.btn_cache = QtWidgets.QPushButton("🧹 Cache leeren")
        self.btn_cache.clicked.connect(self.on_clear_cache)

        toolbar.addWidget(QtWidgets.QLabel("Start:"))
        toolbar.addWidget(self.start_input)
        toolbar.addSpacing(8)
        toolbar.addWidget(QtWidgets.QLabel("Ende:"))
        toolbar.addWidget(self.end_input)
        toolbar.addStretch(1)
        toolbar.addWidget(self.btn_cache)
        toolbar.addWidget(self.btn_fetch)
        vbox.addLayout(toolbar)

        # ---------- Zeile 2: Verwendete Stationen (rechts) ----------
        row2 = QtWidgets.QHBoxLayout()
        row2.addStretch(1)
        self.btn_show_stations = QtWidgets.QPushButton("Verwendete Stationen")
        self.btn_show_stations.clicked.connect(self.show_stations_dialog)
        self.btn_show_stations.setVisible(False)
        row2.addWidget(self.btn_show_stations, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        vbox.addLayout(row2)

        # ---------- Progress + Status ----------
        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("⏳ Bereit")
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        vbox.addWidget(self.progress)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color:#6e6e73;")
        vbox.addWidget(self.status_label)

        # ---------- Tabs ----------
        self.tabs = QtWidgets.QTabWidget()
        vbox.addWidget(self.tabs)

        # Tab Ergebnisse
        self.tab_results = QtWidgets.QWidget()
        self.tabs.addTab(self.tab_results, "📊 Ergebnisse")
        res_layout = QtWidgets.QVBoxLayout(self.tab_results)
        res_layout.setContentsMargins(8, 8, 8, 8)
        res_layout.setSpacing(8)

        res_layout.addWidget(QtWidgets.QLabel("Zeitraum-Zusammenfassung"))

        # Bevölkerung mit freien Tagen (Ferien/Feiertage)
        self.free_share_label = QtWidgets.QLabel("—")
        self.free_share_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.free_share_label.setStyleSheet("color:#6e6e73; font-weight:600;")
        res_layout.addWidget(self.free_share_label)

        # Karten-Grid
        self.cards_container = QtWidgets.QWidget()
        self.cards_layout = QtWidgets.QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setHorizontalSpacing(12)
        self.cards_layout.setVerticalSpacing(12)
        res_layout.addWidget(self.cards_container)

        # Daily-Tabs je Region (initial versteckt)
        self.daily_header = QtWidgets.QLabel("Tägliche Mittelwerte je Region")
        res_layout.addWidget(self.daily_header)

        self.daily_tabs = QtWidgets.QTabWidget()
        res_layout.addWidget(self.daily_tabs)

        self.daily_views: Dict[str, QtWidgets.QTableView] = {}
        self.model_daily_by_region: Dict[str, PandasModel] = {}
        for region in REGION_ORDER:
            view = QtWidgets.QTableView()
            view.verticalHeader().setVisible(False)
            view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            model = PandasModel(
                pd.DataFrame(columns=["Datum", "Temperatur (°C)", "Niederschlag (mm)", "berücksichtigte Stationen"]),
                formatters={
                    "Datum": lambda x: (
                        pd.to_datetime(x, errors="coerce").strftime("%d.%m.%Y") if pd.notna(x) else ""
                    ),
                    "Temperatur (°C)": lambda v: f"{float(v):.1f} °C" if pd.notna(v) else "",
                    "Niederschlag (mm)": lambda v: f"{float(v):.2f}" if pd.notna(v) else "",
                    "berücksichtigte Stationen": lambda v: f"{int(v)}" if pd.notna(v) else "",
                }
            )
            view.setModel(model)
            self.daily_views[region] = view
            self.model_daily_by_region[region] = model
            self.daily_tabs.addTab(view, region)

        export_row = QtWidgets.QHBoxLayout()
        export_row.addStretch(1)
        self.btn_export_daily = QtWidgets.QPushButton("CSV exportieren (tägliche Werte)")
        self.btn_export_daily.clicked.connect(self.export_daily_csv)
        export_row.addWidget(self.btn_export_daily)
        res_layout.addLayout(export_row)

        # Initially: Tagesliste aus
        self.daily_header.setVisible(False)
        self.daily_tabs.setVisible(False)
        self.btn_export_daily.setVisible(False)

        # ETA-Countdown
        self.eta_timer = QtCore.QTimer(self)
        self.eta_timer.setInterval(1000)
        self.eta_timer.timeout.connect(self._tick_eta)
        self._eta_active = False
        self._eta_start_time = None
        self._eta_pred_total_seconds = None
        self._eta_done_steps = 0
        self._eta_total_steps = 0

    # ================= Einstellungen =================
    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.exec()

    def _on_settings_changed(self):
        self._colors = load_config()
        # Re-Render der Karten mit neuen Farben
        self.build_summary_cards(self.df_summary, self._build_spark_map_from_df(self.df_spark))

    # ================= Utils =================
    def _read_dates(self) -> Tuple[dt.date, dt.date]:
        s = parse_german_date(self.start_input.text())
        e = parse_german_date(self.end_input.text())
        if e < s:
            raise ValueError("Ende darf nicht vor Start liegen.")
        return s, e

    def _update_free_share(self, s: dt.date, e: dt.date):
        vac, hol = union_affected_states(s, e)
        self._states_with_vacation = vac
        self._states_with_holiday = hol
        uni = vac.union(hol)
        self._states_free_union = uni
        pop = sum(BUNDESLAND_POP.get(bl, 0) for bl in uni)
        self._free_share_pct = (pop / TOTAL_POP * 100.0) if TOTAL_POP > 0 else 0.0

        self.free_share_label.setText(
            f"Freie Tage/Ferien beeinflussen ≈ {self._free_share_pct:.1f} % der Bevölkerung"
        )
        self.status_label.setText(
            f"Zeitraum {s.strftime('%d.%m.%Y')}–{e.strftime('%d.%m.%Y')} · "
            f"Ferien in {len(vac)} BL · Feiertage in {len(hol)} BL"
        )

    def _eta_text(self) -> str:
        if not self._eta_active or self._eta_pred_total_seconds is None:
            return "⏳ Lade …"
        elapsed = time.perf_counter() - self._eta_start_time
        remaining = max(int(round(self._eta_pred_total_seconds - elapsed)), 0)
        return f"⏳ Restzeit ~{remaining}s"

    def _tick_eta(self):
        if not self._eta_active:
            return
        self.progress.setFormat(self._eta_text())

    def _build_spark_map_from_df(self, spark_df: pd.DataFrame) -> Dict[str, List[float]]:
        """Extrahiert je Region eine Liste von bis zu 30 Temperaturwerten (chronologisch)."""
        out: Dict[str, List[float]] = {r: [] for r in REGION_ORDER}
        if spark_df is None or spark_df.empty:
            return out

        df = spark_df.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if "temp_mean_C" not in df.columns:
            return out

        for region in REGION_ORDER:
            sub = df[df["region"] == region].copy()
            if sub.empty:
                continue
            sub = sub.sort_values("date")
            vals = pd.to_numeric(sub["temp_mean_C"], errors="coerce").dropna().astype(float).tolist()
            out[region] = vals[-30:]
        return out

    # ================= Aktionen =================
    def on_clear_cache(self):
        from wetterdienst.settings import Settings
        import shutil
        from pathlib import Path

        cache_dir = Path(Settings(cache_disable=False).cache_dir).expanduser()
        try:
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            self.status_label.setStyleSheet("color:#2d7d46;")
            self.status_label.setText(f"🧹 Cache geleert: {cache_dir}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Fehler", f"Cache konnte nicht gelöscht werden:\n{e}")

    def on_fetch(self):
        # Läuft schon ein Thread?
        t = getattr(self, "worker_thread", None)
        if isinstance(t, QtCore.QThread) and t.isRunning():
            return

        try:
            s, e = self._read_dates()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, "Datum", str(ex))
            return

        self.last_start_date, self.last_end_date = s, e

        # UI-Reset
        self.status_label.setText("Starte Abruf …")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.progress.setFormat("⏳ Lade …")

        # Tagesliste (Tabs) nur bei mehr als einem Tag
        same_day = s == e
        self.daily_header.setVisible(not same_day)
        self.daily_tabs.setVisible(not same_day)
        self.btn_export_daily.setVisible(not same_day)

        # ETA Setup
        self._eta_start_time = time.perf_counter()
        self._eta_done_steps = 0
        self._eta_total_steps = 1 + len(REGIONS) * 2 + 1  # grob: Stationen & pro Region (Main+Spark)
        self._eta_pred_total_seconds = None
        self._eta_active = True
        self.eta_timer.start()

        # Ferien/Feiertage vorberechnen
        self._update_free_share(s, e)

        # Worker
        self.worker_thread = QtCore.QThread(self)
        self.worker = FetchWorker(s, e, REGIONS)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run, QtCore.Qt.ConnectionType.QueuedConnection)
        self.worker.progress.connect(self.on_progress, QtCore.Qt.ConnectionType.QueuedConnection)
        self.worker.finished.connect(self.on_finished, QtCore.Qt.ConnectionType.QueuedConnection)
        self.worker.error.connect(self.on_error, QtCore.Qt.ConnectionType.QueuedConnection)

        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self.on_thread_finished)

        self.worker_thread.start()

        self.btn_fetch.setEnabled(False)
        self.btn_cache.setEnabled(False)
        self.btn_show_stations.setVisible(False)

    def on_thread_finished(self):
        self.worker_thread = None
        self.worker = None

    @QtCore.pyqtSlot(int, int, str)
    def on_progress(self, done: int, total: int, note: str):
        # ETA-Schätzung updaten
        self._eta_done_steps = done
        if done >= 1:
            elapsed = time.perf_counter() - self._eta_start_time
            avg = elapsed / max(done, 1)
            self._eta_pred_total_seconds = avg * total

        pct = int(min(max(done / max(total, 1) * 100, 0), 100))
        self.progress.setValue(pct)
        self.progress.setFormat(f"{self._eta_text()}  •  {note}")
        self.status_label.setText(note)

    @QtCore.pyqtSlot(pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame)
    def on_finished(self, summary: pd.DataFrame, daily: pd.DataFrame, stations: pd.DataFrame, spark: pd.DataFrame):
        self._eta_active = False
        self.eta_timer.stop()
        self.progress.setVisible(False)

        self.df_summary = summary.copy()
        self.df_daily = daily.copy()
        self.df_stations = stations.copy()
        self.df_spark = spark.copy()

        # Daily: Anzeige-Spaltennamen (Temp/Niederschlag/Stationen umbenennen)
        if not self.df_daily.empty:
            if "temp_mean_C" in self.df_daily.columns:
                self.df_daily = self.df_daily.rename(columns={"temp_mean_C": "Temperatur (°C)"})
            if "precip_mm" in self.df_daily.columns:
                self.df_daily = self.df_daily.rename(columns={"precip_mm": "Niederschlag (mm)"})
            if "stations_used" in self.df_daily.columns:
                self.df_daily = self.df_daily.rename(columns={"stations_used": "berücksichtigte Stationen"})

        # Karten bauen (Sparkline aus df_spark)
        spark_map = self._build_spark_map_from_df(self.df_spark)
        self.build_summary_cards(self.df_summary, spark_map)

        # Tägliche Tabellen je Region aktualisieren
        self.update_daily_tabs(self.df_daily)

        if self.df_summary.empty and self.df_daily.empty:
            self.status_label.setStyleSheet("color:#6e6e73;")
            self.status_label.setText("ℹ️ Keine Daten im Zeitraum gefunden.")
            self.btn_show_stations.setVisible(False)
        else:
            self.status_label.setStyleSheet("color:#2d7d46;")
            self.status_label.setText("Berechnung abgeschlossen.")
            self.btn_show_stations.setVisible(True)

        self.btn_fetch.setEnabled(True)
        self.btn_cache.setEnabled(True)

    @QtCore.pyqtSlot(str)
    def on_error(self, msg: str):
        self._eta_active = False
        self.eta_timer.stop()
        self.progress.setVisible(False)
        self.btn_fetch.setEnabled(True)
        self.btn_cache.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Fehler beim Laden", msg)

    # ================= Ergebnisse aufbauen =================
    def build_summary_cards(self, df_summary: pd.DataFrame, spark_map: Dict[str, List[float]]):
        # Grid leeren
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        if df_summary.empty:
            return

        order = REGION_ORDER
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for idx, region in enumerate(order):
            row, col = positions[idx]

            sub = df_summary[df_summary["Region"] == region]
            if sub.empty:
                self.cards_layout.addWidget(QtWidgets.QFrame(), row, col)
                continue

            temp_mean = float(sub["Ø Temperatur (°C)"].iloc[0]) if "Ø Temperatur (°C)" in sub.columns and pd.notna(sub["Ø Temperatur (°C)"].iloc[0]) else None
            precip_sum = float(sub["Σ Niederschlag (mm)"].iloc[0]) if "Σ Niederschlag (mm)" in sub.columns and pd.notna(sub["Σ Niederschlag (mm)"].iloc[0]) else None

            stations_day_max = 0
            if "max. Stationsanzahl/Tag" in sub.columns:
                v = pd.to_numeric(sub["max. Stationsanzahl/Tag"].iloc[0], errors="coerce")
                stations_day_max = int(v) if pd.notna(v) else 0

            stations_total = int(sub["berücksichtigte Stationen (Anzahl)"].iloc[0]) if "berücksichtigte Stationen (Anzahl)" in sub.columns and pd.notna(sub["berücksichtigte Stationen (Anzahl)"].iloc[0]) else 0

            states = REGIONS[region]
            pop_share = region_population_share(region)

            vac_states = set(s for s in states if s in self._states_with_vacation)
            hol_states = set(s for s in states if (s in self._states_with_holiday and s not in vac_states))

            spark_vals = spark_map.get(region, [])

            card = RegionCard(
                region=region,
                states=states,
                temp_mean=temp_mean,
                precip_sum=precip_sum,
                stations_day_max=stations_day_max,
                stations_total=stations_total,
                population_share_pct=pop_share,
                vacation_states=vac_states,
                holiday_states=hol_states,
                spark_values=spark_vals,
            )
            self.cards_layout.addWidget(card, row, col)

    def update_daily_tabs(self, df_daily: pd.DataFrame):
        for region in REGION_ORDER:
            model = self.model_daily_by_region[region]
            model.setDataFrame(pd.DataFrame(columns=["Datum", "Temperatur (°C)", "Niederschlag (mm)", "berücksichtigte Stationen"]))
            view = self.daily_views[region]
            autosize_columns(view)

        if df_daily.empty:
            return

        df = df_daily.copy()
        if "date" in df.columns:
            df["Datum"] = pd.to_datetime(df["date"], errors="coerce")
        elif "Datum" in df.columns:
            df["Datum"] = pd.to_datetime(df["Datum"], errors="coerce")

        for region in REGION_ORDER:
            cols = ["Datum", "Temperatur (°C)", "Niederschlag (mm)", "berücksichtigte Stationen"]
            sub = df[df["region"] == region][cols].copy() if all(c in df.columns for c in cols) else pd.DataFrame(columns=cols)
            if sub.empty:
                self.model_daily_by_region[region].setDataFrame(pd.DataFrame(columns=cols))
                autosize_columns(self.daily_views[region])
                continue

            sub = sub.sort_values("Datum", ascending=False).reset_index(drop=True)
            self.model_daily_by_region[region].setDataFrame(sub)
            autosize_columns(self.daily_views[region])

    # ================= Export & Dialoge =================
    def export_daily_csv(self):
        if self.df_daily.empty:
            QtWidgets.QMessageBox.information(self, "Export", "Keine täglichen Werte vorhanden.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "CSV speichern", "dwd_regions_daily.csv", "CSV (*.csv)"
        )
        if path:
            df = self.df_daily.copy()
            if "Datum" in df.columns:
                df = df.sort_values("Datum", ascending=False)
            df.to_csv(path, index=False)

    def show_stations_dialog(self):
        if self.df_stations.empty:
            QtWidgets.QMessageBox.information(self, "Verwendete Stationen", "Keine Stationenliste vorhanden.")
            return
        try:
            dlg = StationsDialog(self.df_stations, self)
        except TypeError:
            dlg = StationsDialog(self)
            if hasattr(dlg, "set_dataframe"):
                dlg.set_dataframe(self.df_stations)
        dlg.exec()
