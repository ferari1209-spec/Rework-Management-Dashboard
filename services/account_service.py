"""이메일 아이디 전환 및 일회용 비밀번호 재설정."""
import re
import time
import secrets
import hashlib
import sqlite3
import bcrypt
from app.services.login_sessions import ensure_sessions


def normalize_email(value):
    email=str(value or '').strip().lower()
    if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
        raise ValueError('이메일 형식으로 입력하세요. 예: name@company.com')
    return email


def valid_password(password):
    if len(password)<8 or len(password.encode('utf-8'))>72:
        raise ValueError('비밀번호는 8자 이상, UTF-8 72바이트 이하여야 합니다.')


def password_matches(password,hashed):
    try:
        return bcrypt.checkpw(password.encode(),hashed.encode())
    except ValueError:
        return False


def email_available(conn,email,user_id=None):
    return conn.execute('SELECT 1 FROM users WHERE (email=? COLLATE NOCASE OR login_id=? COLLATE NOCASE) AND id!=?',(email,email,user_id or -1)).fetchone() is None


def migrate_email(conn,old_login,password,email):
    email=normalize_email(email)
    row=conn.execute('SELECT * FROM users WHERE login_id=?',(old_login.strip(),)).fetchone()
    if not row or not row['approved'] or not password_matches(password,row['password_hash']):
        raise ValueError('기존 계정 정보 또는 승인 상태를 확인하세요.')
    if row['email']:
        raise ValueError('이메일이 이미 등록된 계정입니다. 이메일로 로그인하세요.')
    if not email_available(conn,email,row['id']):
        raise ValueError('이미 사용 중인 이메일입니다.')
    with conn:
        conn.execute('UPDATE users SET email=? WHERE id=? AND email IS NULL',(email,row['id']))
    return email


def issue_reset(conn,actor_id,actor_password,target_id):
    actor=conn.execute("SELECT * FROM users WHERE id=? AND approved=1 AND role='관리자'",(actor_id,)).fetchone()
    if not actor or not password_matches(actor_password,actor['password_hash']):
        raise PermissionError('관리자 비밀번호와 권한을 확인하세요.')
    target=conn.execute('SELECT * FROM users WHERE id=? AND approved=1 AND email IS NOT NULL',(target_id,)).fetchone()
    if not target:
        raise ValueError('이메일 등록과 승인이 완료된 계정만 재설정할 수 있습니다.')
    token=secrets.token_urlsafe(24)
    with conn:
        conn.execute('INSERT OR REPLACE INTO password_resets(user_id,token_hash,expires_at,issued_by) VALUES(?,?,?,?)',(target_id,hashlib.sha256(token.encode()).hexdigest(),int(time.time())+1800,actor_id))
    return token


def reset_password(conn,email,token,password):
    email=normalize_email(email)
    valid_password(password)
    if not 20<=len(token.strip())<=100:
        raise ValueError('재설정 코드가 올바르지 않거나 만료되었습니다.')
    token_hash=hashlib.sha256(token.strip().encode()).hexdigest()
    hashed=bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()
    ensure_sessions(conn)
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('''SELECT u.id FROM users u JOIN password_resets r ON r.user_id=u.id
            WHERE u.email=? COLLATE NOCASE AND u.approved=1 AND r.token_hash=? AND r.expires_at>?''',(email,token_hash,int(time.time()))).fetchone()
        if not row:
            raise ValueError('재설정 코드가 올바르지 않거나 만료되었습니다.')
        conn.execute('UPDATE users SET password_hash=? WHERE id=?',(hashed,row['id']))
        conn.execute('DELETE FROM password_resets WHERE user_id=?',(row['id'],))
        conn.execute('DELETE FROM login_sessions WHERE user_id=?',(row['id'],))
