-- Totales del panel de administración en una sola ida y vuelta.
SELECT
    (SELECT count(*) FROM users)                          AS total_users,
    (SELECT count(*) FROM users WHERE is_active IS TRUE)  AS active_users,
    (SELECT count(*) FROM players)                        AS total_players,
    (SELECT count(*) FROM snapshots)                      AS total_snapshots,
    (SELECT count(*) FROM matches)                        AS total_matches
