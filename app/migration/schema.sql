CREATE TABLE rework_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL CHECK (category IN ('완제품', '대여')),
    source_no       INTEGER,
    입고일           DATE,
    담당자           TEXT,
    담당팀           TEXT,
    site            TEXT,
    재작업월         TEXT,
    재작업일         DATE,
    품목분류         TEXT,
    모델명           TEXT,
    serial          TEXT,
    변경모델명       TEXT,
    변경serial       TEXT,
    투입공수         REAL,
    작업주체         TEXT,
    입고수량         INTEGER,
    완료수량         INTEGER,
    구분             TEXT,
    재작업내용       TEXT,
    비고_원문        TEXT,
    status          TEXT NOT NULL DEFAULT '확정' CHECK (status IN ('검수대기', '확정', '완료')),
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    updated_by      TEXT
);
CREATE INDEX idx_rework_category ON rework_items(category);
CREATE INDEX idx_rework_status ON rework_items(category, status);
CREATE INDEX idx_rework_입고일 ON rework_items(입고일);
CREATE INDEX idx_rework_재작업일 ON rework_items(재작업일);

CREATE TABLE settings (
    key             TEXT PRIMARY KEY,
    category        TEXT,
    value           TEXT NOT NULL,
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE managers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE site_flags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rework_item_id  INTEGER REFERENCES rework_items(id),
    original_value  TEXT,
    flag_reason     TEXT,
    resolved        INTEGER NOT NULL DEFAULT 0,
    resolved_by     TEXT,
    resolved_at     TEXT
);

CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company         TEXT,
    name            TEXT NOT NULL,
    team            TEXT,
    position        TEXT,
    login_id        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT '일반' CHECK (role IN ('관리자', '일반')),
    approved        INTEGER NOT NULL DEFAULT 0,
    can_upload      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE upload_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL,
    uploaded_by     TEXT,
    file_name       TEXT,
    row_count       INTEGER,
    status          TEXT NOT NULL DEFAULT '검수중' CHECK (status IN ('검수중', '확정', '실패')),
    note            TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
