# main_window.py
from __future__ import annotations
import re, time, datetime as dt
import pandas as pd
from typing import Dict, Optional
from PyQt6 import QtCore, QtGui, QtWidgets

from regions import REGIONS, REGION_ORDER
from style_utils import mac_default_font, style_line_edit, autosize_columns
from pandas_model import PandasModel
from region_card import RegionCard
from stations_dialog import StationsDialog
from fetch_worker import FetchWorker

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

        self.setWindowTitle("DWD Regions")
        self.resize(1100, 820)
        self.setFont(mac_default_font())

        self.worker_thread: Optional[QtCore.QThread] = None
        self.worker: Optional[FetchWorker] = None
        self.stations_dialog: Optional[StationsDialog] = None

        try:
            from PyQt6.QtWidgets import QStyleFactory
            if "macOS" in QStyleFactory.keys():
                QtWidgets.QApplication.setStyle("macOS")
            else:
                QtWidgets.QApplication.setStyle("Fusion")
        except Exception:
            pass

        central = QtWidgets.QWidget(); self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central); vbox.setContentsMargins(16,16,16,16); vbox.setSpacing(12)

        # Toolbar Zeile 1
        toolbar = QtWidgets.QHBoxLayout(); toolbar.setSpacing(8)
        yesterday = (dt.date.today() - dt.timedelta(days=1)).strftime("%d.%m.%Y")
        self.start_input = QtWidgets.QLineEdit(); self.start_input.setPlaceholderText("TT.MM.JJJJ")
        self.start_input.setText(yesterday); self.start_input.setInputMask("00.00.0000;_"); style_line_edit(self.start_input)
        self.end_input = QtWidgets.QLineEdit(); self.end_input.setPlaceholderText("TT.MM.JJJJ")
        self.end_input.setText(yesterday); self.end_input.setInputMask("00.00.0000;_"); style_line_edit(self.end_input)

        self.start_input.returnPressed.connect(self.on_fetch)
        self.end_input.returnPressed.connect(self.on_fetch)

        self.btn_fetch = QtWidgets.QPushButton("Berechnen"); self.btn_fetch.clicked.connect(self.on_fetch)
        self.btn_cache = QtWidgets.QPushButton("🧹 Cache leeren"); self.btn_cache.clicked.connect(self.on_clear_cache)

        toolbar.addWidget(QtWidgets.QLabel("Start:")); toolbar.addWidget(self.start_input)
        toolbar.addSpacing(8)
        toolbar.addWidget(QtWidgets.QLabel("Ende:")); toolbar.addWidget(self.end_input)
        toolbar.addStretch(1)
        toolbar.addWidget(self.btn_cache); toolbar.addWidget(self.btn_fetch)
        vbox.addLayout(toolbar)

        # Zeile 2: rechtsbündiger Button „Verwendete Stationen“
        row2 = QtWidgets.QHBoxLayout(); row2.addStretch(1)
        self.btn_show_stations = QtWidgets.QPushButton("Verwendete Stationen")
        self.btn_show_stations.clicked.connect(self.show_stations_dialog)
        self.btn_show_stations.setVisible(False)
        row2.addWidget(self.btn_show_stations, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        vbox.addLayout(row2)

        # Progress + Status
        self.progress = QtWidgets.QProgressBar(); self.progress.setTextVisible(True)
        self.progress.setFormat("⏳ Bereit"); self.progress.setMinimum(0); self.progress.setMaximum(100)
        vbox.addWidget(self.progress)
        self.status_label = QtWidgets.QLabel(""); self.status_label.setStyleSheet("color:#6e6e73;")
        vbox.addWidget(self.status_label)

        # EIN Tab: Ergebnisse
        self.tabs = QtWidgets.QTabWidget(); vbox.addWidget(self.tabs)
        self.tab_results = QtWidgets.QWidget(); self.tabs.addTab(self.tab_results, "📊 Ergebnisse")
        res_layout = QtWidgets.QVBoxLayout(self.tab_results); res_layout.setContentsMargins(8,8,8,8); res_layout.setSpacing(8)

        res_layout.addWidget(QtWidgets.QLabel("Zeitraum-Zusammenfassung"))

        # Kacheln
        self.cards_container = QtWidgets.QWidget()
        self.cards_layout = QtWidgets.QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0); self.cards_layout.setHorizontalSpacing(12); self.cards_layout.setVerticalSpacing(12)
        res_layout.addWidget(self.cards_container)

        # Daily-Tabs je Region (initial unsichtbar)
        self.daily_header = QtWidgets.QLabel("Tägliche Mittelwerte je Region"); res_layout.addWidget(self.daily_header)
        self.daily_tabs = QtWidgets.QTabWidget(); res_layout.addWidget(self.daily_tabs)

        self.daily_views: Dict[str, QtWidgets.QTableView] = {}
        self.model_daily_by_region: Dict[str, PandasModel] = {}
        for region in REGION_ORDER:
            view = QtWidgets.QTableView()
            view.verticalHeader().setVisible(False)
            view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            model = PandasModel(pd.DataFrame(columns=["Datum","Temperatur (°C)","Niederschlag (mm)","berücksichtigte Stationen"]), formatters={
                "Datum": lambda x: (pd.to_datetime(x, errors="coerce").strftime("%d.%m.%Y") if pd.notna(x) else ""),
                "Temperatur (°C)": lambda v: f"{float(v):.1f} °C" if pd.notna(v) else "",
                "Niederschlag (mm)": lambda v: f"{float(v):.2f}" if pd.notna(v) else "",
                "berücksichtigte Stationen": lambda v: f"{int(v)}" if pd.notna(v) else "",
            })
            view.setModel(model)
            self.daily_views[region] = view
            self.model_daily_by_region[region] = model
            self.daily_tabs.addTab(view, region)

        export_row = QtWidgets.QHBoxLayout(); export_row.addStretch(1)
        self.btn_export_daily = QtWidgets.QPushButton("CSV exportieren (tägliche Werte)")
        self.btn_export_daily.clicked.connect(self.export_daily_csv)
        export_row.addWidget(self.btn_export_daily); res_layout.addLayout(export_row)

        # Initial ausblenden
        self.daily_header.setVisible(False); self.daily_tabs.setVisible(False); self.btn_export_daily.setVisible(False)

        # Daten-Halter
        self.df_summary = pd.DataFrame(); self.df_daily = pd.DataFrame(); self.df_stations = pd.DataFrame()

        # ETA
        self.eta_timer = QtCore.QTimer(self); self.eta_timer.setInterval(1000)
        self.eta_timer.timeout.connect(self._tick_eta)
        self._eta_active = False; self._eta_start_time = None
        self._eta_pred_total_seconds = None; self._eta_done_steps = 0; self._eta_total_steps = 0

    # ---- Layout Helper ----
    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        super().resizeEvent(e)
        self.update_stations_button_width()

    def update_stations_button_width(self):
        try:
            total = self.btn_cache.sizeHint().width() + self.btn_fetch.sizeHint().width()
            spacing = 8
            self.btn_show_stations.setFixedWidth(max(220, total + spacing))
        except Exception:
            pass

    # ---- UI Aktionen ----
    def show_stations_dialog(self):
        if self.df_stations.empty:
            QtWidgets.QMessageBox.information(self, "Stationen", "Keine Stationenliste vorhanden.")
            return
        if self.stations_dialog is None:
            self.stations_dialog = StationsDialog(self)
        self.stations_dialog.set_dataframe(
            self.df_stations.sort_values(["region", "state", "name", "station_id"])
        )
        self.stations_dialog.show(); self.stations_dialog.raise_(); self.stations_dialog.activateWindow()

    def on_clear_cache(self):
        from wetterdienst.settings import Settings
        from pathlib import Path
        import shutil
        cache_dir = Path(Settings(cache_disable=False).cache_dir).expanduser()
        try:
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
            self.status_label.setStyleSheet("color:#2d7d46;")
            self.status_label.setText(f"🧹 Cache geleert: {cache_dir}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Fehler", f"Cache konnte nicht gelöscht werden:\n{e}")

    def _read_dates(self) -> tuple[dt.date, dt.date]:
        s_text = self.start_input.text().strip()
        e_text = self.end_input.text().strip()
        s_date = parse_german_date(s_text)
        e_date = parse_german_date(e_text)
        if e_date < s_date:
            raise ValueError("Ende darf nicht vor Start liegen.")
        return s_date, e_date

    def on_fetch(self):
        t = getattr(self, "worker_thread", None)
        if isinstance(t, QtCore.QThread) and t.isRunning():
            return
        try:
            s, e = self._read_dates()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(self, "Ungültiges Datum", str(ex))
            return

        try:
            self.status_label.setStyleSheet("color:#6e6e73;")
            self.status_label.setText("⏳ Starte Ladevorgang …")
            self.progress.setVisible(True); self.progress.setValue(0); self.progress.setFormat("⏳ Lade …")
            self.btn_show_stations.setVisible(False)

            same_day = (s == e)
            show_daily = not same_day
            self.daily_header.setVisible(show_daily); self.daily_tabs.setVisible(show_daily); self.btn_export_daily.setVisible(show_daily)

            self._eta_start_time = time.perf_counter()
            self._eta_done_steps = 0; self._eta_total_steps = 1 + len(REGIONS)
            self._eta_pred_total_seconds = None; self._eta_active = True; self.eta_timer.start()

            self.worker_thread = QtCore.QThread(self)
            self.worker = FetchWorker(s, e)
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

            self.btn_fetch.setEnabled(False); self.btn_cache.setEnabled(False)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"Start des Ladevorgangs fehlgeschlagen:\n{e}")
            self.btn_fetch.setEnabled(True); self.btn_cache.setEnabled(True)
            self.progress.setVisible(False); self._eta_active = False; self.eta_timer.stop()

    def on_thread_finished(self):
        self.worker_thread = None; self.worker = None

    @QtCore.pyqtSlot(int, int, str)
    def on_progress(self, done: int, total: int, note: str):
        self.status_label.setStyleSheet("color:#6e6e73;")
        self.status_label.setText(note)
        self._eta_done_steps = done
        if done >= 1:
            elapsed = time.perf_counter() - self._eta_start_time
            avg = elapsed / max(done, 1)
            self._eta_pred_total_seconds = avg * total
        pct = int(done / total * 100)
        eta_text = self._eta_text()
        self.progress.setValue(min(pct, 100))
        self.progress.setFormat(f"{eta_text}  •  {note}")

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

    @QtCore.pyqtSlot(pd.DataFrame, pd.DataFrame, pd.DataFrame)
    def on_finished(self, summary: pd.DataFrame, daily: pd.DataFrame, stations: pd.DataFrame):
        self._eta_active = False; self.eta_timer.stop(); self.progress.setVisible(False)

        self.df_summary = summary.copy()
        self.df_daily = daily.copy()
        self.df_stations = stations.copy()

        # Kacheln
        self.build_summary_cards(self.df_summary)

        # Daily je Region füllen (immer), Anzeige ggf. versteckt
        if not self.df_daily.empty:
            if "temp_mean_C" in self.df_daily.columns:
                self.df_daily = self.df_daily.rename(columns={"temp_mean_C": "Temperatur (°C)"})
            for region in REGION_ORDER:
                sub = self.df_daily[self.df_daily["region"] == region].copy()
                if sub.empty:
                    pretty = pd.DataFrame(columns=["Datum", "Temperatur (°C)", "Niederschlag (mm)", "berücksichtigte Stationen"])
                else:
                    sub = sub.rename(columns={
                        "date": "Datum",
                        "precip_mm": "Niederschlag (mm)",
                        "stations_used": "berücksichtigte Stationen",
                    })
                    sub["Datum"] = pd.to_datetime(sub["Datum"], errors="coerce").dt.tz_localize(None)
                    pretty = sub[["Datum", "Temperatur (°C)", "Niederschlag (mm)", "berücksichtigte Stationen"]] \
                        .sort_values("Datum", ascending=False)
                self.model_daily_by_region[region].setDataFrame(pretty)
                autosize_columns(self.daily_views[region])

        # Stations-Button freigeben, wenn Daten da
        has_any_data = (not self.df_summary.empty) or (not self.df_daily.empty) or (not self.df_stations.empty)
        self.btn_show_stations.setVisible(has_any_data)
        if has_any_data:
            QtCore.QTimer.singleShot(0, self.update_stations_button_width)

        # Status
        self.status_label.setStyleSheet("color:#2d7d46;" if has_any_data else "color:#6e6e73;")
        self.status_label.setText("Fertig." if has_any_data else "ℹ️ Keine Daten im Zeitraum gefunden.")

        self.btn_fetch.setEnabled(True); self.btn_cache.setEnabled(True)

    def build_summary_cards(self, df: pd.DataFrame):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w: w.setParent(None)

        if df is None or df.empty:
            placeholder = QtWidgets.QLabel("Keine Zusammenfassung verfügbar.")
            placeholder.setStyleSheet("color:#6e6e73;")
            placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addWidget(placeholder, 0, 0, 1, 1)
            return

        df_sorted = df.copy()
        df_sorted["__order__"] = df_sorted["Region"].apply(lambda r: REGION_ORDER.index(r) if r in REGION_ORDER else 999)
        df_sorted = df_sorted.sort_values("__order__")

        col_count = 2
        for idx, (_, row) in enumerate(df_sorted.iterrows()):
            region = str(row.get("Region", ""))
            tmean = pd.to_numeric(row.get("Ø Temperatur (°C)"), errors="coerce")
            psum  = pd.to_numeric(row.get("Σ Niederschlag (mm)"), errors="coerce")
            smax  = pd.to_numeric(row.get("max. Stationsanzahl/Tag"), errors="coerce")
            stot  = pd.to_numeric(row.get("berücksichtigte Stationen (Anzahl)"), errors="coerce")
            smax_i = int(smax) if pd.notna(smax) else 0
            stot_i = int(stot) if pd.notna(stot) else 0

            card = RegionCard(region=region, states=REGIONS.get(region, []),
                              temp_mean=(float(tmean) if pd.notna(tmean) else None),
                              precip_sum=(float(psum) if pd.notna(psum) else None),
                              stations_day_max=smax_i, stations_total=stot_i)
            r = idx // col_count; c = idx % col_count
            self.cards_layout.addWidget(card, r, c)
        for c in range(col_count):
            self.cards_layout.setColumnStretch(c, 1)

    @QtCore.pyqtSlot(str)
    def on_error(self, msg: str):
        self._eta_active = False; self.eta_timer.stop(); self.progress.setVisible(False)
        self.btn_fetch.setEnabled(True); self.btn_cache.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Fehler beim Laden", msg)

    # Export
    def export_daily_csv(self):
        rows = []
        for region in REGION_ORDER:
            df = self.model_daily_by_region[region].dataframe()
            if df.empty: continue
            tmp = df.copy()
            tmp["Datum"] = pd.to_datetime(tmp["Datum"], errors="coerce").dt.strftime("%d.%m.%Y")
            tmp.insert(0, "Region", region)
            rows.append(tmp)
        if not rows:
            QtWidgets.QMessageBox.information(self, "Export", "Keine täglichen Werte vorhanden."); return
        out = pd.concat(rows, ignore_index=True)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "CSV speichern", "dwd_regions_daily.csv", "CSV (*.csv)")
        if path: out.to_csv(path, index=False)
