"""Start of season 26, when the Role Quests appeared.

It is a game date, not a preference: the season windows the API uses to count
matches come from its configuration (SEASON_START and SEASON_END).
"""

from __future__ import annotations

from datetime import UTC, datetime

SEASON_START = datetime(2026, 1, 1, tzinfo=UTC)
