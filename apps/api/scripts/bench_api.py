"""Latencia de la API contra una instancia en marcha (fuente de docs/metrics.md).

    python scripts/bench_api.py --base-url http://localhost:8000 --email demo@ygg.gg --password ...

- Dashboard frío: la primera petición de cada snapshot (se construye desde Postgres).
- Dashboard caliente: las siguientes (se sirve de la caché en Redis).
- Peticiones secuenciales desde la misma máquina: mide el servidor, no la red.
- Por defecto se queda por debajo del límite global de 300 peticiones por minuto.
"""

import argparse
import time

import httpx


def percentile(samples: list[float], pct: float) -> float:
    ordered = sorted(samples)
    rank = (len(ordered) - 1) * pct / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def timed(client: httpx.Client, method: str, url: str, **kwargs) -> tuple[httpx.Response, float]:
    started = time.perf_counter()
    response = client.request(method, url, **kwargs)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return response, elapsed_ms


def report(name: str, samples: list[float]) -> None:
    print(
        f"{name:28} n={len(samples):3}  p50={percentile(samples, 50):7.1f} ms  "
        f"p95={percentile(samples, 95):7.1f} ms  max={max(samples):7.1f} ms"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("-n", type=int, default=80, help="muestras por endpoint en caliente")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        login, _ = timed(client, "POST", "/auth/login", json={"email": args.email, "password": args.password})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

        players = client.get("/players/").json()["items"]
        snapshot_ids = [
            snapshot["id"]
            for player in players
            for snapshot in client.get(f"/snapshots/player/{player['id']}").json()["items"]
        ]
        if not snapshot_ids:
            raise SystemExit("No snapshots found for this account.")

        cold = [timed(client, "GET", f"/snapshots/{sid}/dashboard")[1] for sid in snapshot_ids]
        warm = [
            timed(client, "GET", f"/snapshots/{snapshot_ids[i % len(snapshot_ids)]}/dashboard")[1]
            for i in range(args.n)
        ]
        matches = [
            timed(client, "GET", f"/matches/snapshot/{snapshot_ids[i % len(snapshot_ids)]}", params={"limit": 50})[1]
            for i in range(args.n)
        ]
        player_list = [timed(client, "GET", "/players/")[1] for _ in range(args.n)]

    print(f"{len(players)} players, {len(snapshot_ids)} snapshots at {args.base_url}")
    report("dashboard (cold, no cache)", cold)
    report("dashboard (warm, Redis)", warm)
    report("matches page (50)", matches)
    report("players list", player_list)


if __name__ == "__main__":
    main()
