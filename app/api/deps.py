"""Залежності FastAPI: поточний користувач і перевірка ролей."""

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import Role, User

settings = get_settings()
COOKIE_NAME = "access_token"


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


async def get_optional_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User | None:
    token = _extract_token(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
    # Роль беремо з БД, а не з токена: зміна ролі діє одразу
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*roles: Role):
    allowed = {r.value for r in roles}

    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return checker
