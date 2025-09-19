# fetch_worker.py
from __future__ import annotations
import datetime as dt
import pandas as pd
from PyQt6 import QtCore
from typing import Dict, List
from regions import REGIONS
from dwd_service import get_stations_df, get_values_df

class FetchWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(int, int, str)
    finished = QtCore.pyqtSignal(pd.DataFrame, pd.DataFrame, pd.DataFrame)
    error = QtCore.pyqtSignal(str)

    def __init__(self, start_date: dt.date, end_date: dt.date):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date

    @QtCore.pyqtSlot()
    def run(self):
        try:
            start_dt_py = dt.datetime.combine(self.start_date, dt.time.min)
            end_dt_py = dt.datetime.combine(self.end_date, dt.time.max)
            start_ts = pd.Timestamp(start_dt_py)
            end_ts = pd.Timestamp(end_dt_py)

            total_steps = 1 + len(REGIONS)
            done = 0
            self.progress.emit(done, total_steps, "Stationsliste laden…")

            sdf = get_stations_df(start_dt_py, end_dt_py)
            sdf = sdf[(sdf["end_date"] >= start_ts) & (sdf["start_date"] <= end_ts)].copy()

            done += 1
            self.progress.emit(done, total_steps, "Stationsliste geladen")

            region_summaries, daily_tables, used_station_meta = [], [], []

            for region_name, states in REGIONS.items():
                self.progress.emit(done, total_steps, f"Werte für {region_name} laden…")

                sdf_region = sdf[sdf["state"].isin(states)].copy()
                station_ids = sdf_region["station_id"].dropna().unique().tolist()
                if not station_ids:
                    done += 1
                    self.progress.emit(done, total_steps, f"{region_name} übersprungen (keine Stationen)")
                    continue

                vdf = get_values_df(tuple(station_ids), start_dt_py, end_dt_py)
                if vdf is None or len(vdf) == 0:
                    done += 1
                    self.progress.emit(done, total_steps, f"{region_name} ohne Werte")
                    continue

                if "date" in vdf.columns:
                    vdf["date"] = pd.to_datetime(vdf["date"], utc=True, errors="coerce").dt.tz_convert(None)
                if "station_id" in vdf.columns:
                    vdf["station_id"] = vdf["station_id"].astype(str)

                wide = vdf.pivot_table(
                    values="value", index=["date", "station_id"], columns="parameter", aggfunc="mean"
                ).reset_index()

                # Per-Station-Aggregate
                temp_mean = (wide.groupby("station_id")["temperature_air_mean_2m"].mean()
                             .rename("temp_mean_C_period") if "temperature_air_mean_2m" in wide.columns
                             else pd.Series(dtype="float"))
                precip_sum = (wide.groupby("station_id")["precipitation_height"].sum()
                              .rename("precip_sum_mm_period") if "precipitation_height" in wide.columns
                              else pd.Series(dtype="float"))
                temp_days = (wide.dropna(subset=["temperature_air_mean_2m"]).groupby("station_id")["date"].nunique()
                             .rename("temp_days") if "temperature_air_mean_2m" in wide.columns
                             else pd.Series(dtype="int64"))
                precip_days = (wide.dropna(subset=["precipitation_height"]).groupby("station_id")["date"].nunique()
                               .rename("precip_days") if "precipitation_height" in wide.columns
                               else pd.Series(dtype="int64"))
                date_min = wide.groupby("station_id")["date"].min().rename("first_date")
                date_max = wide.groupby("station_id")["date"].max().rename("last_date")
                per_station_agg = pd.concat(
                    [temp_mean, precip_sum, temp_days, precip_days, date_min, date_max], axis=1
                ).reset_index()

                # Daily region mean
                daily_mean = wide.groupby("date", as_index=False).agg(
                    temp_mean_C=("temperature_air_mean_2m", "mean"),
                    precip_mm=("precipitation_height", "mean"),
                    stations_used=("station_id", "nunique"),
                )
                daily_mean["region"] = region_name
                daily_tables.append(daily_mean)

                # Summary row
                summary = pd.DataFrame(
                    {
                        "Region": [region_name],
                        "Ø Temperatur (°C)": [pd.to_numeric(daily_mean["temp_mean_C"], errors="coerce").mean()],
                        "Σ Niederschlag (mm)": [pd.to_numeric(daily_mean["precip_mm"], errors="coerce").sum()],
                        "max. Stationsanzahl/Tag": [int(pd.to_numeric(daily_mean["stations_used"], errors="coerce").max() or 0)],
                        "berücksichtigte Stationen (Anzahl)": [len(station_ids)],
                    }
                )
                region_summaries.append(summary)

                # Stationen-Metadaten + Werte
                meta_cols = ["station_id", "name", "state", "height", "latitude", "longitude", "start_date", "end_date"]
                meta_base = (sdf_region[meta_cols].drop_duplicates(subset=["station_id"])
                             if all(c in sdf_region.columns for c in meta_cols)
                             else sdf_region.drop_duplicates(subset=["station_id"]))
                meta_enriched = meta_base.merge(per_station_agg, on="station_id", how="left").assign(region=region_name)
                used_station_meta.append(meta_enriched[["region"] + [c for c in meta_enriched.columns if c != "region"]])

                done += 1
                self.progress.emit(done, total_steps, f"{region_name} fertig")

            if region_summaries:
                summary_all = pd.concat(region_summaries, ignore_index=True)
                daily_all = pd.concat(daily_tables, ignore_index=True)
                stations_all = pd.concat(used_station_meta, ignore_index=True) if used_station_meta else pd.DataFrame()
            else:
                summary_all = pd.DataFrame(); daily_all = pd.DataFrame(); stations_all = pd.DataFrame()

            self.finished.emit(summary_all, daily_all, stations_all)

        except BaseException as e:
            self.error.emit(str(e))
