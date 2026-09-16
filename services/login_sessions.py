"""브라우저 새로고침을 견디는 만료/폐기 가능한 서버 로그인 세션."""
import hashlib
import secrets
import time

SESSION_SECONDS = 8 * 60 * 60


def ensure_sessions(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS login_sessions (
        token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at INTEGER NOT NULL)''')
    conn.commit()


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue(conn, user_id):
    ensure_sessions(conn)
    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute('DELETE FROM login_sessions WHERE expires_at<=?', (int(time.time()),))
        conn.execute('INSERT INTO login_sessions VALUES(?,?,?)', (digest(token),user_id,int(time.time())+SESSION_SECONDS))
    return token


def resolve(conn, token):
    if not isinstance(token,str) or not 30 <= len(token) <= 128:
        return None
    ensure_sessions(conn)
    row = conn.execute('''SELECT u.* FROM users u JOIN login_sessions s ON s.user_id=u.id
        WHERE s.token_hash=? AND s.expires_at>? AND u.approved=1''', (digest(token),int(time.time()))).fetchone()
    return dict(row) if row else None


def revoke(conn, token):
    ensure_sessions(conn)
    with conn:
        conn.execute('DELETE FROM login_sessions WHERE token_hash=?',(digest(token),))
