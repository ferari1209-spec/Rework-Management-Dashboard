"""마스터 백업 xlsx 생성."""

from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
from openpyxl import Workbook

from app.migration.mapping_config import MASTER_EXPORT_COLUMNS
from app.migration.mapping_config import COLUMN_MAPPING
from app.services.excel_format import format_sheet


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


def build_master_xlsx(conn, category: str) -> bytes:
    rows = conn.execute(
        "SELECT * FROM rework_items WHERE category = ? AND status != '검수대기' ORDER BY id",
        (category,),
    ).fetchall()
    wb = Workbook()
    ws = wb.active
    title = "완제품재작업현황" if category == "완제품" else "대여작업현황"
    ws.title = title
    site_header = "사이트명" if category == "완제품" else "대여처"
    headers = list(COLUMN_MAPPING[category]['columns'])
    ws.append([f"{datetime.now().year}년 {'완제품 재작업현황' if category == '완제품' else '대여작업현황'}"])
    ws.append([])
    ws.append(headers)
    for i, row in enumerate(rows, start=1):
        rec = dict(row)
        inbound = _as_date(rec.get("입고일"))
        rework = _as_date(rec.get("재작업일"))
        ws.append(
            [
                rec.get("source_no") or i,
                f"{inbound.year}년" if inbound else None,
                f"{inbound.month:02d}월" if inbound else None,
                inbound.isoformat() if inbound else None,
                rec.get("담당자"),
                rec.get("담당팀"),
                rec.get("site"),
                rec.get("재작업월"),
                rework.isoformat() if rework else None,
                rec.get("품목분류"),
                rec.get("모델명"),
                rec.get("serial"),
                rec.get("변경모델명"),
                rec.get("변경serial"),
                rec.get("투입공수"),
                rec.get("작업주체"),
                rec.get("입고수량"),
                rec.get("완료수량"),
                rec.get("구분"),
                rec.get("재작업내용"),
                rec.get("비고_원문"),
            ]
        )
    format_sheet(ws, 3)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
