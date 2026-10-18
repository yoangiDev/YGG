"""References by rank and role: what each metric of a match or a snapshot is judged against.

They come from 1,001 matches of 16.19 (143 per league, from Gold to Challenger) measured with
research/replays/references.py: rank_reference.json stores, per league, role and
metric, the mean and the 10th, 35th, 50th, 65th and 90th percentiles of a match. Percentages
are on a 0-100 scale, as in ParticipantSummary.

Each metric is judged by **where it falls among that league's matches**, with
the percentiles as anchors for the grade (match_score) and for its status:

- **excellent** from the 90th percentile (grade 85): among the league's best matches;
- **good** from the 65th (grade 70): better than two out of three. It is the target, above
  the typical match: the typical is what that league already does, and here the aim
  is for the player to improve;
- **normal** from the 35th (grade 55): what the league does;
- **bad** below that. The 10th percentile is worth 40.

Between anchors the grade is interpolated. Percentiles are used rather than mean and standard deviation
because several metrics are very skewed: the KDA of a match with no deaths
stretches the upper tail, and with a symmetric band almost nothing would come out "bad".

For those where less is better (deaths), the other way round: the 10th percentile is the excellent one and
the 35th the target.

The match grade and the history colours use Challenger; changing the table
changes the grade of every match, including those already stored, because it is computed
when they are served. The other leagues are the targets that can be chosen for each
player (snapshot cards). `average` is the mean, the one the radar and the
trends draw: what a player of that league really does.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

_DATA: Final = json.loads(Path(__file__).with_name("rank_reference.json").read_text(encoding="utf-8"))
assert _DATA["percentiles"] == [10, 35, 50, 65, 90], _DATA["percentiles"]

# For these, less is better.
LOWER_IS_BETTER: Final = frozenset({"deaths", "laning_deaths", "post14_deaths"})

# Match totals (not per minute nor percentages): they depend on how long it lasts.
PER_GAME: Final = frozenset({"kills", "deaths", "assists"})

# Measured leagues, from lowest to highest: they are the ranks that can be chosen as a target.
RANKS: Final[tuple[str, ...]] = tuple(_DATA["metrics"])
DEFAULT_TARGET_RANK: Final = "CHALLENGER"

# Kills of both teams in an average match of each league: the pace used to normalise kills and deaths.
MATCH_KILLS: Final[dict[str, float]] = _DATA["kills_per_game"]

Percentiles = tuple[float, float, float, float, float]  # 10, 35, 50, 65, 90

# {rank: {role: {metric: percentiles}}}
RANK_BENCHMARKS: Final[dict[str, dict[str, dict[str, Percentiles]]]] = {
    rank: {role: {metric: tuple(stats["p"]) for metric, stats in metrics.items()} for role, metrics in roles.items()}
    for rank, roles in _DATA["metrics"].items()
}
CHALLENGER_BENCHMARKS: Final = RANK_BENCHMARKS["CHALLENGER"]


def reference(rank: str, role: str, metric: str) -> Percentiles:
    """Percentiles 10, 35, 50, 65 and 90 of a match at that rank in that role."""
    return RANK_BENCHMARKS[rank][role][metric]


def target(rank: str, role: str, metric: str) -> float:
    """The target: the rank's 65th percentile (the 35th for deaths), better than two out of three matches."""
    _, p35, _, p65, _ = reference(rank, role, metric)
    return p35 if metric in LOWER_IS_BETTER else p65


def average(rank: str, role: str, metric: str) -> float:
    """What a player of that rank in that role does on average in a match."""
    return float(_DATA["metrics"][rank][role][metric]["mean"])
