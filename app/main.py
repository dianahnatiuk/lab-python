"""Точка входу FastAPI-застосунку."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import auth as auth_api
from app.api.v1 import orders as orders_api
from app.api.v1 import users as users_api
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db import mongo
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import lab as _lab_models  # noqa: F401  (реєстрація моделей)
from app.models import user as _user_models  # noqa: F401
from app.services.auth import backfill_patients, ensure_seed_admin
from app.services.errors import AppError
from app.web.pages import router as web_router
from app.web.workflow import router as workflow_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Для лабораторної: таблиці створюються при старті (далі можна замінити на Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await ensure_seed_admin(session)
        await backfill_patients(session)
    await mongo.connect()
    yield
    mongo.close()
    await engine.dispose()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.include_router(api_router, prefix="/api/v1")
app.include_router(auth_api.router, prefix="/api/v1")
app.include_router(users_api.router, prefix="/api/v1")
app.include_router(orders_api.router, prefix="/api/v1")
app.include_router(web_router)
app.include_router(workflow_router)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(StarletteHTTPException)
async def auth_aware_http_handler(request: Request, exc: StarletteHTTPException):
    """API повертає 401 JSON, а HTML-сторінки перенаправляють анонімів на /login (302)."""
    if exc.status_code == 401 and not request.url.path.startswith("/api"):
        return RedirectResponse("/login", status_code=302)
    return await http_exception_handler(request, exc)
