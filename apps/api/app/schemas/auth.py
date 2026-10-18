from pydantic import BaseModel, EmailStr

from app.auth.passwords import NewPassword


class UserRegister(BaseModel):
    """Data needed to register a new user."""
    email: EmailStr
    username: str
    password: NewPassword


class UserLogin(BaseModel):
    """Credentials to sign in (no policy: old accounts must be able to get in)."""
    email: EmailStr
    password: str


class DeleteAccount(BaseModel):
    """Deleting your account asks for the password: a stolen session isn't enough to take your data."""
    password: str


class TokenResponse(BaseModel):
    """Short-lived access token. The refresh token travels separately, in an httpOnly cookie."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """Public data of the authenticated user."""
    id: int
    email: str
    username: str
    role: str
    is_active: bool
    avatar_url: str | None = None

    model_config = {"from_attributes": True}
