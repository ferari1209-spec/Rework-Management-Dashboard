import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.db import get_connection,ensure_schema
from app.auth import register_user,authenticate,hash_password
from app.services.account_service import migrate_email,issue_reset,reset_password
from app.services import login_sessions


class Accounts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.conn=get_connection(Path(self.temp.name)/'test.db')
        ensure_schema(self.conn)
        self.conn.execute("INSERT INTO users(name,login_id,password_hash,role,approved) VALUES('Admin','admin',?,'관리자',1)",(hash_password('Original123!'),))
        self.conn.commit()
    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()
    def test_email_signup_duplicate_and_approval(self):
        payload=dict(company='ATEC',name='Test',team='Team',position='Staff',email='User@Example.com',password='Original123!')
        self.assertTrue(register_user(self.conn,payload)[0])
        self.assertFalse(register_user(self.conn,payload)[0])
        self.assertIsNone(authenticate(self.conn,'user@example.com','Original123!')[0])
        self.conn.execute("UPDATE users SET approved=1 WHERE email='user@example.com'")
        self.conn.commit()
        self.assertIsNotNone(authenticate(self.conn,'USER@example.com','Original123!')[0])
        self.assertFalse(register_user(self.conn,{**payload,'email':'invalid'})[0])
    def test_legacy_transition_requires_password_and_preserves_id(self):
        with self.assertRaises(ValueError): migrate_email(self.conn,'admin','wrong','admin@example.com')
        migrate_email(self.conn,'admin','Original123!','admin@example.com')
        self.assertIsNone(authenticate(self.conn,'admin','Original123!')[0])
        self.assertEqual(authenticate(self.conn,'admin@example.com','Original123!')[0]['login_id'],'admin')
        with self.assertRaises(ValueError): migrate_email(self.conn,'admin','Original123!','another@example.com')
    def test_reset_one_use_revokes_sessions(self):
        migrate_email(self.conn,'admin','Original123!','admin@example.com')
        session=login_sessions.issue(self.conn,1)
        with self.assertRaises(PermissionError): issue_reset(self.conn,1,'wrong',1)
        token=issue_reset(self.conn,1,'Original123!',1)
        with self.assertRaises(ValueError): reset_password(self.conn,'admin@example.com',token+'bad','Changed123!')
        reset_password(self.conn,'admin@example.com',token,'Changed123!')
        self.assertIsNone(login_sessions.resolve(self.conn,session))
        self.assertIsNotNone(authenticate(self.conn,'admin@example.com','Changed123!')[0])
        self.assertIsNone(authenticate(self.conn,'admin@example.com','Original123!')[0])
        with self.assertRaises(ValueError): reset_password(self.conn,'admin@example.com',token,'Again123!')
    def test_expired_code_and_new_issue(self):
        migrate_email(self.conn,'admin','Original123!','admin@example.com')
        first=issue_reset(self.conn,1,'Original123!',1)
        second=issue_reset(self.conn,1,'Original123!',1)
        with self.assertRaises(ValueError): reset_password(self.conn,'admin@example.com',first,'Changed123!')
        self.conn.execute('UPDATE password_resets SET expires_at=0')
        self.conn.commit()
        with self.assertRaises(ValueError): reset_password(self.conn,'admin@example.com',second,'Changed123!')
