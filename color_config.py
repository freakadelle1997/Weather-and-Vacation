# color_config.py
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# 7 Temperaturbereiche:
# -20..10.9 | 11..14.9 | 15..19.9 | 20..24.9 | 25..29.9 | 30..34.9 | 35..49.9
# Neue Standardfarben (wie gewünscht):
# –20.0 bis 10.9 °C  -> #1E3A8A (dunkelblau)
# 11.0 bis 14.9 °C   -> #2563EB (kräftiges Blau)
# 15.0 bis 19.9 °C   -> #3B82F6 (helleres Blau)
# 20.0 bis 24.9 °C   -> #22C55E (grünlich – neutral)
# 25.0 bis 29.9 °C   -> #FACC15 (warm gelb)
# 30.0 bis 34.9 °C   -> #F97316 (orange)
# 35.0 bis 49.9 °C   -> #DC2626 (kräftig rot)

_DEFAULTS: List[Dict[str, Any]] = [
    {"min": -20.0, "max": 10.9, "color": "#1E3A8A"},
    {"min": 11.0,  "max": 14.9, "color": "#2563EB"},
    {"min": 15.0,  "max": 19.9, "color": "#3B82F6"},
    {"min": 20.0,  "max": 24.9, "color": "#22C55E"},
    {"min": 25.0,  "max": 29.9, "color": "#FACC15"},
    {"min": 30.0,  "max": 34.9, "color": "#F97316"},
    {"min": 35.0,  "max": 49.9, "color": "#DC2626"},
]

def _config_dir() -> Path:
    # macOS: ~/Library/Application Support/Wetterdaten
    base = Path.home() / "Library" / "Application Support" / "Wetterdaten"
    base.mkdir(parents=True, exist_ok=True)
    return base

def _config_path() -> Path:
    return _config_dir() / "colors.json"

def default_config() -> List[Dict[str, Any]]:
    return [dict(e) for e in _DEFAULTS]

def _is_hex_color(s: str) -> bool:
    if not isinstance(s, str) or len(s) != 7 or not s.startswith("#"):
        return False
    try:
        int(s[1:], 16)
        return True
    except Exception:
        return False

def load_config() -> List[Dict[str, Any]]:
    p = _config_path()
    if not p.exists():
        return default_config()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        out: List[Dict[str, Any]] = []
        for e in data:
            try:
                mn = float(e["min"]); mx = float(e["max"]); col = str(e["color"]).upper()
                if mn <= mx and _is_hex_color(col):
                    out.append({"min": mn, "max": mx, "color": col})
            except Exception:
                pass
        if len(out) != 7:
            return default_config()
        return out
    except Exception:
        return default_config()

def save_config(items: List[Dict[str, Any]]) -> None:
    # erwartet genau 7 Items mit min/max/color (#RRGGBB)
    if len(items) != 7:
        raise ValueError("Es müssen genau 7 Farbbereiche konfiguriert werden.")
    for e in items:
        if not {"min","max","color"} <= set(e):
            raise ValueError("Ungültiger Eintrag in colors.json")
        if not _is_hex_color(e["color"]):
            raise ValueError(f"Ungültige Hex-Farbe: {e['color']}")
        float(e["min"]); float(e["max"])
    p = _config_path()
    p.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

def color_for_temp_hex(temp: Optional[float]) -> str:
    cfg = load_config()
    if temp is None:
        # neutrale Karte, wenn kein Wert: dezentes Grau-Blau
        return "#6B7A90"
    for e in cfg:
        if e["min"] <= temp <= e["max"]:
            return str(e["color"]).upper()
    if temp < cfg[0]["min"]:
        return str(cfg[0]["color"]).upper()
    return str(cfg[-1]["color"]).upper()