"""Конфігурація застосунку (12-factor: все через змінні середовища)."""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MedLab Aggregator"
    debug: bool = False

    # PostgreSQL (у Docker повний URL приходить через DATABASE_URL)
    postgres_user: str = "medlab"
    postgres_password: str = "medlab"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "medlab"
    database_url_env: str | None = Field(default=None, alias="DATABASE_URL")

    # MongoDB (JSON-результати аналізів, використаємо на наступному кроці)
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "medlab"

    # Параметри пулу з'єднань — важливо для пікових навантажень зранку
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # Автентифікація
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cookie_secure: bool = False  # True у продакшені (HTTPS)

    # Перший адміністратор (створюється при старті, якщо його ще немає)
    admin_email: str = "admin@medlab.com"
    admin_password: str = "admin12345"
    admin_full_name: str = "Адміністратор"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        if self.database_url_env:
            return self.database_url_env
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
