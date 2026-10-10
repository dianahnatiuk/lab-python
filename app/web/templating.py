"""Спільні Jinja2-шаблони."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

STATUS_LABELS = {
    "registered": "Зареєстровано",
    "collected": "Матеріал забрано",
    "in_lab": "У лабораторії",
    "completed": "Результат готовий",
}

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
templates.env.filters["status_label"] = lambda s: STATUS_LABELS.get(s, s)
