"""Бізнес-логіка замовлень: створення, переходи статусів, доступ."""

import secrets
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab import Order, OrderStatus, OrderStatusHistory, Patient
from app.models.user import Role, User
from app.services.catalog import CATALOG
from app.services.errors import (
    AccessDeniedError,
    InvalidInputError,
    InvalidTransitionError,
    NotFoundError,
)
from app.services.results import build_results, save_results

# Дозволені переходи: лише на наступний крок
TRANSITIONS = {
    OrderStatus.REGISTERED: OrderStatus.COLLECTED,
    OrderStatus.COLLECTED: OrderStatus.IN_LAB,
    OrderStatus.IN_LAB: OrderStatus.COMPLETED,
}
TIMESTAMP_FIELD = {
    OrderStatus.COLLECTED: "collected_at",
    OrderStatus.IN_LAB: "received_at",
    OrderStatus.COMPLETED: "completed_at",
}


# --- Пацієнти ---


async def create_patient(
    db: AsyncSession, full_name: str, birth_date: date | None, phone: str | None
) -> Patient:
    patient = Patient(
        full_name=full_name.strip(), birth_date=birth_date, phone=(phone or "").strip() or None
    )
    db.add(patient)
    await db.commit()
    return patient


async def get_patient_for_user(db: AsyncSession, user: User) -> Patient | None:
    return await db.scalar(select(Patient).where(Patient.user_id == user.id))


# --- Створення та читання замовлень ---


def _new_barcode() -> str:
    return f"ML-{datetime.now(UTC):%y%m%d}-{secrets.token_hex(3).upper()}"


async def create_order(
    db: AsyncSession, patient_id: int, test_codes: list[str], user: User
) -> Order:
    codes = list(dict.fromkeys(test_codes))  # без дублікатів, зі збереженням порядку
    if not codes:
        raise InvalidInputError("Select at least one test")
    unknown = [c for c in codes if c not in CATALOG]
    if unknown:
        raise InvalidInputError(f"Unknown tests: {', '.join(unknown)}")
    patient = await db.get(Patient, patient_id)
    if patient is None:
        raise NotFoundError("Patient not found")
    order = Order(
        barcode=_new_barcode(),
        patient=patient,
        status=OrderStatus.REGISTERED.value,
        test_codes=codes,
        created_by=user.id,
    )
    db.add(order)
    await db.flush()
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=None,
            to_status=OrderStatus.REGISTERED.value,
            changed_by=user.id,
        )
    )
    await db.commit()
    return order


async def get_order_for_user(db: AsyncSession, order_id: int, user: User) -> Order:
    """Захист від IDOR: пацієнт бачить лише свої замовлення, персонал — усі."""
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found")
    if user.role == Role.PATIENT.value:
        patient = await get_patient_for_user(db, user)
        if patient is None or order.patient_id != patient.id:
            raise AccessDeniedError("Forbidden")
    return order


async def list_orders(
    db: AsyncSession, user: User, status: str | None = None, limit: int = 200
) -> list[Order]:
    stmt = select(Order).order_by(Order.id.desc()).limit(limit)
    if user.role == Role.PATIENT.value:
        patient = await get_patient_for_user(db, user)
        if patient is None:
            return []
        stmt = stmt.where(Order.patient_id == patient.id)
    if status:
        stmt = stmt.where(Order.status == status)
    return list(await db.scalars(stmt))


async def get_history(db: AsyncSession, order_id: int) -> list[dict]:
    rows = await db.scalars(
        select(OrderStatusHistory)
        .where(OrderStatusHistory.order_id == order_id)
        .order_by(OrderStatusHistory.id)
    )
    return [
        {"from_status": r.from_status, "to_status": r.to_status, "changed_at": r.changed_at}
        for r in rows
    ]


# --- Переходи статусів ---


async def _lock_order(db: AsyncSession, order_id: int) -> Order:
    # FOR UPDATE: два одночасні запити не зможуть виконати один перехід двічі
    order = await db.scalar(select(Order).where(Order.id == order_id).with_for_update(of=Order))
    if order is None:
        raise NotFoundError("Order not found")
    return order


def _advance(db: AsyncSession, order: Order, expected: OrderStatus, user: User) -> None:
    if order.status != expected.value:
        raise InvalidTransitionError(f"Order is '{order.status}', expected '{expected.value}'")
    target = TRANSITIONS[expected]
    order.status = target.value
    setattr(order, TIMESTAMP_FIELD[target], datetime.now(UTC))
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=expected.value,
            to_status=target.value,
            changed_by=user.id,
        )
    )


async def mark_collected(db: AsyncSession, order_id: int, user: User) -> Order:
    order = await _lock_order(db, order_id)
    _advance(db, order, OrderStatus.REGISTERED, user)
    await db.commit()
    return order


async def mark_received(db: AsyncSession, order_id: int, user: User) -> Order:
    order = await _lock_order(db, order_id)
    _advance(db, order, OrderStatus.COLLECTED, user)
    await db.commit()
    return order


async def complete_order(
    db: AsyncSession, order_id: int, user: User, values: dict[str, float], conclusion: str
) -> Order:
    order = await _lock_order(db, order_id)
    if order.status != OrderStatus.IN_LAB.value:
        raise InvalidTransitionError(
            f"Order is '{order.status}', expected '{OrderStatus.IN_LAB.value}'"
        )
    tests = build_results(order.test_codes, values)
    # Спочатку Mongo (upsert, ідемпотентно), потім статус у PostgreSQL
    await save_results(order.id, user.id, tests, conclusion)
    _advance(db, order, OrderStatus.IN_LAB, user)
    await db.commit()
    return order
