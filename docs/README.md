# Documentation

| To… | Read |
|---|---|
| Understand how it all fits together | [`architecture.md`](architecture.md) |
| Know why it was decided this way | [`adr/`](adr/README.md) (six decisions with their alternatives) and [`engineering-notes.md`](engineering-notes.md) (four real problems) |
| See how big it is, how fast it is and what the coverage is | [`metrics.md`](metrics.md) |
| Deploy it | [`deploy.md`](deploy.md) (planned, not carried out) |
| See how it looks | [`design/`](design) |
| Understand a game's grade and a player's performance | [`model/`](model) |
| Follow how it was planned | [`history/`](history) |

The README screenshots are in [`img/`](img) and are regenerated with `make screenshots`. The research behind the model,
and the reference reviews, are in [`../research`](../research/README.md).

## What's in `design/` and `model/`

| Document | What it is |
|---|---|
| [`design/DESIGN.md`](design/DESIGN.md) | The reference visual system the `apps/web` redesign starts from (it belongs to another project) |
| [`design/color-guide.md`](design/color-guide.md) | Thresholds and semantic colours for the metrics (`excellent`, `good`, `normal`, `bad`); written for the TFG's Flutter client |
| [`model/match_grade.md`](model/match_grade.md) | Design of the history's game grade (a design draft: read its status at the top) |
| [`model/player_performance.md`](model/player_performance.md) | A catalogue of ideas for measuring a player's performance, where they come from and their status (applied, in progress…) |
