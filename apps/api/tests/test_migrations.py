"""El esquema lo define Alembic y solo Alembic.

Estos tests fallan si alguien añade o cambia un modelo sin escribir la
migración correspondiente: la clase de deriva que `Base.metadata.create_all`
ocultaba (la tabla `rank_cutoffs` existía en producción sin migración).
Requieren que la base de tests esté en `alembic upgrade head`.
"""

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.session import engine

API_ROOT = Path(__file__).resolve().parents[1]


def _script_directory() -> ScriptDirectory:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_single_migration_head():
    assert len(_script_directory().get_heads()) == 1


def test_database_is_at_head():
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    assert current == _script_directory().get_current_head()


def test_models_match_migrations():
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)
    assert diff == [], f"Modelos y migraciones divergen: {diff}"
