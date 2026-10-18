"""Тести конфігурації: ізоляція середовищ, режими безпеки, відсутність hardcoded секретів."""

from pathlib import Path

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError

from app.core.config import Settings

ROOT = Path(__file__).resolve().parent.parent


def make(**overrides) -> Settings:
    values = {
        "app_env": "sandbox",
        "debug": False,
        "jwt_secret": "a" * 40,
        "postgres_user": "user",
        "postgres_password": "pass",
        "postgres_db": "medlab_sandbox",
        "mongo_user": "muser",
        "mongo_password": "mpass",
        "mongo_db": "medlab_sandbox",
        "admin_email": "admin@medlab.com",
        "admin_password": "adminpass1",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


PROD = {"app_env": "production", "postgres_db": "medlab_prod", "mongo_db": "medlab_prod"}


def test_production_with_debug_is_rejected():
    with pytest.raises(ValidationError, match="DEBUG"):
        make(**PROD, debug=True)


def test_production_is_valid_with_debug_off():
    assert make(**PROD).debug is False


def test_production_cannot_use_sandbox_databases():
    with pytest.raises(ValidationError, match="sandbox"):
        make(app_env="production")


def test_sandbox_cannot_use_production_databases():
    with pytest.raises(ValidationError, match="production"):
        make(postgres_db="medlab_prod")


def test_production_rejects_placeholder_secrets():
    with pytest.raises(ValidationError, match="placeholder"):
        make(**PROD, admin_password="change-me-please")
    with pytest.raises(ValidationError, match="placeholder"):
        make(**PROD, jwt_secret="change-me-" + "x" * 30)


def test_short_jwt_secret_is_rejected():
    with pytest.raises(ValidationError):
        make(jwt_secret="short")


def test_connection_urls_escape_special_characters():
    settings = make(postgres_password="p@ss:w/rd", mongo_password="m@ng/o")
    assert "p%40ss%3Aw%2Frd" in settings.database_url
    assert "m%40ng%2Fo" in settings.mongo_url


def test_secrets_have_no_default_values_in_code():
    required = (
        "jwt_secret",
        "postgres_user",
        "postgres_password",
        "postgres_db",
        "mongo_user",
        "mongo_password",
        "mongo_db",
        "admin_email",
        "admin_password",
    )
    for name in required:
        assert Settings.model_fields[name].is_required(), f"{name} must not have a default"


def test_env_examples_are_isolated():
    sandbox = dotenv_values(ROOT / ".env.sandbox.example")
    production = dotenv_values(ROOT / ".env.production.example")

    assert sandbox["APP_ENV"] == "sandbox"
    assert production["APP_ENV"] == "production"
    assert production["DEBUG"].lower() == "false"
    for key in ("POSTGRES_DB", "MONGO_DB", "POSTGRES_USER", "MONGO_USER", "ENV_FILE"):
        assert sandbox[key] != production[key], f"{key} must differ between environments"
    for key in ("API_PORT", "POSTGRES_PORT", "MONGO_PORT"):
        assert sandbox[key] != production[key], f"{key} must differ (parallel run)"
