from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import UserType


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_name: str = Field(min_length=1, max_length=255, description="Display name for the new organization")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    role: str
    user_type: str
    organization_id: str
    permissions: list[str] = Field(default_factory=list)


class SignupResponse(BaseModel):
    message: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class MePermissionsResponse(BaseModel):
    role: str
    permissions: list[str]
