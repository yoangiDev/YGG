-- Rendimiento por rol de un jugador sobre todas sus partidas guardadas.
-- Parámetros: :puuid
SELECT
    mp.player_role                                                              AS role,
    count(*)                                                                    AS games,
    round(avg(CASE WHEN mp.win THEN 100.0 ELSE 0.0 END), 1)                     AS win_rate,
    round(avg((mp.kills + mp.assists)::numeric / greatest(mp.deaths, 1)), 2)    AS kda,
    round(avg(mp.total_cs / nullif(m.duration / 60.0, 0)), 2)                   AS cs_per_min,
    round(avg(mp.gold_diff_14) FILTER (WHERE mp.timeline_enriched), 0)          AS gold_diff_14,
    round(avg(mp.deaths), 2)                                                    AS deaths
FROM match_participants mp
JOIN matches m ON m.match_id = mp.match_id
WHERE mp.puuid = :puuid
GROUP BY mp.player_role
ORDER BY games DESC, role
