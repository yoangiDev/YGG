# What wins in Challenger EUW, measured with WPA

A study of 5,000 games from EUW's 50 best players (10 per role) to fix YGG's grading system with data. Version 2:
everything is measured with **WPA (win probability added)** to separate what *causes* winning from what merely *goes along
with* being ahead. Nothing decided earlier in the conversation enters as a weight.

Data: ``data/dataset.json`` (what was computed, one row per game and player, and each death with its WPA) and
`data/matches.jsonl.gz` (the 5,650 raw games, with the timeline compacted). How they are regenerated, at the end.

---

## Summary

1. **A death costs −5.2 win-probability points on average, and its weight is decided by three things: the minute, how the
   fight ended and what the enemy took while you were dead.** Ten more features (where, whether you were alone, how many
   caught you, gold given away, turret…) explain nothing those three don't explain.
2. **After minute 25, a death that concedes nothing costs nothing** (−0.4). One that concedes something, −12.3. At the start
   it is the other way round: dying in lane costs even if nothing falls (−4.7).
3. **Dying in a fight your team wins adds** (+3.9; after 25, +6.4). In one that loses, it subtracts −7.5 (−10.6 after 25).
4. **The objectives worth most are the dragons and the epics, not the structures.** Elder +9.8, first dragon +7.1, Baron
   +6.5, soul +6.1. **You were right about the inhibitor**: with WPA it is worth +2.6, the same as the placebo (nexus
   turrets, +3.0). Almost all of its apparent value was that the team was already winning.
5. **The mid outer turret is the most valuable turret of its tier** (+2.7 against +1.9 for the side lanes), and dying while it
   falls costs −8.1 against −5 for the side lanes. But it isn't decisive: it comes out well below the dragons.
6. **Taking part in grubs is associated with winning, but causes nothing**: WPA +0.3 ± 0.4. It is the textbook Mejai effect,
   and the previous grade gave them 10-13% of the weight.
7. **The WPA grade reflects the result a lot**: it separates win from loss with AUC 0.97, because the probability of winning
   *is* the sum of the WPAs. It serves to say what each thing cost, not to say "you played well and lost". What is useful for
   YGG is the breakdown: your deaths cost X, your takedowns added Y.

## What was wrong in the previous version

| Problem | Consequence | Corrected |
|---|---|---|
| The probability model was only validated with AUC, not with calibration | What happens while winning came out with an inflated value: nexus turrets +8.4, inhibitor +8.5 | Calibration measured by deciles and a placebo |
| Gold was interpolated between minutes | The "before" baseline already included the event's own gold: it shrank turrets and deaths | Gold from the last closed minute; kills, dead players and objectives exact from events |
| The baseline didn't know who was dead | The fourth death of a lost fight carried the whole fight | Players dead at each instant, per team |
| The per-role metrics and the grade were based on AUC against the result | It is a winrate: it rewarded what is done while winning (grubs, invading, plates) | The grade becomes WPA; AUC stays as descriptive |

---

## Sample

| | |
|---|---|
| Players | 50 (10 per role), all Challenger I, from 2,439 to 4,704 LP (median 3,045) |
| Games | 100 in their role per player = 5,000. To gather them, 7,181 were looked at |
| Unique games with a timeline | 4,276 (many lobbies coincide) |
| Deaths analysed | 233,242 (those of the 10 players of each game) |
| Season | 2026, patches 16.4 to 16.18 |
| Sample winrate | top 56%, jungle 54%, mid 52%, adc 54%, support 55% |

## Method: WPA

A winrate measures two things mixed together: the effect of the decision and the bias of *when* it is taken. Mejai has a 76%
winrate because it is bought while winning.

```
WPA = winrate − average WP just before the decision
```

The prior WP is the selection bias: what they were already going to win. What is left is the decision's average effect. Here
the decisions are **dying**, **killing** and **taking an objective**.

### The win-probability model

Logistic regression, **one per game segment** (0-10, 10-15, 15-20, 20-25, 25-30, 30-35, 35+), trained with the state every 30
s of the 4,276 games, seen from both teams. It only uses what was known before the evaluated instant:

- From the last closed minute: gold and XP difference.
- Exact from events: kills, **players dead at that instant**, turrets by tier (outer, inner, base, nexus), inhibitors down,
  dragons, soul point, soul, Baron and Elder active, grubs, herald.
- Draft strength: each champion's winrate in the sample not counting that game, shrunk towards 50%.

Validated by game (never the same game in training and test): **AUC 0.81**; 0.68 at 0-10 min, 0.86 at 15-20 and 0.89 at
20-25.

**Calibration**: when it says X%, X% win.

| Predicts | 4.8 | 15.0 | 25.1 | 35.2 | 45.4 | 54.6 | 64.8 | 74.9 | 85.0 | 95.2 |
|---|---|---|---|---|---|---|---|---|---|---|
| Wins | 5.2 | 15.1 | 25.9 | 35.7 | 44.9 | 55.1 | 64.3 | 74.1 | 84.9 | 94.8 |

Mean calibration error: **0.47 points**. By segment, 0.4-1.3 up to minute 35; 2.8 after 35 (there are few games that long).

**Placebo**: taking nexus turrets barely changes the result, so their WPA has to come out near 0. With the old model it gave
+8.4; with this one, **+3.0**. Those 3 points mark the bias that may remain in already-won states: any WPA of a closing event
below ~3 can't be told apart from "they were already winning".

---

## 1. Which deaths weigh

WPA in win-probability points of the dead player's team. Standard error in parentheses. **All deaths: −5.23 (0.08)** (winrate
38.9%, prior WP 44.2%).

### The Mejai effect on deaths

A death type's winrate misleads just like Mejai's:

| Death | Winrate | Prior WP | **WPA** | What the winrate would say |
|---|---|---|---|---|
| In your base | 1.7% | 5.3% | **−3.6** | "The worst" → it is among the cheapest: you were already lost |
| With a shutdown ≥ 300 | 78.7% | 85.1% | **−6.4** | "Almost free" → worse than average: you were winning |
| In the enemy half | 55.0% | 59.7% | **−4.7** | "A good sign" → almost like any other |
| While a nexus turret falls | 1.7% | 9.6% | **−7.9** | "Catastrophic" → the game was already lost |
| While an inhibitor falls | 12.5% | 16.1% | **−3.7** | The previous version gave it −12.7 |

### What the enemy takes while you are dead

Enemy objectives between the death and the respawn + 12 s (wiki timer). If several fall, the most valuable counts.

| During the death falls… | Deaths | Winrate | Prior WP | **WPA** |
|---|---|---|---|---|
| **Nothing** | 152,113 | 47.4 | 50.7 | **−3.3** (0.1) |
| Elder | 275 | 21.1 | 38.5 | **−17.4** (2.1) |
| First dragon | 4,784 | 36.6 | 50.7 | **−14.1** (0.6) |
| Baron | 8,650 | 19.8 | 32.4 | **−12.6** (0.4) |
| Soul | 1,546 | 10.9 | 22.6 | −11.7 (0.8) |
| Inhibitor-ring turret | 12,888 | 7.2 | 17.8 | −10.6 (0.2) |
| Second dragon | 5,138 | 27.6 | 37.9 | −10.3 (0.6) |
| Third dragon | 2,545 | 22.4 | 31.7 | −9.3 (0.7) |
| Mid outer turret | 8,501 | 33.2 | 41.3 | **−8.1** (0.4) |
| Mid inner turret | 5,807 | 19.2 | 27.2 | **−8.0** (0.5) |
| Herald | 2,658 | 29.2 | 36.4 | −7.2 (0.7) |
| Grubs | 3,183 | 38.1 | 44.0 | −6.0 (0.8) |
| Bot outer turret | 6,134 | 38.5 | 44.3 | −5.8 (0.5) |
| Top inner turret | 2,620 | 25.3 | 30.7 | −5.4 (0.7) |
| Top outer turret | 5,700 | 39.8 | 44.8 | −5.0 (0.5) |
| Bot inner turret | 2,706 | 24.3 | 27.8 | −3.5 (0.7) |

The same death is worth between −3.3 and −17.4 depending on what the enemy converts. Deaths with the game almost lost (while
the inhibitor ring or the nexus falls) carry the same ~3-point residue as the placebo. **The mid turrets weigh more than the
side ones of the same tier**, as you say: a death that lets the mid outer fall costs −8.1; the top one, −5.0.

### How the fight ended

Kills of both teams within ±15 s of the death.

| | All | 0-14 | 14-25 | 25+ |
|---|---|---|---|---|
| Your team loses the fight | **−7.5** | −7.1 | −6.7 | **−10.6** |
| Draws | −1.9 | −2.0 | −1.7 | −2.4 |
| Your team wins the fight | **+3.9** | +3.1 | +3.3 | **+6.4** |

Dying in a 1-for-4 in your favour is good play. Dying in a 0-for-1 is gifting.

### The minute

| | Conceding nothing | Conceding something |
|---|---|---|
| 0-14 | −4.7 | −7.8 |
| 14-25 | −2.0 | −7.4 |
| 25+ | **−0.4** | **−12.3** |

After 25, **the whole cost of dying is what the enemy takes while you are away**. At the start, the death costs even if
nothing falls: the lane's gold and XP carry over.

### The rest

| Death | WPA | |
|---|---|---|
| 0 / 1 / 2 / 3+ teammates already dead | −4.7 / −5.6 / −6.0 / −6.4 | Dying in a fight that is already being lost still costs |
| 0 / 1 / 2 / 3+ assisters | −4.3 / −4.6 / −5.5 / −7.2 | Being caught by many is worse |
| 0 / 1 / 2+ allies nearby | −4.8 / −5.3 / −5.8 | Being alone isn't worse |
| River (jungle) / your jungle / enemy half | −6.5 / −6.1 / −4.7 | The river is where it costs most |
| Near the dragon pit / Baron / far | −6.1 / −5.8 / −5.0 | |
| Jungle / mid / adc / top / support | −6.5 / −5.3 / −5.2 / −5.0 / −4.3 | The jungler's are the most expensive |

All of these differences exist, but **they are explained by the fight and what was conceded**: being caught by four is losing
the fight; dying in the river is dying in the fight for an objective. A model with minute, fight and conceded explains each
death's WPA just the same as adding these ten features to it (validated R² 0.0205 against 0.0214). R² is low because a single
death decides little of a whole game; its *expected value* is stable, and that is the one used.

### Formula for a death's WPA

```
WPA (pp) = −4.37 + 3.86·(min/10) − 0.81·(min/10)² + 3.38·exchange − 0.86·conceded
```

- `min`: the minute of the death.
- `exchange`: your team's kills minus your team's deaths within ±15 s (this one included). Dying alone = −1; dying in a 4-for-1
  in your favour = +3.
- `conceded`: the sum of the WPA (the table in section 2, in pp) of the objectives the enemy takes between the death and the
  respawn + 12 s.

| Example | WPA |
|---|---|
| Alone at 8, nothing falls | −5.2 |
| Alone at 18, the first dragon falls | −9.6 |
| Alone at 32, nothing falls | −3.7 |
| At 25, a 1-for-4 fight, Baron and mid inner fall | **−17.7** |
| At 25, a 4-for-1 fight in your favour, nothing falls | **+10.4** |

---

## 2. What each objective is worth

The WPA of taking it: the winrate of whoever takes it minus their WP just before.

| Objective | Times | Winrate | Prior WP | **WPA** | Your scale |
|---|---|---|---|---|---|
| Elder | 142 | 78.2 | 68.4 | **+9.8** (3.2) | 10 |
| First dragon | 6,817 | 60.5 | 53.4 | **+7.1** (0.5) | 4 |
| Baron | 4,371 | 80.2 | 73.8 | **+6.5** (0.5) | 8 |
| Soul (4th dragon) | 871 | 89.2 | 83.1 | **+6.1** (1.0) | 10 |
| Second dragon | 4,814 | 71.4 | 66.8 | +4.6 (0.6) | 4 |
| Mid outer turret | 6,540 | 63.1 | 60.5 | +2.7 (0.5) | 9 |
| Mid inner turret | 4,589 | 79.5 | 77.0 | +2.6 (0.5) | 7 |
| Third dragon | 2,607 | 79.1 | 76.6 | +2.5 (0.7) | 7 |
| Herald | 3,551 | 67.0 | 64.7 | +2.3 (0.7) | 4 |
| Bot / top outer turret | 7,215 / 7,185 | 57.6 / 56.9 | 55.6 / 55.0 | +2.0 / +1.9 | 4 |
| Top / bot inner turret | 3,642 / 3,964 | 74.4 / 76.8 | 72.9 / 75.5 | +1.5 / +1.3 | 8 |
| Grubs (each) | 12,718 | 54.3 | 54.0 | +0.3 (0.4) | out |
| *Closing, at the placebo's level:* | | | | | |
| Inhibitor-ring turret | 6,163 | 90.2 | 86.7 | +3.5 (0.3) | 3 |
| Nexus turrets (placebo) | 6,207 | 97.7 | 94.7 | +3.0 (0.2) | 1 |
| Inhibitor | 5,542 | 92.8 | 90.2 | +2.6 (0.3) | 3 |

**Inhibitor, inhibitor ring and nexus** all end up in the placebo's zone: they are taken with the game at 87-95% and barely
change it. It is exactly your argument, and the previous version had it the wrong way round.

**Mid outer turret**, by the minute it falls:

| Falls | Times | WPA |
|---|---|---|
| Before 12 | 101 | +6.6 (3.2) |
| 12-16 | 2,102 | +1.8 (0.8) |
| 16-20 | 2,867 | +2.9 (0.8) |
| 20+ | 1,470 | +3.1 (1.1) |

The distance to the result doesn't shrink it: WPA compares with the WP just before, not with the end, and with 6,540 cases the
error is half a point. What comes out is that it is **the most valuable turret of its tier and the one that costs most to lose
by dying**, but not of the order of a dragon. Taking it before 12 could be worth much more (+6.6), but with 101 cases the error
is ±3.2. An honest nuance: WPA measures what it adds for the turret to *fall*, given how the game was. If its value lies in the
pressure that brings it down, that pressure is already in the baseline and isn't attributed to the turret.

**First dragon's negative control.** At the start the model is less accurate (AUC 0.68), so one may suspect the first dragon
inherits "the team that takes it is stronger". Grubs are taken at the same time and with the same prior WP (54% against 53%)
and give +0.3. If it were strong-team bias, grubs would also come out high. They don't: the first dragon's +7.1 looks real.

---

## 3. Why games are won and lost

**Point of no return**: the last 2-minute stretch in which the game was still open (WP between 40 and 60%) before breaking
completely.

| | top | jungle | mid | adc | support |
|---|---|---|---|---|---|
| Median minute (losses) | 14 | 14 | 14 | 14 | 16 |
| Median minute (wins) | 12 | 12.5 | 13 | 14 | 14 |

What happens in that stretch, in losses:

| | top | jungle | mid | adc | support |
|---|---|---|---|---|---|
| A fight with no objective | 30% | 30% | 28% | 31% | 26% |
| First dragon | 14% | 12% | 13% | 13% | 15% |
| Baron | 11% | 13% | 14% | 12% | 13% |
| Pressure with no objective | 10% | 11% | 10% | 10% | 9% |

| | top | jungle | mid | adc | support |
|---|---|---|---|---|---|
| Losses: the player died in the stretch | 63% | 62% | 62% | 68% | 64% |
| Losses: an average teammate | 71% | 68% | 70% | 70% | 69% |
| Wins: took part in a kill in the stretch | 69% | 84% | 78% | 81% | 89% |

At the moment the game breaks, the Challenger dies **somewhat less** than an average teammate: it is a team fight, not an
individual mistake. In wins, the presence of the support (89%) and the jungler (84%) stands out; the top is the one who is
least where it is decided (69%).

---

## 4. Association is not effect

The previous version ranked metrics by AUC against the result. That is a winrate: it measures association. What is done while
winning always comes out high.

| Previous grade's metric | Association (AUC) | What WPA says | Verdict |
|---|---|---|---|
| Taking part in grubs | 0.63-0.74 | Taking them: +0.3 ± 0.4 | **Mejai**: it goes along with winning |
| Whole-game plates | 0.76-0.87 | 63% fall after 14, pushing with a lead | A consequence |
| Enemy jungle monsters | 0.52-0.73 | No events in the timeline: its WPA can't be measured | Unproven; you invade while winning |
| Kills near an enemy turret | 0.58-0.74 | Already included in the takedowns' WPA | Duplicated |
| Damage relative to the game | 0.54-0.74 | More is dealt in the fights that are won | Unproven |
| Cost of deaths (previous version) | 0.93 | Redone with WPA (section 1) | Kept, corrected |

They didn't separate anything even as an association either: vision per minute (0.53-0.59), control wards (0.51-0.60), kill
participation (0.47-0.57).

---

## 5. The grade: the player's WPA

Everything in win-probability points, so it adds up without weights:

- **Deaths**: the WPA of each one with the formula in section 1.
- **Takedowns**: for each enemy death in which they kill or assist, what that death took from the enemy, split equally among
  those who took part.
- **Objectives**: the objective's WPA (section 2), split among those who took part (last hit and assisters).
- **Farm**: what the CS difference with their opponent at 14 is worth, converted to gold (21 gold per CS). Only CS, so as not to
  count the kills' gold twice.

```
grade = 100 · Φ((total_WPA − role_mean) / role_deviation)
```

50 = the median game of a Challenger of that role.

| | top | jungle | mid | adc | support |
|---|---|---|---|---|---|
| Total WPA mean / deviation | 9.2 / 41.7 | 19.7 / 50.8 | 10.1 / 47.2 | 9.8 / 50.1 | 10.7 / 46.2 |
| Deaths (mean per game) | −28.2 | −27.9 | −28.4 | −32.6 | −32.0 |
| Takedowns | +31.5 | +37.0 | +33.0 | +35.1 | +39.3 |
| Objectives | +4.9 | **+10.5** | +4.8 | +6.4 | +3.4 |
| Farm | +1.0 | +0.1 | +0.7 | +0.8 | 0.0 |

The jungler is the only role that gets a large part of its value from objectives. Farm barely weighs (±2-3 points against
±40-50 of the total): in YGG it can be omitted.

### Validation

- **It tells the best apart**: each player's mean WPA correlates 0.51 with their winrate across the 50 (jungle 0.93, support
  0.72, mid 0.56, adc 0.41, top 0.19). The first ones: the jungler (+37.2 per game), the mid (+22.3), the adc (+20.2), the
  support (+17.0) and the top (+14.6).
- **It reflects the result a lot**: AUC 0.96-0.98; only 0.7-2.2% of losses score 70 or more.

The second one isn't a flaw: a team's probability of winning *is* the sum of the WPAs of what happens in the game, and the
death is evaluated with its "global count" (the fight and what was conceded), as you asked. That is why the grade serves to
**value decisions**, not to say "you played well and lost".

### Recommendation for YGG

1. **Show the breakdown, not just the grade**: deaths −X, takedowns +Y, objectives +Z.
2. **A list of deaths ordered by cost**: "min 25, 1-for-4 fight, Baron and mid inner fell: −17.7". It is your idea of important
   deaths, with a number.
3. If you want a grade that can reward a well-played loss, the alternative is to measure each death by its **immediate** WP
   change (staying dead, the gold given away) without what the team did afterwards. It is another design decision; tell me and
   I'll compute it.

### What YGG needs

Everything comes from what is already downloaded for a snapshot (match + timeline): no new calls to Riot, and **the probability
model isn't needed in the app**.

| Piece | What it is |
|---|---|
| Objectives' WPA table | 17 constants (section 2) |
| The death formula | 5 coefficients (section 1) |
| Respawn timer | The wiki's formula, already written |
| Per death | Exchange (kills within ±15 s) and enemy objectives between the death and the respawn + 12 s |
| Per takedown and objective | Who kills and assists (`killerId`, `assistingParticipantIds`) |

After that: raise `TIMELINE_VERSION` and redo the old snapshots with `scripts/refresh_timelines.py`.

---

## 5 bis. What is in YGG: a WPA timeline per game

In the app, the grade and the timeline are computed **event by event, with the real state of that game**, not with this
report's average values. All of it is in `packages/ygg-core/src/ygg_core/metrics/wpa.py`; the coefficients and the reference
are generated by `research/ladder/export_wpa_model.py` with the same code.

- **An event's value** = how much it moves its team's WP, measured as if the game were even: the model's log-odds change
  divided by 4, which at 50% is the change in points (baseball's "WPA/LI"). The curve and the before → after of each event are
  still the real WP. With the real change, a lost game flattened everything that came after (dying at 10% subtracts 2 points,
  at 50% subtracts 8) and a 0/11 Jinx scored −18.6 and a 54, the grade of a normal loss. Now it scores −73.3 and a 20.
- **Which events**: their kills, assists and deaths; the objectives they take part in; the objectives their team takes while an
  enemy they killed is still dead (credited to them) and those the enemy takes while they are dead (charged to them).
- **Split**: a kill, equally among those who took part; a death, entirely to whoever dies; an own objective, half to those who
  took it and half to those who killed the enemy who was still dead; an enemy objective, entirely to the dead teammates. Adding
  everyone up, each event splits exactly its value.
- **Instant gold**: the timeline gives gold once a minute, so a turret's value arrived a minute late and belonged to no one. The
  state adds at once the gold of each event, measured with the gold jump between frames: plate 129, outer turret 344, inner
  160, Baron 784, Elder 845; a kill 1.71 × its bounty (with the assist gold) and a shutdown 1.04 × its own (almost only
  whoever kills collects it). Together, with a single multiplier of 1.58, the shutdown weighed too much.
- **The shutdown is worth its gold, no more and no less**: 30 s after collecting a 600+ one, the model gives 19.8% to the team
  that collects it and 20.2% win; with shutdowns of 300–599, 22.1% and 23.0%. With no shutdown, 65.7% and 66.1%. The bounty
  system hides no separate effect: what it costs to give one away is the gold, and the gold is already in the state.
- **Advantages with no negative weight**: with fixed gold, "having taken a turret" before 15 came out with a negative weight
  (it is associated with having traded it for something elsewhere) and losing a turret raised the probability. In the fit no
  advantage can subtract. AUC 0.806 and calibration ±0.18 points.
- **Grade**: 70 is the mean of the 50 Challengers of their role, 100 sits two deviations above and 0 three below. With 15 points
  per deviation on both sides, 0 sat at −4.7 deviations: the worst game of the study didn't go below 30.

| | top | jungle | mid | adc | support |
|---|---|---|---|---|---|
| Mean total value / deviation (points) | +2.2 / 34.4 | +17.4 / 39.6 | +6.9 / 37.7 | +4.5 / 36.2 | +10.9 / 31.7 |
| The grade's AUC against the result | 0.89 | 0.93 | 0.91 | 0.94 | 0.92 |
| Mean grade winning / losing | 77 / 53 | 79 / 52 | 79 / 53 | 80 / 51 | 79 / 52 |
| Losses with grade ≥ 70 | 13.9% | 11.4% | 13.8% | 11.1% | 13.0% |
| ≥ 8 deaths and KDA < 1: mean grade | 30 | 28 | 31 | 31 | 29 |

With the real change the grade resembled the result less (AUC 0.76–0.85, one in five losses with a grade ≥ 70), but because in
a decided game nothing you did counted. Counting each play as in an even game brings it closer to the result: whoever wins by
a landslide adds many good plays and whoever loses by a landslide, many bad ones. Even so, one in eight losses scores a
Challenger grade: the grade can still say "you played well and lost". What is useful for YGG is the breakdown: your deaths
cost X, your takedowns added Y.

## 6. Limits

- **WPA is only as good as the model.** It is calibrated (±0.5 points) and passes the placebo with a residue of 3 points in
  already-won states; after minute 35 the error rises to 2.8.
- **Unmeasured confounders**: each player's level (all Challenger, assumed similar) and what the draft doesn't capture. At the
  start of the game the model is less accurate (AUC 0.68).
- **The WPA of correlated events doesn't just add up**: a fight with Baron gives WPA to the kills and to Baron. In the grade
  each thing is split among those who took part, but the same moment can appear from two sides.
- **Ten players per role**, their champions and their style; only Challenger. For other ranks the sample has to be repeated.
- **Patches 16.4-16.18.** The sample's jungler had to look at 837 games to gather 100 jungle ones: their sample is the oldest.

## Regenerate

```bash
cd apps/api
python scripts/ladder_dataset.py ../../research/ladder/roster.json ../../research/ladder/data --games 100
cd ../..
python research/ladder/analyse.py research/ladder/data
```

The download is resumable (with the development key, about 5 h). The analysis only uses numpy and takes a few minutes.
