# ygg-core

Motor de análisis de YGG. Paquete Python puro: **no importa FastAPI ni SQLAlchemy**.
Recibe payloads de la Riot API y devuelve objetos de dominio y métricas, así que
se testea sin base de datos y se usa igual desde la API, un worker o la terminal.

```
ygg_core/
├─ domain/     ParticipantStats, PlayerRef, RankInfo, roles
├─ riot/       cliente HTTP, rate limiter global, routing, parsers
├─ timeline/   diffs @8/14/25, muertes y wards, dragon setups, visión de objetivos, Role Quests
├─ metrics/    estado semántico, radar normalizado por rol, dashboard, agregados
├─ ddragon/    Data Dragon con almacenamiento intercambiable
├─ store/      DuckDB: caché de payloads crudos y analítica SQL local
└─ cli.py      ygg fetch / ygg stats / ygg store / ygg reparse
```

## Instalación

```bash
pip install -e "packages/ygg-core[dev]"
```

## CLI

```bash
# Descarga partidas (necesita RIOT_API_KEY) y las guarda en la caché DuckDB
ygg fetch "Jugador#EUW" --region euw --from 2026-08-01 --to 2026-09-01 --out partidas.json

# Métricas del dashboard a partir del fichero, sin red ni base de datos
ygg stats partidas.json --role JUNGLE

# Analítica local sobre todo lo descargado
ygg store roles
ygg store query "select champion, count(*) from participants group by 1 order by 2 desc"
ygg store export partidas.parquet

# Recalcula las métricas desde los payloads cacheados, sin gastar cuota de Riot
ygg reparse <puuid>
```

## Tests

```bash
pytest packages/ygg-core
mypy --config-file packages/ygg-core/pyproject.toml
```

Las fixtures de `tests/fixtures/match_v5/` son sintéticas: siguen el formato de
match-v5 y timeline-v5, con identificadores inventados.
