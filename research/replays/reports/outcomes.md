# The jungler's outcomes tree — third version

Each of the jungler's options after a camp is valued by what usually happens in the next 90 s, instead of by how much its team's WP
moves. It comes from `outcomes.py` (usage in its docstring), over the 245,565 jungle decisions of 5,264 games, from the 1st camp until
14:00, read from the timeline. The complete tables are in `research/ladder/data/outcomes3/analyse.md`. In the same folder are the
tree for the Qiyana game (`qiyana.md`), the comparison with the adjusted measurement (`correct.md`) and the stability test
(`stable.md`). **It is not integrated into the app.**

## The idea

Measuring an option by the WP change at 90 s or at 5 min drags in everything that happens on the map. With that, an option's value state by
state wasn't learned (`routes.md`). Here the option is split into its outcomes, like a decision tree:

1. **What each outcome is worth**: the change in its team's WP against how often each thing happens, with all the decisions at once.
2. **What usually happens with each option in each state**: one model per outcome, with the option as a feature and only what the player
   knew.
3. **What an option is worth in a state**: the sum of each outcome expected times what it is worth, plus what the option is worth by
   itself.

## How it has changed

- **First version.** It said that ganking bot was the best in 82% of the decisions from the 3rd to the 6th camp, whether there was prio or
  not. A gank was only one that reached to hit, and outcomes were missing.
- **Second version:**
  - **Options go by intent**, that is, where the jungler is going:
    - **going to a lane** is being 4 s in a row in it (5 in mid), between the two turrets, with an enemy of that lane within 3,000;
    - **dive** is entering, in the 30 s after arriving, the range of a living enemy turret with an enemy beneath it;
    - **counter-gank** is arriving with the enemy jungler within 3,000 in the previous 20 s.
  - **The wave is the one that was seen and the one there will be on arriving** (below).
  - **More outcomes**: the lanes' CS, the turret and plate gold, and the jungler's health, mana and spent gold.
  - **What each option is worth by itself**, apart from its outcomes.

  That way it stopped saying "always gank", but the value of ganking barely depended on the state of the lane.
- **Third version (this one):**
  - **A separate model for going to a lane**, with that lane's state as the main thing:
    - the wave, the minions and how long it takes to arrive;
    - each side's health and flash, and the enemy's R and basic abilities;
    - their team's wards near the wave, the level difference (taken from experience) and the champions;
    - from the jungler itself, its flash, its R and its abilities.
  - **A new outcome: whether the gank ends in a kill** of an enemy of that lane in the 30 s after arriving. The earlier "kill" was any kill
    in the next 90 s.
  - **What each option is worth by itself, by stretches** of the game: a gank at the 3rd camp doesn't resemble one at the 10th.
  - **The enemy wards** are extracted, but don't enter the decision's value, because the jungler doesn't know where they are. They only
    serve for checking.

## The wave on arriving

The model is trained with one half of the games and checked with the other. The mean error is in advance (from 0 to 1 between the two
barracks):

| within | the model | assuming it stays where it is seen |
|---|---|---|
| 3-10 s | 0.031 | 0.052 |
| 11-20 s | 0.039 | 0.072 |
| 21-30 s | 0.051 | 0.088 |
| 31-45 s | 0.062 | 0.096 |

A wave that crashes against the enemy tower (0.64 on average) comes back by itself: 15 s or more later it is at 0.52, and the model
predicts 0.52. Of the decisions the first version gave "with prio", the wave is still crashing when the jungler arrives in 52%; in 45% it
has already come back to the centre.

## What is measured directly

**When a gank ends in a kill.** Of the 35,948 times a jungler goes to a lane before 14:00, 46% end in a kill of an enemy of that lane in 30
s, and the jungler dies within 90 s in 29%.

| in that lane, on deciding | kill | it dies |
|---|---|---|
| the enemy with flash / without flash | **40% / 50%** | 29% / 29% |
| the enemy's R ready / spent | 48% / 41% | 29% / 31% |
| the enemy with all 3 basics ready / with 1 or none | 45% / 45% | 29% / 29% |
| an enemy ward on the way / without it | 46% / 46% | 31% / 28% |
| its own ward nearby / without it | 48% / 44% | 30% / 28% |
| one level lower / one level higher | 42% / 47% | 30% / 28% |

- **The flash is the only thing that clearly separates.**
- **The enemy's abilities and wards barely change the kill.** It may be because junglers already take them into account: if the lane is
  warded, they go around or don't go.
- **By option:** gank top 59%, gank bot 57%, dive bot 64%, and mid quite a lot less (gank 27%, dive 41%).

**Ganking or diving bot, according to the wave on arriving.** From the 3rd to the 6th camp, whoever goes minus whoever continues clearing in
the same state, in WP points with its error. In bold, what ends up more than two errors from zero.

| the wave on arriving | gank at 90 s | gank at 5 min | dive at 90 s | dive at 5 min |
|---|---|---|---|---|
| in its half: the enemy ahead | +0.8 ±0.5 (512) | +1.7 ±0.9 | **+1.8** ±0.6 (280) | **+4.3** ±1.2 |
| in the centre | −0.1 ±0.6 (244) | −0.6 ±1.2 | +0.1 ±0.6 (278) | 0.0 ±1.2 |
| crashing at its tower | −1.7 ±1.3 (84) | **−5.6** ±2.4 | **+1.7** ±0.8 (146) | +2.7 ±1.8 |

With the wave crashing at the enemy tower, going bot and not going under the tower is the worst thing measured, and going under comes out
well. It is the comparison of whoever chose each thing, so there may be something more that distinguishes whoever chose each option in
that state.

## The tree

**What comes out well:**

- **The probability that the gank ends in a kill depends on the lane, and gets it right** with games the model hasn't seen:

  | | the model | for real |
  |---|---|---|
  | all the trips to a lane | 46% | 46% |
  | the enemy with flash / without flash | 41% / 49% | 40% / 50% |
  | the enemy's R ready / spent | 47% / 42% | 48% / 41% |
  | from those it sees as hardest to the easiest (five groups) | 22, 35, 46, 57 and 69% | 23, 37, 48, 58 and 65% |

- **Changing only the enemy's flash**, the kill goes from 55 to 63% in top and from 55 to 62% in bot. The R, the basic abilities, its own
  wards and the levels don't move it, just like in the direct data.
  - In Qiyana's decision at 1:47: Kennen with flash, 44% kill; without flash, 52%.
  - Knowing where the enemy wards were improves nothing (46% against 46%).
- **Ganking no longer comes out overvalued on average.**
  - From the 3rd to the 6th camp, continuing to clear comes out best in 66% of the decisions, invading in 16%, and the trips to a lane in
    14% among all. Only the options that at least 5% of Master-and-above junglers choose in that state count.
  - With the enemy ahead on arriving, the top gank is worth +0.02 in the tree, and what is measured is +0.05. In the second version it was
    worth +0.8.
- **The other outcomes are still calibrated**: kills, deaths, flashes, the lanes' CS and spent gold.
- **Going back to base comes out in the order of what is measured.** The worst is going back with little gold and good health (−2.9 in the
  tree, −3.0 measured); the least bad, with 1,300 gold or more (−0.8 in the tree, −0.1 measured).

**What still doesn't:**

- **It exaggerates the difference in deaths between ganking and clearing.** In the group it sees worst, it expects +0.18 more deaths and
  +0.08 happen. It is what comes from comparing two different models, the going-to-a-lane one and the rest's.
- **Two outcomes can't be read on their own**: the turret and plate gold, and mana, come out with the sign reversed at 90 s.
- **The value in points of each decision**, in the next section.

## The value in points: how far this data goes

**With this version's tree.**

**The measurement "from before" misled.** Comparing whoever chose an option with whoever continued clearing in the same state mixes what the
option is worth with who chooses it. Weighting each decision by how rare it was to choose that option there (with the policy, out of fold),
the adjusted measurement comes out (`outcomes.py correct`):

| group | tree | measured from before | measured, adjusted |
|---|---|---|---|
| gank bot with the wave crashing at its tower on arriving (90 s) | +0.2 | −1.7 ±1.3 | +0.2 ±1.8 |
| going back to base with 1,300 gold or more (90 s) | −0.8 | −0.1 ±0.2 | −0.6 ±0.3 |
| going back with little gold and good health (90 s) | −2.9 | −3.0 ±0.2 | −3.1 ±0.2 |
| gank top with the enemy without flash (90 s) | +0.1 | +1.6 ±0.6 | +1.2 ±1.4 |

- **The tree matches the adjusted measurement.** Of 28 groups (going to each lane according to the wave and the flash, going back according
  to gold and health), none ends up more than two errors off at 90 s, and one at 5 min, about what chance gives.
- **But in the trips to a lane, the adjusted measurement has errors of ±0.8 to ±2.3 points.** With 5,000 games, the data can neither confirm
  nor refute what ganking is worth in a specific state if the difference is 0.1 to 1 point. Going back to base, which is chosen much more,
  can: ±0.2-0.4.
- **Correcting the tree state by state with what is measured doesn't work.** That correction, done with each half of the games, doesn't
  resemble itself between halves (correlation from −0.08 to 0.10): it is noise. `game` doesn't use it.
- **The tree itself isn't stable in the trips to a lane either.** With each half of the games, what ganking is worth against clearing in a
  specific decision resembles itself little (correlation from 0.15 to 0.21), and changes 1.6 points on average. Going back to base (0.77) and
  invading (0.47) hold up better.
  - That is why Qiyana's top gank at 1:47 went from the best to the worst between versions.
  - The two halves agree on the best option in 82% of the decisions, but in those with two or more candidates only in 60%.
- **The probability that the gank ends in a kill is stable** where junglers really go: 0.84 between halves, with the smoothed kill model that
  now lives in `outcomes_model.pkl`, and just as calibrated. The tables in `analyse.md` are from the previous one. Within each option it
  distinguishes less (gank top, from 47 to 69% for real by fifths; gank mid, from 17 to 35%).

**How much data would be needed.** For what is measured about going to a lane in a state to have ±0.3 points, it would take on the order of 10
times more games (about 50,000) in the commonest groups, and more in the rare ones.

## For the review

- **The probabilities of each option** can be shown: that the gank ends in a kill, dying, forcing the flash. Better in bins (high, medium,
  low) than with the exact number. For example, "with Kennen with flash, this gank ends in a kill a little less than half of the time;
  without flash, a little more".
- **The value in points of going back to base** according to gold and health too, because it is stable and what is measured confirms it.
- **The value in points of going to a lane** decision by decision can't be shown as "the best" or "the worst". With this data it isn't stable.

## What each thing is worth

The outcomes, in WP points at 90 s and at 5 min:

| outcome | at 90 s | at 5 min |
|---|---|---|
| a kill it takes part in / its team's without it | +5.0 / +4.3 | +5.7 / +5.2 |
| it dies / an ally beside it | −5.6 / −4.7 | −6.8 / −5.7 |
| a 10-CS lead in the lanes | +1.9 | +2.5 |
| an objective for its team / for the enemy | +1.6 / −1.8 | +1.9 / −2.3 |
| the jungler's health (a whole bar) | +1.4 | +1.0 |
| forces an enemy flash / spends its own | +0.5 / −0.5 | +1.2 / −1.6 |
| 100 gold spent | 0.0 | +0.04 |

## Next

1. **More games**, if the goal is the value in points of each gank. With about 50,000 it could be measured in the common states.
2. **Meanwhile, build the review on what is stable**: the probabilities of each option and the value of going back to base.
3. Step 7 of the catalogue: covering a lane and the model of where the enemy jungler is. That model also serves for the probabilities,
   without depending on the value in points.

## Regenerate

```bash
# where the wave will be (~7 min), the options and outcomes (~40 min), and the tree (~90 min with 2 cores)
python research/replays/outcomes.py wave research/ladder/data/outcomes3 --timelines research/ladder/data/timelines
python research/replays/outcomes.py extract research/ladder/data/outcomes3 --timelines research/ladder/data/timelines \
    --decisions research/ladder/data/routes3/decisions.csv.gz
python research/replays/outcomes.py analyse research/ladder/data/outcomes3 \
    --decisions research/ladder/data/routes3/valued_decisions.pkl --routes-model-file research/ladder/data/routes3/routes_model.pkl
python research/replays/outcomes.py correct research/ladder/data/outcomes3 \
    --decisions research/ladder/data/routes3/valued_decisions.pkl    # ~15 min
python research/replays/outcomes.py game research/ladder/data/outcomes3 EUW1-8008878706 Qiyana \
    --rows research/ladder/data/routes3/games/EUW1-8008878706.csv.gz
```

- `analyse` needs `routes3/valued_decisions.pkl` (200 MB), which isn't on the PC. It is redone with
  `routes.py analyse research/ladder/data/routes3 --wp research/ladder/data/harvest-16.19/wp_per_second/wp_per_second.npz
  --model research/ladder/data/harvest-16.19/value/model.json`, about 8 min.
- `desenlaces_oof.pkl` (620 MB) isn't copied.
- Two analyses shouldn't be run at once: scikit-learn's trees trample each other's cores and go 30 times slower.
- The first version is still in `research/ladder/data/outcomes/` and the second in `desenlaces2/`.
