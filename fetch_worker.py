# fetch_worker.py
from __future__ import annotations

import datetime as dt
from typing import List, Tuple, Optional

import pandas as pd
from PyQt6 import QtCore

from wetterdienst.settings import Settings
from wetterdienst.provider.dwd.observation import DwdObservationRequest


# ---------- Utils ----------
def _as_pandas(df_like):
    """Konvertiere Polars → Pandas, falls nötig."""
    try:
        if df_like.__class__.__module__.startswith("polars"):
            return df_like.to_pandas()
    except Exception:
        pass
    return df_like


def _select_by_ids(req: DwdObservationRequest, station_ids: List[str]):
    """Kompatibel zu verschiedenen wetterdienst-Versionen."""
    try:
        return req.filter_by_station_id(station_id=tuple(station_ids))
    except AttributeError:
        stations_all = req.all()
        return stations_all.filter_by_station_id(station_id=tuple(station_ids))


def get_stations_df(start_dt: dt.datetime, end_dt: dt.datetime) -> pd.DataFrame:
    """Stationen (Meta) laden, die in [start,end] verfügbar sind."""
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


def get_values_df(
    station_ids: Tuple[str, ...],
    start_dt: dt.datetime,
    end_dt: dt.datetime,
) -> pd.DataFrame:
    """Werte robust laden: Batch; Fallback stationweise (mit/ohne Cache)."""
    # 1) Batch mit Cache
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

    # 2) stationweise, erst mit Cache, dann ohne Cache
    parts = []
    for sid in station_ids:
        # mit Cache
        try:
            sel1 = _select_by_ids(req, [sid])
            v1 = _as_pandas(sel1.values.all().df)
            if v1 is not None and len(v1) > 0:
                parts.append(v1)
                continue
        except Exception:
            pass
        # ohne Cache
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


# ---------- Worker ----------
class FetchWorker(QtCore.QObject):
    """
    Gibt jetzt 4 DataFrames zurück:
      - summary_all   : Zusammenfassung pro Region (Zeitraum)
      - daily_all     : Tägliche Mittelwerte pro Region (nur gewählter Zeitraum)
      - stations_all  : verwendete Stationen (Meta + per-Station-Aggregate)
      - spark_all     : Tägliche Temp-Mittel pro Region für die letzten 30 Tage (endbezogen)
    """
    progress = QtCore.pyqtSignal(int, int, str)
    finished = QtCore.pyqtSignal(pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame)
    error = QtCore.pyqtSignal(str)

    def __init__(self, start_date: dt.date, end_date: dt.date, regions_map: dict):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.regions_map = regions_map  # {"Nord":[...], ...}

    @QtCore.pyqtSlot()
    def run(self):
        try:
            start_dt_py = dt.datetime.combine(self.start_date, dt.time.min)
            end_dt_py = dt.datetime.combine(self.end_date, dt.time.max)
            start_ts = pd.Timestamp(start_dt_py)
            end_ts = pd.Timestamp(end_dt_py)

            # Sparkline-Fenster: IMMER letzte 30 Tage relativ zum Enddatum
            spark_start_dt = (dt.datetime.combine(self.end_date, dt.time.min) - dt.timedelta(days=29))

            # Stationslisten für Zeitraum & Sparkline
            self.progress.emit(0, 1, "Stationsliste (Zeitraum) laden …")
            sdf_main = get_stations_df(start_dt_py, end_dt_py)
            self.progress.emit(1, 3, "Stationsliste (Sparkline) laden …")
            sdf_spark = get_stations_df(spark_start_dt, end_dt_py)

            region_summaries = []
            daily_tables = []
            used_station_meta = []
            spark_tables = []

            # Fortschrittszählung: pro Region 2 Schritte (Main + Spark)
            total_regions = len(self.regions_map) * 2 + 2  # +2 für die beiden Stationstasks oben
            done = 2

            for region_name, states in self.regions_map.items():
                # ----- Haupt-Zeitraum -----
                self.progress.emit(done, total_regions, f"Werte {region_name} (Zeitraum) …")
                sdf_region = sdf_main[sdf_main["state"].isin(states)].copy()
                station_ids = sdf_region["station_id"].dropna().unique().tolist()

                if station_ids:
                    vdf = get_values_df(tuple(station_ids), start_dt_py, end_dt_py)
                else:
                    vdf = pd.DataFrame()

                if vdf is not None and len(vdf) > 0:
                    if "date" in vdf.columns:
                        vdf["date"] = pd.to_datetime(vdf["date"], utc=True, errors="coerce").dt.tz_convert(None)
                    if "station_id" in vdf.columns:
                        vdf["station_id"] = vdf["station_id"].astype(str)

                    # Long -> Wide
                    wide = (
                        vdf.pivot_table(
                            values="value",
                            index=["date", "station_id"],
                            columns="parameter",
                            aggfunc="mean",
                        ).reset_index()
                    )

                    # tägliche Region-Mittel
                    daily_mean = (
                        wide.groupby("date", as_index=False).agg(
                            temp_mean_C=("temperature_air_mean_2m", "mean"),
                            precip_mm=("precipitation_height", "mean"),
                            stations_used=("station_id", "nunique"),
                        )
                    )
                    daily_mean["region"] = region_name
                    daily_tables.append(daily_mean)

                    # per-Station-Aggregate (über Zeitraum)
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

                    # Zusammenfassung
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

                    # Metadaten + Werte
                    meta_cols = ["station_id", "name", "state", "height", "latitude", "longitude", "start_date", "end_date"]
                    meta_base = (
                        sdf_region[meta_cols].drop_duplicates(subset=["station_id"])
                        if all(c in sdf_region.columns for c in meta_cols)
                        else sdf_region.drop_duplicates(subset=["station_id"])
                    )
                    meta_enriched = meta_base.merge(per_station_agg, on="station_id", how="left").assign(region=region_name)
                    used_station_meta.append(meta_enriched[["region"] + [c for c in meta_enriched.columns if c != "region"]])

                done += 1
                self.progress.emit(done, total_regions, f"{region_name}: Zeitraum OK")

                # ----- Sparkline (immer 30 Tage) -----
                self.progress.emit(done, total_regions, f"Werte {region_name} (Sparkline 30 Tage) …")
                sdf_region_sp = sdf_spark[sdf_spark["state"].isin(states)].copy()
                station_ids_sp = sdf_region_sp["station_id"].dropna().unique().tolist()

                spark_df_region = pd.DataFrame(columns=["date", "temp_mean_C", "region"])
                if station_ids_sp:
                    vdf_sp = get_values_df(tuple(station_ids_sp), spark_start_dt, end_dt_py)
                    if vdf_sp is not None and len(vdf_sp) > 0:
                        if "date" in vdf_sp.columns:
                            vdf_sp["date"] = pd.to_datetime(vdf_sp["date"], utc=True, errors="coerce").dt.tz_convert(None)
                        if "station_id" in vdf_sp.columns:
                            vdf_sp["station_id"] = vdf_sp["station_id"].astype(str)

                        wide_sp = (
                            vdf_sp.pivot_table(
                                values="value",
                                index=["date", "station_id"],
                                columns="parameter",
                                aggfunc="mean",
                            ).reset_index()
                        )
                        if "temperature_air_mean_2m" in wide_sp.columns:
                            dm = (
                                wide_sp.groupby("date", as_index=False)["temperature_air_mean_2m"]
                                .mean()
                                .rename(columns={"temperature_air_mean_2m": "temp_mean_C"})
                            )
                            dm["region"] = region_name
                            # Nur 30 Tage (sicherheitshalber)
                            dm = dm.sort_values("date").tail(30)
                            spark_df_region = dm[["date", "temp_mean_C", "region"]]

                spark_tables.append(spark_df_region)
                done += 1
                self.progress.emit(done, total_regions, f"{region_name}: Sparkline OK")

            # Ergebnisse zusammenführen
            summary_all = pd.concat(region_summaries, ignore_index=True) if region_summaries else pd.DataFrame()
            daily_all = pd.concat(daily_tables, ignore_index=True) if daily_tables else pd.DataFrame()
            stations_all = pd.concat(used_station_meta, ignore_index=True) if used_station_meta else pd.DataFrame()
            spark_all = pd.concat(spark_tables, ignore_index=True) if spark_tables else pd.DataFrame()

            self.finished.emit(summary_all, daily_all, stations_all, spark_all)

        except Exception as e:
            self.error.emit(str(e))
