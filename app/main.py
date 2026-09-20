"""Точка входу FastAPI-застосунку."""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(api_router, prefix="/api/v1")
