"""Результати аналізів у MongoDB (гнучка JSON-схема)."""

import math
from datetime import UTC, datetime

from app.db.mongo import results_collection
from app.services.catalog import CATALOG, flag_for
from app.services.errors import InvalidInputError


def build_results(codes: list[str], values: dict[str, float]) -> list[dict]:
    unknown = sorted(set(values) - set(codes))
    if unknown:
        raise InvalidInputError(f"Unexpected tests: {', '.join(unknown)}")
    missing = [c for c in codes if c not in values]
    if missing:
        raise InvalidInputError(f"Missing values for: {', '.join(missing)}")
    tests = []
    for code in codes:
        spec = CATALOG[code]
        value = values[code]
        if not math.isfinite(value) or value < 0:
            raise InvalidInputError(f"Invalid value for {code}")
        tests.append(
            {
                "code": code,
                "name": spec["name"],
                "value": value,
                "unit": spec["unit"],
                "ref_min": spec["ref_min"],
                "ref_max": spec["ref_max"],
                "flag": flag_for(value, spec),
            }
        )
    return tests


async def save_results(order_id: int, entered_by: int, tests: list[dict], conclusion: str) -> None:
    """Upsert за order_id: повторне збереження ідемпотентне."""
    doc = {
        "order_id": order_id,
        "entered_by": entered_by,
        "entered_at": datetime.now(UTC),
        "tests": tests,
        "conclusion": conclusion.strip(),
    }
    await results_collection().replace_one({"order_id": order_id}, doc, upsert=True)


async def get_results(order_id: int) -> dict | None:
    return await results_collection().find_one({"order_id": order_id}, {"_id": 0})
