# Openings: where the jungler and the support leave base towards, and where they are before an objective — patch 16.19

**5,143 games** from EUW (harvest 2.0, with the game's real visibility), the same as in `value.md` and `vision.md`. It comes from
`openings.py` (usage in its docstring): `extract` leaves one row per decision in `research/ladder/data/harvest-16.19/openings-2/`
(`openings.csv.gz` for the jungler, and `.support`, `.objectives` and `.roams` alongside) and `model` writes the whole report and
`model.json`, which is the one the app uses (`apps/api/app/service/opening_model.json`).

There are three decisions, and they are different: **the jungler chooses a half of the map** on leaving base, **the support chooses whether
to open through mid or go straight down** to its lane, and **from 14 on both choose whether they are at the objective** that is about to spawn.

---

# 1. The jungler: which half it opens, until minute 14

Each time a jungler leaves its base (after a back or a death, from 2:30 until 14:00) it chooses which half of the map to open: the upper or the lower
side of the diagonal joining the two bases. **44,166 openings** from 5,138 games, 5 to 8 per game.

**Where it opens** is the half of the first thing it does if it arrives within 45 s (a camp of its own, an enemy one, the crab, an objective or a
fight), or the half it is in at 30 s. Clearing the top Wolves and then going down through mid is opening top.

**The map**, at the second it leaves, for each half: its camps (alive and those that spawn in 30 s, with their gold), the enemy's, the crab, the
objective (dragon bottom; grubs, herald or baron top) and how long it has left, and the lane of that half (the enemies' health and flash, the allies'
health and ultimates, where the wave is, gold). And of the enemy jungler, where their team last saw it and where it last cleared.

## What the best choose

A logistic regression on the differences between the two halves, fitted in Challenger and Grandmaster and evaluated **out of fold by game**. An
opening is **clear** if the model gives one side 70% or more: four out of five.

| league | openings | AUC | clear | agree on the clear ones | those who win | those who lose |
|---|---|---|---|---|---|---|
| Gold | 6,950 | 0.871 | 80% | **85%** | 86% | 84% |
| Platinum | 7,048 | 0.888 | 80% | 86% | 87% | 86% |
| Emerald | 7,167 | 0.892 | 79% | 88% | 88% | 87% |
| Diamond | 7,419 | 0.900 | 80% | 88% | 88% | 88% |
| Master | 7,401 | 0.906 | 80% | 89% | 90% | 88% |
| Grandmaster | 5,725 | 0.905 | 79% | 89% | 90% | 89% |
| Challenger | 2,456 | 0.911 | 79% | **90%** | 90% | 90% |

- **The higher the league, the more the opening follows the map**: the AUC rises from 0.871 to 0.911 and opening against a clear reading falls from 15%
  of the time in Gold to 10% in Challenger. Within each league, those who win and those who lose barely differ (0-2 points): it is something that
  rises with level, not something that decides a single game.
- **What weighs** (weights on the standardised features; in parentheses, Gold and Platinum): its own camps alive or spawning in 30 s, **+1.83**
  (+1.34), much more than the rest; those alive now, +0.50 (+0.68); the crab, +0.35 (+0.19); the objective spawning in under a minute, +0.35
  (+0.49); the enemy's camps, +0.16 (+0.03); the wave pushed towards the enemy, −0.15 (−0.17); and the enemy jungler seen in that half, +0.03
  (**+0.19**).
- **The difference reads by itself**: those at the top **count the respawn times** (what there will be in 30 s weighs three times more than what there
  is) and look more at the crab and the enemy's camps. Gold and Platinum are guided more by what is alive now, by the objective and by where they
  saw the enemy jungler: they chase it.

## Whether following them pays

In the clear openings of all leagues, those that match what those at the top would choose against those that don't (90% interval resampling whole
games):

| in the next 90 s | matches | doesn't match | difference |
|---|---|---|---|
| **the jungler dies** | 18.7% | 24.6% | **−5.9 pp** [−7.1, −4.8] |
| the jungler's gold | 630 | 612 | **+18.1** [+11.2, +24.5] |
| its team's WP (neutral points) | −0.9 | −1.4 | **+0.5** [+0.2, +0.8] |

**Opening against a clear reading is when the jungler dies**: almost a third more often. The gold and the WP go in the same direction, with small
differences per opening (a single opening decides little; six are taken per game).

---

# 2. The support: opening through mid or going straight down

In the laning phase (from 2:30 to 14:00) the support leaves base and chooses: going straight down to its lane, or **opening through mid** —vision in
the river and in the jungle of that side, pressure on the enemy mid— and reaching bot later. **53,245 exits** from 5,140 games. It opens through mid
if within 30 s it steps on the mid lane past its inhibitor turret.

What decides it is **how it leaves the wave to its marksman** (`botlane_state`): if it has just crashed into the enemy tower (`crash`) or is pushed
towards them, the marksman has time; if the enemy is building a slow push (they are going to dive under its tower) or has it frozen on its side (it
has to go past the middle of the lane to farm), it doesn't.

## How much they open through mid, by league

| league | exits | open through mid | those who win | those who lose |
|---|---|---|---|---|
| Gold | 8,281 | **13%** | 13% | 13% |
| Platinum | 8,358 | 16% | 16% | 16% |
| Emerald | 8,476 | 21% | 21% | 21% |
| Diamond | 8,696 | 26% | 27% | 25% |
| Master | 9,067 | 38% | 39% | 37% |
| Grandmaster | 7,203 | 44% | 46% | 42% |
| Challenger | 3,164 | **50%** | 51% | 49% |

**It is the cleanest ladder in the whole repository**: from 13% to 50%, fourfold, without winning or losing within a league changing anything (0-4
points). It isn't a trick of one elo: it grows at each step.

## According to the wave it leaves the marksman

| lane on leaving | exits | open through mid, Challenger and GM | Gold and Platinum | **WP 90 s, through mid minus down** |
|---|---|---|---|---|
| pushed (in its favour) | 7,127 | **57%** | 21% | **+0.84** [+0.44, +1.29] |
| no marksman (dead or in base) | 12,165 | 52% | 15% | **+0.73** [+0.33, +1.08] |
| crash (crashed less than 40 s ago) | 8,090 | 46% | 14% | +0.21 [−0.29, +0.72] |
| neutral | 9,972 | 44% | 16% | +0.06 [−0.35, +0.45] |
| at its tower | 4,102 | 40% | 14% | −0.37 [−1.14, +0.36] |
| **enemy slow push** | 11,149 | 35% | 9% | **−0.68** [−1.21, −0.22] |
| **enemy freeze** | 640 | 33% | 7% | −0.67 [−2.45, +0.89] |

- **The player's rule and the data say the same.** Where those at the top open through mid most is where it pays most (pushed wave, +0.84 WP points);
  where they open least is where it costs (the enemy's slow push, −0.68). They are the only two states with the whole interval away from zero.
- **Opening through mid isn't what kills the marksman**: it dies in the next 90 s 26-36% of the time, and the difference between opening through mid
  and going straight down doesn't exceed 2 points in any wave state.
- **What changes is whose the death is.** Of the marksmen who die with their support opening through mid: with the wave pushed or just crashed,
  40-45% die **past the middle of their lane** (they exposed themselves, in a window they had to respect) and 29-32% next to their tower; with an
  enemy slow push it flips, 25% exposed and **51% under their own tower** (they get dived: that one is the wave's they were left).

## The tempo: which wave it goes back to base with

The lane 8 s before arriving at base, that is when the recall starts; only of backs, because after dying there is no choice.

| lane at the start of the recall | backs | share of backs, Challenger and GM | Gold and Platinum | open through mid afterwards, Ch. and GM | Gold-Plat |
|---|---|---|---|---|---|
| pushed | 7,732 | 26% | 23% | **50%** | 15% |
| neutral | 7,495 | 22% | 25% | 44% | 12% |
| no marksman | 5,684 | 16% | 19% | 48% | 13% |
| crash | 4,341 | 12% | 15% | 48% | 14% |
| enemy slow push | 2,999 | 12% | 8% | 40% | 16% |
| at its tower | 2,831 | 9% | 9% | 40% | 14% |
| enemy freeze | 451 | 2% | 1% | 32% | 5% |

**The recall's tempo barely separates leagues**: of the backs of Challenger and Grandmaster, 38% leave with the wave pushed or just crashed, and of
those of Gold and Platinum, 38% too. What separates is what they do on leaving: through mid 48-50% against 14-15%. The only clear gap is the
`enemy freeze`, which those at the top almost don't use for going back (2% against 1%, with very few cases) and after which almost nobody opens
through mid.

## What those at the top choose

A logistic regression (probability of opening through mid) fitted in Challenger and Grandmaster, out of fold by game. AUC 0.71-0.74 in all leagues;
clear (70% or more to one side) in 38-39% of the exits. What weighs most is the game minute (+0.56), the bot enemies in the lane (−0.46), the bot
wave (+0.23) and the extra minions (+0.28): **the wave and who is in the lane, not the whole map**.

Where the model says those at the top open through mid, opening through mid against going straight down: **+0.8 WP points at 90 s** [+0.2, +1.4] and
−0.9 pp of the marksman dying [−2.8, +1.2].

**Careful with the support's "match"**: since Gold almost never opens through mid and most of the clear situations are "don't open", the low leagues
match *more* (83% in Gold against 77% in Challenger). To measure a support, **how much it opens through mid** is what counts, not how much it matches;
that is why the replay analysis uses the former.

## Roams from the lane, according to the wave it leaves

Another, different decision: it is already in the lane with its marksman and leaves. 12,464 roams (of 15 s or more, or cut by a death) against 299,781
moments in which it stays, in the same game state (`value.effect`). **Not counting the 25,821 times it leaves to go back to base**: that isn't a roam,
and it was two out of three "roams" of `moments.roams` and of `value.md`.

| lane on leaving | roams | balance at 60 s | the marksman dies | of those who die: past the middle | next to their tower |
|---|---|---|---|---|---|
| pushed | 3,202 | −1.38 [−1.75, −1.07] | **+10.1 pp** | **69%** | 14% |
| crash | 1,498 | −2.32 [−2.90, −1.69] | +10.8 pp | 49% | 25% |
| at its tower | 1,451 | −1.14 [−1.70, −0.47] | +14.4 pp | 16% | 53% |
| neutral | 4,339 | −1.75 [−2.08, −1.45] | +14.6 pp | 37% | 28% |
| enemy slow push | 1,710 | −1.71 [−2.17, −1.13] | **+19.5 pp** | 19% | **56%** |
| enemy freeze | 264 | −1.81 [−3.12, −0.22] | **+26.6 pp** | 68% | 8% |
| **all** | 12,464 | **−1.63** [−1.81, −1.46] | **+13.5 pp** | 41% | 31% |

- **Leaving the lane costs in all waves** (−1.1 to −2.3 WP points at 60 s): there is no free window, what changes is how much. Removing the trips back
  to base raises the average cost from −0.98 (value.md) to −1.63.
- **What the wave does order is how much and how the marksman dies**: +10 pp with the wave pushed, +19.5 with an enemy slow push and +26.6 with a
  freeze. And with the good wave the one who dies does so past the middle of their lane (69%), whereas with the slow push they die under their tower
  (56%). It is the same distinction as in the openings: **with the wave in your favour the death is the marksman's; with the wave against, the roam's**.
- The WP balance and the marksman's death don't go together (the `crash` wave is the worst in WP and among the best in deaths) because the balance
  compares against staying **without evening out the wave**: the moments in which the support stays don't have the same mix of waves. The deaths
  column is homogeneous and is the one used for coaching.

---

# 3. From 14 on: the opening is the objective

Past the laning phase the opening that matters is the objective's: 45 seconds before a dragon, a baron or a herald spawns, the jungler and the
support want to be already preparing their zone (vision, a catch nearby). **99,060 rows**: each objective that spawns past 14:00 and each jungler and
support of the game.

It **prepares** if it spends 15 s or more of those 45 within 4,000 of the pit; **reset** if it spends 15 or more in base or dead (it doesn't have
those seconds to choose); otherwise, **elsewhere**, and there it is looked at whether it gets something: a kill it takes part in, a summoner that burns
an enemy next to it or a turret. The percentages are of the times it is on the map to choose (without the resets).

| league | jungle: prepares | elsewhere and gets something | and nothing | support: prepares | elsewhere and gets something | and nothing |
|---|---|---|---|---|---|---|
| Gold | 52% | 27% | 21% | 46% | 31% | 23% |
| Platinum | 52% | 27% | 21% | 45% | 31% | 24% |
| Emerald | 53% | 26% | 21% | 48% | 29% | 24% |
| Diamond | 52% | 28% | 21% | 47% | 31% | 22% |
| Master | 51% | 28% | 21% | 49% | 30% | 21% |
| Grandmaster | 53% | 29% | 18% | 51% | 30% | 20% |
| Challenger | 54% | 28% | 19% | 53% | 28% | 19% |

**Being at the objective barely separates leagues** (the jungler, 52% in Gold and 54% in Challenger; the support, 46% and 53%) and within a league
those who win and those who lose differ by a point. What does change is **who takes the objective**:

| position | what it does | times | its team takes it |
|---|---|---|---|
| jungle | prepares | 18,066 | **55%** |
| jungle | elsewhere and gets something | 8,906 | 54% |
| jungle | elsewhere and nothing | 7,049 | 48% |
| jungle | reset | 9,407 | 40% |
| support | prepares | 16,923 | **55%** |
| support | elsewhere and gets something | 9,913 | 53% |
| support | elsewhere and nothing | 7,543 | **43%** |

**Going elsewhere only comes out free if something is got there**: with a kill, a burned summoner or a turret, the team takes the objective almost
the same as if it had prepared it (54% against 55% for the jungler, 53% against 55% for the support); with nothing, it falls to 48% and 43%. Being
dead or in base is the worst (40-43%), and that is why it doesn't count as a decision.

---

## What it doesn't say

- **It is an association, not an experiment.** What the model doesn't see can decide both the opening and what comes out: above all where the enemy
  jungler really is (the player sometimes knows it from a ward the model doesn't look at) and what the team asks for in chat.
- **"What those at the top choose" isn't "the optimal"**: it is what those who play best do, and in the clear ones following it pays. In the unclear
  ones the model doesn't judge.
- The jungler's opening is measured by the half; it doesn't say which camp or which route within it. The support's is measured by stepping on mid; it
  doesn't say what it does there.
- One patch and one region: 16.19, EUW, from Gold to Challenger.
