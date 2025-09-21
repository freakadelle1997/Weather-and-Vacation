# holidays_utils.py
from __future__ import annotations
from typing import Set, Tuple, Dict, List
from pathlib import Path
import sys
import datetime as dt
import pandas as pd
import holidays

# Mapping: Bundesland-Name → DE-Provinzcode für python-holidays
STATE_TO_CODE: Dict[str, str] = {
    "Baden-Württemberg": "BW",
    "Bayern": "BY",
    "Berlin": "BE",
    "Brandenburg": "BB",
    "Bremen": "HB",
    "Hamburg": "HH",
    "Hessen": "HE",
    "Mecklenburg-Vorpommern": "MV",
    "Niedersachsen": "NI",
    "Nordrhein-Westfalen": "NW",
    "Rheinland-Pfalz": "RP",
    "Saarland": "SL",
    "Sachsen": "SN",
    "Sachsen-Anhalt": "ST",
    "Schleswig-Holstein": "SH",
    "Thüringen": "TH",
}

# ---------------- Pfade finden (Projekt / PyInstaller / .app) ----------------

def _candidate_data_dirs() -> List[Path]:
    base = Path.cwd()
    here = Path(__file__).resolve().parent
    dirs = [
        base / "data",
        base / "Data",
        here / "data",
        here / "Data",
    ]
    # PyInstaller (frozen)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        dirs.append(Path(sys._MEIPASS) / "data")
        dirs.append(Path(sys._MEIPASS) / "Data")
    # macOS .app Resources
    app_dir = here
    for _ in range(6):
        res = app_dir / "Resources"
        if res.exists():
            dirs.append(res / "data")
            dirs.append(res / "Data")
            break
        app_dir = app_dir.parent
    return dirs

def _find_data_file(filename: str) -> Path | None:
    for d in _candidate_data_dirs():
        p = d / filename
        if p.exists():
            return p
    return None

# ---------------- Schulferien aus *deiner* CSV ----------------

_FERIEN_DF_CACHE: pd.DataFrame | None = None

def _load_school_holidays_df() -> pd.DataFrame:
    """
    Erwartet CSV mit Spalten: state, start_date, end_date, desc
    Datum im Format TT.MM.JJJJ.
    """
    global _FERIEN_DF_CACHE
    if _FERIEN_DF_CACHE is not None:
        return _FERIEN_DF_CACHE

    path = _find_data_file("school_holidays.csv")
    if path is None:
        _FERIEN_DF_CACHE = pd.DataFrame(columns=["state", "start", "end"])
        return _FERIEN_DF_CACHE

    # Kommas-getrennt laut hochgeladener Datei
    df = pd.read_csv(path, sep=",", dtype={"state": str, "start_date": str, "end_date": str, "desc": str})

    # Nur die relevanten Spalten und klar benennen
    if not {"state", "start_date", "end_date"}.issubset(df.columns):
        # Wenn Datei anders ist, liefern wir leer zurück statt zu crashen
        _FERIEN_DF_CACHE = pd.DataFrame(columns=["state", "start", "end"])
        return _FERIEN_DF_CACHE

    df = df[["state", "start_date", "end_date"]].rename(columns={"start_date": "start", "end_date": "end"})

    # Datumsparsing robust (TT.MM.JJJJ)
    df["start"] = pd.to_datetime(df["start"], errors="coerce", dayfirst=True).dt.date
    df["end"]   = pd.to_datetime(df["end"],   errors="coerce", dayfirst=True).dt.date

    # Nur gültige Zeilen
    df = df.dropna(subset=["state", "start", "end"]).copy()
    df["state"] = df["state"].astype(str).str.strip()

    _FERIEN_DF_CACHE = df
    return _FERIEN_DF_CACHE

def states_with_school_holidays(start: dt.date, end: dt.date) -> Set[str]:
    """Bundesländer mit mind. 1 Ferientag im Intervall [start, end] (inkl. Randtage)."""
    df = _load_school_holidays_df()
    if df.empty:
        return set()

    s = min(start, end)
    e = max(start, end)

    mask = (df["start"] <= e) & (df["end"] >= s)
    states = set(df.loc[mask, "state"].astype(str))

    # Namen auf unsere Mapping-Schreibweise normalisieren (falls Klein/Kapitalschreibung differiert)
    normalized = set()
    for name in states:
        if name in STATE_TO_CODE:
            normalized.add(name)
            continue
        name_cf = name.casefold()
        match = None
        for ref in STATE_TO_CODE.keys():
            if ref.casefold() == name_cf:
                match = ref
                break
        normalized.add(match or name)
    return normalized

# ---------------- Gesetzliche Feiertage (offline via python-holidays) ----------------

def states_with_public_holiday(start: dt.date, end: dt.date) -> Set[str]:
    """Bundesländer mit mind. 1 gesetzlichen Feiertag im Intervall [start, end]."""
    s = min(start, end)
    e = max(start, end)
    years = list(range(s.year, e.year + 1))
    date_range = pd.date_range(s, e, freq="D").date

    affected: Set[str] = set()
    for state_name, prov in STATE_TO_CODE.items():
        de = holidays.Germany(years=years, subdiv=prov)
        if any(d in de for d in date_range):
            affected.add(state_name)
    return affected

# ---------------- Öffentliche API ----------------

def union_affected_states(start: dt.date, end: dt.date) -> Tuple[Set[str], Set[str]]:
    """
    Returns:
        (ferien_states, feiertag_states)
    """
    ferien = states_with_school_holidays(start, end)
    feiertag = states_with_public_holiday(start, end)
    return ferien, feiertag
