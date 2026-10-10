"""Pydantic-схеми користувачів."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class StaffCreateIn(RegisterIn):
    role: Role


class LoginIn(BaseModel):
    email: str
    password: str


class UserUpdateIn(BaseModel):
    """Лише безпечні поля: роль і email через PATCH змінювати не можна."""

    full_name: str = Field(min_length=2, max_length=255)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
