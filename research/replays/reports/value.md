# What each situation is worth and whose it is — patch 16.19

**5,144 games** from EUW (851 each of Gold, Platinum, Emerald and Diamond, 840 of Master, 630 of Grandmaster and 270 of
Challenger), the same as in `wp-per-second.md`. The numbers come from `value.py` (usage in its docstring) and from
`features.py --value`, which regenerates the feature tables with the new columns. The complete outputs stay in
`research/ladder/data/harvest-16.19/value/` (`model.md`, `noise.md`, `effects.md`) and the tables in `features/`, all of it
ignored by git. **It is not integrated into the app.**

All values are in **neutral WP points**: the log-odds change divided by 4, like the app's neutral WPA. At 50% it is the change
in points, and it doesn't let an already-lost game flatten what happens in it. A kill is worth about 4.7. The intervals are 90%
ones resampling whole games: a game's situations share a result, and many of them the same fight.

---

## The essentials

- **What moves WP is fights and objectives**: a won teamfight is worth +19.9 points (four kills), a skirmish +7.5, a dragon
  +12.0 and a baron +17.5. A flash, a fight or an objective really move WP one by one; a roam, a back, a recall or a side-lane
  turn can't be told apart from how much WP moves by itself in that time: for those, only the average of many says anything.
- **The support's roam costs, on average, one point** (−0.98 [−1.08, −0.87] at 60 s, a fifth of a kill) **in all seven
  leagues**. The lane loses it (−0.98) and the map doesn't give it back (0.00). The marksman dies 3 pp more in that minute (7 pp
  in the first 30 s) and the support, 15 pp more. The least bad: going to top (−0.33; the map gains +0.85) or leaving when the
  enemy support has also left (−0.38). The worst: leaving the marksman alone against two (−1.43).
- **A suboptimal flash costs little, and it can't be asserted**: from the skirmish to the dragon, −0.44 [−0.73, −0.22] points and
  −0.8 pp of dragons, but the cleanest comparison (whoever is left without flash by a little against whoever recovers it by a
  little) can't be told apart from 0. What does subtract is arriving at the dragon with more players without flash than the
  enemy: −1.9 pp of taking it, −2.5 with two or more.
- **The fights' credit** gives the marksman +5.3 points per game and the top −5.0. It is the rule (the kill's gold belongs to
  whoever collects it and the death to whoever dies), not a judgement on the position.
- **Limits**: it is an association adjusted by the **visible** state, not an experiment. Missing are the wave and the enemy
  jungler's position, which decide roams and flashes. The prior 30 s check comes out ~0 on everything except Challenger's roam
  (+0.55): that league has to be read with care.

---

## Method

### 1. The WP of each second

`value.curve` gives, for each second of a game from 1:30, the blue team's log-odds (the red team's is the same with the sign
changed) and its WP, with the Phase 3 model (33 features, one logistic regression per segment with the segments blended by
minute). It reuses the extraction in `wp_per_second.py`, now with any step (`states`).

It also gives **what each champion contributes** (`contribution`). The model is linear and almost all its features are sums per
champion: each one's gold, XP and levels, whether they are alive and how long until they come back, whether they are within
range of an enemy and with how much health, their ready spells, their wards. So the log-odds is the intercept, plus the
timeline part (turrets, dragons, baron…), plus the sum of the five blue players' contributions minus the five red players'.
Health and mana are averages of the living: each living player contributes their own and **the dead player contributes their
team's average**, so that what the average moves when someone dies belongs to whoever dies and not to their teammates. The sum
is exact (checked second by second; only the mana of a team in which nobody uses it escapes).

### 2. No negative weights

The Phase 3 model had negative weights on advantages (kills from 20, dragons from 30, outer turrets at 10-15, mana). It is
collinearity —the kill is already in the gold and in the respawn— and for predicting it doesn't matter, but for splitting it
does: a kill would subtract on one side what it adds on another. It is refitted with `export_wpa_model.fit_non_negative`
(remove the most negative advantage and refit until none is left). Only three features with a reason to weigh against stay free:
unspent gold (with total gold inside, it is gold that isn't yet strength), `fight` (with the health of those fighting inside,
more bodies in range with the same health is more people hurt) and being past the river (pressure, but also exposure).

| model, out of fold | log-loss | Brier | AUC | calibration (pp) | difference [90%] |
|---|---|---|---|---|---|
| Phase 3 (full, smooth) | 0.5323 | 0.1805 | 0.803 | 0.53 | — |
| **no negative weights** | **0.5322** | 0.1805 | 0.803 | 0.51 | [−0.0005, +0.0005] |

**It costs nothing**: the prediction is the same, and the WP changes every 10 s of the two models are almost entirely alike
(correlation 0.991; 1.94 points on average in 10 quiet seconds against 1.96). What stays at 0 is what Phase 3 already said:
kills from 20 (the gold and the respawn take them), dragons from 30 (the soul), turrets before 15, mana almost always, vision
(`seen`, `wards`) in half the segments. It is the model for everything that follows.

### 3. The background noise and the windows

A situation's value is the mean of its team's WP in a window just after minus the mean in a window just before. To choose the
width, `value.py noise` measures over 494 games (one in ten) how much that difference changes at **any instants** (every 5 s),
and the signal: the same change around each death, in favour of whoever kills.

| window width | noise: any instants | quiet (no deaths or objectives) | signal of a death | signal / noise |
|---|---|---|---|---|
| 1 s | 2.68 | 1.77 | +4.63 | 1.73 |
| 3 s | 3.27 | 1.93 | +5.28 | 1.61 |
| **5 s** | **3.86** | **2.14** | **+5.75** | **1.49** |
| 10 s | 4.98 | 2.50 | +6.48 | 1.30 |
| 30 s | 7.72 | 3.16 | +7.38 | 0.96 |
| 60 s | 10.13 | 3.50 | +7.70 | 0.76 |

(Standard deviation, in points, with the two windows adjacent. The whole table, with separations from 0 to 60 s, in `noise.md`.)

What matters: **widening the window doesn't remove noise, it adds it**. The almost 2 points WP moves in 10 quiet seconds aren't a
tremor that averages out: the curve behaves like a random walk, and the further back and ahead you look, the more game fits
between the two windows. The signal grows a little (a wide window before picks up the fight that leads to the death), but less
than the noise. **5 s** is chosen: almost the ratio of the 1 s one (1.49 against 1.73), without depending on a single second
(sometimes a row is missing, sometimes the decoder gives a broken value) and picking up part of what happens right before a
situation starts, which is almost never detected at the exact second.

The noise grows with the **separation** between the windows —how long the situation lasts— like a random walk: with 5 s windows,
from 3.9 points adjacent to 5.5 at 5 s, 7.8 at 15 s, 10.0 at 30 s and 12.9 at 60 s. And with the **minute**, because the same
advantage decides more: with a 15 s separation, 4.9 points before 10 and 13.9 from 35.

Consequence: **the value of a single situation says almost nothing**; that of many does. A roam lasts a median of 25 s, and any
two windows 25 s apart vary as much as the values of all the roams: their signal part can't be told apart from 0. The averages of
thousands of roams, on the other hand, have intervals of tenths of a point.

With all the tables: how much the values of each one's situations vary, against how much any two windows with the same
separation and in the same stretch of the game would vary (`effects.md`):

| table | how long it lasts (median) | deviation of the value | that of any two windows | share that isn't noise |
|---|---|---|---|---|
| flashes | 5 s | 9.1 | 5.6 | 62% |
| setups (the objective) | 90 s | 17.7 | 12.9 | 47% |
| fights | 7 s | 8.0 | 6.2 | 40% |
| lane exits | 26 s | 8.8 | 7.3 | 31% |
| trades | 8 s | 5.4 | 4.7 | 24% |
| roams | 25 s | 7.0 | 7.1 | 0% |
| backs | 60 s | 8.7 | 9.3 | 0% |
| side lanes | 35 s | 11.6 | 11.9 | 0% |
| recalls | 8 s | 4.9 | 6.1 | 0% |

Flashes, objectives and fights **really move WP**, each one separately. Roams, backs, side lanes and recalls, no more than it moves
by itself in that time: their single value is noise, and only the average of many says anything. (In recalls the value varies
**less** than any two windows: they are done at quiet moments. The any-two-windows are an upper bound on the noise, not the exact
noise.)

### 4. The value of each situation

Each row of the tables carries `wp_before` and `wp_after` (its team's real WP, %) and `value` (neutral points). The before
window is [starts − 5 s, starts) and the after one, (ends, ends + 5 s]:

| table | starts | ends | whose |
|---|---|---|---|
| roams | leaves the lane | comes back (`time + lasts`) | their team |
| flashes | the flash | 5 s later (what `moments.flashes` looks at to say whether it is offensive) | their team |
| fights | first hit | 3 s after the last (the deaths `moments.fights` counts) | **the blue team's** (`value_100`); the red team's is the opposite |
| backs | the recall | 60 s later (the horizon of the CS that escapes) | their team |
| trades | first hit | 4 s after the last (whoever dies) | each row's team |
| exits, side lanes | `since` | `until` | their team |
| recalls | starts | 8 s later | their team |
| setups | 90 s before the objective falls (the `before` of `moments.setups`) | it falls | each team |

It doesn't wait to see whether an advantage turns into an objective: a well-calibrated WP model already prices that in at the
moment (if being two dead ends in a dragon, that is in the respawn weight). Waiting only adds noise.

### 5. Whose it is: the credit

Rules that add up exactly to the situation's value (checked on all rows, up to rounding):

- **What one player alone decides** —a flash, a back, a lane exit, a side-lane turn, a recall—: **entirely theirs**. It carries
  no separate column: the credit is `value`.
- **Fights and trades**, among those of each team who take part (`value.split`): **each keeps what changed for them** —their
  gold, their XP, their health, whether they die and how long until they come back— **and the rest is split equally**: what the
  enemies lose (their deaths belong to everyone fighting), what belongs to those who weren't there and the objectives. So,
  whoever dies carries their death and whoever takes the kill's gold collects it, as in `wpa.py`, without having to know who
  dealt the last hit. In `fights.csv`, `credit` carries those who take part from both teams (`Champion:+1.23|…`); in
  `trades.csv`, each row's share.
- **Roams**: `value_marksman` is what changes in the lane —the marksman's minus the enemy marksman's— and `value_support`,
  everything else: what the team gains or loses on the map, including what the support itself stops gaining. The roam is the
  support's decision, but if the marksman dies alone in the lane, that death is in theirs, as in `wpa.py`.

The values of different tables **don't add up with each other**: a flash is inside a fight, and a fight can be inside a roam.

### 6. A mistake or not?: comparing with what was decided in the same state

`features.py --value` produces two tables of decisions:

- **`roam_decisions.csv`**: the support in the laning phase (2:00-14:00) every time it decides whether to stay with its
  marksman or leave. **It leaves**: the last second with them within 1,500 before every time it moves away to more than 3,000
  (with both alive and the marksman in their lane, like `moments.roams`), however long it lasts; the row says how far it is
  (`lasts`), whether a death of the marksman or of the support cuts it (`short`) and which lane it goes to. The exits that don't
  start with it being with the marksman (it comes back from base and goes mid) don't count: there is no moment at which it
  decided to leave them. **It stays**: one every 10 s with it within 1,500 of those after which it doesn't move away in 30 s.
  For each moment, the state and what happens at 30, 60 and 90 s: the value for the team between the window before deciding and
  the one after the horizon, split into **lane** (marksman minus enemy marksman) and **map** (the rest), and whether the
  marksman or the support dies.
- **`flash_decisions.csv`**: each skirmish (a fight of fewer than 8) from minute 14 and each of those who play it with the flash
  ready 4 s before. **Flashes**: spends it in it (with the use from `moments.flashes`; objective ones don't count). **Doesn't**:
  has it and doesn't spend it. For each one, the fight's value for their team, theirs, whether they die, the value until the
  next dragon falls, whether their team takes it and, for whoever flashes, how long it takes to come back to them
  (`cooldown`).

**What a roam is here.** `moments.roams` asks for 15 s in a row with the support far away and **both alive**. For describing
roams it works; for comparing them with staying, no: a roam in which the marksman dies at 8 s doesn't reach 15 and vanishes, and
comparing only those that do is comparing the ones that survive. That is why the roam that is compared is **the one of 15 s or
more, or the one cut off earlier by a death** (of the marksman or the support). The short visits with no death (going to ward the
river and coming back) stay out, and the result with any exit is also given to see how much it changes.

The comparison is by **strata**: the decisions taken in the same game state are put together and, within each stratum, the mean of
those who stayed (or didn't flash) is subtracted from that of those who roamed (or flashed); the effect is the mean of those
differences weighted by how many roams (or flashes) each stratum has. It is the average effect **on those who did it**: how much
it changed for them compared with those who, in their same situation, did the other thing.

- Roam: league, minute (in steps of 2), team gold (5 bins, from −1,500 to +1,500), lane gold (marksman and support against the
  two enemies, 3 bins), who has more alive, whether the enemy support is in the lane and the marksman's health (3 bins). About
  11,000 possible strata; 99% of roams have something to compare with.
- Flash: league, minute (14-20, 20-25, 25-30, 30+), team gold (5 bins), who has more alive, who arrives at the fight with more
  people, their health 4 s before (3 bins), how many enemies they have within 1,200 at the start and how long until the dragon
  (alive, 1-90, 90-180, 180+ s). 95% have something to compare with.

**What this doesn't fix**: it compares decisions in the same **visible** state, not the same state. What isn't in the strata can
decide both things at once: the wave (a support roams when the wave is pushed and it is safe), the enemy jungler (where it is,
whether it is seen), the matchup, and in the flash, above all, the danger (you flash when they are about to kill you). It is an
adjusted association, not an experiment. Two checks:

- **`prior_`**: the same difference, but with the 30 s **before** deciding. What is decided afterwards can't change the past: if
  `prior_` comes out different from 0, those who leave (or flash) were already coming from another situation that the strata
  don't capture, and the effect is contaminated in that direction.
- **The flash's deferred cost without the selection**: among those who **do** flash in a skirmish, those left without flash for
  the next dragon by a little (the dragon spawns less than 90 s before it comes back to them) against those who recover it by a
  little (it spawns less than 90 s after). They made the same decision in almost equal situations; what changes is what they
  arrive at the dragon with.

---

## Results

### What each thing is worth, on average

The regenerated tables have 4.18 million situations from the 5,144 games; all those in the `SPAN` tables carry a value except
those that fall before 1:35 or right at the end (3% of flashes and 6% of fights, almost all from minute 1). On average, for the
situation's team:

| situation | how many | mean value | what it says |
|---|---|---|---|
| teamfight, for whoever loses fewer champions | 20,086 | **+19.9** | a won teamfight is worth four kills |
| skirmish, same | 148,078 | **+7.5** | |
| dragon, for whoever takes it (with its minute and a half of preparation) | 20,348 | +12.0 | |
| baron, same | 5,683 | +17.5 | |
| herald / grubs, same | 4,295 / 5,413 | +4.0 / +3.8 | |
| trade in which one dies, for their team | 56,678 | −4.6 | and whoever dies takes −3.9 of credit |
| trade with no deaths | 544,249 | +0.6 | |
| roam in which the marksman dies | 2,870 | −3.4 | −4.2 the marksman, +0.7 the support |
| roam with no marksman death | 37,441 | +0.1 | −0.2 the marksman, +0.3 the support |
| flash in a skirmish, suboptimal / not | 51,784 / 96,487 | −0.1 / 0.0 | |
| flash outside a fight, suboptimal / not | 4,863 / 16,474 | −0.5 / +0.1 | |
| recall cancelled / cut by an enemy / complete | 174,372 / 19,226 / 337,542 | −0.3 / −0.5 / +0.1 | |
| back with a normal wave / with the cannon on its way / after the cannon | 44,450 / 46,237 / 38,525 | +0.2 / +0.1 / −0.1 | the back's wave isn't noticeable in WP |

The flashes' averages are almost 0 because they mix two things that cancel out: the one that saves itself and the one that is
thrown and dies. That is why to say whether a flash is a mistake it has to be compared with whoever doesn't spend it (below).

### Whose the fights are

With the fights' rule (each one keeps their own and the rest is split), a player's credit in all of a game's fights correlates with
winning it (r = 0.65-0.68 in the five positions), and is split like this:

| position | credit per teamfight | per skirmish | sum per game | winning | losing |
|---|---|---|---|---|---|
| marksman | +0.65 | +0.09 | **+5.3** | +30.3 | −19.6 |
| jungle | −0.46 | +0.19 | +1.5 | +25.3 | −22.4 |
| support | +0.11 | −0.06 | −1.1 | +20.0 | −22.3 |
| mid | −0.10 | −0.01 | −0.7 | +25.0 | −26.4 |
| top | −0.25 | −0.13 | **−5.0** | +22.9 | −32.9 |

It sums to 0 across the five, as it should (a fight one team wins the other loses). The marksman comes out ahead because it
finishes: the kill's gold is theirs and counts in theirs. The top comes out behind in both types of fight; of the four who aren't
support, it is the one with the fewest kills per death (5.8 and 6.3 on average, against 7.8 and 6.7 for the marksman). It is what
the rule gives (the gold belongs to whoever collects it and the death to whoever dies), not a judgement on the position; with
`wpa.py` the same happens with kills.

### The support's roam: leaving versus staying

31,073 roams (of 15 s or more, or cut by a death) against 299,837 moments in which the support stays, over the 5,144 games; 99%
have something to compare with in their stratum. Neutral WP points for the support's team, **leaving minus staying**, in the same
state; `died` in percentage points.

What counts as a roam changes the result little:

| roams | how many | prior | balance at 30 s | at 60 s | at 90 s | the marksman dies at 30 s |
|---|---|---|---|---|---|---|
| of 15 s or more (those of `moments.roams`) | 28,173 | +0.09 | −0.92 [−1.00, −0.83] | −0.58 | −0.66 | +2.3 pp |
| **of 15 s or more, or cut by a death** | 31,073 | +0.03 | **−1.26 [−1.33, −1.17]** | **−0.98** | **−1.03** | **+7.2 pp** |
| any exit, even of 2 s | 57,832 | +0.17 | −1.27 [−1.34, −1.20] | −0.84 | −0.89 | +5.4 pp |

Counting only the roams that reach 15 s with both alive hides part of the cost (−0.58 against −0.98 at 60 s): it is the method's
survivorship bias. By league, at 60 s (`botlane`: the marksman's minus the enemy marksman's; `map_`: everything else):

| league | roams | prior | net balance | lane | map | the marksman dies |
|---|---|---|---|---|---|---|
| Gold | 4,841 | −0.11 | −1.02 [−1.25, −0.76] | −0.75 | −0.27 [−0.48, −0.06] | +3.3 pp |
| Platinum | 4,789 | −0.12 | −1.04 [−1.26, −0.76] | −0.93 | −0.11 | +4.4 pp |
| Emerald | 4,827 | +0.10 | −0.83 [−1.10, −0.55] | −0.91 | +0.08 | +5.6 pp |
| Diamond | 4,989 | −0.05 | −0.90 [−1.13, −0.68] | −0.97 | +0.07 | +2.7 pp |
| Master | 5,409 | +0.04 | −1.04 [−1.31, −0.74] | −1.12 | +0.08 | +2.8 pp |
| Grandmaster | 4,327 | +0.13 | −0.75 [−1.04, −0.44] | −1.09 | +0.34 [+0.07, +0.61] | +1.2 pp |
| Challenger | 1,891 | **+0.55** [+0.23, +0.78] | −1.72 [−2.12, −1.21] | −1.27 | −0.45 [−0.82, −0.03] | −0.6 pp |
| **all** | 31,073 | +0.03 [−0.04, +0.09] | **−0.98 [−1.08, −0.87]** | **−0.98** | **−0.00 [−0.08, +0.09]** | **+3.1 pp** |

- **In all leagues the balance is negative**, and almost all of it comes from the lane: the marksman loses a point against the
  enemy marksman (gold, XP, health, deaths). The map, on average, doesn't give it back: neither in Gold (−0.27) nor in Challenger
  (−0.45). Only Grandmaster recovers something on the map (+0.34), and it doesn't make up for it.
- **Adjusting for the state barely changes the result** (without strata, −0.87 for all; with them, −0.98), and the prior 30 s
  check comes out 0: those who leave weren't coming from another situation. **Except in Challenger**, where `prior_` is +0.55:
  there the support leaves when its team was already on the rise, and the −1.72 has to be taken as unreliable (and with only 270
  games).
- **The support who leaves dies 15.4 pp more** in the following minute [+14.9, +15.9].

According to where it goes and what the enemy support does (all leagues, at 60 s):

| roam | how many | prior | net balance | lane | map | the marksman dies |
|---|---|---|---|---|---|---|
| to mid | 14,161 | +0.09 | −0.94 [−1.09, −0.80] | −1.08 | +0.14 | +5.2 pp |
| to top | 2,902 | +0.33 | **−0.33** [−0.60, −0.06] | −1.18 | **+0.85** [+0.60, +1.09] | −2.7 pp |
| to bot (its jungle or the river) | 14,010 | −0.09 | −1.15 [−1.29, −0.97] | −0.84 | −0.31 | +2.3 pp |
| with the enemy support in the lane | 17,610 | −0.15 | **−1.43** [−1.55, −1.31] | −1.18 | −0.25 | **+8.5 pp** |
| with the enemy support out | 13,463 | +0.27 | **−0.38** [−0.53, −0.18] | −0.71 | +0.34 | −4.0 pp |

> **Careful: here "roam" includes going back to base.** `moments.roams` and `roam_decisions` only ask for the support to move away
> from its marksman, so two out of three are the way back to the fountain. Removing them (`openings.roams` stores `base_in`, the
> seconds it takes to step on its base) leaves 12,464 real roams and the balance at 60 s goes from −0.98 to **−1.63**. The
> breakdown by the wave it leaves behind is in `openings.md`.

**What it says**: the laning-phase roam, as it is played in solo queue, is on average a bad deal: it costs one point (a fifth of
a kill) each time, in all leagues. What decides how much it costs is **what it leaves behind**: leaving the marksman against two is
the worst (−1.43, and the marksman dies 8.5 pp more); leaving when the enemy support has also left costs little (−0.38). And where
to: the long trip to top is the only one that clearly gains something on the map (+0.85). A specific roam can come out very well;
the average says it shouldn't be taken as good.

### The suboptimal flash: spending it in a skirmish with the dragon on its way, against keeping it

47,399 suboptimal flashes in skirmishes against 184,748 players who, in a skirmish, had the flash ready and didn't spend it
(5,061 games; 95% have something to compare with). **Flashing minus not flashing**:

| league | flashes | prior | the fight | theirs | dies | from the fight to the dragon | own dragon |
|---|---|---|---|---|---|---|---|
| Gold | 9,793 | −0.16 | −0.81 [−1.12, −0.64] | −1.78 | +22.1 pp | +0.04 [−0.54, +0.44] | −0.5 pp |
| Platinum | 9,220 | +0.17 | −0.92 [−1.13, −0.72] | −1.78 | +22.5 pp | −0.96 [−1.50, −0.45] | −1.9 pp |
| Emerald | 8,381 | +0.07 | −0.63 [−0.87, −0.36] | −1.57 | +21.3 pp | −0.91 [−1.39, −0.41] | −1.2 pp |
| Diamond | 7,651 | +0.03 | −0.65 [−0.93, −0.41] | −1.47 | +21.5 pp | −0.34 [−1.06, +0.26] | −1.1 pp |
| Master | 6,247 | +0.27 | −0.04 [−0.29, +0.24] | −1.30 | +19.0 pp | −0.19 [−0.92, +0.35] | +0.0 pp |
| Grandmaster | 4,314 | +0.12 | −0.10 [−0.47, +0.14] | −1.34 | +17.9 pp | −0.40 [−1.13, +0.43] | −0.1 pp |
| Challenger | 1,793 | −0.15 | +0.21 [−0.41, +0.71] | −1.21 | +19.2 pp | +0.79 [−0.71, +1.99] | +1.7 pp |
| **all** | 47,399 | +0.06 [−0.00, +0.13] | **−0.58 [−0.68, −0.49]** | −1.57 | +21.1 pp | **−0.44 [−0.73, −0.22]** | **−0.8 pp** [−1.4, −0.4] |

- **The +21 pp of dying isn't what flashing costs, it is why you flash**: it is spent when they are about to kill you, and that
  danger isn't in the strata. Without strata the fight comes out −1.18 and with them −0.58: adjusting removes half, a sign that
  what is left to adjust weighs a lot. What is worth taking from this table is the after column.
- **The deferred cost** (from after the fight to after the dragon) is small: −0.44 points and −0.8 pp of dragons on average,
  clear only in Platinum and Emerald. From Master on it isn't seen either in the fight or after.
- By position, the one who pays most at the dragon is the **jungler** (−3.2 pp of dragons [−4.7, −1.8]: it fights the punishment
  without flash) and the **marksman** (−2.3 pp); the **support** is the one who loses most in the skirmish itself (−2.08 points).

**The cleanest comparison**, without the selection of who flashes: among those who **do** spend it in a skirmish, those left
without it for the dragon by a little (12,898; the dragon spawns less than 90 s before it comes back to them) against those who
recover it by a little (2,147). They made the same decision in almost equal situations, and arrive at the dragon with flash 26% of
the former and 69% of the latter. Result, for all leagues: from the fight to the dragon −0.55 [−2.21, +0.62] and own dragon −0.8 pp
[−3.3, +1.3]. **It can't be told apart from 0**: with 2,147 in the control group there isn't the precision to see an effect of the
size of the one above. It neither confirms nor refutes it.

**Arriving at the dragon with more players without flash than the enemy** (90 s before it falls, from minute 14; 9,589 arrivals
against 6,274 matched):

| arrivals | how many | takes it, without strata | takes it | the dragon's value |
|---|---|---|---|---|
| **all** | 9,589 | −0.1 pp | **−1.9 pp** [−3.0, −0.9] | −1.07 [−1.57, −0.56] |
| one more without flash | 5,348 | −0.3 pp | −1.5 pp [−2.6, −0.1] | −0.58 |
| two or more | 4,241 | +0.3 pp | −2.5 pp [−4.1, −0.7] | −1.69 |

**What it says**: spending the flash outside teamfights with the dragon on its way has a cost, but a small one: each extra player
without flash subtracts a point and a half of probability of taking the dragon, and the suboptimal flash's average, half a point of
WP. It is a detail mistake, not one of those that decide games, and in the high leagues it is almost not seen. The suboptimal-flash
rule (`moments.flashes`) serves to point it out, not to score it hard.

### What the data don't allow asserting

- **Causality.** Everything is "in the same visible state, those who did X ended up like this against those who did Y". The wave,
  the enemy jungler's position, the matchup and what each player knows and the model doesn't can decide the decision and the
  result at the same time.
- **A single case.** The value of a specific roam, back, recall or side lane is noise (table in section 3); only the averages of
  many are reliable. For a player, that means dozens of games.
- **Challenger**, with 270 games and the prior 30 s check away from 0 in the roam, is left with wide intervals and a possible
  bias.
- **One patch and one region**: 16.19, EUW, from Gold to Challenger.
