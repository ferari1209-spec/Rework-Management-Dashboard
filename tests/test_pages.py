"""Streamlit 화면을 임시 DB에서 실행해 권한과 실행 오류를 검사한다."""
import tempfile
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import app.db as db
from app.auth import hash_password
from app.migration.migrate_master import load_category, bulk_insert

class Pages(unittest.TestCase):
    def setUp(self):
        self.cookie_patch=patch('app.auth.browser_token',return_value=None)
        self.cookie_patch.start()
        self.connections=[]
        original_connect=sqlite3.connect
        def tracked_connect(*args,**kwargs):
            conn=original_connect(*args,**kwargs)
            self.connections.append(conn)
            return conn
        self.connection_patch=patch('sqlite3.connect',side_effect=tracked_connect)
        self.connection_patch.start()
        self.temp=tempfile.TemporaryDirectory()
        self.patcher=patch.object(db,'DB_PATH',Path(self.temp.name)/'test.db')
        self.patcher.start()
        conn=db.get_connection()
        db.ensure_schema(conn)
        for login,role in [('admin','관리자'),('viewer','일반')]:
            conn.execute('INSERT INTO users(name,login_id,password_hash,role,approved) VALUES(?,?,?,?,1)',(login,login,hash_password('testpass123'),role))
        for cat,pattern in [('완제품','*완제품*Master.xls'),('대여','*대여*Master.xls')]:
            df,_=load_category(next(Path('.').glob(pattern)),cat)
            bulk_insert(conn,df,cat)
        conn.commit()
        self.admin=dict(conn.execute("SELECT * FROM users WHERE login_id='admin'").fetchone())
        self.viewer=dict(conn.execute("SELECT * FROM users WHERE login_id='viewer'").fetchone())
        conn.close()
    def tearDown(self):
        self.cookie_patch.stop()
        for conn in self.connections:
            conn.close()
        self.connection_patch.stop()
        self.patcher.stop()
        self.temp.cleanup()
    def test_pages_admin(self):
        for path in Path('app/pages').glob('*.py'):
            with self.subTest(path=path.name):
                at=AppTest.from_file(str(path),default_timeout=20)
                at.session_state['user']=self.admin
                at.run()
                self.assertFalse(at.exception, str(at.exception))
    def test_viewer_guards(self):
        for pattern in ['2_*','6_*']:
            at=AppTest.from_file(str(next(Path('app/pages').glob(pattern))),default_timeout=20)
            at.session_state['user']=self.viewer
            at.run()
            self.assertFalse(at.exception,str(at.exception))
            if pattern == '2_*':
                self.assertTrue(at.info)
                self.assertEqual(len(at.get('file_uploader')), 0)
                self.assertEqual(len(at.get('download_button')), 0)
            else:
                self.assertTrue(at.error)
    def test_main_navigation(self):
        at=AppTest.from_file('app/main.py',default_timeout=20)
        at.session_state['user']=self.admin
        at.run()
        self.assertFalse(at.exception,str(at.exception))

    def test_personal_ai_flow(self):
        at=AppTest.from_file('app/pages/8_AI분석.py',default_timeout=20)
        at.session_state['user']=self.admin
        with patch('app.ai_ui.explain',return_value='테스트 AI 해설') as explain:
            at.run()
            at.text_input(key='personal_ai_key').set_value('test-key').run()
            next(b for b in at.button if b.label=='분석 실행').click().run()
            self.assertFalse(at.exception,str(at.exception))
            explain.assert_not_called()
            at.checkbox(key='personal_ai_consent').check().run()
            next(b for b in at.button if b.label=='AI 해설 실행').click().run()
            self.assertFalse(at.exception,str(at.exception))
            explain.assert_called_once()
            self.assertTrue(any(t.value=='테스트 AI 해설' for t in at.text))
            next(b for b in at.button if b.label=='키 지우기').click().run()
            self.assertEqual(at.text_input(key='personal_ai_key').value,'')
            self.assertFalse(at.checkbox(key='personal_ai_consent').value)
            at.text_input(key='personal_ai_key').set_value('other-key').run()
            at.session_state['user']=self.viewer
            at.run()
            self.assertEqual(at.text_input(key='personal_ai_key').value,'')
            self.assertFalse(at.exception,str(at.exception))

    def test_first_admin_setup_and_login(self):
        conn=db.get_connection()
        conn.execute('DELETE FROM users')
        conn.commit()
        conn.close()
        at=AppTest.from_file('app/main.py',default_timeout=20).run()
        self.assertFalse(at.exception,str(at.exception))
        at.text_input[0].set_value('Test Admin')
        at.text_input[1].set_value('newadmin@example.com')
        at.text_input[2].set_value('Testing123!')
        at.text_input[3].set_value('Testing123!')
        at.button[0].click().run()
        self.assertFalse(at.exception,str(at.exception))
        at.text_input(key='login_id').set_value('newadmin@example.com')
        at.text_input(key='login_pw').set_value('Testing123!')
        next(b for b in at.button if b.label=='로그인').click().run()
        self.assertFalse(at.exception,str(at.exception))
        self.assertEqual(at.session_state['user']['login_id'],'newadmin@example.com')

if __name__=='__main__': unittest.main()
