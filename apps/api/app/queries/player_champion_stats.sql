-- Rendimiento por campeón de un jugador sobre todas sus partidas guardadas: su
-- historial y los análisis de sus snapshots, sin contar dos veces la misma partida.
-- Los ratios por minuto se calculan sobre el total (no como media de medias), igual
-- que en las webs de estadísticas.
-- Parámetros: :player_id, :limit
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
    round(avg(mp.vision), 1)                                                        AS vision_score
FROM games g
JOIN match_participants mp ON mp.id = g.id
JOIN matches m ON m.match_id = mp.match_id
GROUP BY mp.champion
ORDER BY games DESC, wins DESC, champion_name
LIMIT :limit
