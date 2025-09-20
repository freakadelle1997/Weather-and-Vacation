# holidays_utils.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple, Set, Dict, Optional, Iterable
import datetime as dt
import pandas as pd

# --------- Datenquellen (nur Lesen) ---------
HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

# Optional: exakte Dateien per Env übersteuern (wir lesen nur!)
ENV_FERIEN = os.getenv("WETTERDATEN_FERIEN_PATH")
ENV_FEIERTAGE = os.getenv("WETTERDATEN_FEIERTAGE_PATH")

# Gängige Kandidaten-Dateinamen (wir nehmen die erste, die existiert)
FERIEN_CANDIDATES = [
    "ferien.csv",
    "schulferien.csv",
    "ferien_de.csv",
    "ferien_daten.csv",
    "ferien.json",
    "schulferien.json",
]
FEIERTAGE_CANDIDATES = [
    "feiertage.csv",
    "feiertage_de.csv",
    "holidays.csv",
    "feiertage.json",
    "holidays.json",
]

# Code → Langname Mapping
STATE_CODE_TO_NAME: Dict[str, str] = {
    "BW": "Baden-Württemberg",
    "BY": "Bayern",
    "BE": "Berlin",
    "BB": "Brandenburg",
    "HB": "Bremen",
    "HH": "Hamburg",
    "HE": "Hessen",
    "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen",
    "NW": "Nordrhein-Westfalen",
    "RP": "Rheinland-Pfalz",
    "SL": "Saarland",
    "SN": "Sachsen",
    "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein",
    "TH": "Thüringen",
}
STATE_NAME_TO_CODE: Dict[str, str] = {v: k for k, v in STATE_CODE_TO_NAME.items()}
STATE_TO_CODE = STATE_NAME_TO_CODE
CODE_TO_STATE = STATE_CODE_TO_NAME


def _norm_state(value: Optional[str]) -> Optional[str]:
    """Normalisiert 'BW' oder 'Baden Wuerttemberg' → 'Baden-Württemberg'."""
    if not value:
        return None
    v = str(value).strip()
    # Code?
    if v.upper() in STATE_CODE_TO_NAME:
        return STATE_CODE_TO_NAME[v.upper()]
    # tolerant Langnamen matchen (Bindestriche/Leerzeichen/Umlaute)
    key = (
        v.lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("ä", "a")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ß", "ss")
    )
    for name in STATE_NAME_TO_CODE:
        nkey = (
            name.lower()
            .replace(" ", "")
            .replace("-", "")
            .replace("ä", "a")
            .replace("ö", "o")
            .replace("ü", "u")
            .replace("ß", "ss")
        )
        if key == nkey:
            return name
    return None


def _first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for p in paths:
        if p and p.exists():
            return p
    return None


def _candidate_paths(base: Path, names: Iterable[str]) -> Iterable[Path]:
    for n in names:
        yield base / n


def _read_ferien_df() -> pd.DataFrame:
    paths = []
    if ENV_FERIEN:
        paths.append(Path(ENV_FERIEN))
    paths.extend(_candidate_paths(DATA_DIR, FERIEN_CANDIDATES))
    paths.extend(_candidate_paths(HERE, FERIEN_CANDIDATES))

    fp = _first_existing(paths)
    if not fp:
        return pd.DataFrame(columns=["state", "start_date", "end_date"])

    if fp.suffix.lower() == ".json":
        try:
            df = pd.read_json(fp)
        except Exception:
            return pd.DataFrame(columns=["state", "start_date", "end_date"])
        colmap = {}
        for cand in ["state", "bundesland", "land", "code", "state_code"]:
            if cand in df.columns:
                colmap["state"] = cand; break
        for cand in ["start_date", "start", "von", "beginn"]:
            if cand in df.columns:
                colmap["start_date"] = cand; break
        for cand in ["end_date", "ende", "bis", "schluss"]:
            if cand in df.columns:
                colmap["end_date"] = cand; break
        df = df.rename(columns={v: k for k, v in colmap.items() if k != v})
    else:
        try:
            df = pd.read_csv(fp)
        except Exception:
            return pd.DataFrame(columns=["state", "start_date", "end_date"])
        colmap = {}
        for cand in ["state", "bundesland", "land", "code", "state_code"]:
            if cand in df.columns:
                colmap["state"] = cand; break
        for cand in ["start_date", "start", "von", "beginn"]:
            if cand in df.columns:
                colmap["start_date"] = cand; break
        for cand in ["end_date", "ende", "bis", "schluss"]:
            if cand in df.columns:
                colmap["end_date"] = cand; break
        df = df.rename(columns={v: k for k, v in colmap.items() if k != v})

    for req in ["state", "start_date", "end_date"]:
        if req not in df.columns:
            df[req] = pd.Series(dtype="object")

    df["state"] = df["state"].map(_norm_state)
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce", dayfirst=True).dt.date
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce", dayfirst=True).dt.date
    df = df.dropna(subset=["state", "start_date", "end_date"])
    return df[["state", "start_date", "end_date"]]


def _read_feiertage_df() -> pd.DataFrame:
    paths = []
    if ENV_FEIERTAGE:
        paths.append(Path(ENV_FEIERTAGE))
    paths.extend(_candidate_paths(DATA_DIR, FEIERTAGE_CANDIDATES))
    paths.extend(_candidate_paths(HERE, FEIERTAGE_CANDIDATES))

    fp = _first_existing(paths)
    if not fp:
        return pd.DataFrame(columns=["date", "state"])

    if fp.suffix.lower() == ".json":
        try:
            df = pd.read_json(fp)
        except Exception:
            return pd.DataFrame(columns=["date", "state"])
        date_col = next((c for c in ["date", "datum", "day"] if c in df.columns), None)
        if date_col and date_col != "date":
            df = df.rename(columns={date_col: "date"})
        if "states" in df.columns and "state" not in df.columns:
            df["states"] = df["states"].fillna("").astype(str)
            df["states"] = df["states"].apply(lambda s: [p.strip() for p in s.split(",") if p.strip()])
            df = df.explode("states").rename(columns={"states": "state"})
        elif "state" not in df.columns:
            try:
                df = pd.json_normalize(pd.read_json(fp))
            except Exception:
                return pd.DataFrame(columns=["date", "state"])
            date_col = next((c for c in ["date", "datum", "day"] if c in df.columns), None)
            if date_col and date_col != "date":
                df = df.rename(columns={date_col: "date"})
            if "states" in df.columns and "state" not in df.columns:
                df["states"] = df["states"].fillna("").astype(str)
                df["states"] = df["states"].apply(lambda s: [p.strip() for p in s.split(",") if p.strip()])
                df = df.explode("states").rename(columns={"states": "state"})
    else:
        try:
            df = pd.read_csv(fp)
        except Exception:
            return pd.DataFrame(columns=["date", "state"])
        date_col = next((c for c in ["date", "datum", "day"] if c in df.columns), None)
        if date_col and date_col != "date":
            df = df.rename(columns={date_col: "date"})
        if "states" in df.columns and "state" not in df.columns:
            df["states"] = df["states"].fillna("").astype(str)
            df["states"] = df["states"].apply(lambda s: [p.strip() for p in s.split(",") if p.strip()])
            df = df.explode("states").rename(columns={"states": "state"})

    if "state" not in df.columns:
        df["state"] = pd.Series(dtype="object")
    if "date" not in df.columns:
        df["date"] = pd.Series(dtype="object")

    df["state"] = df["state"].map(_norm_state)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True).dt.date
    df = df.dropna(subset=["date", "state"])
    return df[["date", "state"]]


def union_affected_states(start: dt.date, end: dt.date) -> Tuple[Set[str], Set[str]]:
    """
    Liefert (ferien_states, feiertag_states) als LANGNAMEN (z. B. 'Baden-Württemberg')
    für den Zeitraum [start, end]. Daten werden ausschließlich gelesen (CSV/JSON),
    bestehende Dateien bleiben unverändert.
    """
    if end < start:
        start, end = end, start

    ferien = _read_ferien_df()
    feiertage = _read_feiertage_df()

    vac_states: Set[str] = set()
    hol_states: Set[str] = set()

    if not ferien.empty:
        mask = (pd.to_datetime(ferien["end_date"]) >= pd.Timestamp(start)) & \
               (pd.to_datetime(ferien["start_date"]) <= pd.Timestamp(end))
        vac_states = set(ferien.loc[mask, "state"].dropna().astype(str).tolist())

    if not feiertage.empty:
        mask = (pd.to_datetime(feiertage["date"]) >= pd.Timestamp(start)) & \
               (pd.to_datetime(feiertage["date"]) <= pd.Timestamp(end))
        hol_states = set(feiertage.loc[mask, "state"].dropna().astype(str).tolist())

    return vac_states, hol_states