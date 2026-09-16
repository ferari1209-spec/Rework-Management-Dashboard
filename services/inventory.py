"""재고/장기재고 계산."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from app.services import settings_service
from app.services.completion import is_completed


def _as_date(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date()


def annotate_inventory(df: pd.DataFrame, conn, today: date | None = None) -> pd.DataFrame:
    today = today or date.today()
    excluded = set(settings_service.get_excluded_status_values(conn))
    out = df.copy()
    thresholds = {
        "완제품": settings_service.get_threshold_days(conn, "완제품"),
        "대여": settings_service.get_threshold_days(conn, "대여"),
    }

    is_inv = []
    is_long = []
    ages = []
    age_buckets = []
    for row in out.to_dict(orient="records"):
        rework = _as_date(row.get("재작업일"))
        inbound = _as_date(row.get("입고일"))
        gubun = row.get("구분")
        category = row.get("category")
        status = row.get("status")
        excluded_gubun = str(gubun) in excluded if gubun is not None and str(gubun) != "None" else False
        inventory = not is_completed(row) and (not excluded_gubun) and status != "검수대기"
        is_inv.append(inventory)
        age = (today - inbound).days if inventory and inbound else None
        ages.append(age)
        threshold = thresholds.get(str(category), 180)
        is_long.append(bool(inventory and age is not None and age >= threshold))
        age_buckets.append(age_bucket_months(age) if inventory and age is not None else None)
    out["is_inventory"] = is_inv
    out["is_long_term"] = is_long
    out["age_days"] = ages
    out["age_bucket"] = age_buckets
    return out


def age_bucket_months(age_days: int | None) -> str | None:
    if age_days is None:
        return None
    months = age_days / 30.4375
    if months < 3:
        return "0~3개월"
    if months < 6:
        return "3~6개월"
    if months < 12:
        return "6~12개월"
    return "12개월+"


def qty(row) -> int:
    value = row.get("입고수량") if isinstance(row, dict) else None
    if value is None or pd.isna(value):
        return 1
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1
