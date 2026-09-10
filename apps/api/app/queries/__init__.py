"""Consultas analíticas escritas a mano, versionadas como ficheros .sql.

El ORM se queda con el CRUD; los agregados van en SQL legible y revisable en
los PRs, cada uno con su test.
"""

from functools import cache
from importlib import resources

from sqlalchemy import TextClause, text


@cache
def load(name: str) -> TextClause:
    sql = resources.files(__package__).joinpath(f"{name}.sql").read_text(encoding="utf-8")
    return text(sql)
