# MedLab Aggregator

Агрегатор результатів медичних аналізів (варіант «Соціальні та громадські сервіси №9»).
Навчальний проєкт з курсу проєктування високонавантажених систем.

Обґрунтування вибору: [docs/adr/0001-domain-choice.md](docs/adr/0001-domain-choice.md) ·
Архітектура: [docs/architecture.md](docs/architecture.md)

## Структура репозиторію

```
app/            код застосунку (FastAPI)
  api/v1/       ендпоінти та роутер
  core/         конфігурація
  db/           engine, сесії, Base
  models/       моделі SQLAlchemy
tests/          тести
scripts/        службові скрипти (init_db)
infra/          конфігурації інфраструктури (nginx, тощо — у наступних ЛР)
docs/           документація, ADR, діаграми
```

## Швидкий старт

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

docker compose up -d db                                # MySQL
python -m scripts.init_db                              # створити таблиці
uvicorn app.main:app --reload
```

- Swagger UI: http://localhost:8000/docs
- Liveness: `GET /api/v1/health`
- Readiness (з перевіркою БД): `GET /api/v1/health/db`

Або все разом: `docker compose up --build`.

## Контроль якості коду

Інструменти: **ruff** (лінтер + сортування імпортів), **black** (форматування),
**pre-commit** (автоматичний запуск перед комітом). Конфіг — у `pyproject.toml`
і `.pre-commit-config.yaml`.

```bash
pre-commit install            # один раз після клонування
pre-commit run --all-files    # ручний запуск
ruff check . && black --check .
```

### Демонстрація блокування коміту

```bash
printf 'import os\ndef f( x ):\n  return x+1\n' > app/bad.py
git add app/bad.py
git commit -m "test: bad code"
```

Очікуваний результат: хук `ruff` повідомляє про `F401 'os' imported but unused`, `black`
переформатовує файл, коміт **відхиляється** (`Failed`). Після виправлення й повторного
`git add` коміт проходить.

Синтаксичну помилку (наприклад, `def f(:`) блокує хук `check-ast`.
