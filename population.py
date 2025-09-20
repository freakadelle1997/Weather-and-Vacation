# population.py
from __future__ import annotations
from typing import Dict, List

BUNDESLAND_POP: Dict[str, int] = {
    "Baden-Württemberg": 11_310_000,
    "Bayern": 13_430_000,
    "Berlin": 3_850_000,
    "Brandenburg": 2_590_000,
    "Bremen": 680_000,
    "Hamburg": 1_912_000,
    "Hessen": 6_416_000,
    "Mecklenburg-Vorpommern": 1_610_000,
    "Niedersachsen": 8_080_000,
    "Nordrhein-Westfalen": 17_960_000,
    "Rheinland-Pfalz": 4_180_000,
    "Saarland": 980_000,
    "Sachsen": 4_070_000,
    "Sachsen-Anhalt": 2_170_000,
    "Schleswig-Holstein": 2_980_000,
    "Thüringen": 2_100_000,
}
TOTAL_POP = sum(BUNDESLAND_POP.values())

def region_population(states: List[str]) -> int:
    return sum(BUNDESLAND_POP.get(s, 0) for s in states)

def region_population_share(states: List[str]) -> float:
    return (region_population(states) / TOTAL_POP * 100.0) if TOTAL_POP else 0.0