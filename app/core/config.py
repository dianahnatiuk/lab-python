"""Конфігурація застосунку (12-factor): усе береться зі змінних оточення.

Середовище вибирається змінною APP_ENV (sandbox | production | test).
Для локального запуску значення читаються з файлу `.env.<APP_ENV>`;
у Docker і CI вони приходять напряму як змінні оточення (мають пріоритет над файлом).
Секрети й паролі не мають значень за замовчуванням і в коді не зберігаються.
"""

import os
from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ENV = os.getenv("APP_ENV", "sandbox")
PLACEHOLDER = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=f".env.{APP_ENV}", extra="ignore")

    app_name: str = "MedLab Aggregator"
    app_env: Literal["sandbox", "production", "test"] = "sandbox"
    debug: bool = False

    # PostgreSQL: структуровані дані (credentials обов'язкові)
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # MongoDB: JSON-результати аналізів
    mongo_user: str
    mongo_password: str
    mongo_db: str
    mongo_host: str = "localhost"
    mongo_port: int = 27017

    # Параметри пулу з'єднань — важливо для пікових навантажень зранку
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # Автентифікація
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cookie_secure: bool = False  # true, якщо застосунок працює за HTTPS

    # Перший адміністратор (створюється при старті, якщо його ще немає)
    admin_email: str
    admin_password: str = Field(min_length=8)
    admin_full_name: str = "Адміністратор"

    @model_validator(mode="after")
    def _check_environment(self) -> "Settings":
        db_names = (self.postgres_db, self.mongo_db)
        if self.app_env == "production":
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if any("sandbox" in name.lower() for name in db_names):
                raise ValueError("production must not use sandbox databases")
            for field in ("jwt_secret", "postgres_password", "mongo_password", "admin_password"):
                if PLACEHOLDER in getattr(self, field).lower():
                    raise ValueError(f"{field.upper()} still contains a placeholder value")
        elif any("prod" in name.lower() for name in db_names):
            raise ValueError("sandbox/test must not use production databases")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mongo_url(self) -> str:
        user = quote_plus(self.mongo_user)
        password = quote_plus(self.mongo_password)
        return f"mongodb://{user}:{password}@{self.mongo_host}:{self.mongo_port}/?authSource=admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
