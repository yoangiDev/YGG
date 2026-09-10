from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base declarativa compartida por todos los modelos.

    eager_defaults: los valores generados por el servidor (created_at…) se leen
    con RETURNING al insertar. Con AsyncSession no hay carga perezosa implícita,
    así que un atributo expirado no se puede leer después.
    """

    __mapper_args__ = {"eager_defaults": True}
