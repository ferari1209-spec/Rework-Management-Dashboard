"""설정 조회/저장. 카테고리별 키는 settings.key 에 'key|category' 형태로 저장한다."""

from __future__ import annotations

import json
import sqlite3


def _lookup_key(key: str, category: str | None) -> str:
    if category:
        return f"{key}|{category}"
    return key


def get_value(conn: sqlite3.Connection, key: str, category: str | None = None, default=None):
    lookup = _lookup_key(key, category)
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (lookup,)).fetchone()
    if row is None and category:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    return row["value"]


def set_value(conn: sqlite3.Connection, key: str, value: str, category: str | None = None) -> None:
    lookup = _lookup_key(key, category)
    conn.execute(
        """
        INSERT INTO settings (key, category, value, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, category=excluded.category, updated_at=datetime('now')
        """,
        (lookup, category, value),
    )
    conn.commit()


def get_json(conn: sqlite3.Connection, key: str, category: str | None = None, default=None):
    raw = get_value(conn, key, category)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def get_threshold_days(conn: sqlite3.Connection, category: str) -> int:
    raw = get_value(conn, "long_term_threshold_days", category, "180")
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return 180


def get_excluded_status_values(conn: sqlite3.Connection) -> list[str]:
    values = get_json(conn, "excluded_status_values", None, [])
    if not isinstance(values, list):
        return []
    return [str(v) for v in values]


def get_minute_wage_rate(conn: sqlite3.Connection) -> float:
    raw = get_value(conn, "minute_wage_rate", None, "547")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 547.0


def get_options(conn: sqlite3.Connection, key: str, fallback: list[str]) -> list[str]:
    values = get_json(conn, key, None, fallback)
    if not isinstance(values, list) or not values:
        return fallback
    return [str(v) for v in values]


def list_distinct_구분(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT 구분 FROM rework_items
        WHERE 구분 IS NOT NULL AND TRIM(구분) <> ''
        ORDER BY 구분
        """
    ).fetchall()
    return [r["구분"] for r in rows]
