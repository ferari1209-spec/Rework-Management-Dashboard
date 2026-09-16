"""비고란 파싱 및 이상치 검증."""

from __future__ import annotations

import re
import sqlite3
import pandas as pd

SITE_ONLY_SPECIAL = re.compile(r"^[\d\W_]+$", re.UNICODE)


def split_remark(remark: str | None) -> dict:
    """비고 = SITE, 담당자, 시리얼번호 (쉼표 구분)."""
    flags: list[str] = []
    if remark is None or pd.isna(remark) or str(remark).strip() == "":
        return {
            "site": None,
            "담당자": None,
            "serial": None,
            "flags": ["비고 누락"],
        }
    parts = [p.strip() for p in str(remark).split(",")]
    site = parts[0] if len(parts) >= 1 else None
    manager = parts[1] if len(parts) >= 2 else None
    serial = parts[2] if len(parts) >= 3 else None
    if len(parts) != 3:
        flags.append(f"필드수 {len(parts)}개")
    if len(parts) > 3:
        # 예: SITE, 팀약칭, 담당자, 시리얼 → 마지막을 시리얼, 끝에서 두 번째를 담당자로 사용
        serial = parts[-1]
        manager = parts[-2]
        flags.append("필드수 3개 초과")
    for name, value in (("SITE", site), ("담당자", manager), ("시리얼", serial)):
        if value is None or str(value).strip() == "":
            flags.append(f"{name} 누락")
    flags.extend(site_anomaly_flags(site))
    return {"site": site, "담당자": manager, "serial": serial, "flags": unique(flags)}


def site_anomaly_flags(site: str | None) -> list[str]:
    flags: list[str] = []
    if site is None or str(site).strip() == "":
        flags.append("SITE 빈값")
        return flags
    text = str(site).strip()
    if len(text) < 2:
        flags.append("SITE 너무 짧음")
    if SITE_ONLY_SPECIAL.fullmatch(text):
        flags.append("SITE 숫자/특수문자만")
    return flags


def unique(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return flags_or(out)


def flags_or(out: list[str]) -> list[str]:
    return out


def unknown_manager(conn: sqlite3.Connection, name: str | None) -> bool:
    if name is None or str(name).strip() == "":
        return True
    row = conn.execute(
        "SELECT 1 FROM managers WHERE is_active = 1 AND name = ?",
        (str(name).strip(),),
    ).fetchone()
    return row is None


def evaluate_row(conn: sqlite3.Connection, remark: str | None, parsed: dict | None = None) -> dict:
    parsed = parsed or split_remark(remark)
    flags = list(parsed["flags"])
    if unknown_manager(conn, parsed.get("담당자")):
        flags.append("담당자 미등록")
    parsed["flags"] = unique(flags)
    parsed["has_issue"] = len(parsed["flags"]) > 0
    return parsed
