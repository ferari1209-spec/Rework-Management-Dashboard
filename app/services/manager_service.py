import pandas as pd
from app.services.import_service import authorize


def fill_teams(frame, conn):
    out = frame.copy()
    if '담당자' not in out:
        return out
    mapping = {r['name'].strip(): r['team'] for r in conn.execute("SELECT name,team FROM managers WHERE is_active=1 AND team IS NOT NULL AND TRIM(team)<>''")}
    if '담당팀' not in out:
        out['담당팀'] = None
    missing = out['담당팀'].isna() | out['담당팀'].astype(str).str.strip().eq('')
    out.loc[missing, '담당팀'] = out.loc[missing, '담당자'].fillna('').astype(str).str.strip().map(mapping)
    return out


def delete_users(conn, ids, actor):
    ids = set(map(int, ids))
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        authorize(conn, actor)
        users = [dict(r) for r in conn.execute('SELECT id,login_id,role,approved FROM users')]
        if any(r['id'] in ids and r['login_id']==actor for r in users):
            raise ValueError('현재 로그인한 계정은 삭제할 수 없습니다.')
        if not any(r['id'] not in ids and r['role']=='관리자' and r['approved'] for r in users):
            raise ValueError('승인된 관리자가 최소 한 명 필요합니다.')
        conn.executemany('DELETE FROM users WHERE id=?', [(i,) for i in ids])


def update_user_profile(conn, user_id, actor, company, name, team, position, email):
    from app.services.account_service import normalize_email, email_available
    email = normalize_email(email)
    values = [str(v or '').strip() for v in (company, name, team, position)]
    if not all(values):
        raise ValueError('회사명, 이름, 담당팀, 직책을 모두 입력하세요.')
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        authorize(conn, actor)
        if not conn.execute('SELECT 1 FROM users WHERE id=?', (user_id,)).fetchone():
            raise ValueError('사용자가 삭제되었거나 존재하지 않습니다.')
        if not email_available(conn, email, user_id):
            raise ValueError('이미 사용 중인 이메일입니다.')
        conn.execute('UPDATE users SET company=?,name=?,team=?,position=?,email=? WHERE id=?', (*values,email,user_id))
