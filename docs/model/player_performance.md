# How a player's performance is analysed

All the ideas YGG uses, or could use, to measure how someone plays League of Legends: where they come from (many from
traditional sport), how they are computed and how they are read. Each idea carries its status:

- **Applied**: already in the code and visible in the app.
- **In progress**: being worked on now.
- **To apply**: a proposal, with how it would be done.
- **Discarded**: thought through and shelved, with the reason.

At the end there is a glossary of the technical terms.

---

## 1. The questions and the traps

Analysing performance means answering one question: **how much of the result is this player's merit (or fault), and how
much is context?** Five traps appear again and again, in LoL and in any sport.

1. **Result ≠ performance.** You can play well and lose, or play badly and win carried. A metric that only rewards winning
   measures the team, not the player.
2. **Association ≠ cause.** The team that takes down an inhibitor wins 93% of the time, but it doesn't win *by* taking it
   down: it takes it down *because* it was already winning. What an event adds has to be separated from what merely goes
   along with being ahead.
3. **Context changes the value.** Dying in an even game isn't the same as dying in a decided one; a kill in a game of 60
   kills is worth less than in one of 15.
4. **Few games lie.** With 3 games on a champion, a 100% winrate says nothing. Every average needs to know how much noise
   it carries.
5. **You have to compare with the right reference.** A support doesn't farm like a mid; an Iron doesn't play like a
   Challenger; a 40-minute game isn't a 20-minute one.

Every idea in this document answers one of these five traps.

---

## 2. What is already applied

### 2.1 Per-minute stats · Applied

- **Idea:** compare production per unit of time, not totals. It is basketball's "per 36 minutes": whoever plays more
  minutes accumulates more.
- **In YGG:** CS/min, damage/min, vision/min and gold/min. Kills, deaths and assists stay per game, but adjusted for pace
  (2.3).
- **Limit:** in a 45-minute game CS/min drops naturally: waves are fought over more and farmed less.

### 2.2 Reference by role and by rank · Applied

- **Idea:** baseball's position adjustment (WAR): a catcher isn't compared with a first baseman.
- **In YGG:** each metric is judged against the games of its role in a league
  ([benchmarks.py](../../packages/ygg-core/src/ygg_core/metrics/benchmarks.py)), measured on 1,001 games of 16.19, 143 per
  league from Gold to Challenger ([references.py](../../research/replays/references.py) extracts them from the replay
  harvest, with the same formulas as the API). Per league, role and metric, the mean and the 10th, 35th, 50th, 65th and
  90th percentiles of one game are stored. A single criterion for everything: history, snapshot cards, grade and radar:
  - **excellent** from the 90th percentile;
  - **good** from the 65th: better than two of every three games of that league. It is the target, deliberately above the
    typical: the typical is what the league already does;
  - **normal** from the 35th;
  - **bad** below. For deaths, the other way round.

  For example, a Challenger top averages 7.8 CS/min, and the target is 8.3 (their 65th percentile). With percentiles and not
  with mean and deviation because several metrics are very asymmetric: the KDA of a game with no deaths stretches the upper
  tail. On the cards you can choose each player's target league (all 7); the stats grade (2.5) and the history's colours
  always compare with Challenger. The radar and the trends draw each league's averages.
  The exception is **KDA**, with a softer fixed threshold, the same in all roles and leagues: grey below 3, green from 3 to
  4 and orange from 4.
- **Limit:** one harvest, one patch and one region. The cards the harvest doesn't measure (solo kills, roaming, deaths to
  early ganks, objective control and vision) keep a fixed threshold.

### 2.3 Pace adjustment · Applied

- **Idea:** basketball's "pace". A team that plays fast has more possessions and scores more without being better, so it is
  compared per 100 possessions.
- **In YGG:** in the stats grade, kills, deaths and assists are brought to the pace of an average Challenger game. In a game
  with double the kills they count half. The factor is limited to 0.5–2 so that a game of 10 kills doesn't multiply each
  death by five.

### 2.4 Usage versus efficiency · Applied

- **Idea:** basketball separates how many shots a player uses (usage) from how many points they get per shot (efficiency).
  Scoring 30 points on 35 shots isn't good.
- **In YGG:** "efficiency" is the percentage of the team's damage divided by the percentage of the team's gold. A 1.2 means
  they produce more damage than their gold "entitles" them to. It enters the stats grade and the trends.
- **Limit:** it only looks at damage. A tank or a support produce other things: vision, control, absorbing damage.

### 2.5 Stats grade (the original grade) · Applied

- **What it is:** a 0-to-100 grade against the role's Challenger games
  ([match_score.py](../../packages/ygg-core/src/ygg_core/metrics/match_score.py)).
- **How it is computed:** each of eight metrics (kills, deaths, assists, CS/min, damage/min, efficiency, kill
  participation, damage percentage) is scored according to which Challenger percentile it falls in (2.2): the 10th, 35th,
  50th, 65th and 90th are worth 40, 55, 62.5, 70 and 85, and between them it is interpolated. 70 is the target, better than
  two of every three Challenger games; the median scores 62.5. Then a weighted average by role is taken. Deaths weigh 0.30
  in all roles; kill participation weighs 0.20 in jungle and support. Above 85 each point counts double: nobody beats
  Challenger in all eight at once and, without that, 100 would be unreachable.
- **Where it is used today:** in the season and in the history's games that have no timeline.
- **Limits:**
  - The weights are a human decision, not measured.
  - It doesn't know when anything happened: a death at minute 3 weighs the same as at 35.
  - It doesn't distinguish a decisive kill from an irrelevant one.

  That is why the WPA grade came (2.13).

### 2.6 Laning phase: differences with the direct opponent · Applied

- **Idea:** compare against the direct opponent at the same moment, like the one-on-one duels in a team sport.
- **In YGG:** gold, experience and CS difference with your lane opponent at minutes 8, 14 and 25 (experience only at 8 and
  14), read from the timeline frames. The "GD@14" of the games table is this.
- **Limit:** in a lane each team's jungler also has an influence. A gold difference can be the jungler's merit, not the
  laner's.

### 2.7 Per-role impact from the timeline · Applied

Facts the timeline lets us reconstruct
([role_impact.py](../../packages/ygg-core/src/ygg_core/timeline/role_impact.py),
[role_metrics.py](../../packages/ygg-core/src/ygg_core/metrics/role_metrics.py)):

- **Ganks and roams:** a visit to another lane is detected when the player appears there near an enemy, or takes part in a
  kill or death in it. It counts as a success if:
  - it wins the kill exchange;
  - it takes down a structure;
  - or, with no kills, the lane comes out at least 250 gold plus experience ahead (covering a recall, taking the enemy's
    health down, pushing the wave).
- **Objective preparation:** wards placed in the previous 90 s next to the dragon or Baron pit (radius of 2,500 units).
  Whether it was prepared, whether it was secured and whether it was contested.
- **Early deaths:** deaths in the laning phase (up to minute 14), in your lane or away from it, and solo deaths.
- **Others:** the jungle's first-clear time, plates, wards destroyed and the difference in the time to complete the role
  quest against the opponent.
- **Limit:** position arrives once a minute, so everything that happens between two frames is inferred, not seen.

### 2.8 Trends and well-made averages · Applied

- **Moving average:** the snapshot's trends smooth with a window of games to see the shape without each game's noise.
- **Ratio of sums, not average of ratios:** the percentage of successful ganks over 20 games is computed as total
  successful ganks divided by total visits, not as the mean of 20 percentages. That way a game with 5 ganks weighs more
  than one with 1. The same for objective preparation and securing. It is the criterion by which baseball computes the
  season's batting average.

### 2.9 Win-probability model · Applied

The basis of everything that follows
([wpa.py](../../packages/ygg-core/src/ygg_core/metrics/wpa.py)). The American leagues (MLB, NFL, NBA) and tennis have had
models like this for decades.

- **What it does:** at any second of the game, it estimates the probability that each team wins according to the state of
  the game at that moment.
- **State it looks at** (always as a difference between teams):
  - gold and experience;
  - kill balance and players dead at that instant;
  - turrets by type (outer, inner, inhibitor, nexus) and inhibitors down;
  - dragons, soul point, soul and Elder;
  - Baron active, grubs and herald;
  - the minute.
- **Type of model:** a logistic regression per game segment (0–10, 10–15, 15–20, 20–25, 25–30, 30–35 and 35+ minutes). A
  gold lead doesn't weigh the same at minute 8 as at 30.
- **Instant gold:** Riot gives gold once a minute, but each event carries its gold at its moment, measured by comparing the
  gold jump between frames with that minute's events:

  | Event | Gold added instantly |
  |---|---|
  | Kill | 1.71 × its bounty (includes assists) |
  | Shutdown | 1.04 × its bounty (it gives almost no assist gold) |
  | Plate | 129 |
  | Outer turret | 344 |
  | Inner turret | 160 |
  | Baron | 784 |
  | Elder | 845 |

  Without this, a turret's value arrived a minute late and belonged to no one.
- **Advantages that don't subtract:** in the fit, no advantage can have a negative weight. Without that rule, "having taken
  a turret" before minute 15 came out negative (it is associated with having traded it for something elsewhere), and
  losing a turret raised the probability of winning, which is absurd.
- **Data:** 4,276 games with a timeline from 50 Challenger EUW players (10 per role, 100 games in their role each), patches
  16.4–16.18.
- **How good it is:**
  - **It ranks well (AUC 0.806):** of every 100 pairs "a winner's moment, a loser's moment", about 81 times it gives the
    higher probability to the one who ended up winning.
  - **It is calibrated:** when it says 30%, 30% win. The mean error is 0.32%, measured with games the model never saw when
    training.

### 2.10 WPA: what each play changes the probability by · Applied

- **Idea:** baseball's WPA (win probability added). Each play is worth how much it moves your team's probability of
  winning: after minus before.
- **Which events enter your timeline:**
  - your kills, assists and deaths;
  - the objectives you take;
  - the objectives your team takes while an enemy you killed is still dead (credited to you);
  - the objectives the enemy takes while you are dead (charged to you).

  "Dead" is from the death to the respawn, with the wiki's official timer by level and minute, plus 12 s to come back from
  base.
- **How** each event's value is split, so that adding everyone up gives exactly the total:

  | Event | Split |
  |---|---|
  | Kill | Equally between the killer and the assisters |
  | Death | Entirely to whoever dies |
  | Own objective | Half to those who take it, half to those who killed an enemy who was still dead |
  | Enemy objective | Entirely to the teammates who were dead |

  Several events in the same millisecond share the change.
- **Limit:** the split is a hand-made rule. A death caused by the jungler's bad engage counts entirely for whoever dies. It
  is the problem of the pitcher's "wins" in baseball: an arbitrary attribution that ended up replaced by components (4.3).

### 2.11 Neutral value: the play, not the scoreboard · Applied

- **Problem:** with the game decided, the probability barely moves. Dying at 10% subtracts 2 points and the same death at 50%
  subtracts 8. So a 0/11 Jinx scored −18.6 and a 54, the grade of a normal loss.
- **Idea:** baseball's WPA/LI (WPA divided by the leverage of the moment). Each play is valued as if the game were even.
- **How:** the change in log-odds divided by 4, which at 50% is exactly the change in points. The curve and the "44% → 36%"
  seen on each event are still the real probability; what adds to the grade is the neutral value.
- **Effect:** the 0/11 Jinx goes to −73.3 and a grade of 20.

### 2.12 The why of each event · Applied

- **Idea:** that each play's value can be explained, not just shown.
- **How:** being a linear model in log-odds, an event's change is exactly the sum of what each feature changed times its
  weight. The three that weigh most are shown. For example: "Gold −633 (−7.6) · Numbers advantage −1 (−0.6)". In addition:
  - which part belongs to the player and why;
  - whether the game was already decided;
  - the bounty gold, when there was a shutdown of 300 or more.

### 2.13 WPA grade · Applied

- **What it is:** the player's total neutral value in the game, compared with that of the Challengers of their role.
- **Scale:** the same as the stats grade (2.5). The 10th, 35th, 50th, 65th and 90th percentiles of the role's Challengers'
  total WPA (derived from their mean and deviation, as a normal) are worth 40, 55, 62.5, 70 and 85: 70 is better than two
  of every three, and 100 is about 2.2 deviations above. The figures of the study below are with the previous scale, which
  put 70 at the mean: with this one they come out about 7 points lower.
- **How it comes out in the study:**
  - an average grade of 77–80 when winning and 51–53 when losing;
  - one in eight losses scores 70 or more ("you played well and lost");
  - games with 8 or more deaths and a KDA below 1 hover around 30.
- **Where it is seen:**
  - in the snapshots' games, with their timeline;
  - in the player's history, where from a single timeline the grade of all 10 players is computed and from it come the
    position (1st–10th) and the MVP (best of the winning team) and the ACE (best of the losing one).
- **Where it isn't:** the season (hundreds of games) is downloaded without a timeline and uses the stats grade.

### 2.14 Causality: separating what an event adds from what goes along with it · Applied (study)

- **Idea:** the question of the second point in section 1. The "with consequences" WPA is the winrate of the team that gets
  the event minus the probability it already had just before. It discounts that whoever takes an inhibitor was already
  winning.
- **Placebo test:** measure something that can't have an effect. Nexus turrets are taken just before the end: if the method
  gave them a lot of value, it would be counting the prior advantage as if it were an effect. With the first model they came
  out at +8.4; after fixing the information leak, +3.0. That is how it was detected and fixed.
- **Results** ([REPORT.md](../../research/ladder/REPORT.md),
  [event_winrates.py](../../research/ladder/event_winrates.py)):

  | Event | Winrate | Real value (WPA) |
  |---|---|---|
  | Nexus turret | 97.7% | +2.8 |
  | Inhibitor | 92.8% | +2.3 |
  | Elder | 78.2% | +10.4 |
  | The game's first dragon | 63.0% | +7.1 |
  | First blood | 56.5% | +6.5 |
  | Baron | 80.2% | +6.1 |
  | Soul | 89.2% | +5.7 |
  | Mid T1 | 63.1% | +2.0 |
  | Top / bot T1 | 56.9% / 57.6% | +1.6 / +1.5 |
  | Side-lane T2 | — | +0.8 / +0.9 |
  | Grubs | 54.3% | 0 |

  Late objectives have a huge winrate but add little.
- **Deaths:**
  - an average death costs 5.2 points;
  - its weight is explained by the minute, the fight's exchange and what was conceded while you were dead;
  - after minute 25, a death that concedes nothing costs almost 0.
- **Who takes mid T1 first:** that team wins 73.5%, but it was already at 71.7%: the turret adds +1.8. The one the enemy
  gives back adds +2.6. Having priority in mid is mostly a symptom of being ahead.
- **Shutdowns:** it was checked whether giving one away weighs more than its gold. After a shutdown of 600 or more, the
  model gives 19.8% to the team that collects it and 20.2% win. It is worth its gold, no more and no less, and the gold is
  already in the model.

### 2.15 Calibration (Guo et al., 2017) · Applied (verification)

- **The paper's idea:** modern neural networks are more accurate than old ones but are overly confident. It is measured
  with:
  - **reliability diagrams:** predicted versus real by segments;
  - **ECE:** the mean calibration error;
  - **worst segment** (MCE in the paper);
  - **optimal temperature:** a single number that softens or hardens all the probabilities; if it comes out as 1, none is
    needed.
- **In YGG:**

  | Metric | Value |
  |---|---|
  | ECE (15 bins) | 0.32% |
  | Worst bin | 0.60% |
  | Optimal temperature | 1.01 (no improvement) |

  The tails also match: when it predicts 1%, 1.3% win. It matters because the neutral value is measured in log-odds: an
  overly confident model would inflate the value of every play.

---

## 3. In progress

### 3.1 A sample of the whole playerbase · In progress

- **Problem:** the model is Challenger's. In low leagues games last longer and advantages are thrown away much more. A 14% at
  minute 13 can be real in Challenger and exaggerated in Gold.
- **How:**
  - 1,500 games per league, from Iron to Grandmaster, on EUW ([tier_dataset.py](../../apps/api/scripts/tier_dataset.py));
  - random players spread across each league's divisions (a league's best don't represent it), 25 recent games each;
  - in rounds (500, 1,000, 1,500 per league), so that a cut leaves all the leagues with data;
  - each game brings two players of each role, so they don't need to be picked by role.
- **What will come out:** **a general model** with all the leagues (each league weighing the same) and **another for the
  best**, with Challenger and Grandmaster. There won't be a per-league model. It will also be measured in general, not just
  with one case, how extreme the probabilities get and how much a small event moves them.

---

## 4. To apply

Ordered by priority. The first one (economy) is the next to be done.

### 4.1 Economy: gold and experience over expected · To apply (next)

- **Idea:** football's xG (expected goals) and the NFL's CPOE (completion percentage over expected). It isn't measured how
  much you did, but how much you did **against what is expected** in your situation.
- **Why:** most of a game's gold is farm. That gold moves the probability of winning between one event and another, but
  today it belongs to no one. Farming well doesn't raise the grade and farming badly doesn't lower it.
- **How it would be done:**
  1. From each minute of each player (the timeline gives gold, experience, minions, monsters and position), compute what is
     **expected**: the mean of players of the same role, at the same minute, of the same league and in a similar game state
     (being ahead or behind changes what can be farmed).
  2. The difference is the gold and experience **above or below what is expected**.
  3. Value it in win-probability points with the model itself: 500 gold over expected at minute 12 is worth 500 × the weight
     of gold in that segment.
  4. Add it to the grade as one more component (4.3).
- **What it would answer:**
  - "You lose 40 gold per minute against a player of your league between minute 10 and 20."
  - "Your laning phase is good, but after minute 15 your farm drops."
- **Refinements:**
  - what is expected by champion (4.9): a Pyke doesn't farm like a Kayle;
  - separating farm gold from kill and objective gold, which already count in their event, so as not to count it twice.

### 4.2 Opportunity cost of a death · To apply

- **Idea:** basketball's lost minutes: what you don't produce while you are out.
- **Today:** a death costs the gold it gives away and the numbers disadvantage, but not the gold and experience you stop
  earning while dead (and the waves you lose).
- **How it would be done:** the expected gold and experience per minute of your role and league, multiplied by the respawn
  time plus the walk back to the lane, valued with the model. A death at minute 32, with 45 s of respawn, costs far more than
  one at minute 8 with 12 s, even if they give away the same gold. It is exactly your "dead timer" intuition.

### 4.3 Value by components · To apply

- **Idea:** baseball doesn't give a single number; it separates batting runs, base-running, defence and position
  adjustment. They add up in WAR, but each is seen separately.
- **In LoL:** the grade split into four components, all in win-probability points:
  1. combat (kills, assists, deaths);
  2. objectives;
  3. economy (4.1 and 4.2);
  4. vision (4.14).
- **What it would answer:** "Your grade is 55: fights +8, objectives +2, economy −14, vision +1. Your problem is farming, not
  fights."

### 4.4 Short-term value · To apply

- **Idea:** football's VAEP (Decroos et al., 2019), expected threat (xT) and the NFL's expected points (EPA). Each action is
  valued by how it changes the probability of scoring or conceding in the next actions, not the final result.
- **Why:** each game only gives one win-or-loss data point, so valuing each play by the final victory brings a lot of noise.
  With a short horizon (what happens in the next 60–90 s: next objective, next kill, gold change), each game contributes
  dozens of data points.
- **How:** a second model that predicts "who gets the next objective or the next advantage in the next 90 s?" from the state.
  A play's value is how much that prediction changes.
- **What it would answer:** whether a death was expensive because it opened a dragon, even if the game ended up won.

### 4.5 Death classification and error patterns · To apply

- **Idea:** Opta's "errors leading to a goal" in football and tennis's unforced errors. Not all deaths are the same; they
  have to be classified.
- **How:** each death, with its context taken from the timeline:
  - alone or in a fight, how many enemies, damage dealt and received (already stored in the study);
  - where (enemy jungle, river, own lane) and when;
  - whether you were ahead or behind, and with how much bounty on you;
  - whether there was an objective in the next 90 s and what was conceded.

  With that the deaths are grouped into types and the mean cost of each type is computed.
- **What it would answer:** "40% of your deaths' cost comes from dying alone in the enemy jungle with over 1,000 gold of
  lead." It is a concrete, correctable error pattern.

### 4.6 Accumulated bounties and comebacks · To apply

- **Idea:** LoL's bounty system is a comeback mechanic. The model knows how much of a gold lead there is, but not how much
  could be given back in shutdowns.
- **How:**
  - estimate at each moment the bounty each player carries, from their kill streak and their gold against the rest;
  - check whether it explains what the model gets wrong: if teams ahead with a lot of exposed gold win less than expected, it
    enters as one more feature of the model.
- **Already measured:** the shutdown, once collected, is worth its gold. What is missing is measuring the gold *at risk*
  before it is collected.

### 4.7 Overconfidence · To apply

- **Idea:** tennis's "point importance" and the studies of performance under pressure: do players play differently depending
  on the score?
- **Your hypothesis:** when far ahead people get overconfident, give away shutdowns and the lead melts away.
- **How:**
  - measure the death rate per minute of the players of the team that is ahead as its lead grows, compared with the expected
    one;
  - separate it from the mechanical effect of bounties (4.6);
  - compare it between leagues: if in Iron the team ahead dies far more than expected and in Challenger doesn't, it is a
    human factor, and with data.

### 4.8 A model that sees each player · To apply

- **Today** the model only sees the team. It lacks:
  - each player's gold and level (it isn't the same for the carry to have the gold as for the support to);
  - completed items (the power spikes);
  - objective timers: dying 30 s before the dragon is worse;
  - interactions: a gold lead is worth more with a numbers advantage.
- **How:** more features in the logistic regression and, if needed, a somewhat more flexible model (decision trees with the
  same rule that an advantage can't subtract), always recalibrated with the temperature (2.15). It only changes if it
  improves with games it hasn't seen; if not, the current one stays, which is explained better.

### 4.9 Champion and patch factors · To apply

- **Idea:** baseball's "park factors": a ballpark with short fences inflates the home runs of whoever plays there, so it is
  corrected.
- **In LoL:** what is expected by champion (a Pyke barely farms, a Kayle does), by patch (an item change moves everyone's
  damage) and the strength of the composition (draft). The study had a draft feature with each champion's winrate; the app
  doesn't yet.

### 4.10 Stabilisation and regression to the mean · To apply

- **Idea:** from baseball. Each statistic needs a number of games to reflect skill and not luck: a batter with 10 at-bats and
  a .500 average isn't a .500 hitter. The classic solution (Efron and Morris, 1975) brings a player's mean closer to their
  population's in proportion to how little is known about them.
- **How:**
  - for each metric, measure its reliability by splitting each player's games into two random halves: if the two halves
    resemble each other, the metric measures skill;
  - from that comes how many games are needed;
  - in the snapshot, flag the averages with few games and bring them closer to their league's mean.
- **What it avoids:** "Orianna, 3 games, 100% winrate" as if it were information.

### 4.11 Consistency and form · To apply

- **Idea:** not just the mean, also the dispersion. Two players with an average grade of 65: one always scores between 60 and
  70, the other alternates 90 and 40.
- **Careful:** the "hot hand" (streaks) exists less than it seems; with few games almost everything is noise (4.10).

### 4.12 Value over a replacement player · To apply

- **Idea:** baseball's WAR measures how many wins a player contributes against a "replacement" one, the one any team could
  sign cheaply.
- **In LoL:** how many win-probability points a player contributes per game against an average player of their league, or
  against one of the league they aspire to. It turns the grade into something like "you're worth +3 wins per 100 games over an
  average Emerald".

### 4.13 Opponent strength · To apply

- **Idea:** "strength of schedule": beating a strong opponent is worth more.
- **In LoL:** adjust what is expected by the game's average rank, or by the direct opponent's performance. Out-farming an
  opponent who farms a lot is worth more.

### 4.14 Vision with value · To apply

- **Today:** vision is counted (wards, vision score) and it is checked whether the dragon or Baron was prepared.
- **Idea:** value it by what it produces. A ward that precedes your own kill or prevents a death is worth something; one in a
  corner with no traffic isn't. With the short-term value (4.4), the probability that your team gets the next objective with
  and without those wards.

### 4.15 Key moments and "clutch" · To apply

- **Idea:** baseball's leverage index measures how much each moment matters. "Clutch" is the name for the difference between
  the real WPA and the neutral one.
- **In LoL:**
  - mark on the timeline the highest-leverage plays (even fights for Baron or Elder);
  - measure whether a player performs better or worse in them than in the rest.

  Sport's data say stable "clutch" is rare; it would have to be checked before showing it.

### 4.16 Adjusted plus-minus · Discarded for now

- **Idea:** in basketball the effect of a player on the scoreboard while on the court is measured, discounting teammates and
  opponents with a regression.
- **Why not:** in SoloQ teammates are random, so in theory it works, but hundreds of games per player are needed with a lot of
  overlap of players between games. It doesn't pay off now.

---

## 5. How any metric is validated

A new metric doesn't enter the app until it passes these filters:

1. **Out of sample.** It is trained on some games and evaluated on others (cross-validation by game: the same game is never
   on both sides). If it only works with the games it was trained on, it is memorising.
2. **Calibration.** If it gives probabilities, that they hold (2.15).
3. **Placebo test.** Apply it to something that can't have an effect and check that it gives zero (2.14).
4. **Related to winning, but not too much.** The grade must separate wins from losses (today AUC 0.89–0.94). If it separated
   them 100%, it would only say who won, not how each played.
5. **Reliability.** That a player scores the same in two halves of their games (4.10).
6. **Margin of error.** Every figure with its ± (for example, "+10.4 ± 3.3" for Elder, with only 142 cases).
7. **Expert review.** You as a player: if a game you know you played badly comes out well, something is wrong. That is how the
   0/11 problem was found.

---

## 6. What Riot's data doesn't see

Any metric is limited by what Riot records:

- **Yes:** the result and each player's final stats; each minute, each player's gold, experience, level, minions, monsters and
  position; and the events with their exact second: kills with assisters, bounty and damage, objectives, turrets, plates,
  wards, item purchases and level-ups.
- **No:**
  - position between two minutes;
  - the state of the waves and cooldowns;
  - fights that don't end in a kill;
  - communication;
  - decisions that leave no trace (rotating late, not going to a fight).

No model can value what it doesn't see. That is why the goal is to measure the visible well and to say clearly what is left
out.

---

## Glossary

- **Win probability (WP):** what the model estimates your team wins at a given moment.
- **WPA:** how much that probability changes with a play.
- **WPA with consequences:** the winrate of the team that gets an event minus the probability it already had just before. It
  includes what the event provokes afterwards.
- **Neutral value (WPA/LI):** the play valued as if the game were even.
- **Log-odds:** another scale of probability, ln(p / (1 − p)). The same event always moves the same amount in log-odds, but
  moves a different amount in percentage depending on how even the game is.
- **Calibration:** that when the model says X%, X% happens.
- **ECE:** mean calibration error, by probability bins.
- **Temperature:** a single number that softens (above 1) or hardens (below 1) all of a model's probabilities.
- **AUC:** the probability that the model gives more to a positive case than to a negative one; 0.5 is chance and 1 is perfect.
- **Logistic regression:** a model that turns a weighted sum of features into a probability. Its advantage is that each weight
  can be read and explained.
- **Placebo:** something that can't have an effect, used to check that the method doesn't invent effects.
- **Out of sample:** evaluated with data the model didn't see when training.
- **Standard deviation:** how far values typically stray from their mean.
