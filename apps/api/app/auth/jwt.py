from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt

from app.db.session import settings


def create_access_token(user_id: int) -> str:
    """
    Genera un token JWT firmado con el SECRET_KEY del .env.
    El token expira según ACCESS_TOKEN_EXPIRE_MINUTES.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),   # subject — identificador del usuario
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> int | None:
    """
    Valida y decodifica un token JWT.
    Devuelve el user_id si el token es válido, None si no lo es.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)
    except JWTError:
        return None