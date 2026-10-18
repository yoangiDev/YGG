# Reference reviews

Real games (the author's, and loose games uploaded to test the engine) with the review a coach would give. They are the
**standard the analysis in [`../replays`](../replays) is calibrated against**: the games with a hand-written review are
held out of the models' training and work as the exam. The product's voice and tone (direct, second person, a minute and
a figure in every claim and an actionable fix) come from here.

Names follow `champion-match.type.md`. `EUW1_123…` is Riot's match id and `EUW1-123…` is the replay file's name; they are
the same game.

| Type | What it is |
|---|---|
| `….author.md` | A review **written by hand by the author**: what really decided the game. It is the truth everything is compared against (translated into English from the author's original Spanish) |
| `….review.md` | The review the product produces (what Claude writes from what was measured), with its headline, lessons and plan |
| `….analysis.md` | The moments engine's output on that game at a given date; some games have several versions (`redone analysis`) because the engine changed |
| `….crosscheck.md` | The cross-check between the author's review and the automatic analysis: which moments it got right, which it missed and which were surplus |
| `….routes.md`, `….decisions.md` | Decision trees for the jungler (routes, recall) and for other loose decisions, learned without hand-written rules |

The reviews are in English because that is the product's interface language.
