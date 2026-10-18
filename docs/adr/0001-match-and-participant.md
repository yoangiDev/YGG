# 0001 · Separate match and participant

**Status:** accepted · **Phase:** 2 · **Resolves:** P1

## Context

The original schema stored each game as a `match_data` row tied to a player and a snapshot. A League game has ten
participants, but the table didn't distinguish *whose* the stats were: the practical key was the `match_id`.

The bug appeared when tracking two players who had been in the same game. When analysing the second one, the cache found
the already-stored `match_id` and reused the first one's row. The second player inherited someone else's champion, KDA
and deaths, with no visible error.

## Decision

Normalise into four tables:

- `matches`: one row per game (duration, queue, version).
- `match_participants`: one row per player and game, with a unique constraint `(match_id, puuid)`. All the metrics and
  timeline events live here.
- `snapshot_participants` and `player_history_entries`: bridge tables to snapshots and history.

The cache always looks up by `(match_id, puuid)` (`known_participants` in `app/crud/participants.py`), and writes are
`INSERT … ON CONFLICT` on that constraint.

The migration was done in three steps (create, copy, verify counts and drop) so it could be stopped between them and
compared before the `DROP`.

## Alternatives

- **Add `puuid` to `match_data` and keep one table.** It fixes the key but keeps the coupling with the snapshot: the same
  game would be duplicated for every analysis that includes it.
- **Store Riot's JSON and compute on the fly.** Simple to write, but every dashboard would re-parse multi-megabyte
  timelines.

## Consequences

- Stats are correct when several consecutively tracked players share a game (`tests/test_two_players_same_match.py` pins
  it).
- A new snapshot reuses the existing rows: only the new games are downloaded.
- It opens the door to a team view (five participants from the same game).
- In exchange, more joins in queries and a data migration that had to be verified carefully.
