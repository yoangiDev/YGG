"""Inspect Role Quest timeline signals and parser output for a match (dev tool)."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select
from ygg_core.domain.roles import normalize_role
from ygg_core.timeline.quests import (
    ADC_ROLE_BOUND_ITEMS,
    DEFAULT_ROLE_BOUND_ITEMS,
    QUEST_DESTROY_ITEMS,
    extract_quest_completion_time,
)

import app.db.models  # noqa: F401
from app.db.models.match import Match
from app.db.session import SessionLocal
from app.service.riot import create_secure_session, riot_client

_IN_PROGRESS = set().union(*QUEST_DESTROY_ITEMS.values())
_REWARD_BY_ROLE: dict[str, set[int]] = {
    **{role: {item} for role, item in DEFAULT_ROLE_BOUND_ITEMS.items()},
    "JUNGLE": {1209, 1210, 1211},
    "TOP": {1220, 1221},
}


def _sec_label(ms: int) -> str:
    sec = ms // 1000
    m, s = divmod(sec, 60)
    return f"{sec}s ({m}m{s:02d})"


async def inspect_match(match_id: str, region: str = "euw") -> None:
    client = riot_client(region)
    async with create_secure_session() as session:
        match = await client.fetch_match(session, match_id)
        timeline = await client.fetch_timeline(session, match_id)
    if not match or not timeline:
        print("Failed to fetch match/timeline")
        return

    info = match["info"]
    print("gameVersion", info.get("gameVersion"))

    for pid, p in sorted((x["participantId"], x) for x in info["participants"]):
        role = normalize_role(p.get("teamPosition", ""))
        rb = p.get("roleBoundItem") or 0
        parsed = extract_quest_completion_time(timeline, pid, role, role_bound_item=rb or None)
        print(f"\nP{pid} {role} roleBound={rb} parser={parsed}s")

        reward_ids = set(_REWARD_BY_ROLE.get(role, set()))
        if role == "ADC":
            reward_ids |= ADC_ROLE_BOUND_ITEMS
        if rb:
            reward_ids.add(rb)

        for frame in timeline["info"]["frames"]:
            for ev in frame.get("events", []):
                if ev.get("participantId") != pid:
                    continue
                et = ev.get("type")
                iid = ev.get("itemId")
                ts = ev.get("timestamp", 0)
                if et == "ITEM_DESTROYED" and iid in _IN_PROGRESS:
                    print(f"  destroy in-progress {iid} @ {_sec_label(ts)}")
                if et == "ITEM_PURCHASED" and iid in reward_ids:
                    print(f"  purchase reward {iid} @ {_sec_label(ts)}")


async def _latest_match_id() -> str | None:
    async with SessionLocal() as db:
        return await db.scalar(select(Match.match_id).order_by(Match.creation_time.desc()).limit(1))


def main() -> None:
    match_id = sys.argv[1] if len(sys.argv) > 1 else None
    region = sys.argv[2] if len(sys.argv) > 2 else "euw"
    if not match_id:
        match_id = asyncio.run(_latest_match_id()) or "EUW1_7867262819"
    asyncio.run(inspect_match(match_id, region))


if __name__ == "__main__":
    main()
