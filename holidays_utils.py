# holidays_utils.py — robust detection of school vacations + public holidays
from __future__ import annotations

import csv
import sys
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Set, Tuple, Optional

import pandas as pd

# ---------- Paths & loading ----------

def _resource_path(*parts: str) -> str:
    """
    Return an absolute path to a resource that works in dev AND in a PyInstaller .app.

    We look in:
      1) alongside this file (repo checkout)
      2) <app bundle>/Contents/Resources if running from PyInstaller (sys._MEIPASS)
    """
    # 1) dev / source tree
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(here, *parts)
    if os.path.exists(candidate):
        return candidate

    # 2) PyInstaller
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = os.path.join(base, *parts)
        if os.path.exists(candidate):
            return candidate

    # 3) try cwd as a last resort
    candidate = os.path.join(os.getcwd(), *parts)
    return candidate


_SCHOOL_CSV_REL = ("Data", "school_holidays.csv")


def _load_school_df() -> pd.DataFrame:
    """
    Load school holidays CSV.
    Columns expected (case-insensitive): state, start_date, end_date[, desc]
    Dates are parsed day-first (German format), converted to datetime.date (no tz).
    """
    csv_path = _resource_path(*_SCHOOL_CSV_REL)
    if not os.path.exists(csv_path):
        # also allow flat layout next to executable
        csv_path = _resource_path("school_holidays.csv")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"school_holidays.csv not found. Looked in: "
            f"{_resource_path(*_SCHOOL_CSV_REL)} and {_resource_path('school_holidays.csv')}"
        )

    df = pd.read_csv(csv_path)

    # normalise column names
    cols = {c.lower(): c for c in df.columns}
    state_col = cols.get("state")
    start_col = cols.get("start") or cols.get("start_date")
    end_col = cols.get("end") or cols.get("end_date")

    if not (state_col and start_col and end_col):
        raise ValueError(
            f"CSV must have columns state, start_date, end_date. Got: {list(df.columns)}"
        )

    # parse dates day-first and drop rows we can't parse
    df["_start_dt"] = pd.to_datetime(df[start_col], dayfirst=True, errors="coerce")
    df["_end_dt"] = pd.to_datetime(df[end_col], dayfirst=True, errors="coerce")

    # ensure we have only valid rows
    df = df.dropna(subset=["_start_dt", "_end_dt"]).copy()

    # Convert to date (strip time)
    df["start_date"] = df["_start_dt"].dt.date
    df["end_date"] = df["_end_dt"].dt.date

    # normalise state names (trim spaces etc.)
    df["state"] = df[state_col].astype(str).str.strip()

    # some simple aliasing if needed
    alias = {
        "nordrhein westfalen": "Nordrhein-Westfalen",
        "nordrheinwestfalen": "Nordrhein-Westfalen",
        "nrw": "Nordrhein-Westfalen",
        "baden württemberg": "Baden-Württemberg",
        "baden-wuerttemberg": "Baden-Württemberg",
        "thueringen": "Thüringen",
        "thüringen": "Thüringen",
        "schleswig holstein": "Schleswig-Holstein",
        "mecklenburg vorpommern": "Mecklenburg-Vorpommern",
        "sachsen anhalt": "Sachsen-Anhalt",
    }
    df["state_norm"] = df["state"].str.lower().str.replace("_", " ").str.replace("-", " ").str.replace("ß", "ss")
    df["state"] = df["state_norm"].map(alias).fillna(df["state"])

    # keep only the columns we need
    return df[["state", "start_date", "end_date"]].sort_values(["state", "start_date"]).reset_index(drop=True)


_SCHOOL_DF_CACHE: Optional[pd.DataFrame] = None


def _school_df() -> pd.DataFrame:
    global _SCHOOL_DF_CACHE
    if _SCHOOL_DF_CACHE is None:
        _SCHOOL_DF_CACHE = _load_school_df()
    return _SCHOOL_DF_CACHE


# ---------- Public holidays (Feiertage) ----------

# We use python-holidays if available, with a safe compatibility layer across versions.
def _get_de_holidays_for_state(year: int, prov: str):
    """
    Returns a set of date objects for all public holidays in `year` for federal state `prov` (e.g. 'BE','BB','NW').
    If python-holidays is missing or incompatible, returns an empty set (so we never crash).
    """
    try:
        import holidays as _hol

        # Try modern API first
        try:
            cal = _hol.country_holidays("DE", subdiv=prov, years=[year])
        except TypeError:
            # Older API (prov= and years=)
            try:
                cal = _hol.Germany(prov=prov, years=[year])
            except Exception:
                cal = _hol.Germany(prov=prov)  # type: ignore

        # Convert to set of dates
        return {d if isinstance(d, date) else d.date() for d in cal.keys()}

    except Exception:
        # No holidays library? Fine; just no public holidays.
        return set()


# mapping from full state name to subdivision code used by python-holidays
PROV_CODE = {
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


# ---------- Query functions ----------

def _to_date(d: date | datetime) -> date:
    return d.date() if isinstance(d, datetime) else d


def _overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    """
    Inclusive range overlap for dates. No timezones involved.
    """
    return (a_start <= b_end) and (b_start <= a_end)


def states_with_school_holidays(start: date | datetime, end: date | datetime) -> Set[str]:
    """
    Return all German federal states that have *any* school vacation day within [start, end] (inclusive).
    """
    s = _to_date(start)
    e = _to_date(end)
    if e < s:
        s, e = e, s

    df = _school_df()
    # vectorised overlap: [start_date, end_date] overlaps [s, e]
    mask = (df["start_date"] <= e) & (df["end_date"] >= s)
    if not mask.any():
        return set()

    return set(df.loc[mask, "state"].unique())


def states_with_public_holiday(start: date | datetime, end: date | datetime) -> Set[str]:
    """
    Return all German federal states that have *any* public holiday within [start, end] (inclusive).
    Works with python-holidays if available; otherwise returns an empty set gracefully.
    """
    s = _to_date(start)
    e = _to_date(end)
    if e < s:
        s, e = e, s

    years = set(range(s.year, e.year + 1))

    affected: Set[str] = set()
    for state, prov in PROV_CODE.items():
        holi_dates: Set[date] = set()
        for y in years:
            holi_dates |= _get_de_holidays_for_state(y, prov)

        # quick overlap test: is there *any* holiday in the inclusive range?
        for d in holi_dates:
            if s <= d <= e:
                affected.add(state)
                break

    return affected


def union_affected_states(start: date | datetime, end: date | datetime) -> Tuple[Set[str], Set[str]]:
    """
    Returns (school_vacation_states, public_holiday_states) for [start, end] inclusive.
    """
    return states_with_school_holidays(start, end), states_with_public_holiday(start, end)


# ---------- Tiny self-test to help diagnose "19.09.2025" confusion ----------

if __name__ == "__main__":
    # Change these to experiment.
    d = date(2025, 9, 19)
    s = d
    e = d
    vac, hol = union_affected_states(s, e)
    print("Date:", d.isoformat())
    print("School vacations:", sorted(vac))
    print("Public holidays:", sorted(hol))
