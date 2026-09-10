from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    """Datos necesarios para registrar un nuevo usuario."""
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    """Credenciales para iniciar sesión."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Respuesta al login/register con el token JWT."""
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Datos para cambiar la contraseña del usuario autenticado."""
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    """Datos públicos del usuario autenticado."""
    id: int
    email: str
    username: str
    role: str
    is_active: bool
    avatar_url: str | None = None

    model_config = {"from_attributes": True}