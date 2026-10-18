"""HTML-сторінки лабораторного процесу: рецепція, забір, лабораторія, пацієнт."""

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_db
from app.models.lab import OrderStatus, Patient
from app.models.user import Role, User
from app.services import orders as svc
from app.services.catalog import CATALOG
from app.services.errors import InvalidInputError, InvalidTransitionError
from app.web.templating import templates

router = APIRouter(include_in_schema=False)


def _page(request: Request, name: str, user: User, status_code: int = 200, **ctx):
    return templates.TemplateResponse(request, name, {"user": user, **ctx}, status_code=status_code)


# --- Рецепція ---


@router.get("/reception")
async def reception_page(
    request: Request,
    user: User = Depends(require_role(Role.RECEPTIONIST)),
    db: AsyncSession = Depends(get_db),
):
    patients = list(await db.scalars(select(Patient).order_by(Patient.full_name)))
    orders = await svc.list_orders(db, user, limit=20)
    return _page(request, "reception.html", user, patients=patients, catalog=CATALOG, orders=orders)


@router.post("/reception/patients")
async def reception_create_patient(
    full_name: str = Form(...),
    birth_date: str = Form(""),
    phone: str = Form(""),
    user: User = Depends(require_role(Role.RECEPTIONIST)),
    db: AsyncSession = Depends(get_db),
):
    if len(full_name.strip()) < 2:
        raise InvalidInputError("Full name is too short")
    try:
        born = date.fromisoformat(birth_date) if birth_date else None
    except ValueError:
        raise InvalidInputError("Invalid birth date") from None
    await svc.create_patient(db, full_name, born, phone)
    return RedirectResponse("/reception", status_code=303)


@router.post("/reception/orders")
async def reception_create_order(
    patient_id: int = Form(...),
    test_codes: list[str] = Form(default=[]),
    user: User = Depends(require_role(Role.RECEPTIONIST)),
    db: AsyncSession = Depends(get_db),
):
    await svc.create_order(db, patient_id, test_codes, user)
    return RedirectResponse("/reception", status_code=303)


# --- Забір матеріалу ---


@router.get("/nurse")
async def nurse_page(
    request: Request,
    user: User = Depends(require_role(Role.NURSE)),
    db: AsyncSession = Depends(get_db),
):
    orders = await svc.list_orders(db, user, status=OrderStatus.REGISTERED.value)
    return _page(request, "nurse.html", user, orders=orders)


@router.post("/nurse/orders/{order_id}/collect")
async def nurse_collect(
    order_id: int,
    user: User = Depends(require_role(Role.NURSE)),
    db: AsyncSession = Depends(get_db),
):
    await svc.mark_collected(db, order_id, user)
    return RedirectResponse("/nurse", status_code=303)


# --- Лабораторія ---


@router.get("/lab")
async def lab_page(
    request: Request,
    user: User = Depends(require_role(Role.LAB_TECH)),
    db: AsyncSession = Depends(get_db),
):
    collected = await svc.list_orders(db, user, status=OrderStatus.COLLECTED.value)
    in_lab = await svc.list_orders(db, user, status=OrderStatus.IN_LAB.value)
    return _page(request, "lab.html", user, collected=collected, in_lab=in_lab)


@router.post("/lab/orders/{order_id}/receive")
async def lab_receive(
    order_id: int,
    user: User = Depends(require_role(Role.LAB_TECH)),
    db: AsyncSession = Depends(get_db),
):
    await svc.mark_received(db, order_id, user)
    return RedirectResponse("/lab", status_code=303)


@router.get("/lab/orders/{order_id}/results")
async def lab_results_form(
    order_id: int,
    request: Request,
    user: User = Depends(require_role(Role.LAB_TECH)),
    db: AsyncSession = Depends(get_db),
):
    order = await svc.get_order_for_user(db, order_id, user)
    if order.status != OrderStatus.IN_LAB.value:
        raise InvalidTransitionError("Order is not in the lab")
    return _page(request, "lab_results.html", user, order=order, catalog=CATALOG, form={})


@router.post("/lab/orders/{order_id}/results")
async def lab_results_submit(
    order_id: int,
    request: Request,
    user: User = Depends(require_role(Role.LAB_TECH)),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    order = await svc.get_order_for_user(db, order_id, user)
    values: dict[str, float] = {}
    try:
        for code in order.test_codes:
            raw = str(form.get(f"value_{code}", "")).strip().replace(",", ".")
            if not raw:
                raise InvalidInputError(f"Вкажіть значення: {CATALOG[code]['name']}")
            try:
                values[code] = float(raw)
            except ValueError:
                raise InvalidInputError(f"Некоректне число: {CATALOG[code]['name']}") from None
        await svc.complete_order(db, order_id, user, values, str(form.get("conclusion", "")))
    except InvalidInputError as exc:
        return _page(
            request,
            "lab_results.html",
            user,
            status_code=422,
            order=order,
            catalog=CATALOG,
            form=dict(form),
            error=exc.detail,
        )
    return RedirectResponse("/lab", status_code=303)


# --- Пацієнт ---


@router.get("/patient")
async def patient_page(
    request: Request,
    user: User = Depends(require_role(Role.PATIENT)),
    db: AsyncSession = Depends(get_db),
):
    orders = await svc.list_orders(db, user)
    return _page(request, "patient.html", user, orders=orders)
