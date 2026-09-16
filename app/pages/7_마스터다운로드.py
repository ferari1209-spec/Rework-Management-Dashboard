import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.auth import require_login
from app.db import get_connection, ensure_schema
from app.services.master_export import build_master_xlsx
from app.ui import category_selector, inject_css, render_header

st.set_page_config(page_title="마스터다운로드", layout="wide")
inject_css()
require_login()
conn = get_connection()
ensure_schema(conn)
from app.auth import require_menu, has_permission
require_menu('master')
render_header()
category = category_selector()

st.write("원본 마스터와 동일한 컬럼 구조(xlsx)로 내려받습니다. 검수대기 건은 제외합니다.")
if not has_permission('master','download'):
    st.info('조회 전용 계정입니다. 다운로드 권한은 관리자에게 요청하세요.')
    st.stop()
data = build_master_xlsx(conn, category)
st.download_button(
    f"{category} 마스터 다운로드",
    data=data,
    file_name=f"{category}_재작업_마스터.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
 icon=':material/download:')
