"""Схеми лабораторного процесу."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TestInfo(BaseModel):
    code: str
    name: str
    unit: str
    ref_min: float
    ref_max: float


class PatientCreateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=32)


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    full_name: str
    birth_date: date | None
    phone: str | None


class OrderCreateIn(BaseModel):
    patient_id: int
    test_codes: list[str] = Field(min_length=1)


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barcode: str
    status: str
    patient_id: int
    patient_name: str
    test_codes: list[str]
    created_at: datetime
    collected_at: datetime | None
    received_at: datetime | None
    completed_at: datetime | None


class HistoryOut(BaseModel):
    from_status: str | None
    to_status: str
    changed_at: datetime


class OrderDetailOut(OrderOut):
    history: list[HistoryOut]


class ResultsIn(BaseModel):
    values: dict[str, float]
    conclusion: str = Field(default="", max_length=2000)
