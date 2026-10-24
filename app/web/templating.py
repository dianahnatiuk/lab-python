"""Спільні Jinja2-шаблони, фільтри та глобальні дані для інтерфейсу."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.services.catalog import CATALOG

STATUS_LABELS = {
    "registered": "Зареєстровано",
    "collected": "Матеріал забрано",
    "in_lab": "У лабораторії",
    "completed": "Результат готовий",
}

ROLE_LABELS = {
    "patient": "Пацієнт",
    "receptionist": "Рецепція",
    "nurse": "Медсестра",
    "lab_tech": "Лаборант",
    "admin": "Адміністратор",
}

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.filters["status_label"] = lambda s: STATUS_LABELS.get(s, s)
templates.env.filters["role_label"] = lambda r: ROLE_LABELS.get(r, r)
templates.env.filters["test_name"] = lambda code: CATALOG.get(code, {}).get("name", code)
templates.env.globals["CATALOG"] = CATALOG
