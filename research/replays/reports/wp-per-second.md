# WP per second from the replay — patch 16.19

**5,144 games** from EUW decoded from their `.rofl` (851 each of Gold, Platinum, Emerald and Diamond, 840 of Master, 630 of Grandmaster
and 270 of Challenger), **842,687 states**: one every 10 s from 1:30 to the end. Blue wins 48.7%. The numbers come from `wp_per_second.py`
(usage in its docstring); the whole output stays in `research/ladder/data/harvest-16.19/wp_per_second/output.md` and the model in
`model.json` in that same folder (ignored by git). **It is not integrated into the app.**

Everything is validated **by game**: 5 folds stratified by league, and each state is predicted with the model trained without its game.
The intervals are 90% ones resampling whole games, because a game's states share a result: they aren't 842,687 data points, they are
5,144.

---

## The essentials

1. **For predicting who wins, the replay adds little.** The new model lowers the app's log-loss by 0.8% (0.5367 → 0.5323, interval
   [−0.0059, −0.0031]) and the AUC goes from 0.800 to 0.803. It is real, but small. Almost everything that can be known about the result
   is already in gold, XP and objectives, which is what the timeline sees. What is left to explain is the future, not a missing
   feature.
2. **Half of that improvement isn't the replay's.** Retraining the app's 17 features with these games already gives 0.5354. The exact
   gold and XP per second, instead of the last minute plus the events' gold, bring it down to 0.5347, and the new features to 0.5330.
   Blending the segments (`smooth`) leaves 0.5323. The app's approximation is good.
3. **Where it does change is in the dynamics, which is what it is wanted for.** In the 10 quiet seconds (no kills or objectives) right
   before a kill, the new WP already moves **+0.64 points** towards whoever is going to make it. The app's doesn't move (−0.07). It sees
   the fight before it ends in a kill, above all through the health of those fighting.
4. **The price is more movement.** In 10 quiet seconds the new WP changes 1.96 points on average, and the app's, 1.08. Part of it is the
   fight that can be seen coming and part is noise. To value a situation you have to compare windows (before and after) against that
   background noise, not subtract two single seconds.
5. **It is better calibrated**, but that comes from the retraining. The app, trained with Challenger from another patch, overshoots at
   the extremes: when it says 85%, 81% win. Retrained, it already calibrates to 0.5 points.
6. **What weighs most**, besides gold, dragons, XP and the soul: the **exact respawn time**, which grows with the minute until it is the
   fifth heaviest; the **health of whoever is fighting**, the **average health** and the **levels** from minute 30. **Vision adds nothing
   measurable** (neither `seen` nor the living wards), and neither do the objective timers.
7. **It doesn't pay to put the league in the model.** Multiplying each feature by the league makes it worse (0.5347), and as a log-odds
   scale too (0.5337). What is real: **in Challenger advantages decide more** (slope 1.33 [1.15, 1.54]) and **in Gold, less** (0.88
   [0.80, 0.96]). From Platinum to Grandmaster it can't be told apart from 1.
8. **A gradient boosting doesn't improve the logistic regression**, even with the same features. scikit-learn isn't added.

---

## The vector

Everything goes from blue: blue minus red, or in favour of blue. A feature that is the same for both teams (the minute, the league, how
long until the dragon) can't move one team's WP alone. That is why the timers enter multiplying other features, and the league is tried
as an interaction or as a scale.

| feature | what it is | where from |
|---|---|---|
| `gold_k`, `xp_k` | total gold and XP, in thousands | the replay's table, at that second |
| `kills`, `dead` | accumulated kills; extra living players | the replay's `Death` (without revives) and the `alive` column |
| turrets by tier, `inhibitors_down`, `dragons`, `soul_point`, `soul`, `baron_active`, `elder_active`, `grubs`, `herald` | the same as the app | timeline events: turrets send no `UnitDeath` in the replay |
| `levels` | sum of levels | replay |
| `unspent_k` | unspent gold | replay |
| `respawn` | seconds left for the dead, red minus blue | the exact `respawn_time` of each `Death` |
| `rival_side` | living players past the river (beyond its width) | position |
| `seen` | enemies in view minus own in view | the `seen` column |
| `wards` | living wards | `moments._wards` |
| `health`, `mana` | average of the living, as a fraction of the maximum | replay |
| `summoners`, `ults` | ready among the living (the R from level 6) | replay |
| `dead_dragon`, `dead_elder`, `dead_baron` | `dead` × (objective alive or within 60 s, a ramp from 0 to 1) | timers |
| `pit_dragon`, `pit_baron` | extra living players within 2,500 of the pit, with the same weight | position and timers |
| `fight`, `health_in_fight` | how many have a living enemy within 1,200, and their summed health | `enemy_dist` and health |

**Timers**: taken from the harvest and not from the wiki. The dragon spawns at 294 s and comes back 293.5 s after falling. From the soul
the elder spawns, 353.5 s after the previous one. Baron spawns at 1,180 and comes back 340 s later. They are checked in every game against
its `SpawnNeutral`: **100%** of the 28,451 spawns fall within ≤ 2 s of the rule (median 0.0 s).

**Cleaning**: the decoder only writes a value when it changes, so before the minute the total gold is blank in three rows out of four;
that is why it starts at 1:30. Also, 5 values of 1.8 million are uninitialised memory (a gold of 1e27). A single one is enough to stop the
logistic regression converging, so they are replaced by the last good value.

**Model**: one logistic regression per segment (0, 10, 15, 20, 25, 30 and 35 min) with `analyse.logistic_fit`, like the app. The final one
blends the two neighbouring segments according to the minute (`smooth`). Otherwise the WP jumps on changing segment, and in a per-second
curve that jump would be charged to whatever happens at 10:00. No mirror: the intercept is the side advantage, and here it is almost 0.

**Baseline comparison**: `ygg_core.metrics.wpa_model.MODEL` as it is, with its 17 features computed by `GameState.features` over the
timeline of the same games and at the same seconds. It is exactly what the app does.

---

## Results

### All games

| model | log-loss | Brier | AUC | calibration (pp) | against the app | difference [90%] |
|---|---|---|---|---|---|---|
| app (MODEL as it is, timeline) | 0.5367 | 0.1820 | 0.800 | 1.72 | — | — |
| app retrained (its 17 features) | 0.5354 | 0.1816 | 0.800 | 0.54 | −0.2% | [−0.0027, −0.0001] |
| replay macro (16 features) | 0.5347 | 0.1814 | 0.801 | 0.48 | −0.4% | [−0.0034, −0.0007] |
| full (33 features) | 0.5330 | 0.1807 | 0.802 | 0.62 | −0.7% | [−0.0051, −0.0025] |
| **full, smooth (the final)** | **0.5323** | **0.1805** | **0.803** | **0.53** | **−0.8%** | [−0.0059, −0.0031] |
| full + each feature by league | 0.5347 | 0.1813 | 0.801 | 0.81 | −0.4% | [−0.0036, −0.0002] |
| full, smooth + scale by league | 0.5337 | 0.1810 | 0.802 | 0.43 | −0.6% | [−0.0049, −0.0012] |

Calibration is the mean of |predicted − real| over the ten WP deciles, weighted by states.

### By game segment: log-loss (AUC)

| minutes | states | app | app retrained | full | final | improvement |
|---|---|---|---|---|---|---|
| 0-10 | 261,633 | 0.639 (0.680) | 0.639 (0.680) | 0.638 (0.683) | 0.637 (0.683) | −0.3% |
| 10-15 | 152,659 | 0.556 (0.787) | 0.554 (0.787) | 0.551 (0.790) | 0.550 (0.790) | −1.1% |
| 15-20 | 146,387 | 0.494 (0.840) | 0.492 (0.840) | 0.490 (0.842) | 0.490 (0.842) | −0.8% |
| 20-25 | 131,399 | 0.437 (0.878) | 0.437 (0.877) | 0.435 (0.879) | 0.434 (0.879) | −0.6% |
| 25-30 | 88,523 | 0.441 (0.876) | 0.439 (0.876) | 0.436 (0.878) | 0.436 (0.878) | −1.3% |
| 30-35 | 41,606 | 0.487 (0.845) | 0.483 (0.846) | 0.479 (0.849) | 0.478 (0.850) | −1.9% |
| 35+ | 20,480 | 0.540 (0.802) | 0.540 (0.794) | 0.526 (0.807) | 0.519 (0.811) | −4.0% |

The improvement grows with the minute: in long games gold saturates (everyone has their build done) and what the app doesn't see weighs
more: who is alive and how long until they come back, the levels and the health.

### By league: log-loss (AUC)

| league | states | app | app retrained | full | final | improvement |
|---|---|---|---|---|---|---|
| Gold | 149,980 | 0.566 (0.775) | 0.562 (0.774) | 0.560 (0.777) | 0.558 (0.778) | −1.3% |
| Platinum | 146,645 | 0.543 (0.796) | 0.541 (0.795) | 0.538 (0.798) | 0.537 (0.799) | −1.1% |
| Emerald | 142,550 | 0.523 (0.812) | 0.523 (0.812) | 0.521 (0.814) | 0.520 (0.815) | −0.6% |
| Diamond | 137,278 | 0.532 (0.807) | 0.531 (0.807) | 0.529 (0.809) | 0.529 (0.809) | −0.6% |
| Master | 129,189 | 0.524 (0.811) | 0.522 (0.811) | 0.520 (0.813) | 0.520 (0.813) | −0.8% |
| Grandmaster | 96,763 | 0.553 (0.785) | 0.550 (0.785) | 0.548 (0.786) | 0.548 (0.787) | −0.9% |
| Challenger | 40,282 | 0.472 (0.854) | 0.478 (0.853) | 0.477 (0.853) | 0.477 (0.853) | **+0.9%** |

### Calibration by deciles

| predicted WP | app: predicts → wins | final: predicts → wins |
|---|---|---|
| 0-10% | 4.6 → 6.5% | 5.0 → 5.2% |
| 10-20% | 15.0 → 17.5% | 15.0 → 15.2% |
| 20-30% | 25.1 → 27.0% | 25.1 → 25.1% |
| 30-40% | 35.2 → 36.2% | 35.2 → 35.0% |
| 40-50% | 45.3 → 45.5% | 45.2 → 45.7% |
| 50-60% | 54.6 → 54.0% | 54.7 → 55.4% |
| 60-70% | 64.8 → 62.9% | 64.8 → 64.0% |
| 70-80% | 74.9 → 71.1% | 74.9 → 73.6% |
| 80-90% | 85.1 → 81.4% | 85.0 → 84.0% |
| 90-100% | 95.2 → 93.6% | 94.8 → 95.2% |

### Does the WP move before anything happens?

Pairs of consecutive states (10 s) from the same game. "Quiet" means nothing changes of what the timeline sees (no kills or objectives).
Anticipation is how much the WP moves towards the team that is going to make the kill in the 10 quiet seconds right before it. There are
556,046 quiet pairs and 122,411 right before a kill.

| model | mean change in 10 quiet seconds | anticipation before a kill | in the kill's 10 s |
|---|---|---|---|
| app | 1.08 pp | −0.07 pp | +5.72 pp |
| full | 2.04 pp | +0.63 pp | +4.80 pp |
| final | 1.96 pp | +0.64 pp | +4.75 pp |

With the new model, more than a tenth of the kill's value arrives before it: it is the fight that is being won. The app charges it all at
the instant of the kill.

### The league

The slope of the result's logistic regression on the final model's log-odds, out of fold, says how much the same advantage decides in
each league. Above 1 it decides more, and below there are more comebacks.

| league | slope [90%] | log-loss without → with the scale |
|---|---|---|
| Gold | 0.88 [0.80, 0.96] | 0.5582 → 0.5563 |
| Platinum | 0.95 [0.88, 1.02] | 0.5372 → 0.5399 |
| Emerald | 1.03 [0.95, 1.13] | 0.5200 → 0.5231 |
| Diamond | 1.00 [0.94, 1.10] | 0.5286 → 0.5304 |
| Master | 1.04 [0.98, 1.15] | 0.5196 → 0.5219 |
| Grandmaster | 0.95 [0.85, 1.06] | 0.5480 → 0.5498 |
| Challenger | 1.33 [1.15, 1.54] | 0.4769 → 0.4739 |

The per-league scale (intercept and slope) is validated with the training games' out-of-fold log-odds, so it doesn't cheat. Even so, it
wins in Gold and in Challenger and loses in the five in the middle, and overall comes out worse than not applying it. It stays measured in
`model.json` (`slope_per_league`) but unapplied. If it were needed, the only defensible one is Challenger's.

### What each group of new features adds

Each group is removed from the full model (without `smooth`) and retrained the same way.

| without… | log-loss | how much worse | difference [90%] |
|---|---|---|---|
| resources (health, mana, summoners, ultimates) | 0.5335 | +0.11% | [+0.0003, +0.0008] |
| respawn time | 0.5333 | +0.07% | [+0.0003, +0.0004] |
| fight in progress | 0.5332 | +0.04% | [+0.0002, +0.0003] |
| position (enemy territory, pits) | 0.5331 | +0.03% | [+0.0001, +0.0002] |
| fine economy (levels, unspent gold) | 0.5331 | +0.02% | [−0.0001, +0.0003] |
| timers × dead | 0.5330 | 0.00% | [−0.0001, +0.0000] |
| vision (seen, wards) | 0.5329 | −0.02% | [−0.0002, −0.0000] |

All are small and none dominates: what the new ones add is split between health, respawn and the fight. Vision, without it, comes out even
a hair better.

### Weights of the final model

Log-odds per standard deviation of the feature in each segment, from most to least average weight. The 15 that don't appear never exceed
±0.2 in any segment (the whole table, in `output.md`).

| feature | 0-10 | 10-15 | 15-20 | 20-25 | 25-30 | 30-35 | 35+ |
|---|---|---|---|---|---|---|---|
| gold_k | +0.56 | +1.05 | +1.23 | +1.21 | +1.14 | +0.80 | +0.21 |
| dragons | +0.15 | +0.30 | +0.37 | +0.46 | +0.41 | −0.19 | −0.36 |
| xp_k | +0.16 | +0.30 | +0.31 | +0.50 | +0.49 | +0.08 | +0.15 |
| soul | 0 | 0 | 0 | +0.11 | +0.15 | +0.69 | +0.60 |
| respawn | +0.01 | +0.07 | +0.09 | +0.17 | +0.26 | +0.36 | +0.48 |
| kills | +0.03 | −0.04 | −0.02 | −0.15 | −0.30 | −0.29 | −0.08 |
| levels | 0.00 | −0.04 | +0.06 | +0.07 | +0.03 | +0.32 | +0.36 |
| health_in_fight | +0.06 | +0.06 | +0.09 | +0.13 | +0.14 | +0.17 | +0.22 |
| inhibitors_down | 0 | +0.02 | +0.01 | +0.10 | +0.09 | +0.15 | +0.33 |
| health | +0.06 | +0.11 | +0.08 | +0.09 | +0.10 | +0.10 | +0.14 |
| inner_turrets | 0 | −0.02 | −0.07 | +0.05 | +0.05 | +0.04 | +0.43 |
| soul_point | 0 | 0 | +0.06 | +0.06 | +0.10 | +0.26 | +0.15 |
| outer_turrets | −0.01 | −0.13 | −0.05 | +0.01 | +0.11 | +0.16 | +0.15 |
| grubs | +0.05 | +0.15 | +0.11 | +0.10 | +0.07 | +0.02 | +0.07 |
| base_turrets | 0 | 0 | −0.05 | +0.03 | +0.15 | +0.24 | +0.05 |
| summoners | +0.04 | +0.07 | +0.03 | +0.04 | +0.06 | +0.10 | +0.16 |
| fight | −0.02 | −0.03 | −0.05 | −0.10 | −0.06 | −0.07 | −0.11 |
| baron_active | 0 | 0 | 0 | +0.01 | +0.07 | +0.09 | +0.25 |

A negative `fight` next to a positive `health_in_fight` reads as a single thing: what counts is the health you arrive at the fight with, not
how many bodies there are. With the same total health, more people means more people hurt. `unspent_k` comes out negative at 35+ (−0.19):
unspent gold isn't strength yet.

### Gradient boosting

`HistGradientBoostingClassifier` from scikit-learn 1.9.1 was tried, in a separate environment and not the project's, with the same states,
the same folds and the 31 features from before `fight`, plus the minute and the league as inputs.

| model | log-loss | AUC |
|---|---|---|
| per-segment logistic regression, same 31 features (`full`) | 0.5332 | 0.802 |
| GB (300 trees, 31 leaves, ≥ 200 per leaf) | 0.5428 | 0.795 |
| a heavily regularised GB (150 trees, 15 leaves, ≥ 3000 per leaf, L2 10) | 0.5366 | 0.799 |
| GB with the app's 17 features and the league | 0.5469 | 0.793 |

It overfits the games: 842,000 rows, but 5,144 results. Regularised, it ties with the app and falls below the logistic regression. **It
isn't worth it**, and scikit-learn isn't added to any `pyproject.toml`.

---

## Where it fails and what stays open

- **The first 10 minutes aren't predicted**: an AUC of 0.68 for all, and the replay doesn't change it (−0.3%). What happens in the laning
  phase shows up later in gold, not before.
- **Challenger is the only league where it doesn't improve on the app** (+0.9%). The app was trained with 4,276 Challenger games, here
  there are 270. And in Challenger the same advantage decides 33% more than a model trained with all the leagues says.
- **There are negative weights on advantages**: `kills` from minute 20, `dragons` from 30 (the soul takes it), `outer_turrets` at
  10-15, `mana`. It is collinearity (the kill is already in the gold and in the respawn), not that killing subtracts. For predicting it
  doesn't matter. For splitting an event's value among its features (the WPA's `drivers`), it does: before using it that way it has to
  be fitted with the non-negative constraint of `export_wpa_model.fit_non_negative`.
- **The curve's noise**: almost 2 points every 10 s with nothing happening. It has to be borne in mind when valuing roams, flashes or fights
  with WP differences. Windows have to be compared against that background.
- **`seen` is geometric**: the decoder marks as seen whoever is within 1,350 of an enemy or 900 of a ward, with no bushes or walls. It
  may be part of why vision adds nothing, although most likely the information turns into gold and kills and the model sees it there.
- **The timers add nothing**, neither crossed with the dead nor with presence at the pit. An objective's value appears when it is taken,
  not while playing for it.
- **Turrets come from the timeline**: the replay doesn't carry them, so this model also needs the match-v5.
- **A single patch** (16.19, builds 820 and 821). The draft doesn't enter, as in the app.
