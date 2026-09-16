"""마스터 엑셀 2종 → SQLite 마이그레이션."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from datetime import date
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import DB_PATH, ensure_schema, get_connection, seed_settings
from app.excel_io import read_xls_sheet, to_iso_date
from app.migration.mapping_config import COLUMN_MAPPING, DATE_FIELDS, NUMERIC_FIELDS

INSERT_COLUMNS = [
    "category",
    "source_no",
    "입고일",
    "담당자",
    "담당팀",
    "site",
    "재작업월",
    "재작업일",
    "품목분류",
    "모델명",
    "serial",
    "변경모델명",
    "변경serial",
    "투입공수",
    "작업주체",
    "입고수량",
    "완료수량",
    "구분",
    "재작업내용",
    "비고_원문",
    "status",
]


def is_fully_empty_row(row: pd.Series) -> bool:
    for value in row.tolist():
        if value is None or pd.isna(value):
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return False
    return True


def cut_trailing_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    """완전 공백만 제외하며 중간 빈행 뒤의 유효 데이터는 보존한다."""
    return df.loc[~df.apply(is_fully_empty_row, axis=1)].copy()


def normalize_columns(df: pd.DataFrame, category: str) -> pd.DataFrame:
    mapping = COLUMN_MAPPING[category]["columns"]
    rename = {}
    for excel_name, db_name in mapping.items():
        if db_name is None:
            continue
        if excel_name in df.columns:
            rename[excel_name] = db_name
    out = df.rename(columns=rename)
    keep = [c for c in INSERT_COLUMNS if c in out.columns]
    result = out[keep].copy()
    business = [c for c in keep if c not in ('source_no', 'status', 'category')]
    return result.loc[~result[business].apply(is_fully_empty_row, axis=1)].copy()


def parse_typed_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report = {"date_fail": []}
    out = df.copy()
    for col in DATE_FIELDS:
        if col not in out.columns:
            continue
        iso_values = []
        for i, value in enumerate(out[col].tolist()):
            iso = to_iso_date(value)
            if value is not None and not pd.isna(value) and str(value).strip() not in ("", "None") and iso is None:
                report["date_fail"].append({"row": i, "column": col, "value": str(value)})
            iso_values.append(iso)
        out[col] = iso_values
    for col in NUMERIC_FIELDS:
        if col not in out.columns:
            continue
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out, report


def assign_status(df: pd.DataFrame) -> pd.DataFrame:
    from app.services.completion import is_completed
    out = df.copy()
    out['status'] = ['완료' if is_completed(row) else '확정' for row in out.to_dict('records')]
    return out


def has_initial_migration(conn: sqlite3.Connection, category: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM upload_logs
        WHERE category = ? AND note = 'initial_migration'
        LIMIT 1
        """,
        (category,),
    ).fetchone()
    return row is not None


def bulk_insert(conn: sqlite3.Connection, df: pd.DataFrame, category: str) -> int:
    work = df.copy()
    work["category"] = category
    for col in INSERT_COLUMNS:
        if col not in work.columns:
            work[col] = None
    work = work[INSERT_COLUMNS]
    records = []
    for row in work.itertuples(index=False, name=None):
        cleaned = []
        for value in row:
            if value is None:
                cleaned.append(None)
            elif isinstance(value, float) and pd.isna(value):
                cleaned.append(None)
            else:
                cleaned.append(value)
        records.append(tuple(cleaned))
    placeholders = ",".join(["?"] * len(INSERT_COLUMNS))
    cols = ",".join(INSERT_COLUMNS)
    conn.executemany(
        f"INSERT INTO rework_items ({cols}) VALUES ({placeholders})",
        records,
    )
    return len(records)


def seed_managers_from_items(conn: sqlite3.Connection) -> int:
    names = conn.execute(
        """
        SELECT DISTINCT TRIM(담당자) AS name
        FROM rework_items
        WHERE 담당자 IS NOT NULL AND TRIM(담당자) <> ''
        """
    ).fetchall()
    count = 0
    for row in names:
        conn.execute(
            "INSERT INTO managers (name, is_active) VALUES (?, 1) ON CONFLICT(name) DO NOTHING",
            (row["name"],),
        )
        count += 1
    return count


def load_category(path: Path, category: str) -> tuple[pd.DataFrame, dict]:
    cfg = COLUMN_MAPPING[category]
    df_raw = read_xls_sheet(path, cfg["sheet_name"], header_row=cfg["header_row"])
    source_rows = len(df_raw)
    df_cut = cut_trailing_empty_rows(df_raw)
    mapped = normalize_columns(df_cut, category)
    typed, type_report = parse_typed_columns(mapped)
    typed = assign_status(typed)
    report = {
        "source_rows": source_rows,
        "after_cut": len(df_cut),
        "valid_rows": len(typed),
        "number_only_rows": len(df_cut) - len(typed),
        "date_fail": type_report["date_fail"],
        "status_done": int((typed["status"] == "완료").sum()),
        "status_confirmed": int((typed["status"] == "확정").sum()),
        "unmapped_columns": [c for c in df_raw.columns if c not in COLUMN_MAPPING[category]["columns"]],
        "sample": typed.head(5).to_dict(orient="records"),
    }
    return typed, report


def migrate(
    finished_path: Path,
    rental_path: Path,
    db_path: Path,
    force: bool = False,
) -> dict:
    conn = get_connection(db_path)
    ensure_schema(conn)
    seed_settings(conn)

    reports = {}
    for category, path in (("완제품", finished_path), ("대여", rental_path)):
        if has_initial_migration(conn, category) and not force:
            print(f"[SKIP] {category}: initial_migration 로그가 있어 중단합니다. --force 로 재실행하세요.")
            reports[category] = {"skipped": True}
            continue
        if force and has_initial_migration(conn, category):
            conn.execute("DELETE FROM rework_items WHERE category = ?", (category,))
            conn.execute(
                "DELETE FROM upload_logs WHERE category = ? AND note = 'initial_migration'",
                (category,),
            )
        df, report = load_category(path, category)
        if report['date_fail']:
            raise ValueError(f'{category}: 날짜를 해석할 수 없는 행이 있어 이관을 중단했습니다.')
        inserted = bulk_insert(conn, df, category)
        conn.execute(
            """
            INSERT INTO upload_logs (category, uploaded_by, file_name, row_count, status, note)
            VALUES (?, ?, ?, ?, '확정', 'initial_migration')
            """,
            (category, "system", Path(path).name, inserted),
        )
        report["inserted"] = inserted
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        archive = Path(db_path).parent / 'raw'
        archive.mkdir(parents=True, exist_ok=True)
        archived = archive / f'{digest}{path.suffix.lower()}'
        if not archived.exists():
            shutil.copy2(path, archived)
        conn.execute('INSERT OR IGNORE INTO import_batches VALUES (?,?,?,?,?)', (digest,category,path.name,date.today().isoformat(),inserted))
        reports[category] = report
        print(f"===== {category} =====")
        print(f"원본 행(헤더 이후): {report['source_rows']}")
        print(f"빈행 컷 후: {report['after_cut']}")
        print(f"적재 행: {inserted}")
        print(f"status 완료: {report['status_done']} / 확정: {report['status_confirmed']}")
        print(f"날짜 파싱 실패: {len(report['date_fail'])}")
        if report["date_fail"]:
            print(report["date_fail"][:20])
        if report["unmapped_columns"]:
            print("매핑 외 컬럼:", report["unmapped_columns"])
        print("샘플 5건:")
        for sample in report["sample"]:
            print(sample)

    seed_managers_from_items(conn)
    conn.commit()
    conn.close()
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="마스터 파일 마이그레이션")
    parser.add_argument("--완제품", dest="finished", required=True)
    parser.add_argument("--대여", dest="rental", required=True)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    migrate(Path(args.finished), Path(args.rental), Path(args.db), force=args.force)


if __name__ == "__main__":
    main()
