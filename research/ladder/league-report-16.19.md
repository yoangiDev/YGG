# What changes when climbing a league — patch 16.19

**1,001 games** from EUW on patch 16.19 (played since 23 September), **143 per league**: Gold, Platinum, Emerald, Diamond,
Master, Grandmaster and Challenger. Each game decoded whole from its `.rofl` (a per-second table of the ten champions and all
their events), and on top of that the concepts from `moments.py`: waves, prio, backs, vision, exits, side lanes,
objectives… In total, 10,010 player rows and about 330,000 concrete situations.

The numbers come from `research/replays/leagues.py`. For each feature there are three questions: **does it change when climbing a
league?**, **does it separate the winner from the loser?** and **does that change with the league?**

> **How to read the figures.** "Gold → Chall" is the mean in Gold and in Challenger. ρ is the rank correlation with the league
> (from −1 to 1; here almost everything that matters is between 0.15 and 0.55, which in game data is a lot). Only what passes
> |z| ≥ 4 counts as a pattern, that is p < 0.0001: with ~700 comparisons, chance lets none through. Counts are **per 10 minutes of
> the stretch they measure**, because Challenger games last less and otherwise it would look like they "do less of everything".

---

## The essentials

1. **Games get 14% shorter**: 30.6 min in Gold, 26.2 in Challenger. That is why the final level and the respawn times drop; that
   isn't skill, it is duration.
2. **The biggest difference between leagues is farming**, and above all the CS that isn't lost. +17 to +22% CS per minute in all
   three lanes, and the CS lost on each back falls 27% (5.3 → 3.9). It is the strongest pattern in the whole report (ρ = −0.56).
3. **Prio is used, and increasingly for more things.** Crashing the wave and doing nothing happens half as often in Challenger
   (8.6% → 4.1%). Rotating to another lane after crashing it multiplies almost threefold (8% → 22%), and a third of the time two
   things are done at once.
4. **The support stops being a lane: it is a map role.** It leaves its lane twice as often (2.7 → 5.5 times in the laning phase),
   places 40% more wards and does 65% of the work of preparing objectives together with the jungler (54% in Gold).
5. **The high-league jungler doesn't leave camps idle.** It loses 30% fewer clears (7.7 → 5.4 in 14 min), shows itself more (+11%)
   but with live camps much less often (68% → 53%), and goes back sooner to spend its gold.
6. **Warding isn't what changes; what changes is removing vision and getting information.** Between 42 and 116% more wards are
   killed depending on the position, and the mid gets 83% more seconds of information from its wards. At objectives, 65% more
   control wards are placed.
7. **What separates the winner from the loser is the same in Gold as in Challenger.** Almost nothing that distinguishes the winner
   changes its weight with the league. Everyone's base level rises, but what decides games is the same: dying less, crashing
   more waves, punishing facechecks, preparing objectives.
8. **Some things don't change at all with the league**: how many times it is frozen (≈2 per game), the damage and the duration of
   trades, which wave you back on, the frequency of slow pushes, and what the sidelaner knows of the map while pushing.

---

## 1. The pace of the game

| | Gold | Plat | Em | Dia | Master | GM | Chall | Gold → Chall | ρ |
|---|---|---|---|---|---|---|---|---|---|
| duration (min) | 30.6 | 30.5 | 29.5 | 27.7 | 26.6 | 27.4 | 26.2 | −14% | −0.25 |

The drop is mostly from Emerald to Diamond and from Diamond to Master. From this follow by themselves:

- a lower **final level** in all positions (support 13.7 → 11.9, top 17.2 → 15.9);
- a shorter **average respawn** (top 45.6 → 37.9 s), because people die at a lower level;
- **fewer seconds dead** per 10 min from minute 14 (−13 to −18%). Part of it is dying less, and part that deaths cost fewer
  seconds.

None of this is the player's merit. Any comparison of "totals" between leagues is contaminated by duration, which is why
everything here is per minute.

---

## 2. Laning phase (minutes 2 to 14): waves and prio

### CS

| CS per 10 min | Gold | Chall | change | ρ |
|---|---|---|---|---|
| top | 65.6 | 77.0 | +17% | +0.40 |
| mid | 65.6 | 79.5 | +21% | +0.47 |
| marksman | 67.6 | 82.6 | +22% | +0.50 |
| jungle (camps) | 54.3 | 65.3 | +20% | +0.53 |

At minute 14 the Challenger marksman has 113 CS and the Gold one 97; the mid, 115 against 97.5. It rises **continuously from
league to league**, with no jumps: it is the metric that best orders the leagues.

### Backs: more and cheaper, but looking the same

- Each laner goes back to base more times in the laning phase: top 2.7 → 3.5, mid 3.2 → 4.0, marksman 2.7 → 3.5, support
  2.8 → 4.0 (+27 to +43%).
- **The CS each back costs falls 27%**: 5.3 → 3.9 minions (ρ = −0.56, the strongest in the report).
- And yet, **the type of back is identical in all leagues**: ~35% with the cannon on its way, ~30% after the cannon, ~34% with
  a normal wave and under 1% without clearing the wave. It doesn't change which wave is left when going back: what changes is
  how well it is left (fully pushed, at the right moment) or how fast you go back.

> **A common mistake in low leagues:** it isn't going back at a bad time, it is going back *badly*: leaving the wave half done
> and losing 5 minions per back instead of 4. It seems little, but it is 3-4 backs per game in each lane.

### Prio: what is done when crashing the wave

| on crashing the wave… | Gold | Chall | change | ρ |
|---|---|---|---|---|
| **does nothing** | 8.6% | 4.1% | −52% | −0.24 |
| goes back to base | 37% | 43% | +15% | +0.20 |
| **rotates to another lane** | 8.1% | 22% | +170% | +0.45 |
| places vision | 24% | 31% | +30% | +0.24 |
| goes into fog | 23% | 19% | −18% | −0.18 |
| harasses under tower | 20% | 19% | = | — |
| **several things at once** | 18% | 32% | +72% | +0.43 |

- Crashing the wave and doing nothing **is cut in half**. In the players, unused prios drop between 52 and 65% in top,
  marksman and support.
- **Rotating after the crash is what rises most in the whole laning phase** (ρ = +0.45). In Gold, prio is spent mostly in one's
  own lane (going back, hiding or hitting); in Challenger, elsewhere on the map.
- Going into fog "just to go in" drops: in high leagues the fog comes on the way to doing something else.
- Harass under tower doesn't change (~19%). It is a use all leagues make the same.
- There are **fewer crashes** (27 → 23 per game up to minute 15) and they **cost less CS** (4.6 → 3.6). The CS the mid loses
  through its crashes halves (19 → 9.8).

### Crashed waves, slow push and freezes

| | Gold | Chall | does it change? |
|---|---|---|---|
| crashed waves per game | 20.8 | 17.2 | −17% (ρ −0.29) |
| of them, stacks of 2+ waves | 19% | 19.5% | **no** |
| a bounce that comes back | 53% | 50% | **no** |
| CS lost per crash | 4.7 | 3.6 | −23% (ρ −0.44) |
| slow pushes per game | 2.3 | 2.7 | **no** |
| slow push that **the enemy eats** | 61% | 73% | +21% (ρ +0.15) |
| slow push that reaches a crash | 68% | 58% | −15% (right at the threshold) |
| freezes per game | 2.0 | 2.2 | **no** |
| seconds each one lasts | 37 | 39 | **no** |

- **Freezing isn't a league thing**: about two freezes per game, of 38 s, in all leagues.
- **The slow push is done the same in all leagues, but in high leagues it is defended better**: the enemy eats it under their
  tower 73% of the time (61% in Gold) and it crashes less often. Setting it up is easy; capitalising on it isn't.
- The proportion of stacks and bounces doesn't change: the wave mechanics are the same. What changes is the cost (−23% CS lost
  per crash).

### Trades

Almost nothing changes: the same number of trades, the same damage (≈320 per champion and trade), the same duration (≈5.7 s),
the same probability of dying in one (≈9-10%) and the same health at the end (≈58%). Only two things change:

- **more abilities are used per trade** (2.4 → 2.7, +13%): denser trades, not longer ones;
- the **mid burns fewer summoner spells** in trades (1.9 → 1.5 per game, −23%).

> What is learned when climbing isn't to trade more or harder: the exchange itself looks very similar. What changes is everything
> around it (the wave, the prio, the backs).

---

## 3. By position

### Top

| | Gold | Chall | change |
|---|---|---|---|
| CS per 10 min | 65.6 | 77.0 | +17% |
| CS lost through its crashes | 16.0 | 10.7 | −33% |
| unused prios | 0.28 | 0.11 | −61% |
| lane exits (laning phase) | 0.93 | 1.40 | +51% |
| — without having pushed first | 0.27 | 0.51 | +91% |
| wards killed per 10 min | 0.34 | 0.62 | +84% |
| seconds of information from its wards | 7.4 | 11.0 | +49% |
| side-lane turns per 10 min (from 14) | 3.3 | 4.0 | +20% |
| objective setups | 1.04 | 0.82 | −22% |
| damage taken per 10 min | 11,900 | 10,550 | −11% |

The high-league top leaves its lane more, even without having pushed (the CS cost is absorbed), kills more vision and plays more
side lane. It takes part less in preparing objectives: the jungler and the support keep that.

### Jungle

| | Gold | Chall | change |
|---|---|---|---|
| camps per 10 min | 54.3 | 65.3 | +20% |
| seconds of idle camps (up to 14) | 884 | 592 | −33% |
| clears lost by leaving them idle | 7.7 | 5.4 | −30% |
| gold lost because of that | 761 | 595 | −22% |
| times it shows itself (up to 14) | 10.8 | 12.0 | +11% |
| shows itself with idle camps | 68% | 53% | −22% |
| seconds above 1,500 gold away from base, per 10 min | 61 | 47 | −22% |
| maximum gold carried | 2,551 | 2,285 | −10% |
| deaths per 10 min | 2.04 | 1.73 | −15% |
| facechecks it is punished for, per 10 min | 1.10 | 0.84 | −23% |
| wards killed per 10 min | 1.09 | 1.54 | +42% |

- **A common mistake:** leaving the small camps alive. In Gold almost a quarter of an hour of idle camps builds up in the laning
  phase: almost 8 lost clears, ~760 gold.
- In high leagues it **shows itself more often** (ganks more), without leaving farming behind. What it gets when showing itself
  is the same in all leagues: getting something ~73% of the time, a kill ~33%.
- It goes back to spend sooner: it spends 22% less time with over 1,500 gold on it.
- It dies less and enters fewer zones where it gets punished.

### Mid

| | Gold | Chall | change |
|---|---|---|---|
| CS per 10 min | 65.6 | 79.5 | +21% |
| CS lost through its crashes | 19.0 | 9.8 | **−49%** |
| backs in the laning phase | 3.2 | 4.0 | +27% |
| lane exits | 2.2 | 3.1 | +41% |
| seconds of information from its wards | 8.1 | 14.9 | **+83%** |
| wards killed per 10 min | 0.41 | 0.88 | **+116%** |
| side-lane turns per 10 min (from 14) | 1.6 | 2.8 | +77% |
| side-lane CS per 10 min | 17 | 31 | +78% |
| side waves crashed | 2.2 | 4.4 | +99% |
| summoners burned in trades | 1.9 | 1.5 | −23% |
| seconds ahead without knowing where the jungler is | 23 | 31 | +39% |
| objective setups | 1.35 | 0.95 | −30% |

- It is the position with **the biggest improvement in wave management** (the CS lost in crashes halves).
- **The high-league mid becomes a sidelaner from 14**: almost double the side-lane turns and double the side waves crashed.
- Its vision produces almost double the information, and it kills double the wards.
- **Surprise:** it spends more time ahead without knowing where the enemy jungler is (+39%), and yet dies less. Either it plays
  closer to the limit knowing it can, or it reads where the jungler is without seeing it (the calculation assumes the worst
  case). With this data it can't be told apart.

### Marksman

| | Gold | Chall | change |
|---|---|---|---|
| CS per 10 min | 67.6 | 82.6 | +22% |
| CS at minute 14 | 97 | 113 | +17% |
| wards killed per 10 min | 0.68 | 1.30 | +91% |
| backs in the laning phase | 2.7 | 3.5 | +31% |
| lane exits | 0.84 | 1.62 | **+92%** |
| — without having pushed first | 0.26 | 0.62 | +141% |
| CS lost by leaving | 5.9 | 10.2 | +73% |
| side-lane turns per 10 min (from 14) | 1.34 | 0.70 | **−48%** |
| deaths in the side lane | 0.20 | 0.10 | −47% |
| facechecks punished per 10 min | 2.96 | 2.44 | −17% |

- **In high leagues the marksman stops playing side lane** (half the turns, half the deaths there): the side lane is for the
  top and the mid. In Gold, the marksman alone in a side lane is common and costs deaths.
- In exchange it leaves its lane more in the laning phase, even without pushing, and pays the CS (+73%). It is probably
  following its support, which leaves twice as often (next section).

### Support

| | Gold | Chall | change |
|---|---|---|---|
| lane exits (laning phase) | 2.7 | 5.5 | **+103%** |
| — without having pushed first | 1.1 | 2.3 | +114% |
| CS its lane loses through its exits | 16 | 29 | +77% |
| wards per 10 min | 9.1 | 12.8 | +40% |
| vision score per 10 min | 23.7 | 29.6 | +25% |
| wards that reveal the enemy jungler | 1.46 | 1.88 | +29% |
| work in preparing objectives | 3.3 | 4.5 | +35% |
| backs in the laning phase | 2.8 | 4.0 | +43% |
| side-lane turns per 10 min | 0.39 | 0.06 | −83% |
| damage per 10 min | 4,800 | 3,560 | −26% |
| CS per 10 min | 13.5 | 10.2 | −25% |
| ward charges recovered while dead | 0.76 | 1.25 | +66% |
| seconds ahead without knowing where the jungler is | 18 | 30 | +65% |

- **It is the position that changes most.** The Challenger support leaves the lane twice as often (almost always without having
  pushed), places more and better vision, and prepares more objectives.
- It stops being a second farmer and a second damage dealer: less CS, less damage.
- It manages to die with charges spent (+66% of charges recovered while dead): it has used the wards before falling. It is
  exactly what makes its death cost less.
- It is almost never alone in a side lane (0.06 turns per 10 min against 0.39 in Gold).

---

## 4. Macro: exits, side lanes, grouping and objectives

### Lane exits (laning phase)

| | Gold | Chall | does it change? |
|---|---|---|---|
| exits per game | 13.4 | 23.3 | **+74%** (ρ +0.50) |
| leaves with the wave pushed | 63% | 59% | no |
| gets something from the exit | 81% | 84% | no |
| — a deep ward | 22% | 28% | +28% |
| — a kill it takes part in | 37% | 34% | no |
| leaves accompanied | 83% | 82% | no |
| CS lost per exit | 6.5 | 5.4 | −18% |

**In high leagues people leave far more, and each exit pays off the same**: ~82% get something in all leagues. That is,
leaving more doesn't lower the exits' quality. Also, each exit costs less CS.

### Side lanes (from minute 14 to the end)

| | Gold | Chall | does it change? |
|---|---|---|---|
| side-lane turns per 10 min | 13.9 | 15.8 | +13% |
| dies in the turn | 16% | 12.5% | **−23%** |
| enemies unlocated while pushing | 2.1 | 2.2 | **no** |
| the enemy shows up | 92% | 92% | no |
| with the ultimate ready | 60% | 53% | −11% |
| CS per turn | 10.1 | 10.7 | +7% |
| side lanes abandoned, per 10 min | 6.5 | 5.4 | −17% |
| gold lost in each abandonment | 573 | 522 | −9% |

- People die less playing side lane **with the same information**: the unlocated enemies are the same (≈2) in all leagues. The
  difference is in how it is left, not in what is known.
- Fewer side lanes are abandoned, and when they are they cost a little less.
- **Curious:** in high leagues people push more times without the ultimate ready. It may be that it is used more, or that they
  push without needing it.

### Over-grouping (overgroup)

Overgroups **rise** with the league (4.3 → 5.7 per 10 min from 14, +33%), but each one costs the same (≈2.4 minions). Together
with the abandoned side lanes, which fall, this draws how the game is played at the top: the team groups more often around
objectives and accepts losing a few minions for it, but fixes the lane sooner and doesn't let it bleed wave after wave.

### Preparing objectives

| per objective and team | Gold | Chall | does it change? |
|---|---|---|---|
| control wards in the zone | 0.30 | 0.50 | **+65%** |
| share of the jungler/support duo's work | 54% | 65% | **+20%** (ρ +0.37) |
| players who prepare it | 2.15 | 1.92 | −11% |
| seconds of ward in the zone | 77 | 80 | +4% |
| facechecks punished during the preparation | 1.17 | 0.97 | −17% |
| seconds ahead on arriving | 68 | 69 | no |

- **Specialisation**: in high leagues fewer players prepare it and the jungler/support duo takes two thirds of the work. The mid,
  the top and the marksman prepare between 20 and 30% less.
- Many more control wards are placed. The total ward time in the zone barely changes.
- There are fewer facechecks punished in the setups: either there is less facechecking, or less punishing. Since the punishments
  per game (≈12 per 10 min) and the probability of dying punished (≈28%) don't change with the league, the former is most likely.

**Who takes the objective?** It is the same in all leagues:

| the team that had more… | takes it |
|---|---|
| presence in the zone | 84% |
| control wards | 68% |
| facechecks punished | 68% |
| ward seconds | 58% |
| lead on arriving | **51%** (doesn't matter) |

Arriving first is worth nothing by itself (51%). What takes the objective is controlling the zone: removing the enemy vision and
punishing whoever enters. (Presence is partly tautological: whoever is there is the one who kills it.)

---

## 5. Vision: what changes isn't how much is warded

| | Gold | Chall | change |
|---|---|---|---|
| wards killed per 10 min — top | 0.34 | 0.62 | +84% |
| — jungle | 1.09 | 1.54 | +42% |
| — mid | 0.41 | 0.88 | +116% |
| — marksman | 0.68 | 1.30 | +91% |
| — support | 2.19 | 2.82 | +29% |
| wards that reveal someone — mid | 1.5 | 2.1 | +38% |
| — top | 1.4 | 1.9 | +34% |
| seconds of information per ward — mid | 8.1 | 14.9 | +83% |
| crash → vision | 24% | 31% | +30% |
| exit → deep ward | 22% | 28% | +28% |

- **Killing the enemy vision is what rises most**, in all positions. In Gold the top and the mid barely kill wards.
- The high-league laners' wards **show someone** more often and for longer: they are placed where people pass.
- The official vision score only really changes for the support (+25%) and the jungler (+18%).

---

## 6. What separates the winner from the loser (and barely changes with the league)

Here the comparison is within each game: the winner against the loser of the same position (same league, same duration, one
against the other). The percentage is in how many games the winner has more; 50% means it separates nothing.

**The result features separate hugely, but they are a consequence of winning**: level (86-92%), plates (81-88%), gold (72-79%),
kills and assists. The winner dies less in 75-85% of games. None of this is surprising.

**The decision features**, those that serve for learning:

| the winner has more… | top | jungle | mid | marksman | support |
|---|---|---|---|---|---|
| punishments of enemy facechecks | 64% | 68% | 69% | 71% | 72% |
| crashed waves (prio) | 59% | — | 64% | 64% | 64% |
| work in preparing objectives | 59% | 60% | — | 61% | 64% |
| lane gold at minute 14 | 59% | — | 66% | 66% | 64% |
| CS at minute 14 | 57% | — | 60% | 62% | — |
| time in enemy territory | 57% | — | 60% | 57% | 60% |
| backs in the laning phase | 57% | — | 60% | 60% | 58% |
| invisible time (jungle) | — | 62% | — | — | — |

| the winner has **fewer**… | top | jungle | mid | marksman | support |
|---|---|---|---|---|---|
| times a facecheck of theirs is punished | — | 30% | 39% | 39% | 28% |
| deaths in trades | 42% | — | 39% | 38% | 39% |
| side-lane turns (marksman and support) | — | — | — | 41% | 36% |
| exits without having pushed (support) | — | — | — | — | 43% |

- **Punishing and not being punished** separates in all positions (64-72%), and more so in the marksman and the support.
- **Crashing more waves** and **going back more often** in the laning phase separate equally in all lanes.
- The marksman and the support who win play *less* side lane: ending up alone in a side lane is a losing thing.
- The support who wins leaves less often without having pushed first.

**Does the weight of this change with the league?** Almost never. Of all the features, only one changes clearly between
Gold/Platinum and Master or above: **the jungler's kills**, which in Gold-Platinum separate the winner in 63% of games and in
Master or above in 77% (z = +3.9). In high leagues, the jungler who converts their ganks into kills wins much more often.
Everything else weighs the same in all leagues.

> **Important:** this is association, not cause. The one who is ahead crashes more waves *because* they are ahead. The laning-phase
> metrics (up to 14) are less contaminated than those after, but they aren't clean either. Separating "what makes you win" from
> "what the one who is winning does" is the model's job, with the game's state at every moment.

---

## 7. Common mistakes: what is corrected most when climbing

Ordered by how strong the pattern is:

| mistake | Gold | Chall | ρ |
|---|---|---|---|
| CS lost on each back | 5.3 | 3.9 | −0.56 |
| CS lost on each crashed wave | 4.7 | 3.6 | −0.44 |
| CS lost by the mid in its crashes | 19.0 | 9.8 | −0.39 |
| seconds of the jungler's idle camps (up to 14) | 884 | 592 | −0.36 |
| jungler who shows itself with idle camps | 68% | 53% | −0.32 |
| CS lost on each lane exit | 6.5 | 5.4 | −0.29 |
| marksman playing side lane (turns per 10 min) | 1.34 | 0.70 | −0.27 |
| a crash with no use at all | 8.6% | 4.1% | −0.24 |
| jungler with gold on them without going back (s per 10 min) | 61 | 47 | −0.20 |
| dying in a side-lane turn | 16% | 12.5% | −0.20 |
| side lanes abandoned (per 10 min) | 6.5 | 5.4 | −0.15 |
| jungler's deaths (per 10 min) | 2.04 | 1.73 | −0.18 |

The message: **in low leagues gold is lost through carelessness, not through bad decisions**. Minions that escape on backs,
crashes and exits, camps left idle and crashed waves that aren't taken advantage of. They are management errors, and all of them
fall continuously from league to league.

---

## 8. Hits: what rises most when climbing

| hit | Gold | Chall | ρ |
|---|---|---|---|
| support exits | 2.7 | 5.5 | +0.53 |
| support wards (per 10 min) | 9.1 | 12.8 | +0.50 |
| lane exits, everyone (per game) | 13.4 | 23.3 | +0.50 |
| rotating after crashing the wave | 8% | 22% | +0.45 |
| doing several things with the prio | 18% | 32% | +0.43 |
| objective work in the hands of the jungler/support duo | 54% | 65% | +0.37 |
| wards killed by the marksman (per 10 min) | 0.68 | 1.30 | +0.34 |
| mid's side lane (turns per 10 min) | 1.6 | 2.8 | +0.33 |
| control wards at objectives | 0.30 | 0.50 | +0.30 |
| abilities per trade | 2.4 | 2.7 | +0.27 |
| information from the mid's wards (s) | 8.1 | 14.9 | +0.27 |
| crash → vision | 24% | 31% | +0.24 |
| exit → deep ward | 22% | 28% | +0.22 |

The message: **in high leagues the lane's advantage is taken to the map**. Waves are crashed to go elsewhere, the support and the
mid move and vision is removed as well as placed. And the roles are shared out: the duo prepares the objectives, and the top and
the mid play the side lanes.

---

## 9. What doesn't change with the league

These features are **the same from Gold to Challenger** (none passes the threshold), and they are clues to what doesn't need
teaching, or to what the concept doesn't capture:

- **freezing**: ≈2 freezes per game, of ≈38 s, with ≈3.7 minions denied;
- **the type of back** (with the cannon on its way, after the cannon, with a normal wave);
- **the trade itself**: number, damage, duration, probability of dying in it;
- **how many times a slow push is set up**, and how many of the crashes are stacks of 2+ waves;
- **the bounce**: it comes back in half of the crashes in all leagues;
- **the quality of each exit**: getting something ~82%, leaving with the wave pushed ~60%, leaving accompanied ~82%;
- **what the jungler gets when showing itself**: something ~73% of the time, a kill ~33%;
- **what the sidelaner knows**: ≈2 enemies unlocated while pushing, and the enemy shows up in 92% of the turns;
- **punishing facechecks**: ≈12 per 10 min, and the punished one dies in ≈28% of cases;
- **arriving first at the objective**: ≈68 s of lead in all leagues, and it doesn't decide who takes it.

---

## 10. Limits

- **One sample, one patch, one region.** EUW, 16.19, 143 games per league. The differences of ρ ≈ 0.15 are real (z ≥ 4) but
  small. A game's league is that of the player it was picked for (YGG takes up to 3 games per player), and the rest of the lobby
  is at a similar MMR.
- **Association, not cause**, above all in what happens after minute 14 (whoever is ahead plays side lane, controls vision and
  prepares objectives *because* they are ahead).
- **The metrics are the concepts of `moments.py`**, which are measured rules and not the truth of the game. Where the rule falls
  short, the pattern inherits it. (E.g.: "ahead without knowing where the jungler is" always assumes the worst case.)
- **Clean data, but not perfect**: ~40 impossible health or mana values are discarded (uninitialised emulator memory, 0.02% of
  trades). 4 games out of 1,001 don't match their own statsJson; removing them changes no result: the same 404 rows come out, and
  only two that were right at the threshold (z ≈ 4) swap places.
- The column `linea_placas` always comes out as 0 (it needs the timeline). Plates come from the `.rofl` in `plates` and
  `plate_gold`.

## How to reproduce

```bash
python research/replays/features.py ../lol-replay-decoder/data/cosecha research/ladder/data/harvest-16.19/features --leagues research/ladder/data/harvest-16.19/matches.jsonl.gz
```

```bash
python research/replays/leagues.py research/ladder/data/harvest-16.19/features > research/ladder/data/harvest-16.19/leagues.md
```

The second writes all the complete tables (about 400 rows: each feature that passes the threshold, by position, and all the
situations). This report is the reading of those tables.
