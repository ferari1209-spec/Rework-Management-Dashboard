import unittest
from streamlit.testing.v1 import AppTest


class TableSelectionTests(unittest.TestCase):
    def test_all_clear_and_filter_reset(self):
        app = AppTest.from_string('''
import pandas as pd
import streamlit as st
from app.table_ui import selectable_table
frame = pd.DataFrame({'id':[1,2], '모델명':['A','B']})
if st.checkbox('필터'):
    frame = frame.iloc[:1]
edited, selected = selectable_table(frame, 'test')
st.text(f'선택 결과 {len(selected)}')
''').run()
        app.button(key='test_select_all').click().run()
        self.assertEqual(app.text[0].value, '선택 결과 2')
        app.button(key='test_clear_all').click().run()
        self.assertEqual(app.text[0].value, '선택 결과 0')
        app.button(key='test_select_all').click().run()
        app.checkbox[0].check().run()
        self.assertEqual(app.text[0].value, '선택 결과 0')
        app.button(key='test_select_all').click().run()
        self.assertEqual(app.text[0].value, '선택 결과 1')
        self.assertFalse(app.exception)
