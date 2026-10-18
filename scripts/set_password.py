"""Показує користувачів, скидає пароль і змінює роль напряму в базі (лише для sandbox).

Приклади (бази мають працювати, запуск із кореня проєкту):
    python -m scripts.set_password --list
    python -m scripts.set_password --email nurse@medlab.com --password demo12345
    python -m scripts.set_password --email lab@medlab.com --role lab_tech
"""

import argparse
import asyncio
import sys

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.lab import Order, Patient
from app.models.user import Role, User


async def list_users() -> None:
    async with SessionLocal() as session:
        users = list(await session.scalars(select(User).order_by(User.id)))
    print(f"{'ID':<4} {'Email':<28} {'Роль':<14} Активний")
    for user in users:
        print(f"{user.id:<4} {user.email:<28} {user.role:<14} {user.is_active}")


async def drop_empty_patient_card(session, user: User) -> None:
    """Картка пацієнта створюється автоматично; працівнику без замовлень вона не потрібна."""
    patient = await session.scalar(select(Patient).where(Patient.user_id == user.id))
    if patient is None:
        return
    orders = await session.scalar(
        select(func.count()).select_from(Order).where(Order.patient_id == patient.id)
    )
    if not orders:
        await session.delete(patient)


async def update_user(email: str, password: str | None, role: str | None) -> bool:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            return False
        if password:
            user.password_hash = hash_password(password)
            user.is_active = True
        if role:
            user.role = role
            if role != Role.PATIENT.value:
                await drop_empty_patient_card(session, user)
        await session.commit()
    return True


async def run(args: argparse.Namespace) -> None:
    try:
        if args.list:
            await list_users()
        elif await update_user(args.email, args.password, args.role):
            print(f"Користувача {args.email} оновлено")
        else:
            sys.exit(f"Користувача {args.email} не знайдено (перевір: --list)")
    finally:
        await engine.dispose()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Керування користувачами (sandbox)")
    parser.add_argument("--list", action="store_true", help="показати користувачів")
    parser.add_argument("--email", help="email користувача")
    parser.add_argument("--password", help="новий пароль (від 8 символів)")
    parser.add_argument("--role", choices=[r.value for r in Role], help="нова роль")
    args = parser.parse_args()

    if get_settings().app_env == "production":
        sys.exit("Скрипт призначений лише для sandbox")
    if not args.list and not (args.email and (args.password or args.role)):
        parser.error("потрібні --email і --password та/або --role (або --list)")
    if args.password and len(args.password) < 8:
        parser.error("пароль має містити щонайменше 8 символів")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
