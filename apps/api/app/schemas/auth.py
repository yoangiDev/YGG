from pydantic import BaseModel, EmailStr

from app.auth.passwords import NewPassword


class UserRegister(BaseModel):
    """Datos necesarios para registrar un nuevo usuario."""
    email: EmailStr
    username: str
    password: NewPassword


class UserLogin(BaseModel):
    """Credenciales para iniciar sesión (sin política: las cuentas antiguas deben poder entrar)."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Access token de vida corta. El refresh token viaja aparte, en una cookie httpOnly."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos


class ChangePasswordRequest(BaseModel):
    """Datos para cambiar la contraseña del usuario autenticado."""
    current_password: str
    new_password: NewPassword


class UserResponse(BaseModel):
    """Datos públicos del usuario autenticado."""
    id: int
    email: str
    username: str
    role: str
    is_active: bool
    avatar_url: str | None = None

    model_config = {"from_attributes": True}
