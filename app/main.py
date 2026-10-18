"""Точка входу FastAPI-застосунку."""

import logging
import uuid
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
from app.web.templating import templates
from app.web.workflow import router as workflow_router

settings = get_settings()
is_production = settings.app_env == "production"

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Для лабораторної: таблиці створюються при старті (далі можна замінити на Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await ensure_seed_admin(session)
        await backfill_patients(session)
    await mongo.connect()
    logger.info("Started in '%s' environment (debug=%s)", settings.app_env, settings.debug)
    yield
    mongo.close()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
    # У production документацію API не публікуємо
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(auth_api.router, prefix="/api/v1")
app.include_router(users_api.router, prefix="/api/v1")
app.include_router(orders_api.router, prefix="/api/v1")
app.include_router(web_router)
app.include_router(workflow_router)

HTTP_MESSAGES = {
    403: "Доступ заборонено.",
    404: "Сторінку не знайдено.",
    405: "Метод не підтримується.",
}


def _is_api(request: Request) -> bool:
    return request.url.path.startswith("/api")


def _html_error(request: Request, status_code: int, message: str, error_id: str | None = None):
    return templates.TemplateResponse(
        request,
        "error.html",
        {"user": None, "code": status_code, "message": message, "error_id": error_id},
        status_code=status_code,
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    if _is_api(request):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return _html_error(request, exc.status_code, exc.detail)


@app.exception_handler(StarletteHTTPException)
async def auth_aware_http_handler(request: Request, exc: StarletteHTTPException):
    """API повертає JSON, а HTML-сторінки: 401 -> перенаправлення на /login, решта -> сторінка."""
    if _is_api(request):
        return await http_exception_handler(request, exc)
    if exc.status_code == 401:
        return RedirectResponse("/login", status_code=302)
    message = HTTP_MESSAGES.get(exc.status_code, "Сталася помилка.")
    return _html_error(request, exc.status_code, message)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """Помилка 500: стектрейс лише в лог, користувачу тільки код помилки."""
    error_id = uuid.uuid4().hex[:8]
    logger.error(
        "Unhandled error %s on %s %s", error_id, request.method, request.url.path, exc_info=exc
    )
    if _is_api(request):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error_id": error_id},
        )
    return _html_error(request, 500, "Внутрішня помилка сервера. Спробуйте пізніше.", error_id)
