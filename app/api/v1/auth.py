"""API автентифікації: реєстрація, вхід, вихід."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import clear_auth_cookie, set_auth_cookie
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import Role
from app.schemas.user import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.auth import EmailTakenError, authenticate, create_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, db: AsyncSession = Depends(get_db)):
    """Публічна реєстрація: завжди створює пацієнта, роль з клієнта не приймається."""
    try:
        return await create_user(
            db,
            email=data.email,
            full_name=data.full_name,
            password=data.password,
            role=Role.PATIENT,
        )
    except EmailTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = await authenticate(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user.id, user.role)
    set_auth_cookie(response, token)
    return TokenOut(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    clear_auth_cookie(response)
