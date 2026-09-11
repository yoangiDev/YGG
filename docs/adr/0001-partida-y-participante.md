# 0001 · Separar partida y participante

**Estado:** aceptada · **Fase:** 2 · **Resuelve:** P1

## Contexto

El esquema original guardaba cada partida como una fila de `match_data` asociada a un jugador y a
un snapshot. Una partida de League tiene diez participantes, pero la tabla no distinguía *de quién*
eran las estadísticas: la clave práctica era el `match_id`.

El fallo apareció al seguir a dos jugadores que habían coincidido en una partida. Al analizar al
segundo, la caché encontraba el `match_id` ya guardado y reutilizaba la fila del primero. El
segundo jugador heredaba el campeón, el KDA y las muertes de otra persona, sin ningún error visible.

## Decisión

Normalizar en cuatro tablas:

- `matches`: una fila por partida (duración, cola, versión).
- `match_participants`: una fila por jugador y partida, con restricción única `(match_id, puuid)`.
  Aquí viven todas las métricas y los eventos del timeline.
- `snapshot_participants` y `player_history_entries`: tablas puente hacia snapshots e historial.

La caché busca siempre por `(match_id, puuid)` (`known_participants` en
`app/crud/participants.py`), y las escrituras son `INSERT … ON CONFLICT` sobre esa restricción.

La migración se hizo en tres pasos (crear, copiar, verificar conteos y borrar) para poder parar
entre ellos y comparar antes del `DROP`.

## Alternativas

- **Añadir `puuid` a `match_data` y seguir con una tabla.** Arregla la clave, pero mantiene el
  acoplamiento con el snapshot: la misma partida se duplicaría por cada análisis que la incluya.
- **Guardar el JSON de Riot y calcular al vuelo.** Simple de escribir, pero cada dashboard volvería
  a parsear timelines de varios megas.

## Consecuencias

- Las estadísticas son correctas cuando varios jugadores seguidos comparten partida
  (`tests/test_two_players_same_match.py` lo fija).
- Un snapshot nuevo reutiliza las filas existentes: solo se descargan las partidas nuevas.
- Abre la puerta a una vista de equipo (cinco participantes de la misma partida).
- A cambio, más joins en las consultas y una migración de datos que hubo que verificar con cuidado.
