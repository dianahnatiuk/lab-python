"""Мінімальний HTML-інтерфейс: вхід, реєстрація, сторінки-заглушки за ролями."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    clear_auth_cookie,
    get_optional_user,
    require_role,
    set_auth_cookie,
)
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import Role, User
from app.services.auth import EmailTakenError, authenticate, create_user
from app.web.templating import templates

router = APIRouter(include_in_schema=False)

HOME = {
    Role.PATIENT.value: "/patient",
    Role.RECEPTIONIST.value: "/reception",
    Role.NURSE.value: "/nurse",
    Role.LAB_TECH.value: "/lab",
    Role.ADMIN.value: "/admin",
}


def _login_redirect(user: User) -> RedirectResponse:
    response = RedirectResponse(HOME[user.role], status_code=303)
    set_auth_cookie(response, create_access_token(user.id, user.role))
    return response


@router.get("/")
async def index(user: User | None = Depends(get_optional_user)):
    return RedirectResponse(HOME[user.role] if user else "/login", status_code=302)


@router.get("/login")
async def login_page(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse(HOME[user.role], status_code=302)
    return templates.TemplateResponse(request, "login.html", {"user": None})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate(db, email, password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"user": None, "error": "Невірний email або пароль", "email": email},
            status_code=401,
        )
    return _login_redirect(user)


@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"user": None})


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    ctx = {"user": None, "email": email, "full_name": full_name}
    if len(password) < 8 or len(full_name.strip()) < 2 or "@" not in email:
        ctx["error"] = "Перевірте дані: пароль щонайменше 8 символів, коректні ім'я та email"
        return templates.TemplateResponse(request, "register.html", ctx, status_code=422)
    try:
        user = await create_user(db, email=email, full_name=full_name, password=password)
    except EmailTakenError:
        ctx["error"] = "Користувач з таким email уже існує"
        return templates.TemplateResponse(request, "register.html", ctx, status_code=409)
    return _login_redirect(user)


@router.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    clear_auth_cookie(response)
    return response


async def _admin_page(request, db, user, error=None, status_code=200):
    users = list(await db.scalars(select(User).order_by(User.id)))
    return templates.TemplateResponse(
        request,
        "admin.html",
        {"user": user, "users": users, "roles": list(Role), "error": error},
        status_code=status_code,
    )


@router.get("/admin")
async def admin_page(
    request: Request,
    user: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await _admin_page(request, db, user)


@router.post("/admin/users")
async def admin_create_user(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    user: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        new_role = Role(role)
    except ValueError:
        return await _admin_page(request, db, user, "Невідома роль", 422)
    if len(password) < 8 or len(full_name.strip()) < 2 or "@" not in email:
        return await _admin_page(request, db, user, "Некоректні дані форми", 422)
    try:
        await create_user(db, email=email, full_name=full_name, password=password, role=new_role)
    except EmailTakenError:
        return await _admin_page(request, db, user, "Такий email уже існує", 409)
    return RedirectResponse("/admin", status_code=303)
