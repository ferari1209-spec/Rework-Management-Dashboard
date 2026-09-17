import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app import browser_login


class CookieRestore(unittest.TestCase):
    def test_browser_fallback_is_cached(self):
        state = {'_cookie_read_request': 'request'}
        fake_st = SimpleNamespace(context=SimpleNamespace(cookies={}), session_state=state)
        with patch.object(browser_login, 'st', fake_st), patch.object(browser_login, 'cookie_component', return_value={
            'request_id': 'request', 'ok': True, 'token': 'test-token', 'remember_email': 'test@example.com'
        }) as component:
            self.assertEqual(browser_login.browser_token(), 'test-token')
            self.assertEqual(browser_login.browser_token(), 'test-token')
            component.assert_called_once()
            self.assertEqual(state['_saved_email'], 'test@example.com')

    def test_header_cookie_does_not_require_component(self):
        fake_st = SimpleNamespace(context=SimpleNamespace(cookies={'rework_login': 'header-token'}), session_state={})
        with patch.object(browser_login, 'st', fake_st), patch.object(browser_login, 'cookie_component') as component:
            self.assertEqual(browser_login.browser_token(), 'header-token')
            component.assert_not_called()

    def test_missing_cookie_stays_logged_out(self):
        fake_st = SimpleNamespace(context=SimpleNamespace(cookies={}), session_state={'_cookie_read_request': 'request'})
        with patch.object(browser_login, 'st', fake_st), patch.object(browser_login, 'cookie_component', return_value={
            'request_id': 'request', 'ok': True, 'token': '', 'remember_email': ''
        }):
            self.assertIsNone(browser_login.browser_token())
