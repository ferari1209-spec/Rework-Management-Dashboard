import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
import bcrypt
from app.db import ensure_schema
from app.services.backup_service import build_backup,inspect_backup,restore_backup
from app.services.login_sessions import issue,resolve


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name);self.raw=self.root/'raw';self.raw.mkdir()
        self.conn=sqlite3.connect(self.root/'live.db');self.conn.row_factory=sqlite3.Row
        ensure_schema(self.conn)
        hashed=bcrypt.hashpw(b'admin-password',bcrypt.gensalt(rounds=4)).decode()
        self.conn.execute("INSERT INTO users(id,name,login_id,email,password_hash,role,approved,permissions) VALUES(1,'admin','admin@example.com','admin@example.com',?,'관리자',1,'{}')",(hashed,))
        self.conn.execute("INSERT INTO users(id,name,login_id,password_hash,role,approved) VALUES(2,'pending','pending@example.com',?,'일반',0)",(hashed,))
        self.conn.execute("INSERT INTO rework_items(category,모델명,담당팀) VALUES('완제품','TEST','TEAM')")
        self.conn.commit();(self.raw/'source.xls').write_bytes(b'original')
        self.token=issue(self.conn,1)
    def tearDown(self):
        self.conn.close();self.tmp.cleanup()
    def test_roundtrip_and_session_revocation(self):
        data=build_backup(self.conn,1,self.raw)
        self.assertIsNotNone(resolve(self.conn,self.token))
        meta=inspect_backup(self.conn,1,data)
        self.assertEqual(meta['counts']['사용자'],2)
        self.conn.execute("UPDATE users SET approved=1 WHERE id=2")
        self.conn.execute('DELETE FROM rework_items');self.conn.commit()
        (self.raw/'source.xls').write_bytes(b'changed')
        restore_backup(self.conn,1,'admin-password',data,self.raw)
        self.assertEqual(self.conn.execute('SELECT approved FROM users WHERE id=2').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM rework_items').fetchone()[0],1)
        self.assertEqual((self.raw/'source.xls').read_bytes(),b'original')
        self.assertIsNone(resolve(self.conn,self.token))
    def test_non_admin_and_bad_password(self):
        with self.assertRaises(PermissionError): build_backup(self.conn,2,self.raw)
        data=build_backup(self.conn,1,self.raw)
        with self.assertRaises(PermissionError): restore_backup(self.conn,1,'wrong',data,self.raw)
        self.assertIsNotNone(resolve(self.conn,self.token))
    def test_tampered_zip_rejected(self):
        data=build_backup(self.conn,1,self.raw);out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as z,zipfile.ZipFile(out,'w') as target:
            for n in z.namelist():target.writestr(n,b'tampered' if n=='data/raw/source.xls' else z.read(n))
        with self.assertRaises(ValueError):inspect_backup(self.conn,1,out.getvalue())
    def test_path_traversal_rejected(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('../escape','bad')
        with self.assertRaises(ValueError):inspect_backup(self.conn,1,out.getvalue())
        self.assertFalse((self.root/'escape').exists())
    def test_raw_failure_leaves_db_unchanged(self):
        data=build_backup(self.conn,1,self.raw)
        self.conn.execute("UPDATE rework_items SET 모델명='NEW'");self.conn.commit()
        from unittest.mock import patch
        with patch('app.services.backup_service.authorize',side_effect=[None,PermissionError('revoked')]):
            with self.assertRaises(PermissionError):restore_backup(self.conn,1,'admin-password',data,self.raw)
        self.assertEqual(self.conn.execute('SELECT 모델명 FROM rework_items').fetchone()[0],'NEW')
