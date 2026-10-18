# Research

The scripts and reports used to measure **what decides a League of Legends game**. The win-probability model, the
per-league and per-role reference tables and the coaching concepts the product uses come from here. It isn't product
code in the sense of `apps/` and `packages/`, but **part of it is loaded by the API at runtime** (see
[What the API uses](#what-the-api-uses)), so it can't be moved without touching `apps/api`.

Everything in this folder is in English: prose (reports, comments, docstrings), module names, identifiers and the keys
and columns of the data files. The only Spanish names left belong to the separate decoder project this code reads
from (`cosecha.py`, its `cosecha-*` output folders and the `torres` key of its turret file); they are not ours to
rename. The table of [former module names](#former-module-names) maps the older Spanish names that still appear in
the historical notes under `docs/history`.

## What's here

| Folder | Contents |
|---|---|
| [`ladder/`](ladder) | A ladder harvest through the Riot API and a study of what wins games for the best players in each role, measured with WPA (*win probability added*) |
| [`replays/`](replays) | What comes out of decoding replays (`.rofl`): each game's timeline, win probability second by second, the value of each situation and the coach's concepts |
| [`coaching/`](coaching) | Reference reviews the author wrote by hand on specific games, and their cross-check against what the engine measures: the standard it is calibrated against |

### `ladder/`

| File | What for |
|---|---|
| [`REPORT.md`](ladder/REPORT.md) | Report: 5,000 games of EUW's 50 best players (10 per role), which deaths weigh most, what each objective is worth and how the grade comes out |
| [`league-report-16.19.md`](ladder/league-report-16.19.md) | What changes from one league to another in patch 16.19 |
| `analyse.py`, `economy.py`, `event_winrates.py` | The analyses that produce the report |
| `export_wpa_model.py` | Fits the WP model and **generates** `ygg_core/metrics/wpa_model.py` (not edited by hand) |
| `roster.example.json` | The shape of the player list the harvest walks (`apps/api/scripts/ladder_dataset.py`) |

### `replays/`

The reports are in [`reports/`](replays/reports); the code is in the folder itself:

| Report | What it answers |
|---|---|
| [`catalog.md`](replays/reports/catalog.md) | What is analysed, where each piece of data comes from and what it costs to repeat |
| [`wp-per-second.md`](replays/reports/wp-per-second.md) | Win-probability model every 10 s over 5,144 games (Gold to Challenger) |
| [`value.md`](replays/reports/value.md) | What each situation is worth (fight, objective, roam, flash…) and whose it is, in neutral WP points |
| [`recall-policy.md`](replays/reports/recall-policy.md), [`routes.md`](replays/reports/routes.md), [`openings.md`](replays/reports/openings.md), [`outcomes.md`](replays/reports/outcomes.md) | Jungler and support decisions learned without hand-written rules: recall, routes, openings and what usually happens after each option |
| [`vision.md`](replays/reports/vision.md) | The support's vision: what a ward is worth, what it risks and what rises with the league |
| [`situations.md`](replays/reports/situations.md) | What can be learned from each situation in a game and how the author's judgement enters the model without the model just copying it |

| Code | What for |
|---|---|
| `coach.py`, `moments.py` | **The coaching engine**: turns a decoded game into moments with minute, place and cost |
| `features.py`, `premium_references.py` | Each player's features and the per-league, per-role references they are compared with |
| `value.py`, `wp_per_second.py` | Win probability per second and the value of each situation |
| `timeline.py` | A game's timeline, extracted once so the analyses don't repeat the work |
| `policy.py`, `routes.py`, `routes_model.py`, `openings.py`, `outcomes.py`, `trees.py`, `jungle.py` | Analyses of jungler and support decisions |
| `leagues.py`, `grades.py`, `grade_history.py`, `fit_history.py`, `references.py` | 1-to-100 grades and what changes when climbing a league |
| `rofl.py`, `client.py` | Reading `.rofl` files |
| `zone_map.py`, `bushes_from_wad.py` | An editor for the map with zone and bush names; they write `zones.json` and `bushes.json` |
| `zones.json`, `bushes.json`, `prio.csv`, `fullclear.csv` | Data `coach.py` reads at runtime (place names, camp priority, full clear per champion) |

### Former module names

Older notes (and the git history before the English rename) use the author's Spanish module names:

| Former name | Current name |
|---|---|
| `rasgos` | `features` |
| `valor` | `value` |
| `wp_segundo` | `wp_per_second` |
| `linea` | `timeline` |
| `politica` | `policy` |
| `rutas`, `rutas_modelo` | `routes`, `routes_model` |
| `aperturas` | `openings` |
| `desenlaces` | `outcomes` |
| `arboles` | `trees` |
| `jungla` | `jungle` |
| `ligas` | `leagues` |
| `notas`, `notas_historial`, `ajusta_historial` | `grades`, `grade_history`, `fit_history` |
| `referencias`, `referencias_premium` | `references`, `premium_references` |
| `mapa_zonas`, `bushes_del_wad` | `zone_map`, `bushes_from_wad` |
| `test_peleas` | `test_fights` |

## What the API uses

`apps/api/app/service/replays.py` adds `research/replays` to `sys.path` and loads `coach`, `features`,
`premium_references` and `value` when a replay has to be analysed. That's why:

- the data files in the table above have to stay **next to** `coach.py`;
- `apps/api/requirements-replays.txt` (numpy and DuckDB) is needed for that analysis; scikit-learn and pandas are only
  needed by the research scripts;
- the API takes the path from `RESEARCH_DIR` (see `apps/api/.env.example`).

The reference each player is compared with is `apps/api/app/service/premium_reference.json`, generated by
`premium_references.py`; the openings model, `opening_model.json`, by `openings.py`.

## What isn't in the repository

The data weighs hundreds of MB or gigabytes and isn't versioned (`research/ladder/data/` is in `.gitignore`):

- the ladder games and the decoded `.rofl` files (`lol-replay-decoder`, a separate project);
- the timelines (`timeline.py`, about 2.8 GB for 5,265 games) and the value model `model.json`, which `value.py` loads if
  it exists;
- the real list of players for the harvest (`research/ladder/roster.json`): start from `roster.example.json` with the
  Riot IDs you want to sample.

Anything generated before the English rename (timelines, CSV tables, `model.json`, stored analyses) carries the old
column names and has to be regenerated; `timeline.VERSION` was bumped so stale timelines are detected.

So the scripts in this folder document their usage in their header but can't be run end to end from a clean clone: the
reports record the result of having run them.

## Tests

`replays/test_fights.py` and the API tests (`apps/api/tests/test_replays.py`) cover the bare minimum of the engine with
made-up games. The real criterion is the reviews in [`coaching/`](coaching): the games with a hand-written review are
**held out of training** and are the exam (see [`recall-policy.md`](replays/reports/recall-policy.md)), and a concept that
isn't calibrated against them yet doesn't score.
