"""Password policy and hashing (a single one for sign-up, change and creation by an admin)."""

from functools import cache
from typing import Annotated

import bcrypt
from pydantic import AfterValidator

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_BYTES = 72  # bcrypt doesn't support more


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
    except ValueError:  # password longer than 72 bytes or corrupt hash
        return False


@cache
def _dummy_hash() -> str:
    return hash_password("password-to-equalise-timing")


def verify_password_or_dummy(plain: str, hashed: str | None) -> bool:
    """If the user doesn't exist, it is verified against a dummy hash.

    That way the response takes the same time whether or not the email exists, and
    which accounts exist can't be found out by measuring times.
    """
    if hashed is None:
        verify_password(plain, _dummy_hash())
        return False
    return verify_password(plain, hashed)
