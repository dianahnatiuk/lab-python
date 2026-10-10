"""Каталог аналізів з референтними значеннями (спрощений довідник)."""

CATALOG: dict[str, dict] = {
    "HGB": {"name": "Гемоглобін", "unit": "г/л", "ref_min": 120.0, "ref_max": 160.0},
    "RBC": {"name": "Еритроцити", "unit": "x10^12/л", "ref_min": 3.8, "ref_max": 5.5},
    "WBC": {"name": "Лейкоцити", "unit": "x10^9/л", "ref_min": 4.0, "ref_max": 9.0},
    "PLT": {"name": "Тромбоцити", "unit": "x10^9/л", "ref_min": 150.0, "ref_max": 400.0},
    "GLU": {"name": "Глюкоза", "unit": "ммоль/л", "ref_min": 3.9, "ref_max": 5.9},
    "CHOL": {"name": "Холестерин загальний", "unit": "ммоль/л", "ref_min": 0.0, "ref_max": 5.2},
    "ALT": {"name": "АЛТ", "unit": "Од/л", "ref_min": 0.0, "ref_max": 41.0},
    "TSH": {"name": "ТТГ", "unit": "мМО/л", "ref_min": 0.4, "ref_max": 4.0},
}


def flag_for(value: float, spec: dict) -> str:
    if value < spec["ref_min"]:
        return "low"
    if value > spec["ref_max"]:
        return "high"
    return "normal"
