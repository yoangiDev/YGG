"""El OpenAPI describe toda la API y es la fuente de los tipos del frontend."""

import json
from pathlib import Path

from fastapi.routing import APIRoute
from sse_starlette.sse import EventSourceResponse

from main import app

OPENAPI_PATH = Path(__file__).resolve().parents[1] / "openapi.json"
NO_BODY_STATUS = {204, 307}


def _documented_without_model(route: APIRoute) -> bool:
    # Sin cuerpo (204, redirecciones) o flujos SSE, documentados con `responses`.
    return route.status_code in NO_BODY_STATUS or route.response_class is EventSourceResponse


def test_every_route_declares_its_response_model():
    missing = [
        f"{','.join(sorted(route.methods))} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.include_in_schema
        and route.response_model is None
        and not _documented_without_model(route)
    ]
    assert missing == []


def test_operation_ids_are_unique_and_readable():
    operation_ids = [
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for operation in path.values()
    ]
    assert len(operation_ids) == len(set(operation_ids))
    assert "players_list_players" in operation_ids


def test_committed_schema_is_up_to_date():
    committed = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    current = json.loads(json.dumps(app.openapi()))
    assert committed == current, "openapi.json desactualizado: python scripts/export_openapi.py"
