"""Тести обробки помилок: користувач не бачить внутрішніх деталей."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

SECRET = "SECRET-INTERNAL-DETAIL-12345"

# У режимі DEBUG=true трейсбек показується навмисно, тому тест лише для DEBUG=false
pytestmark = pytest.mark.skipif(get_settings().debug, reason="debug mode shows tracebacks")


def _boom():
    raise RuntimeError(SECRET)


# Тестові маршрути, що завжди падають з помилкою 500
app.add_api_route("/api/v1/_test/boom", _boom, include_in_schema=False)
app.add_api_route("/_test/boom-page", _boom, include_in_schema=False)


def test_api_500_hides_internals():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/_test/boom")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert response.json()["error_id"]
    assert SECRET not in response.text
    assert "Traceback" not in response.text


def test_html_500_hides_internals():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/_test/boom-page", headers={"Accept": "text/html"})
    assert response.status_code == 500
    assert "text/html" in response.headers["content-type"]
    assert "Помилка 500" in response.text
    assert SECRET not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_html_404_is_a_friendly_page(client):
    response = client.get("/definitely-missing-page")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "Traceback" not in response.text
