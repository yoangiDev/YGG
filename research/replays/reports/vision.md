# The support's vision: which ward is worth it, what it risks and what rises with the league — patch 16.19

**5,143 games** from EUW (harvest 2.0, the one with the game's real visibility), the same ones as `value.md` minus one that
couldn't be decoded. It comes from `moments.vision` and `moments.support_item`, through `features.py` (`watchers.csv`, one row per ward,
and the `guard_*`, `support_item_*` and `control_*` columns of `players.csv`). **305,527 wards from 10,264 supports.**

What decides whether a ward is good is not where it sits on a list of spots: it is **whether it showed someone**. An enemy
counts as revealed by the ward if they are within its range, visible to the team that placed it and **with no living ally close
enough to see them themselves**; that way the information is credited to the ward and not to the teammate who was walking
past.

## The ladder: what really changes from Gold to Challenger

Per-game means of the supports of each league (`players.csv`), and the jump from Gold to Challenger in standard
deviations. The direction of the vision score in the replay analysis (`coach.VISION`) comes from this column, not from
anybody's criterion.

| column | Gold | Master | Challenger | Gold → Challenger |
|---|---|---|---|---|
| wards per 10 min | 8.41 | 11.1 | 12.6 | **+1.34 sd** |
| control wards placed per 10 min | 1.05 | 1.71 | 2.17 | **+0.99 sd** |
| sweeps per 10 min | 2.69 | 3.22 | 3.54 | **+0.79 sd** |
| wards that find the enemy jungler, per 10 min | 1.73 | 2.35 | 2.59 | **+0.79 sd** |
| item charges thrown away on each back to base | 1.87 | 1.37 | 1.18 | **−0.91 sd** |
| wards placed with no window at all | 6.8% | 5.3% | 4.6% | **−0.35 sd** |
| share of wards that show someone | 57.7% | 56.9% | 56.6% | −0.09 sd |
| seconds of information per ward | 4.61 | 4.12 | 3.91 | −0.38 sd |
| share of high-risk wards | 11.0% | 14.4% | 15.8% | +0.20 sd |
| deaths while placing a ward | 0.89 | 0.96 | 1.03 | +0.10 sd |
| share of time with the support item empty | 13.6% | 17.9% | 17.3% | +0.34 sd |

- **What rises is the volume and the care over the refresh**, not the efficiency of each ward. A Challenger places half
  again as many wards as a Gold and almost twice the control wards, and goes back to base with fewer unspent charges.
- **The information per ward drops** (4.61 → 3.91 s): the more you place, the less each one adds —the ranges
  overlap— and the more of them get swept (27.6% in Gold, 31.3% in Challenger). Measuring a support by "seconds of info per
  ward" rewards placing few: **the total per 10 min does rise** (+0.59 sd).
- **The risk rises with the league** (11.0% → 15.8% of high-risk wards) with the same death rate (3.0-3.6%):
  taking risks is not the mistake, dying is. And dying while placing a ward doesn't separate leagues either (+0.10 sd), so it doesn't score;
  it still comes out as a moment, because in your own game it does hurt.
- **Having the item empty is not a vice**: the top players spend *more* time with it empty (13.6% → 17.3%) because
  they spend the charges sooner. What they don't do is go back to base with them still on.
- Comparing with those who win and those who lose **is no use for almost any of this**: in a game that is being lost the
  enemy is all over the place, so the wards show more and for longer (the losers: 62% useful wards
  and 4.77 s per ward, against 53% and 3.77 s for the winners). It is the game, not the support.

## When the ward is placed (`moment`)

| window | wards | share | show someone | s of info per ward | enemy jungler | sweeps | dies within 15 s |
|---|---|---|---|---|---|---|---|
| objective (within 3,500 of a pit, with the objective alive or 90 s from spawning) | 150,538 | 49.3% | 56.4% | 3.70 | 22.6% | 34.5% | 4.1% |
| prio (with their wave pushed) | 61,495 | 20.1% | 58.4% | 4.71 | 20.4% | 27.5% | 3.1% |
| reset (within 75 s of leaving base) | 76,464 | 25.0% | 53.7% | 4.10 | 18.6% | 25.7% | 4.1% |
| loose (none of the three) | 17,030 | 5.6% | 60.3% | 5.62 | 18.5% | 25.0% | 4.7% |

Half the wards are placed preparing an objective, and they are the ones that most often find the enemy jungler (22.6%) and the
ones that get swept most (34.5%: the enemy is doing the same thing there). The prio ones are the most efficient in information
per ward and the ones that cost least. The `loose` (loose) ones drop from 6.8% to 4.6% with the league: it is the window that is left over.

## What is risked (`risk`)

By where **the one placing it** is when they place it, not by where the ward lands. What was being looked for was "don't
facecheck without knowing where they are"; what the 255,928 wards placed outside a fight say (3.9% die in the
next 15 s) is simpler:

| enemies in view within 1,500 | wards | **dies within 15 s** |
|---|---|---|
| none | 186,377 | **2.4%** |
| one | 47,195 | **6.4%** |
| two | 17,251 | **10.1%** |
| three or more | 5,105 | **15.7%** |

**But who you are with also counts, and only once they already see you.** With two enemies in view, 9.2% die if they
have a teammate within 2,000 and **14.4% if alone**; with three or more, 15.3% against 19.3%. With one or with
none it makes exactly no difference (6.3 against 6.4, and 2.5 against 2.2): placing a ward accompanied is not safer in itself,
what changes is whether they can jump on you with nobody answering.

| enemies in view | with a teammate within 2,000 | alone |
|---|---|---|
| none | 2.5% (112,067) | 2.2% (74,310) |
| one | 6.3% (33,655) | 6.4% (13,540) |
| two | **9.2%** (14,483) | **14.4%** (2,768) |
| three or more | 15.3% (4,525) | 19.3% (580) |

**Walking in blind doesn't kill by itself.** With no enemies in view, being past the river or alone makes no difference: 2.7% neither
past nor alone, 2.5% alone, 2.2% past, 2.0% both. And adding the enemies not accounted for —since they
were last seen, have they had time to arrive?— doesn't either: 1.6% with zero, 1.9% with two, 2.2% with four and 2.4% with all five.
A sample of 8,480 wards said that with all five it rose to 22%; with the 5,143 games, it was noise.

So the risk is measured by **how many are already seeing you and whether there is someone with you**: `high` (high) three or more, or two
while alone; `mid` (medium) one, or two with someone beside you; `low` (low) none.

The risk **is paid for with information**: a high-risk ward shows about 30% more seconds than a low-risk
one. Five times more deaths for a third more information, and the share of high-risk wards **rises
with the league**: it isn't a vice to correct, it is a decision, and that is why the analysis shows it instead of scoring it.

## By ward type and by stretch of the game

| type | wards | share | show someone | s of info per ward | enemy jungler | sweeps | live (s) |
|---|---|---|---|---|---|---|---|
| trinket (the yellow one) | 18,061 | 5.9% | 60.1% | 5.51 | 16.6% | **14.6%** | 89 |
| from the support item | 241,613 | 79.1% | 56.7% | 4.21 | 21.8% | 27.0% | 99 |
| control (pink) | 45,853 | 15.0% | 53.1% | 3.05 | 18.4% | **54.3%** | 108 |

The control ward gets taken away more than half the time —it's the one the enemy goes looking for— and it is the one that shows
least per unit of time: its job is to deny, not to see.

| stretch | wards | show someone | s of info per ward | in an objective window | high risk |
|---|---|---|---|---|---|
| until 14:00 | 93,196 | 64.1% | 5.30 | 46.8% | 14.8% |
| 14-25 | 147,960 | 55.3% | 3.78 | 52.6% | 13.4% |
| 25 onwards | 64,371 | 47.5% | 3.16 | 45.3% | 14.5% |

Vision yields less and less as the game goes on: there is more vision placed by everyone, more sweeps and the map is
split into fewer places to pass through.

## The support item

3 charges on completing the first quest (Runic Compass, 3866) and 4 with the second (Bounty of Worlds, 3867, and what
comes out of it). Measured in 120 games: between two visits to the shop nobody places more than 3 with the first nor more than 4
with the second, and **on going from 3 to 4 on the map none is recharged**: the charges only come back in the shop.

Hence `moments.support_item`: the seconds spent on the map with the item empty, the backs to base with unspent charges, the control
wards bought and placed, and the sweeps.

**The control ward (2055) purchase events come duplicated**: in 96% of cases they come out in pairs
at the same instant and the gold only drops once (75 g). Riot's statsJson `VISION_WARDS_BOUGHT_IN_GAME` carries
exactly the same number as the events, so **it also counts double**. What matches the control wards
that are born in the game is counting **distinct purchase instants** (and that gives bought ≈ placed + 0-2,
which is what's expected). That is why the replay analysis shows the **placed** ones (`control_placed`), which are counted from the
ward that is born, and not the bought ones.

## What it doesn't say

- **It is descriptive.** That Challengers place more control wards doesn't prove that placing more control wards
  climbs the ladder; it proves that it goes along with everything else they do.
- The ward's range and the champion's are taken as fixed circles: fog by walls and terrain
  heights are not modelled, so "showed someone" is a generous approximation from above.
- One patch and one region: 16.19, EUW, Gold to Challenger.
