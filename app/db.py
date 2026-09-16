"""SQLite 연결, 스키마 적용, 기본 설정 시드."""

from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "rework.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "migration" / "schema.sql"

# settings.key 는 PRIMARY KEY 이므로 카테고리별 값은 "key|category" 로 저장한다.
# TODO: 스키마를 (key, category) 복합키로 바꾸면 이 규칙을 제거할 수 있다.
DEFAULT_SETTINGS = [
    ("long_term_threshold_days|완제품", "완제품", "180"),
    ("long_term_threshold_days|대여", "대여", "180"),
    ("excluded_status_values", None, '[]'),
    ("minute_wage_rate", None, "547"),
    ("model_group_options", None, '["DISPLAY"]'),
    ("work_type_options", None, '["재작업"]'),
]


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.commit()


def ensure_schema(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='rework_items'"
    ).fetchone()
    if row is None:
        init_schema(conn)
        seed_settings(conn)
    conn.execute("""CREATE TABLE IF NOT EXISTS import_batches (
        digest TEXT NOT NULL, category TEXT NOT NULL, file_name TEXT NOT NULL,
        uploaded_on TEXT NOT NULL, row_count INTEGER NOT NULL,
        PRIMARY KEY (digest, category))""")
    if 'email' not in {r['name'] for r in conn.execute('PRAGMA table_info(users)')}:
        conn.execute('ALTER TABLE users ADD COLUMN email TEXT')
    if 'permissions' not in {r['name'] for r in conn.execute('PRAGMA table_info(users)')}:
        conn.execute("ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT '{}'")
    user_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]
    if "'담당자'" not in user_sql:
        conn.commit()
        conn.execute('PRAGMA foreign_keys=OFF')
        try:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute(user_sql.replace('CREATE TABLE users', 'CREATE TABLE users_roles_new').replace("'관리자', '일반'", "'관리자', '담당자', '일반'"))
                conn.execute('INSERT INTO users_roles_new SELECT * FROM users')
                conn.execute('DROP TABLE users')
                conn.execute('ALTER TABLE users_roles_new RENAME TO users')
                if conn.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('사용자 권한 스키마 참조 오류')
        finally:
            conn.execute('PRAGMA foreign_keys=ON')
    if 'team' not in {r['name'] for r in conn.execute('PRAGMA table_info(managers)')}:
        conn.execute('ALTER TABLE managers ADD COLUMN team TEXT')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email COLLATE NOCASE) WHERE email IS NOT NULL')
    conn.execute('''CREATE TABLE IF NOT EXISTS password_resets (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL, expires_at INTEGER NOT NULL,
        issued_by INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()


def seed_settings(conn: sqlite3.Connection) -> None:
    for key, category, value in DEFAULT_SETTINGS:
        conn.execute(
            """
            INSERT INTO settings (key, category, value)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (key, category, value),
        )
    conn.commit()


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None
