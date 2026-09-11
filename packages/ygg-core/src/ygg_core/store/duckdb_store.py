"""Almacén analítico local con DuckDB.

Guarda dos cosas:
- `raw_payloads`: los JSON crudos de match-v5 y timeline-v5. Permite recalcular
  métricas sin volver a gastar cuota de Riot.
- `participants`: una fila por (partida, jugador) con todas las estadísticas
  de ParticipantStats, consultable con SQL columnar y exportable a Parquet.
"""

from __future__ import annotations

import json
import types
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import fields
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from ygg_core.domain.participant import ParticipantStats

JsonDict = dict[str, Any]

_SCALAR_SQL_TYPES: dict[Any, str] = {
    bool: "BOOLEAN",
    int: "BIGINT",
    float: "DOUBLE",
    str: "VARCHAR",
    datetime: "TIMESTAMP",  # UTC sin zona: evita depender de pytz al leer TIMESTAMPTZ
}


def _sql_type(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        inner = [arg for arg in get_args(annotation) if arg is not type(None)]
        return _sql_type(inner[0])
    if origin is list:
        return "JSON"
    return _SCALAR_SQL_TYPES[annotation]


# El esquema se deriva del dataclass: añadir un campo al dominio lo añade aquí.
PARTICIPANT_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(ParticipantStats))
_HINTS = get_type_hints(ParticipantStats)
COLUMN_TYPES: dict[str, str] = {name: _sql_type(_HINTS[name]) for name in PARTICIPANT_COLUMNS}
_JSON_COLUMNS = frozenset(name for name, sql in COLUMN_TYPES.items() if sql == "JSON")


def load_query(name: str) -> str:
    """SQL versionado en `ygg_core/store/queries/<name>.sql`."""
    return (
        resources.files("ygg_core.store")
        .joinpath("queries", f"{name}.sql")
        .read_text(encoding="utf-8")
    )


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


class MatchStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        try:
            import duckdb
        except ImportError as exc:  # pragma: no cover - depende del entorno
            raise RuntimeError("DuckDB no está instalado: pip install 'ygg-core[store]'") from exc

        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self._con = duckdb.connect(self.path)
        self._create_schema()

    def _create_schema(self) -> None:
        columns = ",\n    ".join(f"{name} {COLUMN_TYPES[name]}" for name in PARTICIPANT_COLUMNS)
        self._con.execute(
            f"CREATE TABLE IF NOT EXISTS participants (\n    {columns},\n"
            "    PRIMARY KEY (match_id, puuid)\n)"
        )
        self._con.execute(
            "CREATE TABLE IF NOT EXISTS raw_payloads ("
            "kind VARCHAR, match_id VARCHAR, payload JSON, PRIMARY KEY (kind, match_id))"
        )

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> MatchStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ── Payloads crudos (implementa RawPayloadCache) ───────────────────────────

    def get_payload(self, kind: str, match_id: str) -> JsonDict | None:
        row = self._con.execute(
            "SELECT payload FROM raw_payloads WHERE kind = ? AND match_id = ?", [kind, match_id]
        ).fetchone()
        if row is None:
            return None
        payload: JsonDict = json.loads(row[0])
        return payload

    def put_payload(self, kind: str, match_id: str, payload: JsonDict) -> None:
        self._con.execute(
            "INSERT OR REPLACE INTO raw_payloads VALUES (?, ?, ?)",
            [kind, match_id, json.dumps(payload)],
        )

    def iter_payloads(self, kind: str) -> Iterator[tuple[str, JsonDict]]:
        rows = self._con.execute(
            "SELECT match_id, payload FROM raw_payloads WHERE kind = ? ORDER BY match_id", [kind]
        ).fetchall()
        for match_id, payload in rows:
            yield match_id, json.loads(payload)

    # ── Participantes ──────────────────────────────────────────────────────────

    @staticmethod
    def _to_row(stats: ParticipantStats) -> list[Any]:
        row: list[Any] = []
        for name in PARTICIPANT_COLUMNS:
            value = getattr(stats, name)
            if name in _JSON_COLUMNS:
                value = json.dumps(value)
            elif isinstance(value, datetime):
                value = value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
            row.append(value)
        return row

    @staticmethod
    def _from_row(row: Sequence[Any]) -> ParticipantStats:
        values = dict(zip(PARTICIPANT_COLUMNS, row, strict=True))
        for name in _JSON_COLUMNS:
            raw = values[name]
            values[name] = json.loads(raw) if isinstance(raw, str) else (raw or [])
        created = values["creation_time"]
        if isinstance(created, datetime) and created.tzinfo is None:
            values["creation_time"] = created.replace(tzinfo=UTC)
        return ParticipantStats(**values)

    def upsert_participants(self, items: Iterable[ParticipantStats]) -> int:
        rows = [self._to_row(stats) for stats in items]
        if not rows:
            return 0
        placeholders = ", ".join("?" for _ in PARTICIPANT_COLUMNS)
        self._con.executemany(
            f"INSERT OR REPLACE INTO participants ({', '.join(PARTICIPANT_COLUMNS)}) "
            f"VALUES ({placeholders})",
            rows,
        )
        return len(rows)

    def participants(self, puuid: str | None = None, role: str | None = None) -> list[ParticipantStats]:
        conditions: list[str] = []
        params: list[Any] = []
        if puuid:
            conditions.append("puuid = ?")
            params.append(puuid)
        if role and role.upper() != "ALL":
            conditions.append("player_role = ?")
            params.append(role.upper())
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._con.execute(
            f"SELECT {', '.join(PARTICIPANT_COLUMNS)} FROM participants{where} "
            "ORDER BY creation_time DESC, match_id",
            params,
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def known_participants(self, puuid: str) -> dict[str, ParticipantStats]:
        """match_id → estadísticas ya calculadas de este jugador (para no repetir descargas)."""
        return {stats.match_id: stats for stats in self.participants(puuid=puuid)}

    # ── Analítica ──────────────────────────────────────────────────────────────

    def query(self, sql: str, params: Sequence[Any] | None = None) -> list[JsonDict]:
        cursor = self._con.execute(sql, list(params or []))
        columns = [description[0] for description in cursor.description or []]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def role_summary(self, puuid: str | None = None) -> list[JsonDict]:
        return self.query(load_query("role_summary"), [puuid or "", puuid or ""])

    def export_parquet(self, path: str | Path) -> int:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._con.execute(f"COPY participants TO {_sql_literal(path)} (FORMAT parquet)")
        row = self._con.execute("SELECT count(*) FROM participants").fetchone()
        return int(row[0]) if row else 0

    def import_parquet(self, path: str | Path) -> int:
        columns = ", ".join(PARTICIPANT_COLUMNS)
        before = self._count()
        self._con.execute(
            f"INSERT OR REPLACE INTO participants ({columns}) "
            f"SELECT {columns} FROM read_parquet({_sql_literal(path)})"
        )
        return self._count() - before

    def _count(self) -> int:
        row = self._con.execute("SELECT count(*) FROM participants").fetchone()
        return int(row[0]) if row else 0
