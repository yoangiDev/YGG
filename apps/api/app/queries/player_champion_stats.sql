-- Per-champion performance of a player over all their stored matches: their
-- history and the analyses of their snapshots, without counting the same match twice.
-- The per-minute ratios are computed over the total (not as a mean of means), just
-- like on stats sites. `role` is the one most played with the champion.
-- Parameters: :player_id, :limit, :since and :until (the matches' date window)
WITH games AS (
    SELECT h.match_participant_id AS id
    FROM player_history_entries h
    WHERE h.player_id = :player_id
    UNION
    SELECT sp.match_participant_id
    FROM snapshot_participants sp
    JOIN snapshots s ON s.id = sp.snapshot_id
    WHERE s.player_id = :player_id
)
SELECT
    mp.champion                                                                     AS champion_name,
    count(*)                                                                        AS games,
    count(*) FILTER (WHERE mp.win)                                                  AS wins,
    count(*) FILTER (WHERE NOT mp.win)                                              AS losses,
    round(100.0 * count(*) FILTER (WHERE mp.win) / count(*), 1)                     AS win_rate,
    round(avg(mp.kills), 1)                                                         AS kills,
    round(avg(mp.deaths), 1)                                                        AS deaths,
    round(avg(mp.assists), 1)                                                       AS assists,
    round(sum(mp.kills + mp.assists)::numeric / greatest(sum(mp.deaths), 1), 2)     AS kda,
    coalesce(round(sum(mp.total_cs) / nullif(sum(m.duration) / 60.0, 0), 1), 0)     AS cs_per_min,
    coalesce(round(sum(mp.damage) / nullif(sum(m.duration) / 60.0, 0), 0), 0)       AS dmg_per_min,
    round(avg(mp.vision), 1)                                                        AS vision_score,
    mode() WITHIN GROUP (ORDER BY mp.player_role)                                   AS role
FROM games g
JOIN match_participants mp ON mp.id = g.id
JOIN matches m ON m.match_id = mp.match_id
WHERE mp.creation_time BETWEEN :since AND :until
GROUP BY mp.champion
ORDER BY games DESC, wins DESC, champion_name
LIMIT :limit
