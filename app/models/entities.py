"""Початкова доменна модель (буде розширюватись у наступних роботах)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    orders: Mapped[list["LabOrder"]] = relationship(back_populates="patient")


class Laboratory(Base):
    __tablename__ = "laboratories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(128), index=True)

    orders: Mapped[list["LabOrder"]] = relationship(back_populates="laboratory")


class LabOrder(Base):
    """Замовлення на аналізи (один візит пацієнта до лабораторії)."""

    __tablename__ = "lab_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    laboratory_id: Mapped[int] = mapped_column(ForeignKey("laboratories.id"), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    patient: Mapped[Patient] = relationship(back_populates="orders")
    laboratory: Mapped[Laboratory] = relationship(back_populates="orders")
    results: Mapped[list["TestResult"]] = relationship(back_populates="order")
    reports: Mapped[list["ReportJob"]] = relationship(back_populates="order")


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_orders.id"), index=True)
    test_code: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[float] = mapped_column(Numeric(12, 4))
    unit: Mapped[str] = mapped_column(String(32))

    order: Mapped[LabOrder] = relationship(back_populates="results")


class ReportJob(Base):
    """Завдання на асинхронну генерацію PDF-звіту (обробляє worker)."""

    __tablename__ = "report_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_orders.id"), index=True)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus), default=ReportStatus.PENDING, index=True
    )
    file_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[LabOrder] = relationship(back_populates="reports")
