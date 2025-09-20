# tools/fetch_ferien_to_csv.py
from __future__ import annotations
import sys, time
import datetime as dt
from pathlib import Path
from typing import Dict, List
import requests
import pandas as pd

# --- robustes Importieren aus dem Projektroot ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from holidays_utils import STATE_TO_CODE, DEFAULT_SCHOOL_CSV  # <- muss in holidays_utils.py existieren

API_BASE = "https://ferien-api.de/api/v1/holidays"

def fetch_state_year(state_code: str, year: int) -> list[dict]:
    url = f"{API_BASE}/{state_code}/{year}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def to_date(iso_utc: str) -> dt.date:
    # "2017-04-09T22:00" -> Datum
    return dt.datetime.fromisoformat(iso_utc).date()

def build_csv(year_from: int, year_to: int, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    states_by_code: Dict[str, str] = {v: k for k, v in STATE_TO_CODE.items()}

    for code, name in states_by_code.items():
        for y in range(year_from, year_to + 1):
            try:
                entries = fetch_state_year(code, y)
            except Exception as e:
                print(f"[WARN] {code}/{y} fehlgeschlagen: {e}")
                time.sleep(1.0)
                continue
            for item in entries:
                try:
                    s = to_date(item["start"]); e = to_date(item["end"])
                except Exception:
                    s = pd.to_datetime(item.get("start"), errors="coerce").date()
                    e = pd.to_datetime(item.get("end"), errors="coerce").date()
                rows.append({
                    "state": name,
                    "start_date": s.isoformat(),
                    "end_date": e.isoformat(),
                    "desc": item.get("name", ""),
                    "source": "ferien-api.de",
                    "slug": item.get("slug", ""),
                    "year": item.get("year", y),
                    "state_code": code,
                })
            time.sleep(0.15)  # freundlich zur API

    if not rows:
        print("Keine Daten empfangen – Abbruch.")
        sys.exit(2)

    df = pd.DataFrame(rows).sort_values(["state", "start_date", "end_date", "desc"]).drop_duplicates()

    # TT.MM.JJJJ schreiben (unser Loader nutzt dayfirst=True)
    for col in ("start_date", "end_date"):
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d.%m.%Y")

    df[["state", "start_date", "end_date", "desc"]].to_csv(out_path, index=False)
    print(f"✅ Geschrieben: {out_path} ({len(df)} Zeilen)")

if __name__ == "__main__":
    # Jahre per Argument oder Standard: voriges Jahr .. +2 Jahre
    today = dt.date.today()
    default_from = today.year - 1
    default_to = today.year + 2

    y_from = int(sys.argv[1]) if len(sys.argv) > 1 else default_from
    y_to = int(sys.argv[2]) if len(sys.argv) > 2 else default_to

    build_csv(y_from, y_to, DEFAULT_SCHOOL_CSV)
