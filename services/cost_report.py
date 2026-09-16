"""비용 리포트 xlsx 생성. 금액 = 투입공수 × 분당임율 × 60."""

from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
from openpyxl import Workbook

from app.migration.mapping_config import COST_FINISHED_COLUMNS, COST_RENTAL_COLUMNS
from app.services import settings_service
from app.services.excel_format import format_sheet


def calc_amount(man_hours, minute_rate: float) -> float | None:
    if man_hours is None or (isinstance(man_hours, float) and pd.isna(man_hours)):
        return None
    try:
        return round(float(man_hours) * float(minute_rate) * 60, 0)
    except (TypeError, ValueError):
        return None


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


def year_month_label(d: date | None) -> str | None:
    if d is None:
        return None
    return f"{d.year}년 {d.month:02d}월"


def inbound_year_month(d: date | None) -> tuple[str | None, str | None]:
    if d is None:
        return None, None
    return f"{d.year}년", f"{d.month:02d}월"


def load_completed(conn, date_from: date, date_to: date) -> pd.DataFrame:
    if date_from > date_to:
        raise ValueError('시작일은 종료일보다 늦을 수 없습니다.')
    rows = conn.execute(
        """
        SELECT * FROM rework_items
        WHERE status = '완료'
          AND 재작업일 IS NOT NULL
          AND date(재작업일) >= date(?)
          AND date(재작업일) <= date(?)
        ORDER BY 재작업일, id
        """,
        (date_from.isoformat(), date_to.isoformat()),
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def build_finished_sheet(df: pd.DataFrame, conn) -> pd.DataFrame:
    rate = settings_service.get_minute_wage_rate(conn)
    model_group = settings_service.get_options(conn, "model_group_options", ["DISPLAY"])[0]
    work_type = settings_service.get_options(conn, "work_type_options", ["재작업"])[0]
    records = []
    subset = df[df["category"] == "완제품"] if not df.empty else df
    for row in subset.to_dict(orient="records"):
        work_date = _as_date(row.get("재작업일"))
        records.append(
            {
                "계획날짜": year_month_label(work_date),
                "작업날짜": work_date.isoformat() if work_date else None,
                "MODEL군": model_group,
                "MODEL": str(row['모델명'])[:4] if pd.notna(row.get('모델명')) else None,
                "작업구분": work_type,
                "구분": "생산계획",
                "SITE": row.get("site"),
                "무/재작업 현황": row.get("구분"),
                "재작업수량": row.get("완료수량"),
                "재작업공수": row.get("투입공수"),
                "귀책부서": row.get("담당팀"),
                "금액": calc_amount(row.get("투입공수"), rate),
                "귀책사유정리": None,
                "전산공수반영여부": None,
                "LOSS실공수": None,
                "품질보증팀귀책확정": None,
            }
        )
    return pd.DataFrame(records, columns=COST_FINISHED_COLUMNS)


def build_rental_sheet(df: pd.DataFrame, conn) -> pd.DataFrame:
    rate = settings_service.get_minute_wage_rate(conn)
    records = []
    subset = df[df["category"] == "대여"] if not df.empty else df
    for row in subset.to_dict(orient="records"):
        inbound = _as_date(row.get("입고일"))
        work_date = _as_date(row.get("재작업일"))
        y, m = inbound_year_month(inbound)
        records.append(
            {
                "입고년도": y,
                "입고월": m,
                "입고일": inbound.isoformat() if inbound else None,
                "담당자": row.get("담당자"),
                "담당팀": row.get("담당팀"),
                "대여처": row.get("site"),
                "재작업월": row.get("재작업월"),
                "재작업일": work_date.isoformat() if work_date else None,
                "품목분류": row.get("품목분류"),
                "모델명": row.get("모델명"),
                "Ser.": row.get("serial"),
                "변경모델명": row.get("변경모델명"),
                "변경Ser.": row.get("변경serial"),
                "투입공수": row.get("투입공수"),
                "금액": calc_amount(row.get("투입공수"), rate),
                "작업주체": row.get("작업주체"),
                "입고수량": row.get("입고수량"),
                "완료수량": row.get("완료수량"),
                "구분": row.get("구분"),
                "재작업내용": row.get("재작업내용"),
                "비고": row.get("비고_원문"),
            }
        )
    return pd.DataFrame(records, columns=COST_RENTAL_COLUMNS)


def build_report_xlsx(conn, date_from: date, date_to: date) -> bytes:
    df = load_completed(conn, date_from, date_to)
    finished = build_finished_sheet(df, conn)
    rental = build_rental_sheet(df, conn)
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "재작업현황"
    ws1.append(COST_FINISHED_COLUMNS)
    for rec in finished.itertuples(index=False, name=None):
        ws1.append(list(rec))
    ws2 = wb.create_sheet("대여반납")
    ws2.append(COST_RENTAL_COLUMNS)
    for rec in rental.itertuples(index=False, name=None):
        ws2.append(list(rec))
    format_sheet(ws1)
    format_sheet(ws2)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
