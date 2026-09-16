import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.auth import current_user, ensure_bootstrap_admin, render_auth_screen
from app.db import get_connection, ensure_schema, seed_settings
from app.ui import inject_css, render_header, logo_html
from app.browser_login import flush_cookie

st.set_page_config(page_title="재작업 통합 관리 대시보드", layout="wide", page_icon="📊")
inject_css()
conn = get_connection()
ensure_schema(conn)
seed_settings(conn)
flush_cookie()
user = current_user()
if not user:
    def login_page():
        if st.session_state.get('_backup_restore_notice'):
            st.success('백업 복원이 완료되었습니다. 백업에 있던 승인 계정으로 다시 로그인하세요.')
        with st.container(key='auth_card'):
            st.markdown(f'<div class="auth-brand">{logo_html()}</div><div class="auth-description">재작업 통합 관리 시스템</div>', unsafe_allow_html=True)
            ensure_bootstrap_admin(conn)
            render_auth_screen(conn)

    # Register navigation before rendering authentication so pages/ discovery
    # never exposes the automatic sidebar on a fresh server session.
    try:
        st.navigation([st.Page(login_page, title='로그인', default=True)], position='hidden').run()
    finally:
        conn.close()
    st.stop()
pages = [st.Page("pages/1_개요.py", title="개요", icon=':material/dashboard:', default=True)]
menu_icons = dict(upload='upload_file',inventory='inventory_2',history='task_alt',cost='calculate',master='download',analysis='analytics')
from app.services.permissions import allowed
for menu, path, title in [('upload','2_업로드_검수.py','업로드·검수'),('inventory','3_재고현황.py','재고현황'),('history','4_완료이력.py','완료이력'),('cost','5_비용리포트.py','비용리포트'),('master','7_마스터다운로드.py','마스터 다운로드'),('analysis','8_AI분석.py','AI 분석')]:
    if allowed(user, menu):
        pages.append(st.Page('pages/'+path,title=title,icon=f':material/{menu_icons[menu]}:'))
if user["role"] == "관리자":
    pages.append(st.Page("pages/6_설정.py", title="설정",icon=':material/settings:'))
conn.close()
st.navigation(pages, position='top').run()
