# fetch_worker.py
from __future__ import annotations
from typing import Tuple, List
import datetime as dt
import pandas as pd
from PyQt6 import QtCore

from regions import REGIONS
from wetterdienst.settings import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest

def _as_pandas(df_like):
    try:
        if df_like.__class__.__module__.startswith("polars"):
            return df_like.to_pandas()
    except Exception:
        pass
    return df_like

def _select_by_ids(req: DwdObservationRequest, station_ids: List[str]):
    try:
        return req.filter_by_station_id(station_id=tuple(station_ids))
    except AttributeError:
        stations_all = req.all()
        return stations_all.filter_by_station_id(station_id=tuple(station_ids))

def get_stations_df(start_dt: dt.datetime, end_dt: dt.datetime) -> pd.DataFrame:
    req = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=start_dt,
        end_date=end_dt,
        settings=Settings(cache_disable=False),
    )
    df = _as_pandas(req.all().df).copy()
    for c in ("start_date", "end_date"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, errors="coerce").dt.tz_convert(None)
    if "station_id" in df.columns:
        df["station_id"] = df["station_id"].astype(str)
    return df

def get_values_df(station_ids: Tuple[str, ...], start_dt: dt.datetime, end_dt: dt.datetime) -> pd.DataFrame:
    req = DwdObservationRequest(
        parameters=[
            ("daily", "climate_summary", "temperature_air_mean_2m"),
            ("daily", "climate_summary", "precipitation_height"),
        ],
        start_date=start_dt,
        end_date=end_dt,
        settings=Settings(cache_disable=False),
    )
    try:
        sel = _select_by_ids(req, list(station_ids))
        vdf = _as_pandas(sel.values.all().df)
        if vdf is not None and len(vdf) > 0:
            return vdf
    except Exception:
        pass

    parts = []
    for sid in station_ids:
        try:
            sel1 = _select_by_ids(req, [sid])
            v1 = _as_pandas(sel1.values.all().df)
            if v1 is not None and len(v1) > 0:
                parts.append(v1)
                continue
        except Exception:
            pass
        try:
            req_nc = DwdObservationRequest(
                parameters=[
                    ("daily", "climate_summary", "temperature_air_mean_2m"),
                    ("daily", "climate_summary", "precipitation_height"),
                ],
                start_date=start_dt,
                end_date=end_dt,
                settings=Settings(cache_disable=True),
            )
            sel2 = _select_by_ids(req_nc, [sid])
            v2 = _as_pandas(sel2.values.all().df)
            if v2 is not None and len(v2) > 0:
                parts.append(v2)
        except Exception:
            pass

    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

class FetchWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(int, int, str)   # done, total, note
    # Wichtig: breit als 'object' typisieren -> robust beim Import
    finished = QtCore.pyqtSignal(object, object, object, object)  # summary, daily, stations, spark
    error = QtCore.pyqtSignal(str)

    def __init__(self, start_date, end_date):
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
            spark_start_dt = end_dt_py - dt.timedelta(days=29)

            total_steps = 1 + 2 * len(REGIONS)
            done = 0
            self.progress.emit(done, total_steps, "Stationsliste laden…")

            sdf = get_stations_df(start_dt_py, end_dt_py)
            sdf = sdf[(sdf["end_date"] >= start_ts) & (sdf["start_date"] <= end_ts)].copy()

            done += 1
            self.progress.emit(done, total_steps, "Stationsliste geladen")

            region_summaries, daily_tables, used_station_meta, spark_tables = [], [], [], []

            for region_name, states in REGIONS.items():
                # --- Werte im gewählten Zeitraum
                self.progress.emit(done, total_steps, f"Werte für {region_name} laden…")
                sdf_region = sdf[sdf["state"].isin(states)].copy()
                station_ids = sdf_region["station_id"].dropna().unique().tolist()

                if not station_ids:
                    done += 1
                    self.progress.emit(done, total_steps, f"{region_name} übersprungen (keine Stationen)")
                    self.progress.emit(done, total_steps, f"Sparkline 30 Tage für {region_name} … (keine Stationen)")
                    done += 1
                    self.progress.emit(done, total_steps, f"{region_name} fertig")
                    continue

                vdf = get_values_df(tuple(station_ids), start_dt_py, end_dt_py)
                if vdf is None or len(vdf) == 0:
                    done += 1
                    self.progress.emit(done, total_steps, f"{region_name} ohne Werte")
                else:
                    if "date" in vdf.columns:
                        vdf["date"] = pd.to_datetime(vdf["date"], utc=True, errors="coerce").dt.tz_convert(None)
                    if "station_id" in vdf.columns:
                        vdf["station_id"] = vdf["station_id"].astype(str)

                    wide = (
                        vdf.pivot_table(
                            values="value",
                            index=["date", "station_id"],
                            columns="parameter",
                            aggfunc="mean",
                        ).reset_index()
                    )

                    temp_days = (
                        wide.dropna(subset=["temperature_air_mean_2m"])
                        .groupby("station_id")["date"].nunique().rename("temp_days")
                        if "temperature_air_mean_2m" in wide.columns else pd.Series(dtype="int64")
                    )
                    precip_days = (
                        wide.dropna(subset=["precipitation_height"])
                        .groupby("station_id")["date"].nunique().rename("precip_days")
                        if "precipitation_height" in wide.columns else pd.Series(dtype="int64")
                    )
                    temp_mean = (
                        wide.groupby("station_id")["temperature_air_mean_2m"].mean().rename("temp_mean_C_period")
                        if "temperature_air_mean_2m" in wide.columns else pd.Series(dtype="float")
                    )
                    precip_sum = (
                        wide.groupby("station_id")["precipitation_height"].sum().rename("precip_sum_mm_period")
                        if "precipitation_height" in wide.columns else pd.Series(dtype="float")
                    )
                    date_min = wide.groupby("station_id")["date"].min().rename("first_date")
                    date_max = wide.groupby("station_id")["date"].max().rename("last_date")
                    per_station_agg = pd.concat(
                        [temp_mean, precip_sum, temp_days, precip_days, date_min, date_max], axis=1
                    ).reset_index()

                    daily_mean = (
                        wide.groupby("date", as_index=False).agg(
                            temp_mean_C=("temperature_air_mean_2m", "mean"),
                            precip_mm=("precipitation_height", "mean"),
                            stations_used=("station_id", "nunique"),
                        )
                    )
                    daily_mean["region"] = region_name
                    daily_tables.append(daily_mean)

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

                    meta_cols = ["station_id", "name", "state", "height", "latitude", "longitude", "start_date", "end_date"]
                    meta_base = (
                        sdf_region[meta_cols].drop_duplicates(subset=["station_id"])
                        if all(c in sdf_region.columns for c in meta_cols)
                        else sdf_region.drop_duplicates(subset=["station_id"])
                    )
                    meta_enriched = meta_base.merge(per_station_agg, on="station_id", how="left").assign(region=region_name)
                    used_station_meta.append(meta_enriched[["region"] + [c for c in meta_enriched.columns if c != "region"]])

                    done += 1
                    self.progress.emit(done, total_steps, f"{region_name} Werte fertig")

                # --- Sparkline (immer 30 Tage bis Enddatum) ---
                self.progress.emit(done, total_steps, f"Sparkline 30 Tage für {region_name} …")
                vdf_spark = get_values_df(tuple(station_ids), spark_start_dt, end_dt_py)
                if vdf_spark is not None and len(vdf_spark) > 0:
                    if "date" in vdf_spark.columns:
                        vdf_spark["date"] = pd.to_datetime(vdf_spark["date"], utc=True, errors="coerce").dt.tz_convert(None)
                    if "station_id" in vdf_spark.columns:
                        vdf_spark["station_id"] = vdf_spark["station_id"].astype(str)

                    wide_s = (
                        vdf_spark.pivot_table(
                            values="value",
                            index=["date", "station_id"],
                            columns="parameter",
                            aggfunc="mean",
                        ).reset_index()
                    )
                    if "temperature_air_mean_2m" in wide_s.columns:
                        spark_daily = (
                            wide_s.groupby("date", as_index=False)
                            .agg(temp_mean_C=("temperature_air_mean_2m", "mean"))
                            .assign(region=region_name)
                        )
                        spark_tables.append(spark_daily)

                done += 1
                self.progress.emit(done, total_steps, f"{region_name} Sparkline fertig")

            summary_all = pd.concat(region_summaries, ignore_index=True) if region_summaries else pd.DataFrame()
            daily_all = pd.concat(daily_tables, ignore_index=True) if daily_tables else pd.DataFrame()
            stations_all = pd.concat(used_station_meta, ignore_index=True) if used_station_meta else pd.DataFrame()
            spark_all = pd.concat(spark_tables, ignore_index=True) if spark_tables else pd.DataFrame()

            self.finished.emit(summary_all, daily_all, stations_all, spark_all)

        except Exception as e:
            self.error.emit(str(e))
