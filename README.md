# MedLab Aggregator

Агрегатор результатів медичних аналізів (варіант «Соціальні та громадські сервіси №9»).
Навчальний проєкт з курсу проєктування високонавантажених систем.

Програма проводить замовлення на аналізи через увесь процес медичної лабораторії:
реєстрація на рецепції → забір матеріалу → передача в лабораторію → готовий результат
із завантаженням у форматі PDF.

Обґрунтування вибору: [docs/adr/0001-domain-choice.md](docs/adr/0001-domain-choice.md) ·
Архітектура: [docs/architecture.md](docs/architecture.md) ·
Ролі та автентифікація: [docs/auth-architecture.md](docs/auth-architecture.md) ·
Лабораторний процес (MVP): [docs/mvp-architecture.md](docs/mvp-architecture.md)

## Можливості

- Реєстрація та вхід користувачів, п'ять ролей з розмежуванням доступу.
- Замовлення зі статусами `registered → collected → in_lab → completed`; пропуск кроку заборонений,
  кожен перехід зберігається в історії.
- Структуровані дані в **PostgreSQL**, JSON-результати аналізів у **MongoDB**.
- PDF-звіт з результатами (з позначками «вище/нижче норми», кирилиця).
- Мінімальний веб-інтерфейс (Jinja2) і REST API (FastAPI).
- Два ізольованих середовища (sandbox і production) та CI на GitHub Actions.

## Ролі

| Роль | Можливості |
|---|---|
| `patient` | реєструється сам, бачить лише свої замовлення, завантажує свої PDF |
| `receptionist` | реєструє пацієнтів, створює замовлення на аналізи |
| `nurse` | відмічає забір біоматеріалу |
| `lab_tech` | приймає зразок у лабораторію, вносить результати |
| `admin` | створює працівників, переглядає всіх користувачів |

Публічна реєстрація завжди створює пацієнта. Працівників створює адміністратор на сторінці `/admin`.
Перший адміністратор з'являється при старті з даних `ADMIN_EMAIL` та `ADMIN_PASSWORD` із файлу середовища.

## Структура репозиторію

```
.github/workflows/  CI (GitHub Actions)
app/                код застосунку (FastAPI)
  api/v1/           ендпоінти: auth, users, orders, health
  core/             конфігурація, безпека (JWT, Argon2)
  db/               engine і сесії PostgreSQL, клієнт MongoDB, Base
  models/           моделі SQLAlchemy (users, patients, orders, history)
  schemas/          Pydantic-схеми
  services/         бізнес-логіка (auth, orders, results, pdf, каталог аналізів)
  web/              HTML-сторінки (рецепція, забір, лабораторія, пацієнт, адмін)
  templates/        Jinja2-шаблони
  assets/fonts/     шрифти для PDF
tests/              тести (pytest)
scripts/            службові скрипти (init_db)
infra/              конфігурації інфраструктури (nginx, тощо, у наступних ЛР)
docs/               документація, ADR, діаграми
```

## Середовища: sandbox і production

Налаштування беруться зі змінних оточення (файли `.env.sandbox` та `.env.production`), у коді
немає жодних паролів чи ключів. Середовище вибирається змінною `APP_ENV`.

| | Sandbox (тестове) | Production (робоче) |
|---|---|---|
| Файл змінних | `.env.sandbox` | `.env.production` |
| `APP_ENV` | `sandbox` | `production` |
| PostgreSQL | база `medlab_sandbox`, порт 5432 | база `medlab_prod`, порт 5433 |
| MongoDB | база `medlab_sandbox`, порт 27017 | база `medlab_prod`, порт 27018 |
| API | http://127.0.0.1:8000 | http://127.0.0.1:8001 |
| Проєкт Docker Compose | `medlab-sandbox` | `medlab-production` |
| Swagger (`/docs`) | увімкнено | вимкнено |
| `DEBUG` | `false` (можна `true` для налагодження) | завжди `false` |

### Ізоляція даних

- Кожне середовище запускається як окремий проєкт Compose (`-p`): власні контейнери, мережа й томи.
- Окремі бази PostgreSQL і MongoDB, окремі користувачі та паролі, окремі порти.
- Захист від помилок конфігурації: у production застосунок не стартує, якщо `DEBUG=true`, якщо
  використовуються бази з `sandbox` у назві або залишились значення-заглушки `change-me`.
  Sandbox, навпаки, не може підключитися до бази з `prod` у назві.
- Порти баз прив'язані до `127.0.0.1`, ззовні вони недоступні.
- Тести відмовляються запускатися, якщо `APP_ENV=production`.

### Перший запуск

1. Створи файли змінних із шаблонів (самі файли `.env.*` у git не потрапляють):
   ```bash
   cp .env.sandbox.example .env.sandbox
   cp .env.production.example .env.production
   ```
   Windows (PowerShell): `Copy-Item .env.sandbox.example .env.sandbox`.
2. Відредагуй обидва файли: задай свої паролі й згенеруй `JWT_SECRET`:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   У `.env.production` усі значення `change-me...` обов'язково замінити, інакше застосунок не запуститься.
   `JWT_SECRET` у production має відрізнятися від sandbox.

Потрібні Docker Desktop (або Docker Engine з Compose v2).

### Запуск sandbox

```bash
docker compose --env-file .env.sandbox -p medlab-sandbox up -d --build
docker compose --env-file .env.sandbox -p medlab-sandbox logs -f api
```
Застосунок: http://127.0.0.1:8000, документація API: http://127.0.0.1:8000/docs.

### Запуск production

```bash
docker compose --env-file .env.production -p medlab-production up -d --build
docker compose --env-file .env.production -p medlab-production logs -f api
```
Застосунок: http://127.0.0.1:8001 (документація API вимкнена).
Обидва середовища можуть працювати одночасно.

### Зупинка

```bash
docker compose --env-file .env.sandbox -p medlab-sandbox down        # дані зберігаються
docker compose --env-file .env.sandbox -p medlab-sandbox down -v     # разом з даними
```
Для production аналогічно з `.env.production` і `-p medlab-production`.

### Локальний запуск API без Docker

Бази запускаємо в Docker, а API з локального Python:

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

docker compose --env-file .env.sandbox -p medlab-sandbox up -d db mongo
APP_ENV=sandbox uvicorn app.main:app --reload          # PowerShell: $env:APP_ENV="sandbox"
```
Налаштування читаються з `.env.sandbox`. Таблиці створюються автоматично при старті застосунку.

## Користування

1. Увійти як адміністратор (`ADMIN_EMAIL` / `ADMIN_PASSWORD` із файлу середовища) на `/login`.
2. На сторінці `/admin` створити працівників: `receptionist`, `nurse`, `lab_tech`.
3. Пацієнт реєструється самостійно на `/register`.
4. Процес замовлення (кожен крок під своєю роллю):
   1. рецепція (`/reception`): створює замовлення, обравши пацієнта й аналізи;
   2. медсестра (`/nurse`): «Матеріал забрано»;
   3. лаборант (`/lab`): «Прийняти в лабораторію», потім «Внести результати»;
   4. пацієнт (`/patient`): завантажує PDF із результатами.

Щоб працювати під кількома ролями одночасно, використовуйте окремі вікна інкогніто.

### Основні ендпоінти API

| Метод і шлях | Доступ |
|---|---|
| `POST /api/v1/auth/register`, `POST /api/v1/auth/login` | усі |
| `GET /api/v1/users/me`, `PATCH /api/v1/users/{id}` | власник (адмін: будь-який) |
| `GET/POST /api/v1/admin/users` | admin |
| `GET/POST /api/v1/patients` | receptionist, admin |
| `POST /api/v1/orders` | receptionist |
| `GET /api/v1/orders`, `GET /api/v1/orders/{id}` | пацієнт: свої, персонал: усі |
| `POST /api/v1/orders/{id}/collect` | nurse |
| `POST /api/v1/orders/{id}/receive`, `POST /api/v1/orders/{id}/results` | lab_tech |
| `GET /api/v1/orders/{id}/results`, `GET /api/v1/orders/{id}/pdf` | власник або персонал, лише для `completed` |
| `GET /api/v1/health`, `GET /api/v1/health/db` | усі |

## Безпека

- Паролі зберігаються як хеші Argon2, сесія це JWT у httpOnly-cookie (або заголовок `Bearer` для API).
- Роль користувача береться з бази на кожен запит, тому зміна ролі діє одразу.
- Вертикальне розмежування: залежність `require_role(...)` дає 403 для чужої ролі.
- Горизонтальне (IDOR): пацієнт бачить лише свої замовлення й PDF, чуже дає 403.
- `DEBUG=false` у production (перевіряється при старті), Swagger/OpenAPI у production вимкнені.
- Необроблена помилка (500) не показує користувачу стектрейс: API повертає
  `{"detail": "Internal server error", "error_id": "..."}`, а сторінки показують повідомлення з кодом
  помилки. Повний стектрейс із цим кодом пишеться лише в лог сервера
  (`docker compose ... logs api`).
- Помилки 403 і 404 на сторінках відображаються як зрозумілі HTML-сторінки.

## Тести

Тести працюють на sandbox-базах (потрібні запущені `db` і `mongo`, див. «Локальний запуск»):

```bash
pytest -v
```

Покрито: анонімний доступ (401/302), вхід і помилки входу, вертикальне й горизонтальне (IDOR)
розмежування, весь лабораторний процес зі статусами, PDF, валідацію, конфігурацію та ізоляцію
середовищ, приховування внутрішніх помилок.

## CI (GitHub Actions)

Файл `.github/workflows/ci.yml` запускається при коміті в `main` та при створенні Pull Request:

1. **lint**: `ruff check` і `black --check`;
2. **test**: `pytest` на тимчасових PostgreSQL та MongoDB (секрети генеруються під час запуску);
3. **docker-build**: перевірка збірки Docker-образу.

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