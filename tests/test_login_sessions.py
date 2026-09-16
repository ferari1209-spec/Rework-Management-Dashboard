import unittest
import sqlite3
from unittest.mock import patch
from app.services import login_sessions as sessions


class LoginSessions(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,approved INTEGER,role TEXT)')
        self.conn.execute("INSERT INTO users VALUES(1,1,'관리자')")
        self.conn.commit()
    def tearDown(self):
        self.conn.close()
    def test_refresh_restores_and_stores_only_hash(self):
        token=sessions.issue(self.conn,1)
        self.assertNotEqual(self.conn.execute('SELECT token_hash FROM login_sessions').fetchone()[0],token)
        self.assertEqual(sessions.resolve(self.conn,token)['id'],1)
        self.assertIsNone(sessions.resolve(self.conn,token+'tamper'))
    def test_logout_and_expiration(self):
        token=sessions.issue(self.conn,1)
        sessions.revoke(self.conn,token)
        self.assertIsNone(sessions.resolve(self.conn,token))
        with patch.object(sessions.time,'time',return_value=100):
            token=sessions.issue(self.conn,1)
        with patch.object(sessions.time,'time',return_value=100+sessions.SESSION_SECONDS):
            self.assertIsNone(sessions.resolve(self.conn,token))
    def test_approval_and_role_checked_on_restore(self):
        token=sessions.issue(self.conn,1)
        self.conn.execute("UPDATE users SET role='일반'")
        self.conn.commit()
        self.assertEqual(sessions.resolve(self.conn,token)['role'],'일반')
        self.conn.execute('UPDATE users SET approved=0')
        self.conn.commit()
        self.assertIsNone(sessions.resolve(self.conn,token))
