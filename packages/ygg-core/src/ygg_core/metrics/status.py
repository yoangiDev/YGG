"""Semantic classification of average metrics: excellent / good / normal / bad.

The frontend colours the cards according to this status (see docs/design/color-guide.md).
"""

from __future__ import annotations

Status = str  # "excellent" | "good" | "normal" | "bad"


def _higher_is_better(value: float, excellent: float, good: float, normal: float) -> Status:
    if value >= excellent:
        return "excellent"
    if value >= good:
        return "good"
    if value >= normal:
        return "normal"
    return "bad"


def _lower_is_better(value: float, excellent: float, good: float, normal: float) -> Status:
    if value <= excellent:
        return "excellent"
    if value <= good:
        return "good"
    if value <= normal:
        return "normal"
    return "bad"


# KDA: gentler than the rest and the same in all roles and leagues, by product decision. Below 3, grey
# (bad); from 3 to 4, green (normal); from 4, orange (excellent). There is no blue band.
KDA_NORMAL_FROM = 3.0
KDA_EXCELLENT_FROM = 4.0


def check_status(key: str, val: float, role: str = "") -> Status:
    """Fixed threshold: the KDA and the cards the harvest does not measure yet.

    The others (CS/min, deaths, vision, control wards, @14 differences...) are judged against the matches of the
    target league: see RANKED_CARDS in dashboard.py and benchmarks.py.
    """
    k = key.lower().replace("_", " ").strip()

    if k == "kda":
        return _higher_is_better(val, KDA_EXCELLENT_FROM, KDA_EXCELLENT_FROM, KDA_NORMAL_FROM)

    if k == "solo kills":
        return _higher_is_better(val, 2.0, 1.0, 0.5)
    if k == "solo deaths":
        return _lower_is_better(val, 0.4, 0.8, 1.2)
    if k in ("obj control", "objective control"):
        return _higher_is_better(val, 60.0, 50.0, 40.0)
    if k in ("roaming", "roaming proactivity"):
        return _higher_is_better(val, 4.0, 2.5, 1.5)
    if k in ("obj vision", "obj prep vision") or "objective prep" in k:
        return _higher_is_better(val, 6.0, 4.0, 2.5)
    if k in ("early gank deaths", "death by early ganks", "early ganks"):
        return _lower_is_better(val, 0.15, 0.35, 0.60)
    return "normal"
