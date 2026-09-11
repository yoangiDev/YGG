-- Agregados de las partidas de un snapshot.
-- Parámetros: :snapshot_id
-- Las fórmulas coinciden con las de ygg_core.metrics.radar (test_queries.py lo comprueba).
SELECT
    count(*)                                                                   AS games_played,
    coalesce(round(avg(CASE WHEN mp.win THEN 100.0 ELSE 0.0 END), 1), 0)       AS winrate,
    coalesce(round(avg((mp.kills + mp.assists)::numeric / greatest(mp.deaths, 1)), 2), 0) AS avg_kda,
    coalesce(round(avg(mp.total_cs / nullif(m.duration / 60.0, 0)), 2), 0)    AS avg_cs_per_min,
    coalesce(round(avg(mp.damage / nullif(m.duration / 60.0, 0)), 2), 0)      AS avg_damage_per_min,
    coalesce(round(avg(mp.gold / nullif(m.duration / 60.0, 0)), 2), 0)        AS avg_gold_per_min,
    coalesce(round(avg(mp.vision)::numeric, 1), 0)                             AS avg_vision,
    coalesce(round(avg(mp.kill_participation)::numeric, 1), 0)                 AS avg_kill_participation,
    count(*) FILTER (WHERE mp.first_dragon)                                    AS first_dragons,
    count(*) FILTER (WHERE mp.herald)                                          AS heralds,
    count(*) FILTER (WHERE mp.void_grubs)                                      AS void_grubs
FROM snapshot_participants sp
JOIN match_participants mp ON mp.id = sp.match_participant_id
JOIN matches m ON m.match_id = mp.match_id
WHERE sp.snapshot_id = :snapshot_id
