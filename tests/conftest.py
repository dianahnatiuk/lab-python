"""Спільні фікстури: один TestClient на сесію (один event loop для asyncpg та motor)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from tests.helpers import auth, login, unique_email

settings = get_settings()


@pytest.fixture(scope="session")
def client():
    # Lifespan створює таблиці, першого адміна та підключення до MongoDB
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_cookies(client):
    client.cookies.clear()
    yield
    client.cookies.clear()


@pytest.fixture(scope="session")
def staff(client):
    """Токени рецепціоніста, медсестри та лаборанта (створює адмін)."""
    admin = login(client, settings.admin_email, settings.admin_password)
    tokens = {}
    for role in ("receptionist", "nurse", "lab_tech"):
        email = unique_email()
        r = client.post(
            "/api/v1/admin/users",
            headers=auth(admin),
            json={
                "email": email,
                "full_name": f"Staff {role}",
                "password": "StrongPass123",
                "role": role,
            },
        )
        assert r.status_code == 201, r.text
        tokens[role] = login(client, email)
    return tokens
