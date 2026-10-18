# Situations: what can be learned from the games and how your knowledge enters

All the situations of a game that can be analysed with what the replay carries, what can be learned from each one, and how what you
know passes into the model without the model just copying you. It completes the decisions table of `catalog.md`; the numbers in
parentheses ("catalogue 2") are those of that table.

---

## What the replay doesn't carry

- **Communication**: pings and chat. You can't know whether the jungler warned or whether the support asked for the roam.
- **The camera**: what the player was looking at. What they "knew" is derived from what their team saw, not from their screen.
- **The draft**: the order of picks and bans. Champions enter as state, not as a decision.
- **What they were thinking**: intention is deduced from where they go, not from what they wanted to do.

The seconds left on each ability or spell don't come, but they can be deduced: each cast carries its cooldown.

---

## The situations

**Learned with**: how many games are needed for the value of each option decision by decision.

- **already**: with today's 5,000, and measured.
- **10-20 thousand**: it happens many times per game or weighs several points.
- **~50 thousand**: once or twice per player and game, and weighs little (0.1-1 point), like a gank.
- **probabilities**: too rare for its value in points. From it you do learn what usually happens with each option and the player's
  habits.

Only "already" and the ganks are measured (`outcomes.md`). The rest comes from counting how many times it happens in 1,317 games and
from what it weighs, so it is an estimate.

### Level 1 (until 1:30)

| situation | who | options | learned with |
|---|---|---|---|
| Invading or defending at level 1 | all five | invade, defend the jungle, deep ward, go to lane | probabilities (once per game) |
| Leash | the laners on the side where the jungler starts | help or not, and for how long | 10-20 thousand |
| Side and first camp | jungle | the starting camps | already (catalogue 2) |

### Laning phase (until 14:00): laners

| situation | who | options | learned with |
|---|---|---|---|
| **Going back to base** | everyone | go back or continue, and with how much gold | already (catalogue 1) |
| The wave before leaving | laners | push, freeze, leave it, stack it | 10-20 thousand (catalogue 7) |
| Trading hits | laners | hit, all-in, retreat | 10-20 thousand (about 20 skirmishes per laner) |
| Going for the kill in lane, 1v1 or 2v2 | laners | all-in or not, with or without ignite and flash | ~50 thousand |
| The race to level 2 and 3 | bot, mid | push to level sooner or not | probabilities |
| **Roam** | mid, support; top and ADC less | go to each lane or stay | ~50 thousand (catalogue 6). Per game: support 1.9, mid 0.9, ADC 0.4, top 0.3 |
| Responding to a roam or an enemy gank | laners | follow it, push and plates, stay | ~50 thousand |
| TP | top, sometimes mid | back to lane or flank | to lane, 10-20 thousand (the top uses it 2 times per game); flank, probabilities (catalogue 9) |
| Positioning according to the enemy jungler | laners | move up with the wave or not | 10-20 thousand, once the model of where the enemy jungler is exists (catalogue 3) |
| Plates with the enemy out of lane | laners | plates, go back, roam | 10-20 thousand |
| Flash, ignite, exhaust | everyone | use or keep | 10-20 thousand (about 4 flashes per player and game) (catalogue 9) |

### Laning phase: jungle

| situation | who | options | learned with |
|---|---|---|---|
| **Route** | jungle | camp, invade, crab, objective, gank, dive, counter-gank, base | already for going back and invading; ~50 thousand for each gank (catalogue 2) |
| **Covering a lane** | jungle | go before the enemy arrives, carry on with its own, invade the other side | ~50 thousand (catalogue 3) |
| Smite on a contested objective | jungle | use it or not, and when | probabilities |

### Objectives (the whole game)

| situation | who | options | learned with |
|---|---|---|---|
| **Showing up** | everyone | go or not | 10-20 thousand (catalogue 5; done in `trees.py`) |
| Taking it, contesting it, trading it or giving it up | the team | take it, contest it, trade it for something else (a turret, another epic), give it up | 10-20 thousand (7-9 epics per game) |
| Preparing it | the team | vision and pushed waves in the minute before | 10-20 thousand |
| Baron and Elder | the team | start or not; with how many enemies dead or far | 10-20 thousand: it weighs a lot |

### Fights

| situation | who | options | learned with |
|---|---|---|---|
| **Engaging or not** | everyone | engage or not | 10-20 thousand (catalogue 4; done in `trees.py`, without the fine features) |
| Starting it | whoever engages first | engage now or wait (the R, the flash, the numbers) | 10-20 thousand |
| Whom to hit | everyone | the carry, the one in front, the closest | 10-20 thousand (each one's damage to each one) |
| Retreating or chasing | everyone | chase, cut off, go back | 10-20 thousand |
| **After winning it** | the team | turret, objective, invade, go back | 10-20 thousand (about 5 team fights per game, plus picks) |
| After losing it | the team | defend, concede, go back | 10-20 thousand |

### After 14:00

| situation | who | options | learned with |
|---|---|---|---|
| Grouping or split | everyone | group in mid, split a side lane, farm | not estimated (catalogue 10) |
| Responding to a split | the team | send one or two, force the other side | not estimated |
| Farming or rotating | everyone | the jungle, the side lanes, going with the group | not estimated |
| Turrets and inhibitors | the team | siege, defend, concede | 10-20 thousand |
| Playing with the enemies dead | the team | baron, inhibitor, turret, go back | 10-20 thousand |
| Closing the game | the team | go to the nexus or go back | probabilities |

What comes after 14:00 doesn't have options defined yet. That is where almost all the team situations are, and where your judgement
is most needed to know what counts as a "split" or as "grouping".

### The whole game

| situation | who | options | learned with |
|---|---|---|---|
| Vision | everyone (the support places about 30 wards per game; the rest, 6-9) | where and when; control ward; sweeping | not estimated: it depends on how many zones the map is split into (catalogue 8) |
| **Why it dies** | everyone | it isn't a decision: without vision, without flash, with the enemy jungler unseen, outnumbered… | already: it happens a lot |
| Items | everyone | what and when | probabilities, per champion (catalogue 11) |
| Ability order | everyone | what to level at each level | probabilities, per champion |
| Performance | everyone | it isn't a decision: CS, gold and experience against their opponent, damage, ability accuracy | already: it needs no model, it is compared with their elo |

---

## How your knowledge enters

Your knowledge decides **what is looked at and what is compared**. The games decide **what it is worth**. That way the model reaches its
own conclusions, but looking at what a good player looks at.

| what you write | example | where it enters |
|---|---|---|
| 1. **The situations and their real options** | "A gank with prio doesn't exist" → the dive became a separate option (2nd version) | each decision's detector and its options |
| 2. **What you look at** in each one | "The flash, the abilities and the wards" → the kill probability went on to distinguish from 23 to 65% (3rd version) | state features, taken from the timeline |
| 3. **Each champion's traits** | (new) | a table that replaces the champion's name |
| 4. **What you are sure of** | "Without the enemy's flash, the kill isn't less likely" | fixed directions of the model (`monotonic_cst`) |
| 5. **Test cases** | Qiyana's top gank at 1:47 | checked in every version |
| 6. **Reviewing where you disagree** | — | looks for what is missing; it doesn't enter as an answer |
| 7. **How you would say it** | "The wave is crashing into your tower" | the coach's phrases for each feature |

**1 and 2** are what changes the model most, and what you have already done twice.

**3, the champion traits**, is what makes 50,000 games enough.
- Today the model uses the champion by its name. In the 5,265 games, the tenth most played champion of each role appears in 260-340, and the typical champion in
  6-51.
- With traits (how much control it has, how many escapes, its range, its strength in each phase, the threat of its gank at level 2, 3
  and 6), a little-played champion learns from those that resemble it.
- Most are measured in the games: the control it applies, the dashes, the range of its attacks, the damage per level. You correct what
  the data doesn't capture, such as a champion's R being a map-wide gank.

**4, the fixed directions**: the model can't go against them, even if the data say otherwise.
- They are only valid for the obvious.
- Before fixing one, it is checked whether the data already satisfy it. If they don't, that is a case for point 6.

**5, the test cases**: moments with what you expect (for example, "kill between 40 and 60%").
- They are checked in every version. A version that breaks one is looked at before being accepted.
- That would have warned about Qiyana's top gank, which went from the best to the worst between versions.

**6, reviewing where you disagree**: it replaces injecting your reviews.
- You review the moments where the model says something that doesn't add up for you.
- Either a factor is missing, and it goes back to point 2, or the data say something else, and the one who learns is you.

**What doesn't enter: your verdict on which one is the good one.** If it is trained on that, the model copies you, and with 50,000 games
the data can measure it.

---

## Each situation's sheet

One per situation. Each section goes to a part of the code:

```markdown
## <situation>
- Who and when it starts:        → the decision's detector
- Real options:                  → the options (and those that don't exist)
- What you look at, by weight:   → the state features
- What you are sure of (if X, Y): → fixed directions and test cases
- When it changes:               → crossings between features (champions, timers)
- How it looks in the replay:    → what separates one option from another
- Cases (2-3 moments):           → test cases
- How you would say it:          → the coach's phrases
```

An example with the gank, with what you have already said; you fill in what is missing:

```markdown
## Gank
- Who and when it starts: the jungler, on finishing a camp, until 14:00 (catalogue 2).
- Real options: gank, dive, counter-gank, or carry on with its own. With prio there is no gank: the enemy is under its tower, and
  that is a dive.
- What you look at, by weight: the enemy's flash; its abilities and your laner's; the wards that see you coming; the wave on arriving;
  (to be filled in).
- What you are sure of: the kill chances are much lower than they seem, because of the flash, the abilities and the wards. (To be
  filled in: whatever has no exception.)
- When it changes: (to be filled in)
- How it looks in the replay: it arrives at the lane with an enemy of its own within 3,000; a dive if it goes under the tower with an
  enemy below.
- Cases: Qiyana, 1:47, top gank: the model gives the kill 48%. (What do you expect?)
- How you would say it: (to be filled in)
```

---

## Before downloading

**The download only depends on the decoder saving everything raw.** The situations, the features and the sheets are taken afterwards
from the timeline, without decoding again. So the sheets can go at the same time as the download.

What has to be checked beforehand:

1. **The champions' headings**: each click's destination and the dashes. Only the recent decoder produces them. Check with a couple of
   new games that they come out.
2. **`SkillUp` and `SellItem`**: the decoder produces them, but the timeline doesn't store them. They are added to `timeline.py` (layer 2,
   without decoding again).
3. **The runes**: they come in `match.json`. They are stored in the timeline next to the spells.
4. **The WP of the new games**: today it comes from `wp_per_second`. For the new ones it has to be computed from the timeline.
5. **The space**:
   - a `.rofl` takes about 20 MB, so 50,000 are ~1 TB;
   - the decoded output, ~5 MB per game (~260 GB);
   - the timeline, 560 KB (~28 GB).

   Without the `.rofl` it can't be decoded again. If there is no room to keep them, they are deleted only after checking points 1 and 2
   with the new patch.
6. **The time**: at ~25 s per game, 50,000 is about 350 h of decoder with one process.

---

## Order

1. Check the decoder (points 1-4) with a few games of the current patch, and start downloading.
2. Meanwhile, you, the sheets. First those that weigh most in the coach:
   - covering a lane, which is step 7 of the catalogue;
   - going back to base and the wave before leaving;
   - the roam;
   - after winning a fight.
3. Me, the champion-trait table, with what is measured in the games, for you to correct.
4. With 10,000 games, the stability test of `outcomes.md`: if the correlation between halves of the ganks rises from ~0.18 to ~0.30, the
   50,000 estimate holds.
