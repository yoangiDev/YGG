# Game grade (redesign)

Status: **design notes**. The timeline-based grade is implemented (see the last section); the per-role rubrics and the
reference ranges below are superseded or provisional. This file records what was agreed so it isn't discussed again.

## Scope

The detailed grades (weighted deaths and kills) go **only in the games history of the snapshots**, which already download
the timeline. The player's history keeps the simple grade: requesting each game's timeline would double the calls to Riot.

## Important deaths

Not all deaths cost the same. A death's cost has two parts.

### 1. Objectives conceded while you were dead

A death is tied to an objective **because the objective fell while you were away**, not because of where it happened. That
way the catch far from the pit that loses Baron comes in, which is the case that distance-to-the-pit swallows.

    death at t  →  respawn at t + timer
    enemy objective at t' ∈ (t, t + timer + 12 s]  →  that death paid for it

It counts **any** objective, not just the one in the fight where you died: if your team is on a dragon and the enemy takes
the top tower while you are there, dying is a mistake, because the enemy's play was foreseeable.

- **Shared blame**: if 3 teammates were dead at t', that death is worth 1/3.
- **Free sum**: no cap. A death can pay for Baron + a tower + an inhibitor; that death *is* the one that lost the game. The
  trimming is done by the rank's benchmark.
- **N = 12 s** of margin after the respawn (the walk back from base).

### 2. The fight's count

The exchange in which you died: dying 1x4 in your favour is a trade, dying 1x0 is a gift. Kills of both teams in the
fight's window.

### Symmetric for kills

The same machinery in reverse: a kill whose victim is still dead when your team takes the objective is an important kill.
If deaths are weighted and kills aren't, the player who fights gets punished.

## Objective weights (1-10)

| Objective | match-v5 event | Weight |
|---|---|---|
| Mid outer turret | `OUTER_TURRET` + `MID_LANE` | 9 |
| Mid inner turret | `INNER_TURRET` + `MID_LANE` | 7 |
| Top/bot outer turret | `OUTER_TURRET` + `TOP_LANE`/`BOT_LANE` | 4 |
| Top/bot inner turret | `INNER_TURRET` + `TOP_LANE`/`BOT_LANE` | 8 |
| Inhibitor-ring turret | `BASE_TURRET` | 3 |
| Inhibitor | `INHIBITOR_BUILDING` | 3 |
| Nexus turrets | `NEXUS_TURRET` | 1 |
| Team's 1st and 2nd dragon | `DRAGON` | 4 |
| Team's 3rd dragon | `DRAGON` | 7 |
| Team's 4th dragon (soul) | `DRAGON` | 10 |
| Elder dragon | `ELDER_DRAGON` | 10 |
| Baron Nashor | `BARON_NASHOR` | 8 |
| Herald | `RIFTHERALD` | 4 |

Dragons are counted **per team**, not in total.

Excluded: **grubs** (`HORDE`), **Atakhan** (it was removed from the game; if it shows up in an old game, weight 0) and
**allied camps** (the timeline has no camp event: only a per-minute counter, too expensive and coarse for a weight of 2).

## Death timer

From the [wiki](https://wiki.leagueoflegends.com/en-us/Death):

    BRW by level 1-18 = 10 10 12 12 14 16 20 25 28 32.5 35 37.5 40 42.5 45 47.5 50 52.5

    TIF = 0                                    before 15:00
          0.425 × ceil(2×(min-15))      %      15:00-29:59
          12.75 + 0.30 × ceil(2×(min-30)) %    30:00-44:59
          21.75 + 1.45 × ceil(2×(min-45)) %    45:00-54:59
          hard cap 50 %

    timer = BRW × (1 + TIF)                    max 78.75 s

The level at death comes from the timeline's `LEVEL_UP` events, with the `participantFrames` (1 per minute) as a fallback.

## What already exists and is reused

- `DeathEvent` (x, y, time, assistants) is already stored per player.
- `extract_objective_setups` already walks the epics with their timestamp.
- `map_zones`, `within_objective_radius`, `_frame_at` in `timeline/`.
- Re-analysing the old snapshots: `scripts/refresh_timelines.py`. Zero new calls to Riot.

## Per-role rubrics

> **Superseded** by [research/ladder/REPORT.md](../../research/ladder/REPORT.md): 5,000 games of 50 players. What is below
> came from one player per role and is no longer valid.

Final weights (they sum to 1). They come from the user's proposal, adjusted by what separates a win from a loss in the 205
games of the five references.

| | TOP | JG | SUP | MID | ADC |
|---|---|---|---|---|---|
| Cost of deaths | .22 | .17 | .15 | .23 | .23 |
| Value of takedowns | .12 | .12 | .12 | .12 | .12 |
| CS/min | .13 | .06 | — | .16 | .17 |
| Lane diff @14 (gold + XP + CS) | .18 | .17 | — | .16 | .14 |
| Damage/min relative to the game | .10 | .05 | — | .10 | .08 |
| Plates | .10 | — | — | .05 | .15 |
| Presence at objectives | .15 | — | .15 | .12 | .06 |
| Objectives secured | — | .17 | — | — | — |
| Successful ganks / roams | — | .12 | .15 | — | — |
| Counter-jungling | — | .09 | — | — | — |
| Kill participation | — | .03 | .13 | — | — |
| Objectives prepared | — | .02 | .20 | — | — |
| Useful vision (control + wards killed, per minute) | — | — | .10 | — | — |
| Takedowns before 14 | — | — | — | .06 | .05 |

Changes from what you asked for, all with data behind them:

- **Plates** from .05 to .15 in adc and .10 in top: it is the metric that best separates winning from losing in both, and
  the only one clean of duration (correlation 0.09-0.34).
- **Damage/min** goes down in all of them and becomes **relative to the game's average**: raw, it measures how long the
  game lasted (correlation 0.25-0.70), not playing well.
- **Lane diff** goes up in adc (.08 → .14) and jungle (.16 → .17): in jungle it is the strongest metric of all (gold@14
  1.35, XP@14 1.16).
- **Kill participation and objectives prepared** nearly disappear in jungle (separation −0.12 and 0.00) and are
  redistributed to what does measure.
- **Objectives secured** enters support (.15): it is its best separator (1.21).
- **Useful vision** enters support (.10) in place of vision score, which is useless.
- **Takedowns before 14** enters mid and adc (0.96 and 0.87, clean of duration).

## Reference ranges

From the best of each role on the ladder, not by hand. Tool: `research/ladder/` (the ladder harvest and `analyse.py`); the
players are treated as anonymous.

| Reference | Role | LP | Games in role | Winrate |
|---|---|---|---|---|
| Reference 1 | TOP | 2991 | 50/50 | 60% |
| Reference 2 | JUNGLE | 3613 | 35/47 | 40% |
| Reference 3 | SUPPORT | 3225 | 48/50 | 62% |
| Reference 4 | MID | 4704 | 35/50 | 37% |
| Reference 5 | ADC | 4301 | 37/49 | 57% |

p25 / median / p75 of each reference:

| Metric | TOP | JG | SUP | MID | ADC |
|---|---|---|---|---|---|
| cs_per_min | 6.9 / 7.8 / 8.7 | 6.7 / 7.4 / 8.4 | 0.8 / 1.0 / 1.1 | 7.6 / 8.2 / 9.1 | 7.6 / 8.5 / 9.5 |
| damage_per_min | 703 / 860 / 1061 | 473 / 655 / 810 | 251 / 304 / 379 | 725 / 856 / 1022 | 745 / 959 / 1191 |
| deaths | 3 / 5 / 7 | 4 / 6 / 8 | 4 / 5 / 7 | 4 / 6 / 9 | 3 / 6 / 8 |
| kills | 2.8 / 5 / 8 | 4 / 6 / 7 | 0.3 / 2 / 4 | 3 / 7 / 10 | 4.5 / 8 / 11 |
| assists | 1 / 5 / 7.3 | 3 / 5 / 10 | 10 / 15 / 22 | 3 / 6 / 11 | 4 / 6 / 9.5 |
| kill_participation | 25 / 38 / 49 | 40 / 53 / 63 | 50 / 58 / 65 | 40 / 50 / 60 | 43 / 55 / 66 |
| damage_share | 20 / 25 / 27 | 16 / 19 / 23 | 7 / 8 / 11 | 20 / 24 / 30 | 21 / 28 / 34 |
| efficiency | 1.06 / 1.23 / 1.32 | 0.77 / 0.88 / 0.99 | 0.52 / 0.58 / 0.69 | 0.95 / 1.13 / 1.33 | 0.94 / 1.08 / 1.21 |
| gold_diff_14 | −873 / −193 / 975 | −1299 / −250 / 682 | −300 / 4 / 502 | −473 / 428 / 1429 | −837 / 652 / 2421 |
| xp_diff_14 | −952 / −304 / 1248 | −762 / −50 / 909 | 56 / 355 / 862 | −380 / 357 / 838 | −495 / 535 / 1822 |
| cs_diff_14 | −18 / −1.5 / 22 | −13 / 1 / 14 | −3 / 0.5 / 7 | 1 / 13 / 24 | −11 / 14 / 38 |
| turret_plates | 2 / 4.5 / 8 | 0 / 1 / 2 | 0 / 0 / 1 | 3 / 4 / 6 | 2 / 4 / 8.5 |
| control_wards | 0 / 1 / 3 | 0 / 1 / 2 | 12 / 20 / 23 | 2 / 4 / 5 | 0 / 1 / 2 |
| wards_killed | 0.8 / 1 / 3 | 2 / 4 / 6 | 4 / 8 / 11 | 2 / 5 / 7 | 1.5 / 3 / 4 |
| enemy_jg_monsters | 0 / 0 / 1 | 4 / 12 / 22 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 2.5 |
| early_takedowns | 1 / 3 / 4 | 3 / 5 / 7 | 5 / 7 / 10 | 2 / 4 / 7 | 4 / 5 / 8 |
| objectives_secured | 1 / 3.5 / 5 | 2 / 3 / 5 | 2 / 4 / 5 | 2 / 3 / 4 | 2 / 3 / 5 |
| lane_visits | 0 / 0 / 0.3 | 3 / 4 / 5 | 1 / 2 / 3 | 1 / 1 / 2 | 0 / 0 / 1 |

### Discarded metrics and why

- **Raw vision score**: it correlates 0.72-0.94 with duration in all five roles. It measures minutes played. It is
  replaced by control wards + wards killed.
- **The jungler's `lane_visits`**: separation **−0.53**. You gank more when you're losing. Only the successful gank
  (`swing`) is worth anything, not the count.
- **`solo_kills`**, **`early_gank_deaths`**, **`wards_killed` in mid**: no signal or inverted.
- **`damage_structures`** and **`objectives_secured`**: they separate a lot but are partly a consequence of winning. They
  are used with a low weight and only where there is no alternative.

### Warnings about the sample

- One player per role, 35-50 games, their champion pool. It isn't "the Challenger average": they are the top of the
  ladder, that is, the ceiling.
- **Mid and jungle have 37% and 40% winrate in the sample**: few wins, so their win/loss separation is the least reliable
  of the five.
- **The current `RANK_BENCHMARKS` table is badly calibrated**: it puts Challenger deaths at 3.5-4.2 and the real median is
  5-6 in all five roles.


## Status (09-10): the grade with a timeline predicts the analysis grade

Implemented in `packages/ygg-core/src/ygg_core/metrics/timeline_grade.py`. With the timeline, each history player's grade is
a per-position regression (43 variables from the game and the timeline: deaths and when, time dead, the enemy's objectives
that fall while you are dead, gold/XP/CS differences with the lane opponent at 10, 14 and 20 min, kills and assists, damage,
plates, vision...) that predicts what the moments of their analysis (`coach.grade`) would add up to, and is turned into 1-100
with the position's Challenger percentiles, just like `coach.grades`. Fitted with 8,660 players from 866 games of the 16.19
harvest (`research/replays/grade_history.py` + `fit_history.py`); the saved model is `timeline_grade_model.json`.

| | mean error (grade points) | Spearman with the analysis | within ±10 points |
|---|---|---|---|
| stats grade (today's, without a timeline) | 8 - 14 | 0.43 - 0.72 | 43 - 69 % |
| WPA grade (the previous one with a timeline), 500 players | 11 - 15 (12.6) | 0.53 - 0.75 (0.64) | - |
| new model (cross-validation by game) | 5 - 9 | 0.79 - 0.91 | 67 - 87 % |
| new model through the production route, 500 players | 6.5 | 0.86 | 81 % |

Worse for SUPPORT (9 points of error): its analysis grade depends on vision and roams, which the timeline doesn't see. It
doesn't cover what is only seen in the replay: waves, timers, information. Without a timeline, the grade stays the stats
grade. Already-stored games keep the previous grade until they are read again (`MATCH_SUMMARY_VERSION` 2 regenerates the
summaries).
