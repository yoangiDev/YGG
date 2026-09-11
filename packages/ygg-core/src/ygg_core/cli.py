"""CLI de ygg-core.

    ygg fetch "Nombre#TAG" --region euw --from 2026-08-01 --to 2026-09-01 --out partidas.json
    ygg stats partidas.json [--role JUNGLE]
    ygg store roles | query "<sql>" | export fichero.parquet | import fichero.parquet
    ygg reparse <puuid>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ygg_core.domain.participant import ParticipantStats, PlayerRef
from ygg_core.domain.roles import DASHBOARD_ROLES, dashboard_role
from ygg_core.metrics.dashboard import compute_dashboard

if TYPE_CHECKING:
    from ygg_core.store.duckdb_store import MatchStore

DEFAULT_STORE = Path(".ygg") / "ygg.duckdb"


def _riot_id(value: str) -> tuple[str, str]:
    name, separator, tag = value.rpartition("#")
    if not separator or not name or not tag:
        raise argparse.ArgumentTypeError("el Riot ID debe tener el formato Nombre#TAG")
    return name, tag


def _date(value: str) -> int:
    try:
        return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("la fecha debe tener el formato AAAA-MM-DD") from exc


def _dump(data: Any, out: str | None = None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")


def _progress(done: int, total: int) -> None:
    sys.stderr.write(f"\r{done}/{total} partidas")
    if done >= total:
        sys.stderr.write("\n")
    sys.stderr.flush()


def _open_store(path: str | Path) -> MatchStore:
    from ygg_core.store.duckdb_store import MatchStore

    return MatchStore(path)


# ── fetch ──────────────────────────────────────────────────────────────────────


async def _fetch(args: argparse.Namespace, api_key: str) -> list[ParticipantStats]:
    from ygg_core.riot.client import RiotAPIClient
    from ygg_core.riot.http import create_secure_session

    store = _open_store(args.store) if args.store else None
    try:
        client = RiotAPIClient(api_key, args.region, raw_cache=store)
        name, tag = args.riot_id
        async with create_secure_session() as session:
            puuid = await client.get_puuid(session, name, tag)
            results = await client.fetch_participants(
                session,
                PlayerRef(puuid, name, tag),
                start_t=args.date_from,
                end_t=args.date_to,
                role_filter=args.role,
                max_matches=args.max,
                include_timeline=not args.no_timeline,
                on_progress=_progress,
                known=store.known_participants(puuid) if store else None,
            )
        if store:
            store.upsert_participants(results)
        return results
    finally:
        if store:
            store.close()


def cmd_fetch(args: argparse.Namespace) -> int:
    api_key = os.environ.get("RIOT_API_KEY", "")
    if not api_key:
        print("Falta la variable de entorno RIOT_API_KEY.", file=sys.stderr)
        return 2
    results = asyncio.run(_fetch(args, api_key))
    _dump([stats.to_dict() for stats in results], args.out)
    return 0


# ── stats ──────────────────────────────────────────────────────────────────────


def _load_participants(path: str) -> list[ParticipantStats]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ParticipantStats.from_dict(item) for item in data]


def _most_played_role(participants: Sequence[ParticipantStats]) -> str:
    roles = Counter(p.player_role for p in participants if p.player_role in DASHBOARD_ROLES)
    return roles.most_common(1)[0][0] if roles else "MID"


def cmd_stats(args: argparse.Namespace) -> int:
    participants = _load_participants(args.file)
    role = dashboard_role(args.role) if args.role else _most_played_role(participants)
    metrics = compute_dashboard(participants, role, args.label or Path(args.file).stem)
    _dump(asdict(metrics), args.out)
    return 0


# ── store / reparse ────────────────────────────────────────────────────────────


def cmd_store(args: argparse.Namespace) -> int:
    with _open_store(args.store) as store:
        if args.store_command == "roles":
            _dump(store.role_summary(args.puuid))
        elif args.store_command == "query":
            _dump(store.query(args.sql))
        elif args.store_command == "export":
            count = store.export_parquet(args.path)
            print(f"{count} filas exportadas a {args.path}", file=sys.stderr)
        elif args.store_command == "import":
            count = store.import_parquet(args.path)
            print(f"{count} filas nuevas importadas de {args.path}", file=sys.stderr)
    return 0


def cmd_reparse(args: argparse.Namespace) -> int:
    from ygg_core.store.rebuild import rebuild_participants

    with _open_store(args.store) as store:
        count = rebuild_participants(store, args.puuid, args.role)
    print(f"{count} partidas recalculadas", file=sys.stderr)
    return 0


# ── parser ─────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ygg", description="Motor de análisis de YGG")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch", help="descarga partidas de un jugador desde Riot")
    fetch.add_argument("riot_id", type=_riot_id, help='Riot ID, p. ej. "Jugador#EUW"')
    fetch.add_argument("--region", default="euw")
    fetch.add_argument("--from", dest="date_from", type=_date)
    fetch.add_argument("--to", dest="date_to", type=_date)
    fetch.add_argument("--role", default="ALL")
    fetch.add_argument("--max", type=int)
    fetch.add_argument("--no-timeline", action="store_true")
    fetch.add_argument("--store", default=str(DEFAULT_STORE), help="caché DuckDB ('' para desactivarla)")
    fetch.add_argument("--out", help="fichero JSON de salida (por defecto, stdout)")
    fetch.set_defaults(handler=cmd_fetch)

    stats = commands.add_parser("stats", help="métricas del dashboard a partir de un JSON de partidas")
    stats.add_argument("file")
    stats.add_argument("--role", help="TOP, JUNGLE, MID, ADC/BOTTOM o SUPPORT")
    stats.add_argument("--label")
    stats.add_argument("--out")
    stats.set_defaults(handler=cmd_stats)

    store = commands.add_parser("store", help="analítica sobre la caché DuckDB")
    store.add_argument("--store", default=str(DEFAULT_STORE))
    store_commands = store.add_subparsers(dest="store_command", required=True)
    roles = store_commands.add_parser("roles", help="resumen por rol")
    roles.add_argument("--puuid")
    query = store_commands.add_parser("query", help="consulta SQL libre")
    query.add_argument("sql")
    export = store_commands.add_parser("export", help="exporta los participantes a Parquet")
    export.add_argument("path")
    import_ = store_commands.add_parser("import", help="importa participantes desde Parquet")
    import_.add_argument("path")
    for sub in (roles, query, export, import_):
        sub.add_argument("--store", default=argparse.SUPPRESS)
    store.set_defaults(handler=cmd_store)

    reparse = commands.add_parser("reparse", help="recalcula métricas desde los payloads cacheados")
    reparse.add_argument("puuid")
    reparse.add_argument("--role", default="ALL")
    reparse.add_argument("--store", default=str(DEFAULT_STORE))
    reparse.set_defaults(handler=cmd_reparse)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
