"""Clasificación semántica de métricas promedio: excellent / good / normal / bad.

El frontend colorea las tarjetas según este estado (ver docs/FRONTEND_COLOR_GUIDE.md).
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


def check_status(key: str, val: float, role: str = "") -> Status:
    k = key.lower().replace("_", " ").strip()
    r = role.upper()

    if k == "kda":
        return _higher_is_better(val, 5.0, 4.0, 3.0)
    if k in ("cs/min", "cs min"):
        return _higher_is_better(val, 10.0, 9.0, 8.0)
    if k in ("deaths", "deaths/game"):
        return _lower_is_better(val, 3.0, 4.0, 5.0)
    if k == "solo kills":
        return _higher_is_better(val, 2.0, 1.0, 0.5)
    if k == "solo deaths":
        return _lower_is_better(val, 0.4, 0.8, 1.2)
    if "gold diff" in k:
        return _higher_is_better(val, 500, 200, -100)
    if "cs diff" in k:
        return _higher_is_better(val, 15, 8, 0)
    if "vision" in k:
        # Por minuto (valores pequeños) o score total.
        if val < 10.0:
            return _higher_is_better(val, 2.2, 1.8, 1.4)
        return _higher_is_better(val, 70.0, 55.0, 40.0)
    if "kp" in k or "participation" in k:
        return _higher_is_better(val, 70.0, 60.0, 50.0)
    if k in ("struct dmg", "daño a estructuras"):
        return _higher_is_better(val, 8000, 6000, 4000)
    if k in ("obj control", "control objetivos"):
        return _higher_is_better(val, 60.0, 50.0, 40.0)
    if k == "enemy jg" or "camps cleared" in k:
        return _higher_is_better(val, 15, 10, 6)
    if k in ("pink wards", "control wards") or "pink" in k:
        if r == "SUPPORT":
            return _higher_is_better(val, 8, 6, 4)
        if r == "JUNGLE":
            return _higher_is_better(val, 6, 4, 2)
        return _higher_is_better(val, 4, 2.5, 1.5)
    if k == "laning deaths":
        return _lower_is_better(val, 0.5, 2.0, 2.8)
    if k == "post-14 deaths":
        return _lower_is_better(val, 1.2, 2.0, 4.0)
    if k == "lane deaths" or "laning (pre-14)" in k:
        return _lower_is_better(val, 30.0, 45.0, 60.0)
    if k == "side deaths" or "side (post-14)" in k:
        return _lower_is_better(val, 20.0, 35.0, 50.0)
    if k in ("dmg/gold", "dmg gold"):
        return _higher_is_better(val, 1.25, 1.05, 0.85)
    if k in ("roaming", "roaming proactivity"):
        return _higher_is_better(val, 4.0, 2.5, 1.5)
    if k in ("obj vision", "obj prep vision") or "objective prep" in k:
        return _higher_is_better(val, 6.0, 4.0, 2.5)
    if k in ("efficiency", "efficiency ratio", "dmg share / gold share"):
        return _higher_is_better(val, 1.2, 1.0, 0.8)
    if k in ("dmg share", "damage share"):
        return _higher_is_better(val, 32.0, 28.0, 24.0)
    if k in ("early gank deaths", "death by early ganks", "early ganks"):
        return _lower_is_better(val, 0.15, 0.35, 0.60)
    return "normal"
