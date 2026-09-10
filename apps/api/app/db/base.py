from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base declarativa compartida por todos los modelos.
    Todos los archivos de db/models/ importan esta clase.
    """
    pass