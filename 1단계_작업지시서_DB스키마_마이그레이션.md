# 1단계 작업 지시서: DB 스키마 구성 + 기존 마스터 파일 마이그레이션

> 이 문서는 Claude Code에 그대로 전달하여 작업을 시작할 수 있도록 작성되었습니다.
> 목표: 기존 마스터 엑셀 2종(완제품/대여)을 손실 없이 DB로 이관하고, 이후 단계(업로드·대시보드·리포트)가 이 DB 위에서 동작할 수 있는 기반을 만든다.

---

## 0. 프로젝트 구조

```
rework-dashboard/
├── app/
│   ├── __init__.py
│   ├── db.py                  # DB 연결/세션 관리
│   ├── models.py               # 테이블 정의 (SQLAlchemy 권장, 또는 raw SQL)
│   └── migration/
│       ├── __init__.py
│       ├── schema.sql          # 전체 스키마 DDL
│       ├── migrate_master.py   # 마스터 파일 → DB 적재 스크립트
│       └── mapping_config.py   # 카테고리별 컬럼 매핑 정의
├── data/
│   ├── raw/                    # 원본 마스터 xls 원본 보관 (읽기 전용)
│   └── rework.db               # SQLite DB 파일 (gitignore 대상)
├── tests/
│   └── test_migration.py       # 마이그레이션 검증 테스트
├── requirements.txt
└── README.md
```

**기술 스택**: Python 3.11+, SQLite (파일 기반, 추후 필요시 교체 용이), `pandas` + `xlrd`(레거시 .xls 읽기), `SQLAlchemy`(선택, 스키마 관리 용이) 또는 `sqlite3` 표준 라이브러리.

---

## 1. DB 스키마 (`schema.sql`)

아래 DDL을 기준으로 작성한다. SQLite 문법 기준.

```sql
-- ========================================
-- 1. 재작업 품목 (완제품/대여 통합, category로 구분)
-- ========================================
CREATE TABLE rework_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL CHECK (category IN ('완제품', '대여')),
    source_no       INTEGER,                 -- 원본 마스터의 No. (참고용, 중복 가능)
    입고일           DATE,                    -- = 이관/업로드일로 취급, 수정 가능
    담당자           TEXT,
    담당팀           TEXT,
    site            TEXT,                    -- 완제품:사이트명 / 대여:대여처 → 통일된 컬럼명
    재작업월         TEXT,
    재작업일         DATE,                    -- NULL = 미완료(현재 재고)
    품목분류         TEXT,
    모델명           TEXT,
    serial          TEXT,
    변경모델명       TEXT,
    변경serial       TEXT,
    투입공수         REAL,
    작업주체         TEXT,
    입고수량         INTEGER,
    완료수량         INTEGER,
    구분             TEXT,                    -- 해체/출고/완제품화/폐기 등
    재작업내용       TEXT,
    비고_원문        TEXT,                    -- 원본 비고란 그대로 보존
    status          TEXT NOT NULL DEFAULT '확정'
                        CHECK (status IN ('검수대기', '확정', '완료')),
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    updated_by      TEXT
);

CREATE INDEX idx_rework_category ON rework_items(category);
CREATE INDEX idx_rework_status ON rework_items(category, status);
CREATE INDEX idx_rework_입고일 ON rework_items(입고일);
CREATE INDEX idx_rework_재작업일 ON rework_items(재작업일);

-- ========================================
-- 2. 설정
-- ========================================
CREATE TABLE settings (
    key             TEXT PRIMARY KEY,
    category        TEXT,                    -- NULL이면 전역 설정
    value           TEXT NOT NULL,            -- JSON 문자열로 저장 (리스트/객체 대응)
    updated_at      TEXT DEFAULT (datetime('now'))
);
-- 예시 row:
--  ('long_term_threshold_days', '완제품', '180')
--  ('long_term_threshold_days', '대여', '180')
--  ('excluded_status_values', NULL, '["폐기"]')
--  ('minute_wage_rate', NULL, '547')
--  ('model_group_options', NULL, '["DISPLAY"]')
--  ('work_type_options', NULL, '["재작업"]')

-- ========================================
-- 3. 담당자 관리 목록
-- ========================================
CREATE TABLE managers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ========================================
-- 4. SITE 이상치 검토 이력
-- ========================================
CREATE TABLE site_flags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rework_item_id  INTEGER REFERENCES rework_items(id),
    original_value  TEXT,
    flag_reason     TEXT,                    -- 예: '빈값', '형식이상', '너무 짧음'
    resolved        INTEGER NOT NULL DEFAULT 0,
    resolved_by     TEXT,
    resolved_at     TEXT
);

-- ========================================
-- 5. 사용자 / 권한
-- ========================================
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
    can_upload      INTEGER NOT NULL DEFAULT 0,   -- 일반 사용자 확장 권한
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ========================================
-- 6. 업로드 이력
-- ========================================
CREATE TABLE upload_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL,
    uploaded_by     TEXT,
    file_name       TEXT,
    row_count       INTEGER,
    status          TEXT NOT NULL DEFAULT '검수중' CHECK (status IN ('검수중', '확정', '실패')),
    note            TEXT,                    -- 마이그레이션의 경우 'initial_migration' 등 표기
    created_at      TEXT DEFAULT (datetime('now'))
);
```

**설계 메모**
- `site`, `변경serial` 등은 완제품(`사이트명`)/대여(`대여처`) 컬럼명이 다르므로 **DB에서는 통일된 컬럼명**을 쓰고, 매핑은 `mapping_config.py`에서 관리한다.
- `status`는 마이그레이션 시 `재작업일 존재 여부`로 자동 산출한다 (섹션 3 참고).
- 최초 마이그레이션은 `upload_logs`에 `note='initial_migration'`으로 기록해, 이후 실제 업로드 이력과 구분한다.

---

## 2. 컬럼 매핑 정의 (`mapping_config.py`)

기존 마스터 파일 2종은 컬럼명이 미세하게 다르다 (완제품: `사이트명`, 대여: `대여처`). 아래처럼 카테고리별 매핑 딕셔너리를 만든다.

```python
COLUMN_MAPPING = {
    "완제품": {
        "sheet_name": "완제품재작업현황",
        "header_row": 2,  # 0-indexed → 실제 엑셀 3번째 행이 헤더
        "columns": {
            "No.": "source_no",
            "입고년도": None,          # 입고일로 통합, 별도 저장 안 함 (필요시 파생 컬럼으로 유지 검토)
            "입고월": None,
            "입고일": "입고일",
            "담당자": "담당자",
            "담당팀": "담당팀",
            "사이트명": "site",
            "재작업월": "재작업월",
            "재작업일": "재작업일",
            "품목\n분류": "품목분류",
            "모델명": "모델명",
            "Ser.": "serial",
            "변경모델명": "변경모델명",
            "변경Ser.": "변경serial",
            "투입\n공수": "투입공수",
            "작업\n주체": "작업주체",
            "입고\n수량": "입고수량",
            "완료\n수량": "완료수량",
            "구분": "구분",
            "재작업내용": "재작업내용",
            "비고": "비고_원문",
        },
    },
    "대여": {
        "sheet_name": "대여작업현황",
        "header_row": 2,
        "columns": {
            "No.": "source_no",
            "입고년도": None,
            "입고월": None,
            "입고일": "입고일",
            "담당자": "담당자",
            "담당팀": "담당팀",
            "대여처": "site",
            "재작업월": "재작업월",
            "재작업일": "재작업일",
            "품목\n분류": "품목분류",
            "모델명": "모델명",
            "Ser.": "serial",
            "변경모델명": "변경모델명",
            "변경Ser.": "변경serial",
            "투입\n공수": "투입공수",
            "작업\n주체": "작업주체",
            "입고\n수량": "입고수량",
            "완료\n수량": "완료수량",
            "구분": "구분",
            "재작업내용": "재작업내용",
            "비고": "비고_원문",
        },
    },
}
```

> ⚠️ 실제 파일의 컬럼명에 개행문자(`\n`)가 포함되어 있음 (`"품목\n분류"` 등). `pandas.read_excel` 결과의 `df.columns`를 그대로 확인 후 매핑 키와 정확히 일치시킬 것.

---

## 3. 마이그레이션 스크립트 요구사항 (`migrate_master.py`)

### 3.1 입력
- CLI 인자로 두 마스터 파일 경로를 받는다.
  ```bash
  python -m app.migration.migrate_master \
      --완제품 "data/raw/2026년_완제품_재작업_비용_및_현황_전체누적_Master.xls" \
      --대여 "data/raw/2026년_대여반납제품_재작업_비용_및_현황_전체누적_Master.xls" \
      --db data/rework.db
  ```

### 3.2 처리 절차
1. `pandas.read_excel(path, sheet_name=..., engine="xlrd", header=header_row)` 로 읽는다.
2. **빈 행 컷**: `No.`, `입고일`, `모델명`이 모두 NaN인 행부터는 이후 전부 제거한다 (trailing 빈 행 제거). 데이터 중간에 우연히 한 행이 비는 경우까지 자르지 않도록, "연속으로 3행 이상 완전히 비는 지점"을 기준으로 컷하는 방식을 권장.
3. 컬럼 매핑 딕셔너리에 따라 컬럼명을 표준화하고, 매핑에 없는 컬럼은 버린다.
4. 날짜 컬럼(`입고일`, `재작업일`)은 `pd.to_datetime(..., errors="coerce")`로 변환, 실패 시 NULL 처리 후 **변환 실패 건수를 로그로 남긴다**.
5. 숫자 컬럼(`투입공수`, `입고수량`, `완료수량`)은 `pd.to_numeric(..., errors="coerce")`.
6. `status` 산출:
   ```python
   status = "완료" if pd.notna(row["재작업일"]) else "확정"
   ```
   (마이그레이션 데이터는 이미 검수를 거친 것으로 간주하여 `검수대기` 상태는 사용하지 않음)
7. `category` 컬럼에 `"완제품"` 또는 `"대여"`를 채운다.
8. `rework_items` 테이블에 bulk insert.
9. `upload_logs`에 1건 기록 (`note="initial_migration"`, `row_count`=실제 적재된 행 수).

### 3.3 검증 (마이그레이션 스크립트 실행 후 자동 출력)
- 카테고리별 적재 행 수 vs 원본 유효 행 수(빈 행 제외) 일치 여부
- 날짜 변환 실패 건수 및 해당 원본 행 번호 리스트 출력
- `status='완료'` 건수 vs `status='확정'`(=현재 재고) 건수 요약 출력
- 샘플 5건 랜덤 출력 (원본 값 ↔ DB 저장 값 비교용)

### 3.4 재실행 안전성 (중요)
- 스크립트를 여러 번 실행해도 데이터가 중복 적재되지 않아야 한다.
- 권장 방식: 마이그레이션 실행 시 `--force` 옵션이 없으면, 해당 category에 이미 `note='initial_migration'` 로그가 있는 경우 실행을 중단하고 경고 메시지를 출력한다.

---

## 4. 기본 설정값 초기화

마이그레이션과 별도로, DB 최초 생성 시 `settings`, `managers` 테이블에 기본값을 넣는 초기화 스크립트(`seed_defaults.py` 또는 `migrate_master.py`에 포함)를 작성한다.

```python
DEFAULT_SETTINGS = [
    ("long_term_threshold_days", "완제품", "180"),
    ("long_term_threshold_days", "대여", "180"),
    ("excluded_status_values", None, '["폐기"]'),
    ("minute_wage_rate", None, "547"),
    ("model_group_options", None, '["DISPLAY"]'),
    ("work_type_options", None, '["재작업"]'),
]
```

`managers`는 마이그레이션된 `담당자` 컬럼의 고유값을 자동 추출해 초기 목록으로 채운다 (중복 제거, 공백/오탈자 그대로 우선 등록 → 이후 화면에서 정리 가능하도록).

---

## 5. 테스트 (`tests/test_migration.py`)

pytest 기준으로 아래를 검증한다.

1. `schema.sql` 실행 후 6개 테이블이 모두 생성되는지
2. 실제 첨부 마스터 파일 2종으로 마이그레이션 실행 시:
   - `rework_items` 테이블의 `category='완제품'` 행 수가 원본 유효 데이터 행 수와 일치
   - `category='대여'` 도 동일
   - `재작업일 IS NULL` 인 행의 `status`가 전부 `'확정'`인지
   - `재작업일 IS NOT NULL` 인 행의 `status`가 전부 `'완료'`인지
3. 동일 스크립트를 `--force` 없이 재실행했을 때 행 수가 늘어나지 않는지 (중복 방지 확인)
4. 날짜 파싱 실패 건수가 0건인지 (0건이 아니면 어떤 행인지 리포트에 남기고 사람이 확인하도록 안내)

---

## 6. 산출물 체크리스트 (완료 정의)

- [ ] `schema.sql` 작성 및 `sqlite3 data/rework.db < schema.sql` 정상 실행
- [ ] `mapping_config.py` 작성, 실제 파일 컬럼명과 1:1 검증 완료
- [ ] `migrate_master.py` 작성 및 첨부된 실제 마스터 파일 2종으로 실행 성공
- [ ] 마이그레이션 검증 리포트(콘솔 출력 또는 로그 파일)에서 행 수 일치 확인
- [ ] `seed_defaults`로 기본 설정값/담당자 목록 초기화 완료
- [ ] `tests/test_migration.py` 전체 통과
- [ ] README에 실행 방법(가상환경 설치, 스크립트 실행 커맨드) 기록

---

## 7. 다음 단계 예고 (2단계 범위, 지금은 착수하지 않음)

2단계는 이 DB를 기반으로 한 **업로드 → 비고란 파싱 → 검수 화면**입니다. 1단계 산출물(특히 `rework_items` 스키마와 `status` 흐름)이 그대로 재사용되므로, 컬럼명이나 status 값(`검수대기/확정/완료`)을 임의로 바꾸지 말고 이 문서 기준을 유지해 주세요.
