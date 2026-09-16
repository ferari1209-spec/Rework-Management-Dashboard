"""DB 조회/갱신 헬퍼."""

from __future__ import annotations

import sqlite3
import json
from datetime import date

import pandas as pd
from app.services.import_service import authorize
from app.models import REWORK_COLUMNS
from app.excel_io import to_iso_date


def fetch_items(conn: sqlite3.Connection, category: str, status: str | None = None) -> pd.DataFrame:
    sql = "SELECT * FROM rework_items WHERE category = ?"
    params: list = [category]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id"
    rows = conn.execute(sql, params).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def fetch_pending(conn: sqlite3.Connection, category: str) -> pd.DataFrame:
    return fetch_items(conn, category, status="검수대기")


def insert_pending_rows(conn: sqlite3.Connection, rows: list[dict], uploaded_by: str) -> int:
    cols = [
        "category",
        "담당자",
        "담당팀",
        "site",
        "품목분류",
        "모델명",
        "serial",
        "입고수량",
        "완료수량",
        "구분",
        "재작업내용",
        "비고_원문",
        "status",
        "updated_by",
    ]
    inserted = 0
    for row in rows:
        values = [row.get(c) for c in cols]
        placeholders = ",".join(["?"] * len(cols))
        conn.execute(
            f"INSERT INTO rework_items ({','.join(cols)}) VALUES ({placeholders})",
            values,
        )
        inserted += 1
    conn.commit()
    return inserted


def confirm_pending(conn: sqlite3.Connection, category: str, inbound_date: date, updated_by: str) -> int:
    cur = conn.execute(
        """
        UPDATE rework_items
        SET status = '확정',
            입고일 = ?,
            updated_at = datetime('now'),
            updated_by = ?
        WHERE category = ? AND status = '검수대기'
        """,
        (inbound_date.isoformat(), updated_by, category),
    )
    conn.commit()
    return cur.rowcount


def update_item_fields(conn: sqlite3.Connection, item_id: int, fields: dict, updated_by: str) -> None:
    authorize(conn, updated_by, menu='inventory')
    allowed = set(REWORK_COLUMNS) - {'id', 'category', 'created_at', 'updated_at', 'updated_by', 'status', '비고_원문'}
    if not set(fields) <= allowed:
        raise ValueError('수정할 수 없는 항목입니다.')
    for col in ('입고일', '재작업일'):
        if col in fields:
            value = to_iso_date(fields[col])
            if fields[col] and value is None:
                raise ValueError('날짜는 YYYY-MM-DD 형식으로 입력하세요.')
            fields[col] = value
    if fields.get('담당자') and not fields.get('담당팀'):
        manager = conn.execute('SELECT team FROM managers WHERE name=? AND is_active=1', (str(fields['담당자']).strip(),)).fetchone()
        if manager and manager['team']:
            fields['담당팀'] = manager['team']
    if not fields:
        return
    assignments = ", ".join([f"{k} = ?" for k in fields])
    values = list(fields.values()) + [updated_by, item_id]
    conn.execute(
        f"UPDATE rework_items SET {assignments}, updated_at = datetime('now'), updated_by = ? WHERE id = ?",
        values,
    )


def complete_items(conn: sqlite3.Connection, ids: list[int], complete_date: date, 구분: str | None, updated_by: str) -> int:
    authorize(conn, updated_by, menu='inventory')
    if not ids:
        return 0
    placeholders = ",".join(["?"] * len(ids))
    params = [complete_date.isoformat(), 구분, updated_by] + ids
    cur = conn.execute(
        f"""
        UPDATE rework_items
        SET 재작업일 = ?,
            완료수량 = CASE WHEN COALESCE(완료수량,0)=0 THEN COALESCE(입고수량,1) ELSE 완료수량 END,
            구분 = COALESCE(?, 구분),
            status = '완료',
            updated_at = datetime('now'),
            updated_by = ?
        WHERE id IN ({placeholders}) AND status='확정' AND 재작업일 IS NULL
        """,
        params,
    )
    conn.commit()
    return cur.rowcount


def log_upload(conn: sqlite3.Connection, category: str, uploaded_by: str, file_name: str, row_count: int, status: str, note: str) -> None:
    conn.execute(
        """
        INSERT INTO upload_logs (category, uploaded_by, file_name, row_count, status, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (category, uploaded_by, file_name, row_count, status, note),
    )
    conn.commit()


def delete_inventory_items(conn, ids, category, deleted_by, reason):
    """관리자가 선택한 재고만 삭제하고 원문을 같은 트랜잭션에 보관한다."""
    from app.services.inventory import annotate_inventory
    ids = sorted(set(int(value) for value in ids))
    if not ids:
        raise ValueError('삭제할 항목을 선택하세요.')
    if not reason.strip():
        raise ValueError('삭제 사유를 입력하세요.')
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        authorize(conn, deleted_by, menu='inventory')
        rows = [dict(row) for item_id in ids for row in conn.execute(
            'SELECT * FROM rework_items WHERE id=? AND category=?', (item_id, category))]
        if len(rows) != len(ids) or not annotate_inventory(pd.DataFrame(rows), conn)['is_inventory'].all():
            raise ValueError('선택 항목이 변경되었거나 재고가 아닙니다. 새로고침 후 다시 선택하세요.')
        conn.execute('''CREATE TABLE IF NOT EXISTS deleted_item_logs (
            id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL, category TEXT NOT NULL,
            deleted_by TEXT NOT NULL, reason TEXT NOT NULL, row_json TEXT NOT NULL,
            deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        conn.executemany('INSERT INTO deleted_item_logs (item_id,category,deleted_by,reason,row_json) VALUES (?,?,?,?,?)',
            [(row['id'], category, deleted_by, reason.strip(), json.dumps(row, ensure_ascii=False)) for row in rows])
        conn.executemany('DELETE FROM rework_items WHERE id=? AND category=?', [(item_id, category) for item_id in ids])
    return len(ids)
