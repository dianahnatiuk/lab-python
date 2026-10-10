"""Тести автентифікації та контролю доступу (сценарії з лабораторної №2).

Потрібна запущена БД (docker compose up -d db mongo) і PostgreSQL на localhost:5432.
"""

import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

settings = get_settings()
PASSWORD = "StrongPass123"


@pytest.fixture(scope="session")
def client():
    # Один клієнт на сесію: lifespan створює таблиці та першого адміна
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_cookies(client):
    client.cookies.clear()
    yield
    client.cookies.clear()


def _email() -> str:
    return f"user_{uuid.uuid4().hex[:10]}@mail.com"


def _register(client, email=None, name="Test User") -> dict:
    email = email or _email()
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": PASSWORD},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _token(client, email, password=PASSWORD) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    client.cookies.clear()  # далі авторизуємося лише заголовком
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _admin_token(client) -> str:
    return _token(client, settings.admin_email, settings.admin_password)


# --- Анонімний доступ ---

def test_anonymous_api_returns_401(client):
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/admin/users").status_code == 401


def test_anonymous_page_redirects_to_login(client):
    for path in ("/patient", "/admin", "/lab"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"] == "/login"


def test_forged_token_rejected(client):
    fake = jwt.encode({"sub": "1", "role": "admin"}, "wrong-secret", algorithm="HS256")
    assert client.get("/api/v1/admin/users", headers=_auth(fake)).status_code == 401


# --- Автентифікація ---

def test_login_success_and_me(client):
    user = _register(client)
    token = _token(client, user["email"])
    r = client.get("/api/v1/users/me", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["email"] == user["email"]
    assert r.json()["role"] == "patient"


def test_login_wrong_password_and_unknown_user(client):
    user = _register(client)
    bad_pass = client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": "WrongPass999"}
    )
    unknown = client.post(
        "/api/v1/auth/login", json={"email": _email(), "password": PASSWORD}
    )
    assert bad_pass.status_code == 401
    assert unknown.status_code == 401


def test_register_duplicate_email(client):
    user = _register(client)
    r = client.post(
        "/api/v1/auth/register",
        json={"email": user["email"], "full_name": "Other", "password": PASSWORD},
    )
    assert r.status_code == 409


def test_register_cannot_choose_role(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": _email(), "full_name": "Hacker", "password": PASSWORD, "role": "admin"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "patient"


# --- Вертикальне розмежування ---

def test_patient_forbidden_on_admin(client):
    token = _token(client, _register(client)["email"])
    assert client.get("/api/v1/admin/users", headers=_auth(token)).status_code == 403
    assert client.get("/admin", headers=_auth(token)).status_code == 403
    assert client.get("/lab", headers=_auth(token)).status_code == 403


def test_admin_access_and_staff_roles(client):
    admin = _admin_token(client)
    assert client.get("/api/v1/admin/users", headers=_auth(admin)).status_code == 200
    assert client.get("/admin", headers=_auth(admin)).status_code == 200

    email = _email()
    r = client.post(
        "/api/v1/admin/users",
        headers=_auth(admin),
        json={"email": email, "full_name": "Nurse Nina", "password": PASSWORD, "role": "nurse"},
    )
    assert r.status_code == 201
    nurse = _token(client, email)
    assert client.get("/nurse", headers=_auth(nurse)).status_code == 200
    assert client.get("/patient", headers=_auth(nurse)).status_code == 403


# --- Горизонтальне розмежування (IDOR) ---

def test_idor_patient_cannot_edit_other_profile(client):
    a = _register(client)
    b = _register(client, name="Victim Name")
    token_a = _token(client, a["email"])

    r = client.patch(
        f"/api/v1/users/{b['id']}", headers=_auth(token_a), json={"full_name": "Hacked"}
    )
    assert r.status_code == 403

    own = client.patch(
        f"/api/v1/users/{a['id']}", headers=_auth(token_a), json={"full_name": "New Name"}
    )
    assert own.status_code == 200
    assert own.json()["full_name"] == "New Name"


def test_admin_can_edit_any_profile(client):
    b = _register(client)
    r = client.patch(
        f"/api/v1/users/{b['id']}",
        headers=_auth(_admin_token(client)),
        json={"full_name": "Renamed By Admin"},
    )
    assert r.status_code == 200
