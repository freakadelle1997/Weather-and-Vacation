# dwd_service.py
from __future__ import annotations
import logging
import datetime as dt
from typing import List, Tuple
import pandas as pd
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
    logging.info("get_stations_df(%s, %s)", start_dt, end_dt)
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
    logging.info("get_stations_df -> %d Zeilen", len(df))
    return df

def get_values_df(station_ids: Tuple[str, ...], start_dt: dt.datetime, end_dt: dt.datetime) -> pd.DataFrame:
    logging.info("get_values_df(%d stationen, %s..%s)", len(station_ids), start_dt, end_dt)
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
            logging.info("get_values_df batch success: %d Zeilen", len(vdf))
            return vdf
    except Exception as e:
        logging.warning("get_values_df batch fail: %s", e)

    parts = []
    for sid in station_ids:
        try:
            sel1 = _select_by_ids(req, [sid])
            v1 = _as_pandas(sel1.values.all().df)
            if v1 is not None and len(v1) > 0:
                parts.append(v1); continue
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
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    logging.info("get_values_df stationwise -> %d Zeilen", len(out))
    return out
