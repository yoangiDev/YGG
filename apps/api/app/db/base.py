from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Declarative base shared by all models.

    eager_defaults: server-generated values (created_at…) are read
    with RETURNING on insert. With AsyncSession there is no implicit lazy loading,
    so an expired attribute can't be read afterwards.
    """

    __mapper_args__ = {"eager_defaults": True}
