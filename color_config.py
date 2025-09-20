# color_config.py
from __future__ import annotations
from pathlib import Path
import json
import re
from typing import Dict, List, Tuple, Optional

APP_DIR = Path.home() / "Library" / "Application Support" / "Wetterdaten"
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = APP_DIR / "settings.json"

# Temperaturbereiche (fixe Grenzen & Keys in Reihenfolge)
RANGES: List[Tuple[float, float, str, str]] = [
    (-20.0, 10.9, "range1", "-20 bis 10,9 °C"),
    (11.0, 14.9, "range2", "11 bis 14,9 °C"),
    (15.0, 19.9, "range3", "15 bis 19,9 °C"),
    (20.0, 24.9, "range4", "20 bis 24,9 °C"),
    (25.0, 29.9, "range5", "25 bis 29,9 °C"),
    (30.0, 34.9, "range6", "30 bis 34,9 °C"),
    (35.0, 49.9, "range7", "35 bis 49,9 °C"),
]

# Defaults (wie zuletzt gewünscht – Splitting der 11–19,9-Spanne)
DEFAULT_COLORS: Dict[str, str] = {
    "range1": "#3840FF",  # -20..10.9
    "range2": "#38ACFF",  # 11..14.9 (kühlblau)
    "range3": "#38ACFF",  # 15..19.9 (erstmal identisch – kann im Dialog geändert werden)
    "range4": "#35EE14",  # 20..24.9
    "range5": "#C6EE14",  # 25..29.9
    "range6": "#EE9F14",  # 30..34.9
    "range7": "#EE1414",  # 35..49.9
}

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _clean_hex(s: str) -> str:
    s = (s or "").strip()
    if HEX_RE.match(s):
        return s.upper()
    raise ValueError(f"Ungültige HEX-Farbe: {s}")


def load_config() -> Dict[str, str]:
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    # Mergen mit Defaults (fehlende Keys auffüllen)
    out = {**DEFAULT_COLORS, **{k: v for k, v in (data or {}).items() if HEX_RE.match(str(v))}}
    # Uppercase normieren
    out = {k: v.upper() for k, v in out.items()}
    return out


def save_config(colors: Dict[str, str]) -> None:
    clean = {}
    for key, val in colors.items():
        if key in {r[2] for r in RANGES}:
            clean[key] = _clean_hex(val)
    CONFIG_PATH.write_text(json.dumps(clean, indent=2), encoding="utf-8")


def get_ranges_meta() -> List[Tuple[str, str, float, float]]:
    """Return [(label, key, lo, hi), ...] in UI-Reihenfolge."""
    return [(label, key, lo, hi) for (lo, hi, key, label) in RANGES]


def color_for_temp_hex(temp_c: Optional[float], cfg: Optional[Dict[str, str]] = None) -> str:
    cfg = cfg or load_config()
    if temp_c is None:
        # neutrale, leicht kühle Farbe
        return cfg["range2"]
    for (lo, hi, key, _label) in RANGES:
        if lo <= temp_c <= hi:
            return cfg.get(key, DEFAULT_COLORS[key])
    # clamp außerhalb
    if temp_c < RANGES[0][0]:
        return cfg.get(RANGES[0][2], DEFAULT_COLORS[RANGES[0][2]])
    return cfg.get(RANGES[-1][2], DEFAULT_COLORS[RANGES[-1][2]])
