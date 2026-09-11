"""Política y hashing de contraseñas (una sola para registro, cambio y alta por admin)."""

from functools import cache
from typing import Annotated

import bcrypt
from pydantic import AfterValidator

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_BYTES = 72  # bcrypt no admite más


def validate_password_policy(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes long.")
    return password


NewPassword = Annotated[str, AfterValidator(validate_password_policy)]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:  # contraseña de más de 72 bytes o hash corrupto
        return False


@cache
def _dummy_hash() -> str:
    return hash_password("contraseña-para-igualar-tiempos")


def verify_password_or_dummy(plain: str, hashed: str | None) -> bool:
    """Si el usuario no existe se verifica contra un hash de relleno.

    Así la respuesta tarda lo mismo exista o no el email, y no se puede
    averiguar qué cuentas hay midiendo tiempos.
    """
    if hashed is None:
        verify_password(plain, _dummy_hash())
        return False
    return verify_password(plain, hashed)
