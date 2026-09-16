"""검수 결과를 원자적으로 반영하고 원본별 중복을 방지한다."""
from datetime import date
import math
import pandas as pd
from app.excel_io import to_iso_date
from app.migration.migrate_master import INSERT_COLUMNS
from app.services.parsing import site_anomaly_flags, unknown_manager
from app.services.completion import is_completed


def authorize(conn, login_id, upload=False, menu=None):
    user = conn.execute("SELECT * FROM users WHERE login_id=? AND approved=1", (login_id,)).fetchone()
    from app.services.permissions import allowed
    permitted = allowed(dict(user), menu or 'upload', 'edit') if user and (upload or menu) else bool(user and user['role']=='관리자')
    if not permitted:
        raise PermissionError("이 작업에 대한 권한이 없습니다.")


def clean(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def editable_import_frame(frame, kind, uploaded_on):
    """Use text columns so mixed numbers, blanks and '-' remain editable."""
    out = frame.drop(columns=['flags','has_issue','category','status'], errors='ignore').copy()
    if kind != 'master':
        out['입고일'] = uploaded_on.isoformat()
    for col in out:
        out[col] = out[col].map(lambda value: '' if clean(value) is None else str(value)).astype('string')
    return out


def review_rows(frame, conn):
    from app.services.manager_service import fill_teams
    out = fill_teams(frame, conn)
    flags = []
    for row in out.to_dict('records'):
        issues = site_anomaly_flags(clean(row.get('site')))
        if unknown_manager(conn, clean(row.get('담당자'))):
            issues.append('담당자 누락/미등록')
        if not clean(row.get('serial')):
            issues.append('시리얼 누락')
        if not clean(row.get('모델명')):
            issues.append('모델명 누락')
        q = pd.to_numeric(row.get('입고수량'), errors='coerce')
        if pd.isna(q) or not math.isfinite(q) or q < 0 or q != int(q):
            issues.append('입고수량 확인')
        for col in ('입고일', '재작업일'):
            val = clean(row.get(col))
            if val is not None and to_iso_date(val) is None:
                issues.append(f'{col} 형식 확인')
        flags.append(', '.join(issues))
    out['flags'] = flags
    out['has_issue'] = [bool(f) for f in flags]
    return out


def commit_import(conn, frame, category, digest, filename, uploaded_on, login_id, kind, reviewed_dates=False, preview=False, return_summary=False):
    authorize(conn, login_id, upload=True)
    from app.services.manager_service import fill_teams
    frame = fill_teams(frame, conn)
    records = []
    for number, row in enumerate(frame.to_dict('records'), 1):
        rec = {col: clean(row.get(col)) for col in INSERT_COLUMNS}
        if rec['투입공수'] == '-':
            rec['투입공수'] = None
        if not rec['모델명']:
            raise ValueError(f'{number}행 모델명을 입력하세요.')
        for col in ('입고수량', '완료수량', '투입공수', 'source_no'):
            value = rec[col]
            if value is None and col != '입고수량':
                continue
            try:
                value = float(value)
                if not math.isfinite(value) or value < 0 or (col != '투입공수' and value != int(value)):
                    raise ValueError()
            except (TypeError, ValueError):
                raise ValueError(f'{number}행 {col}에 유효한 숫자를 입력하세요.')
            rec[col] = value
        for col in ('입고일', '재작업일'):
            if rec[col] is not None and to_iso_date(rec[col]) is None:
                raise ValueError(f'{number}행 {col} 날짜 형식을 확인하세요.')
            rec[col] = to_iso_date(rec[col])
        if kind != 'master' and not reviewed_dates:
            rec['입고일'] = uploaded_on.isoformat()
        rec['category'] = category
        rec['status'] = '완료' if is_completed(rec) else '확정'
        records.append([rec[c] for c in INSERT_COLUMNS] + [login_id])
    if not records:
        raise ValueError('반영할 행이 없습니다.')
    def plan():
        incoming=[dict(zip(INSERT_COLUMNS,r[:-1])) for r in records]
        if kind != 'master':
            return [('신규',None,r) for r in incoming]
        from app.services.master_sync import plan_master
        existing=[dict(r) for r in conn.execute('SELECT * FROM rework_items WHERE category=?',(category,))]
        return plan_master(existing,incoming)
    def report(actions):
        return {label:sum(a[0]==label for a in actions) for label in ('신규','변경','동일')}
    if preview:
        return report(plan())
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        authorize(conn, login_id, upload=True)
        if conn.execute('SELECT 1 FROM import_batches WHERE digest=? AND category=?', (digest, category)).fetchone():
            raise ValueError('이미 반영된 파일입니다. 업로드 이력을 확인하세요.')
        actions=plan();stats=report(actions)
        cols = INSERT_COLUMNS + ['updated_by']
        for action,item_id,rec in actions:
            values=[rec[c] for c in INSERT_COLUMNS]+[login_id]
            if action=='신규':
                conn.execute(f"INSERT INTO rework_items ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",values)
            elif action=='변경':
                conn.execute(f"UPDATE rework_items SET {','.join(c+'=?' for c in cols)},updated_at=datetime('now') WHERE id=?",values+[item_id])
        count=stats['신규']+stats['변경']
        conn.execute('INSERT INTO import_batches VALUES (?,?,?,?,?)', (digest, category, filename, uploaded_on.isoformat(), count))
        conn.execute("INSERT INTO upload_logs(category,uploaded_by,file_name,row_count,status,note) VALUES(?,?,?,?,'확정',?)", (category, login_id, filename, count, f'{kind}; 신규 {stats["신규"]}, 변경 {stats["변경"]}, 동일 건너뜀 {stats["동일"]}; sha256={digest}'))
    return stats if return_summary else count
