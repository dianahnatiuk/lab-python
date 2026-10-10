"""Бізнес-логіка користувачів: автентифікація, створення, початковий адмін."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models.user import Role, User

# Щоб час відповіді не видавав, чи існує такий email
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class EmailTakenError(Exception):
    pass


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.strip().lower()))


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    full_name: str,
    password: str,
    role: Role = Role.PATIENT,
) -> User:
    user = User(
        email=email.strip().lower(),
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role=role.value,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise EmailTakenError from None
    return user


async def ensure_seed_admin(db: AsyncSession) -> None:
    settings = get_settings()
    if await get_user_by_email(db, settings.admin_email):
        return
    await create_user(
        db,
        email=settings.admin_email,
        full_name=settings.admin_full_name,
        password=settings.admin_password,
        role=Role.ADMIN,
    )
