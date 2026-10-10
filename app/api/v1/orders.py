"""API лабораторного процесу: пацієнти, замовлення, статуси, результати, PDF."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.lab import OrderStatus, Patient
from app.models.user import Role, User
from app.schemas.lab import (
    OrderCreateIn,
    OrderDetailOut,
    OrderOut,
    PatientCreateIn,
    PatientOut,
    ResultsIn,
    TestInfo,
)
from app.services import orders as svc
from app.services.catalog import CATALOG
from app.services.errors import InvalidTransitionError, NotFoundError
from app.services.pdf import build_pdf
from app.services.results import get_results

router = APIRouter(tags=["lab"])


@router.get(
    "/catalog", response_model=list[TestInfo], dependencies=[Depends(get_current_user)]
)
async def catalog():
    return [{"code": code, **spec} for code, spec in CATALOG.items()]


@router.get(
    "/patients",
    response_model=list[PatientOut],
    dependencies=[Depends(require_role(Role.RECEPTIONIST, Role.ADMIN))],
)
async def list_patients(db: AsyncSession = Depends(get_db)):
    return list(await db.scalars(select(Patient).order_by(Patient.id)))


@router.post(
    "/patients",
    response_model=PatientOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.RECEPTIONIST, Role.ADMIN))],
)
async def create_patient(data: PatientCreateIn, db: AsyncSession = Depends(get_db)):
    return await svc.create_patient(db, data.full_name, data.birth_date, data.phone)


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreateIn,
    user: User = Depends(require_role(Role.RECEPTIONIST)),
    db: AsyncSession = Depends(get_db),
):
    return await svc.create_order(db, data.patient_id, data.test_codes, user)


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await svc.list_orders(db, user, status)


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
async def read_order(
    order_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    order = await svc.get_order_for_user(db, order_id, user)
    data = OrderOut.model_validate(order).model_dump()
    data["history"] = await svc.get_history(db, order.id)
    return data


@router.post("/orders/{order_id}/collect", response_model=OrderOut)
async def collect(
    order_id: int,
    user: User = Depends(require_role(Role.NURSE)),
    db: AsyncSession = Depends(get_db),
):
    return await svc.mark_collected(db, order_id, user)


@router.post("/orders/{order_id}/receive", response_model=OrderOut)
async def receive(
    order_id: int,
    user: User = Depends(require_role(Role.LAB_TECH)),
    db: AsyncSession = Depends(get_db),
):
    return await svc.mark_received(db, order_id, user)


@router.post("/orders/{order_id}/results", response_model=OrderOut)
async def submit_results(
    order_id: int,
    data: ResultsIn,
    user: User = Depends(require_role(Role.LAB_TECH)),
    db: AsyncSession = Depends(get_db),
):
    return await svc.complete_order(db, order_id, user, data.values, data.conclusion)


async def _completed_results(db, order_id: int, user: User):
    order = await svc.get_order_for_user(db, order_id, user)
    if order.status != OrderStatus.COMPLETED.value:
        raise InvalidTransitionError("Results are not ready yet")
    results = await get_results(order.id)
    if results is None:
        raise NotFoundError("Results not found")
    return order, results


@router.get("/orders/{order_id}/results")
async def read_results(
    order_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    _, results = await _completed_results(db, order_id, user)
    return results


@router.get("/orders/{order_id}/pdf")
async def download_pdf(
    order_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    order, results = await _completed_results(db, order_id, user)
    return Response(
        content=build_pdf(order, results),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="analysis-{order.barcode}.pdf"'},
    )
