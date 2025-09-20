# main_window.py
from __future__ import annotations
import re, time, datetime as dt
from typing import Dict, Optional, List
import pandas as pd

from PyQt6 import QtCore, QtGui, QtWidgets
from wetterdienst.settings import Settings

from regions import REGIONS, REGION_ORDER
from style_utils import mac_default_font, style_line_edit, autosize_columns
from pandas_model import PandasModel
from region_card import RegionCard
from stations_dialog import StationsDialog
from fetch_worker import FetchWorker  # finished(summary, daily, stations, spark_30d)
from population import region_population_share, TOTAL_POP, BUNDESLAND_POP
from holidays_utils import union_affected_states
from color_settings_dialog import ColorSettingsDialog  # Preferences dialog

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
    def __init__(self):
        super().__init__()

        # App-Name überall aktualisiert
        self.setWindowTitle("LCARSlite Weather and Vacation")
        self.resize(1100, 840)
        self.setFont(mac_default_font())

        self.worker_thread: Optional[QtCore.QThread] = None
        self.worker: Optional[FetchWorker] = None

        self._states_with_vacation = set()
        self._states_with_holiday = set()
        self._states_free_union = set()
        self._free_share_pct = 0.0

        try:
            from PyQt6.QtWidgets import QStyleFactory
            if "macOS" in QStyleFactory.keys():
                QtWidgets.QApplication.setStyle("macOS")
            else:
                QtWidgets.QApplication.setStyle("Fusion")
        except Exception:
            pass

        # Native macOS-Menü (Topbar)
        self._build_menubar()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)

        # ---------- Toolbar ----------
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

        toolbar.addWidget(QtWidgets.QLabel("Start:"))
        toolbar.addWidget(self.start_input)
        toolbar.addSpacing(8)
        toolbar.addWidget(QtWidgets.QLabel("Ende:"))
        toolbar.addWidget(self.end_input)
        toolbar.addStretch(1)
        # Hinweis: Cache-Button & „Verwendete Stationen“-Button bewusst entfernt (nur Topbar)
        toolbar.addWidget(self.btn_fetch)
        vbox.addLayout(toolbar)

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

        # Ergebnisse
        self.tab_results = QtWidgets.QWidget()
        self.tabs.addTab(self.tab_results, "📊 Ergebnisse")
        res_layout = QtWidgets.QVBoxLayout(self.tab_results)
        res_layout.setContentsMargins(8, 8, 8, 8)
        res_layout.setSpacing(8)

        # Hinweis oben rechts: erst nach Laden sichtbar
        toprow = QtWidgets.QHBoxLayout()
        toprow.addStretch(1)
        self.free_share_label = QtWidgets.QLabel("")
        self.free_share_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.free_share_label.setStyleSheet("color:#6e6e73; font-weight:600;")
        self.free_share_label.setVisible(False)
        toprow.addWidget(self.free_share_label)
        res_layout.addLayout(toprow)

        # Kacheln
        self.cards_container = QtWidgets.QWidget()
        self.cards_layout = QtWidgets.QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setHorizontalSpacing(12)
        self.cards_layout.setVerticalSpacing(12)
        res_layout.addWidget(self.cards_container)

        # Daily-Tabs je Region
        self.daily_header = QtWidgets.QLabel("Tägliche Mittelwerte je Region")
        res_layout.addWidget(self.daily_header)
        self.daily_tabs = QtWidgets.QTabWidget()
        res_layout.addWidget(self.daily_tabs)

        self.daily_views: Dict[str, QtWidgets.QTableView] = {}
        self.model_daily_by_region: Dict[str, PandasModel] = {}
        for region in REGION_ORDER:
            view = QtWidgets.QTableView()
            view.verticalHeader().setVisible(False)
            view.horizontalHeader().setStretchLastSection(True)
            self.daily_views[region] = view
            self.model_daily_by_region[region] = PandasModel(pd.DataFrame(), formatters={
                "Temperatur (°C)": lambda x: f"{float(x):.1f} °C" if pd.notna(x) else "",
                "Niederschlag (mm)": lambda x: f"{float(x):.2f}" if pd.notna(x) else "",
            })
            view.setModel(self.model_daily_by_region[region])
            self.daily_tabs.addTab(view, region)

        # DFs
        self.df_summary = pd.DataFrame()
        self.df_daily = pd.DataFrame()
        self.df_stations = pd.DataFrame()
        self.df_spark = pd.DataFrame()  # 30 Tage (pro Region)

        # ETA
        self.eta_timer = QtCore.QTimer(self)
        self.eta_timer.setInterval(1000)
        self.eta_timer.timeout.connect(self._tick_eta)
        self._eta_active = False
        self._eta_start_time = None
        self._eta_pred_total_seconds = None
        self._eta_done_steps = 0
        self._eta_total_steps = 0

    # ---------- macOS-Menü ----------
    def _build_menubar(self):
        mb = self.menuBar()
        mb.setNativeMenuBar(True)

        # App-Menü (erstes Menü wird auf macOS zum App-Menü)
        app_menu = mb.addMenu(self.windowTitle())

        act_prefs = QtGui.QAction("Einstellungen …", self)
        act_prefs.setMenuRole(QtGui.QAction.MenuRole.PreferencesRole)
        act_prefs.setShortcut(QtGui.QKeySequence.StandardKey.Preferences)  # ⌘,
        act_prefs.triggered.connect(self.open_color_settings)
        app_menu.addAction(act_prefs)

        act_about = QtGui.QAction("Über LCARSlite Weather and Vacation", self)
        act_about.setMenuRole(QtGui.QAction.MenuRole.AboutRole)
        act_about.triggered.connect(self._show_about)
        app_menu.addAction(act_about)

        act_quit = QtGui.QAction("Beenden", self)
        act_quit.setMenuRole(QtGui.QAction.MenuRole.QuitRole)
        act_quit.setShortcut(QtGui.QKeySequence.StandardKey.Quit)  # ⌘Q
        act_quit.triggered.connect(QtWidgets.QApplication.instance().quit)
        app_menu.addAction(act_quit)

        # Daten-Menü
        data_menu = mb.addMenu("Daten")

        act_stations = QtGui.QAction("Verwendete Stationen …", self)
        act_stations.triggered.connect(self.show_stations_dialog)
        data_menu.addAction(act_stations)

        data_menu.addSeparator()

        # Cache leeren (nur über Topbar)
        act_clear_cache = QtGui.QAction("Cache leeren", self)
        act_clear_cache.triggered.connect(self.on_clear_cache)
        data_menu.addAction(act_clear_cache)

    def _show_about(self):
        QtWidgets.QMessageBox.information(
            self, "Über LCARSlite Weather and Vacation",
            "LCARSlite Weather and Vacation\n\n"
            "Mittelwerte für Temperatur und Niederschlag je Region\n"
            "mit Ferien/Feiertag-Markierungen, Farbanpassung und Sparkline."
        )

    # ---------- Farben-Dialog ----------
    def open_color_settings(self):
        dlg = ColorSettingsDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            spark_map = self._build_spark_map_from_df(self.df_spark)
            self.build_summary_cards(self.df_summary, spark_map)
            self.cards_container.update()

    # ---------- Ferien/Feiertage vorberechnen ----------
    def _update_free_share(self, s: dt.date, e: dt.date):
        vac, hol = union_affected_states(s, e)
        self._states_with_vacation = set(vac)
        self._states_with_holiday = set(hol)
        self._states_free_union = set(vac).union(hol)

        pop = sum(BUNDESLAND_POP.get(bl, 0) for bl in self._states_free_union)
        self._free_share_pct = (pop / TOTAL_POP * 100.0) if TOTAL_POP > 0 else 0.0

    # ---------- Aktionen ----------
    def on_clear_cache(self):
        cache_dir = QtCore.QDir.toNativeSeparators(Settings(cache_disable=False).cache_dir)
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            QtCore.QDir(cache_dir).removeRecursively()
            QtWidgets.QApplication.restoreOverrideCursor()
            self.status_label.setText(f"🧹 Cache geleert: {cache_dir}")
        except Exception as e:
            QtWidgets.QApplication.restoreOverrideCursor()
            QtWidgets.QMessageBox.warning(self, "Fehler", f"Cache konnte nicht gelöscht werden:\n{e}")

    def on_fetch(self):
        if isinstance(self.worker_thread, QtCore.QThread) and self.worker_thread.isRunning():
            return
        try:
            s = parse_german_date(self.start_input.text())
            e = parse_german_date(self.end_input.text())
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, "Datum", str(ex))
            return

        # UI reset
        self.btn_fetch.setEnabled(False)

        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.progress.setFormat("⏳ Starte …")
        self.status_label.setText("Starte Abruf …")

        same_day = s == e
        self.daily_header.setVisible(not same_day)
        self.daily_tabs.setVisible(not same_day)

        self.free_share_label.setVisible(False)

        # ETA
        self._eta_start_time = time.perf_counter()
        self._eta_done_steps = 0
        self._eta_total_steps = 1 + len(REGIONS)
        self._eta_pred_total_seconds = None
        self._eta_active = True
        self.eta_timer.start()

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
        self.worker_thread.finished.connect(lambda: setattr(self, "worker_thread", None))

        self.worker_thread.start()

    @QtCore.pyqtSlot(int, int, str)
    def on_progress(self, done: int, total: int, note: str):
        self._eta_done_steps = done
        if done >= 1:
            elapsed = time.perf_counter() - self._eta_start_time
            avg = elapsed / max(done, 1)
            self._eta_pred_total_seconds = avg * total
        pct = int(done / total * 100)
        eta_text = self._eta_text()
        self.progress.setValue(min(pct, 100))
        self.progress.setFormat(f"{eta_text}  •  {note}")
        self.status_label.setText(note)

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

    # ---------- Ergebnisse ----------
    @QtCore.pyqtSlot(pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame)
    def on_finished(self, summary: pd.DataFrame, daily: pd.DataFrame, stations: pd.DataFrame, spark_30d: pd.DataFrame):
        self._eta_active = False
        self.eta_timer.stop()
        self.progress.setVisible(False)

        self.df_summary = summary.copy()
        self.df_daily = daily.copy()
        self.df_stations = stations.copy()
        self.df_spark = spark_30d.copy()

        self.update_daily_tabs(self.df_daily)

        spark_map = self._build_spark_map_from_df(self.df_spark)
        self.build_summary_cards(self.df_summary, spark_map)

        if not self.df_summary.empty or not self.df_daily.empty:
            self.free_share_label.setText(
                f"Freie Tage/Ferien beeinflussen ≈ {self._free_share_pct:.1f} % der Bevölkerung"
            )
            self.free_share_label.setVisible(True)
        else:
            self.free_share_label.setVisible(False)

        self.status_label.clear()
        self.btn_fetch.setEnabled(True)

    @QtCore.pyqtSlot(str)
    def on_error(self, msg: str):
        self._eta_active = False
        self.eta_timer.stop()
        self.progress.setVisible(False)
        self.btn_fetch.setEnabled(True)
        self.status_label.setText("")
        QtWidgets.QMessageBox.critical(self, "Fehler beim Laden", msg)

    # ---------- Dialoge ----------
    def show_stations_dialog(self):
        if self.df_stations.empty:
            QtWidgets.QMessageBox.information(self, "Stationen", "Keine Stationenliste vorhanden.")
            return
        dlg = StationsDialog(self.df_stations, self)
        dlg.exec()

    # ---------- Tägliche Tabs ----------
    def update_daily_tabs(self, df_daily: pd.DataFrame):
        if df_daily is None or df_daily.empty:
            for region in REGION_ORDER:
                self.model_daily_by_region[region].setDataFrame(pd.DataFrame())
            return
        dd = df_daily.copy()
        if "date" in dd.columns:
            dd["Datum"] = pd.to_datetime(dd["date"], errors="coerce").dt.strftime("%d.%m.%Y")
        if "temp_mean_C" in dd.columns:
            dd["Temperatur (°C)"] = pd.to_numeric(dd["temp_mean_C"], errors="coerce")
        if "precip_mm" in dd.columns:
            dd["Niederschlag (mm)"] = pd.to_numeric(dd["precip_mm"], errors="coerce")
        if "stations_used" in dd.columns:
            dd["berücksichtigte Stationen"] = pd.to_numeric(dd["stations_used"], errors="coerce").astype("Int64")

        cols = ["Datum", "Temperatur (°C)", "Niederschlag (mm)", "berücksichtigte Stationen", "region"]
        dd = dd[[c for c in cols if c in dd.columns]].copy()
        if "Datum" in dd.columns:
            dd["_sort"] = pd.to_datetime(dd["Datum"], format="%d.%m.%Y", errors="coerce")
            dd = dd.sort_values("_sort", ascending=False).drop(columns="_sort")

        for region in REGION_ORDER:
            sub = dd[dd["region"] == region].drop(columns=["region"], errors="ignore")
            self.model_daily_by_region[region].setDataFrame(sub)
            autosize_columns(self.daily_views[region])

    # ---------- Karten ----------
    def _build_spark_map_from_df(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        out: Dict[str, List[float]] = {r: [] for r in REGION_ORDER}
        if df is None or df.empty:
            return out
        dd = df.copy()
        dd = dd[pd.notna(dd.get("region")) & pd.notna(dd.get("date"))]
        dd["date"] = pd.to_datetime(dd["date"], errors="coerce")
        dd = dd.sort_values(["region", "date"])
        for r in REGION_ORDER:
            sub = dd[dd["region"] == r]
            vals = pd.to_numeric(sub.get("temp_mean_C"), errors="coerce").tolist()
            out[r] = [v for v in vals if pd.notna(v)]
        return out

    def build_summary_cards(self, df_summary: pd.DataFrame, spark_map: Dict[str, List[float]]):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        if df_summary is None or df_summary.empty:
            return

        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for idx, region in enumerate(REGION_ORDER):
            sub = df_summary[df_summary["Region"] == region]
            if sub.empty:
                temp_mean, precip_sum, stations_day_max, stations_total = None, None, 0, 0
            else:
                temp_mean = float(sub["Ø Temperatur (°C)"].fillna(pd.NA).iloc[0]) if "Ø Temperatur (°C)" in sub.columns else None
                precip_sum = float(sub["Σ Niederschlag (mm)"].fillna(pd.NA).iloc[0]) if "Σ Niederschlag (mm)" in sub.columns else None
                stations_day_max = int(sub["max. Stationsanzahl/Tag"].fillna(0).iloc[0]) if "max. Stationsanzahl/Tag" in sub.columns else 0
                stations_total = int(sub["berücksichtigte Stationen (Anzahl)"].fillna(0).iloc[0]) if "berücksichtigte Stationen (Anzahl)" in sub.columns else 0

            pop_share = region_population_share(region)
            states_in_region = REGIONS[region]
            vac = set(states_in_region).intersection(self._states_with_vacation)
            hol = set(states_in_region).intersection(self._states_with_holiday)

            card = RegionCard(
                region=region,
                states=states_in_region,
                temp_mean=temp_mean,
                precip_sum=precip_sum,
                stations_day_max=stations_day_max,
                stations_total=stations_total,
                population_share_pct=pop_share,
                vacation_states=vac,
                holiday_states=hol,
                spark_values=spark_map.get(region, []),
            )
            r, c = positions[idx]
            self.cards_layout.addWidget(card, r, c)
