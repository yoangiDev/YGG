-- Per-role summary of the stored matches.
-- Parameters: (puuid | '', puuid | '')  — empty string = all players.
SELECT
    player_role                                                   AS role,
    count(*)                                                      AS games,
    round(avg(CASE WHEN win THEN 100.0 ELSE 0.0 END), 1)          AS win_rate,
    round(avg((kills + assists) / greatest(deaths, 1)), 2)        AS kda,
    round(avg(total_cs / nullif(duration / 60.0, 0)), 2)          AS cs_per_min,
    round(avg(vision / nullif(duration / 60.0, 0)), 2)            AS vision_per_min,
    round(avg(gold_diff_14) FILTER (WHERE timeline_enriched), 0)  AS gold_diff_14,
    round(avg(deaths), 2)                                         AS deaths
FROM participants
WHERE (? = '' OR puuid = ?)
GROUP BY player_role
ORDER BY games DESC, role
