import unittest
import pandas as pd
from app.services.local_explanation import explain_locally


class LocalExplanation(unittest.TestCase):
    def result(self):
        return dict(completed=0, missing_hours=0, inbound=0, hours=0,
                    inventory=pd.DataFrame(), quality=pd.DataFrame(),
                    anomalies=pd.DataFrame(), insufficient=0, repeated=pd.DataFrame())

    def test_empty_period_is_not_claimed_normal(self):
        text=' '.join(v for _,v in explain_locally(self.result()))
        self.assertIn('완료일이 등록된 완료 기록이 없습니다',text)
        self.assertIn('정상 여부를 보장',text)

    def test_missing_hours_and_quality_duplicates(self):
        r=self.result()
        r.update(completed=4,missing_hours=1,hours=3,
                 quality=pd.DataFrame({'확인사항':['입고일 미등록','완료일 미등록']}),
                 inventory=pd.DataFrame({'age_days':[100,None,-1]}))
        text=' '.join(v for _,v in explain_locally(r))
        self.assertIn('25.0%',text)
        self.assertIn('100일',text)
        self.assertIn('미래인 1건',text)
        self.assertIn('확인사항은 2개',text)
        self.assertIn('재고 증감으로 해석하지',text)
