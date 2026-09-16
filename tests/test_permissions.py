import json
import unittest
from app.services.permissions import allowed, MENUS

class PermissionsTests(unittest.TestCase):
    def test_role_defaults(self):
        for role in ['관리자','담당자','일반']:
            user = dict(role=role,approved=1)
            for menu in MENUS:
                self.assertTrue(allowed(user,menu))
                self.assertEqual(allowed(user,menu,'download'),role!='일반')
                self.assertEqual(allowed(user,menu,'edit'),role=='관리자')
    def test_override_and_view_gate(self):
        user = dict(role='일반',approved=1,permissions=json.dumps({'inventory':{'edit':True,'download':True}}))
        self.assertTrue(allowed(user,'inventory','edit'))
        self.assertTrue(allowed(user,'inventory','download'))
        user['permissions']=json.dumps({'inventory':{'view':False,'edit':True}})
        self.assertFalse(allowed(user,'inventory','edit'))
        user['approved']=0
        self.assertFalse(allowed(user,'cost'))
