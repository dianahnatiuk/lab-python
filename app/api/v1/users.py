"""API користувачів: профіль, адмін-функції."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.user import StaffCreateIn, UserOut, UserUpdateIn
from app.services.auth import EmailTakenError, create_user

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserOut)
async def read_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    data: UserUpdateIn,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Захист від IDOR: змінювати можна лише свій профіль (адмін — будь-який)."""
    if current.id != user_id and current.role != Role.ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    target = current if current.id == user_id else await db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    target.full_name = data.full_name.strip()
    await db.commit()
    return target


@router.get(
    "/admin/users",
    response_model=list[UserOut],
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(User).order_by(User.id))
    return list(result)


@router.post(
    "/admin/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN))],
)
async def create_staff(data: StaffCreateIn, db: AsyncSession = Depends(get_db)):
    try:
        return await create_user(
            db,
            email=data.email,
            full_name=data.full_name,
            password=data.password,
            role=data.role,
        )
    except EmailTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
