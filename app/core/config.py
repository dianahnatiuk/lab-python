"""Конфігурація застосунку (12-factor: все через змінні середовища)."""

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MedLab Aggregator"
    debug: bool = False

    mysql_user: str = "medlab"
    mysql_password: str = "medlab"
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_db: str = "medlab"

    # Параметри пулу з'єднань — важливо для пікових навантажень зранку
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
