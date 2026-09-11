"""El esquema lo define Alembic y solo Alembic.

Estos tests fallan si alguien añade o cambia un modelo sin escribir la
migración correspondiente: la clase de deriva que `Base.metadata.create_all`
ocultaba (la tabla `rank_cutoffs` existía en producción sin migración).
Requieren que la base de tests esté en `alembic upgrade head`.
"""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def sync_engine():
    engine = create_engine(settings.database_url, poolclass=NullPool)
    yield engine
    engine.dispose()


def _script_directory() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_single_migration_head():
    assert len(_script_directory().get_heads()) == 1


def test_database_is_at_head(sync_engine):
    with sync_engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    assert current == _script_directory().get_current_head()


def test_models_match_migrations(sync_engine):
    with sync_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)
    assert diff == [], f"Modelos y migraciones divergen: {diff}"
