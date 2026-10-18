"""Hand-written analytical queries, versioned as .sql files.

The ORM keeps the CRUD; the aggregates go in SQL that is readable and reviewable in
PRs, each with its own test.
"""

from functools import cache
from importlib import resources

from sqlalchemy import TextClause, text


@cache
def load(name: str) -> TextClause:
    sql = resources.files(__package__).joinpath(f"{name}.sql").read_text(encoding="utf-8")
    return text(sql)
