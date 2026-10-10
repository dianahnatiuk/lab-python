"""Допоміжні функції для тестів."""

import uuid

PASSWORD = "StrongPass123"


def unique_email() -> str:
    return f"user_{uuid.uuid4().hex[:10]}@mail.com"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client, email: str, password: str = PASSWORD) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    client.cookies.clear()  # далі авторизуємося лише заголовком
    return r.json()["access_token"]


def register_patient(client, name: str = "Test Patient") -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": unique_email(), "full_name": name, "password": PASSWORD},
    )
    assert r.status_code == 201, r.text
    return r.json()
