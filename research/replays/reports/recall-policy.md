# The recall policy, learned without rules — all patches

**5,264 games** decoded: the 5,143 from the ladder (16.18 and 16.19, Gold to Challenger, with their league) and the
121 uploaded by users or loose (16.18 to 16.20, no league). All of them are used, whatever the patch: what this looks at
(gold, health, waves, timers) doesn't change from one patch to the next. The 7 games with a review in `research/coaching` are
left out of the training and are the exam. The numbers come from `policy.py` (usage in its docstring). The rows and the
model stay in `research/ladder/data/policy/`, ignored by git. **It is not integrated into the app.**

The question: can the system know when to go back to base **without anyone telling it**, just by looking at what people
do across thousands of games? Today `coach.py` judges each back with rules taken from the author's reviews (the
wave, the gold, the jungler's window). Here there are no rules.

---

## The essentials

1. **The game state predicts well when people go back**: AUC 0.880 validated by game, calibrated
   (when it says 33%, 33% go back). With only minute, gold, health and time away from base it stays at 0.818: the rest
   of the state (where they are, whom they see, the wave) really does contribute.
2. **What decides a recall most, learned on its own**: where they are on the map, the unspent gold, the health, how long they have been
   away from base and how far away they see an enemy. The wave weighs less than the reviews say, but it weighs: with the
   wave against the enemy tower, a laner goes back almost three times as often as with it far away (11-14% against 4-5% every 10 s).
3. **In the same state, the high league goes back more**: a Challenger, between 11 and 44% more than a Gold depending on the
   situation (28% on average across the 15 measures), and in all of them in the same direction. It fits the league report
   (the CS lost per back drops 27% from Gold to Challenger): they go back sooner and lose less because of it.
4. **Against the author's reviews: 9 of 12 judgements match**, without having been taught any of them. The 8 recalls the
   author considers good it recognises as normal high-league recalls (by chance 36% of moments would pass:
   all eight at once, one time in 3,500). Of the 4 windows the author considers missed it flags 1, nearly flags another
   (46% with the cut at 50%) and the other two it can't see as the author does (why below).
5. **It finds things outside what the author reviewed**: clear missed windows in reviewed games (Kaisa 17:50
   with 2,173 gold and 21% health) and in those with no review from them (Kaisa 8008728214: dies at 28:19 and at
   31:11 after recall windows with 1,293 and 1,985 gold; the one at 31:11 is the same one the rules-based review of
   that game points to, which says they died with 2,027 gold on them).

---

## Method

### The rows

For each champion alive and away from their base (more than 2,500 from the centre), every 10 s from 1:30, what they **could
know** at that instant:

| group | features |
|---|---|
| themself | minute, position, unspent gold, total gold, level, health, mana, summoners and ultimate ready |
| where | distance to their base, depth (0 their base, 1 the enemy's), whether they are in their lane and in the minion corridor |
| wave of the lane they are in | where the minions fall in the last 15 s, against the enemy outer tower and their own; minions alive on each side |
| enemies | the nearest visible enemy and how many are within 2,500 (only those that are seen, `seen`), how long until the lane opponent respawns, how many alive, how long since the enemy jungler was last seen |
| team | nearest ally, allies alive, team gold against the enemy, gold against the lane opponent |
| map | how long until the dragon (with the elder after the soul) and the baron, with the timers of wp-per-second.md |
| time | seconds since last in the base (or dead) |
| league | that of the game (Gold = 0 … Challenger = 6), empty in the uploads |

The label: whether a recall **that ends in the base** starts in those 10 s (`moments.recalls`, without the cancelled ones).
While any recall is channelling there is no row: the decision has already been made. From the ladder one in every
four rows without a recall is kept (and weighs four); from the uploads, all of them.

That gives 2,021,904 rows, 321,719 recalls (6.1 per player and game). The events are read from the first harvest (half
the size, the same thing that is needed) and the table from the second, which brings the game's visibility alongside.
No game failed.

### The model

Gradient boosting (`HistGradientBoostingClassifier`, 300 trees of 31 leaves, ≥ 500 rows per leaf). For the WP it didn't
pay off (wp-per-second.md) because there were 5,144 outcomes for 842,000 states; here every row brings its own label
and there are 321,000 decisions, which is where a model like this doesn't overfit to the games. It hasn't been compared with a
logistic regression.

The **high-league** policy is the mean of what it predicts with the league set to Master, Grandmaster and Challenger.

---

## Validation by game (5 folds, out of fold)

| model | log-loss | AUC |
|---|---|---|
| base rate (4.8% of rows with a recall) | 0.1927 | 0.500 |
| minute, gold, health, time away and position | 0.1599 | 0.818 |
| **the whole state (32 features)** | **0.1399** | **0.880** |

| predicts | go back |
|---|---|
| 0.06% | 0.02% |
| 0.50% | 0.32% |
| 1.59% | 1.35% |
| 4.38% | 4.39% |
| 13.55% | 14.09% |
| 33.15% | 33.37% |

It overshoots a little at the very low end (when it says 0.5%, 0.3% go back), which changes nothing of what follows.

## What decides a recall

How much the log-loss worsens when each feature is shuffled:

| feature | worsens |
|---|---|
| depth | +0.0238 |
| unspent gold | +0.0161 |
| health | +0.0161 |
| time away from base | +0.0115 |
| nearest visible enemy | +0.0109 |
| distance to their base | +0.0082 |
| position | +0.0078 |
| own minions alive | +0.0068 |
| minute | +0.0063 |
| enemy minions alive | +0.0059 |
| in their lane | +0.0054 |
| baron timer | +0.0033 |
| mana | +0.0031 |

## The same situation, a different league

Laners before 14:00, in the same states, probability of starting a recall in the next 10 s:

| the wave, against the enemy tower | Gold | Diamond | Challenger |
|---|---|---|---|
| very far (< −0.25) | 4.0% | 4.5% | 5.2% |
| −0.25 to −0.10 | 5.8% | 6.5% | 7.3% |
| −0.10 to −0.03 | 9.2% | 10.5% | 11.3% |
| arriving (−0.03 to 0.02) | 8.3% | 9.4% | 10.4% |
| against the tower (> 0.02) | 11.0% | 12.8% | 14.4% |

| unspent gold | Gold | Diamond | Challenger |
|---|---|---|---|
| < 500 | 1.3% | 1.5% | 1.8% |
| 500-900 | 7.7% | 8.8% | 10.0% |
| 900-1,300 | 16.7% | 18.6% | 20.5% |
| 1,300-1,800 | 22.9% | 25.5% | 27.3% |
| ≥ 1,800 | 26.7% | 30.2% | 32.1% |

| health | Gold | Diamond | Challenger |
|---|---|---|---|
| < 30% | 22.7% | 23.7% | 25.3% |
| 30-50% | 14.8% | 16.6% | 18.6% |
| 50-70% | 8.8% | 10.3% | 11.6% |
| 70-90% | 4.5% | 5.4% | 6.2% |
| ≥ 90% | 1.6% | 2.0% | 2.3% |

---

## The exam: the games with a review

Two measures, because they are two questions:

- **Staying.** H30 = the share of the high league that, in the states he actually went through, would have started a
  recall in those 30 s. **Missed window**: H30 ≥ 50% and he doesn't go back in those 30 s. It happens in 6.9% of moments.
- **Going back.** p = the share of the high league that goes back in those 10 s in that state. **Against-the-grain recall**: p below
  the 10th percentile of the rows where the high league really goes back (3.4%). 36% of the moments in which they don't
  go back would pass that bar.

The cuts (50% and the 10th percentile) were fixed before looking at the exam.

### Against what the author says

| game | minute | the author | the high-league policy | match? |
|---|---|---|---|---|
| Kaisa 8007142093 | 03:41 | good recall (after pushing, without going for the plate) | p 26%, 69th percentile of the high-league recalls | ✓ |
| Kaisa 8007142093 | 06:58 | good recall (after crashing) | p 24%, 64th percentile | ✓ |
| Kaisa 8007142093 | 10:13 | overstay: should have gone back and dies | H30 25%, 76th percentile of their game | ✗ |
| Kaisa 8007142093 | 13:29 | good recall (wave picked up, 1,570 gold) | p 8%, 25th percentile | ✓ |
| Qiyana 8008878706 | 01:50 | good recall (after the third camp) | p 11%, 37th percentile | ✓ |
| Qiyana 8008878706 | 06:41 | should have gone back (walks to Krugs with 1,350) | H30 46%, 97th percentile of their game | ✗ (close) |
| Qiyana 8008878706 | 08:36 | should have gone back (keeps clearing with 1,370) | H30 50%, 99th percentile: missed window | ✓ |
| Qiyana 8008878706 | 09:12 | good recall, late | p 5%, 17th percentile | ✓ |
| Qiyana 8008878706 | 10:32 | good recall (grubs and fight, opens on the dragon) | p 5%, 17th percentile | ✓ |
| Qiyana 8008878706 | 14:34 | cancels the recall because of a stimulus | H30 20%, 69th percentile | ✗ |
| Qiyana 8008878706 | 14:56 | good recall, at last | p 8%, 26th percentile | ✓ |
| Draven 8007681353 | 02:18 | good cheater recall | p 8%, 27th percentile | ✓ |

**9 of 12.** What each miss says:

- **Kaisa 10:13**: had been back at base 43 s earlier, with 781 gold and 36% health. The high league almost never goes back so
  soon with that gold; the author judges by the crashed wave and the unseen jungler (46 s). The policy is high for
  that game (76th percentile) but doesn't reach. Either the author's rule is stricter than how it is played, or a
  feature is missing (the risk of staying, not just what people do): the value answers that, below.
- **Qiyana 14:34**: it is a **cancelled** recall, and while it channels there are no rows. This doesn't judge cancellations.
- **Qiyana 6:41**: 46% with the cut at 50%. She went back at 7:24; the author rates it low importance if she goes back within 30 s.
- **The jungler's good recalls and the cheater recall** pass, but in the lower third of the high-league ones: the model
  doesn't see the camps (alive, about to respawn) nor does it know what a cheater recall is. It recognises them by the gold, the health and
  the place, not by the reason.

### What it flags outside what the author reviewed

| game | window | H30 | state | then |
|---|---|---|---|---|
| Kaisa 8007142093 | 17:50-18:20 | 96% | 2,173 gold, 21% health | goes back at 18:47 |
| Draven 8007681353 | 17:00-17:20 | 83% | 1,027 gold | goes back at 17:43 |
| Draven 8007681353 | 18:50-20:00 | 88% | 1,442 gold | goes back at 20:21 |
| Kaisa 8008728214 | 27:40-28:10 | 70% | 1,293 gold, 66% health | dies at 28:19 |
| Kaisa 8008728214 | 30:40-31:00 | 57% | 1,985 gold | dies at 31:11 |
| Aphelios 8008826796 | 23:50-24:10 | 84% | 1,231 gold | goes back at 24:34 |
| Kennen 8009746420 | 15:40-15:50 | 52% | 779 gold, 39% health | goes back at 16:12 |

Against-the-grain recalls: Kennen 4:56 (164 gold, 40% health) and three by the jungle Cho'Gath (2:20, 7:47 and 32:28,
with 408-605 gold). The jungler's have to be read with what was said about the camps.

---

## Limits

- **It imitates, it doesn't optimise.** It learns what the high league does, not what wins. If the high league stays too long
  somewhere, so does the policy. The next step is the value: with the per-second WP of `value.py`, compare going back
  against staying in similar states.
- **Jungle half-covered**: it doesn't have the camps (alive, when they respawn), which is what their recall depends on.
- **Cancellations are not judged**: while it channels there are no rows.
- **The exam is small**: 12 judgements across 3 hand-written reviews. The other 4 games only have the review that
  Claude writes from `coach.py`, which is not the author's criterion.
- **The league of the uploads isn't known** (117 games): they enter the training without a league.
- **Almost everything is 16.19**. All patches are used, as requested; with more uploads from other patches it can be measured whether
  the policy changes (the patch isn't among the features).

## Next

1. **The value of the recall**: for each row, the WP of their team 60-90 s later if they go back and if they stay, in similar
   states (`value.py`). With that the disagreement stops being "you don't do what the high league does" and becomes "it costs you
   this much".
2. **The camps in the jungler's rows**, and one row per cancellation (carry on or cancel?).
3. **The same pipeline for the other decisions** that already have a table in `features.py`: what to do with prio, the support's
   roam, holding or letting go of a freeze.
4. **More exam**: each new review from the author, first against the policy and then, if needed, against the code.

## Regenerate

```bash
# on the PC (the repo's Python); resumable: each game leaves its own file
PYTHONPATH=packages/ygg-core/src python research/replays/policy.py rows research/ladder/data/policy --processes 2
python research/replays/policy.py merge research/ladder/data/policy
PYTHONPATH=packages/ygg-core/src python research/replays/policy.py exam research/ladder/data/policy
# in a separate environment with scikit-learn (about 12 minutes with 2 cores)
python research/replays/policy.py train research/ladder/data/policy
python research/replays/policy.py cross research/ladder/data/policy
```
