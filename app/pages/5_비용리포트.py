import sys
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.auth import require_login
from app.db import get_connection, ensure_schema
from app.services.cost_report import build_report_xlsx, calc_amount
from app.services.cost_report import load_completed
import pandas as pd
from app.services import settings_service
from app.ui import inject_css, render_header
from app.table_ui import search_table, selectable_table, selected_download

st.set_page_config(page_title="비용리포트", layout="wide")
inject_css()
require_login()
conn = get_connection()
ensure_schema(conn)
from app.auth import require_menu, has_permission
require_menu('cost')
render_header()

rate = settings_service.get_minute_wage_rate(conn)
undated = conn.execute("SELECT COUNT(*) FROM rework_items WHERE status='완료' AND 재작업일 IS NULL").fetchone()[0]
if undated:
    st.info(f'완료일 미등록 {undated:,}건은 기간별 비용 리포트에서 제외됩니다. 완료 상태와 공수 입력 여부는 별도로 관리합니다.')
st.caption(f"분당임율: **{rate}원** (설정 화면에서 변경)")
st.caption("금액 = 투입공수 × 분당임율 × 60  |  예: 0.8 × 547 × 60 = 26,256원")

with st.container(width=460, key='compact_filters'):
    c1, c2 = st.columns(2)
    with c1:
        d_from = st.date_input(':material/calendar_month: From (재작업일)', value=date(date.today().year, date.today().month, 1))
    with c2:
        d_to = st.date_input(':material/calendar_month: To (재작업일)', value=date.today())

if d_from > d_to:
    st.error('시작일은 종료일보다 늦을 수 없습니다.')
    st.stop()
completed = load_completed(conn, d_from, d_to)
completed = search_table(completed, 'cost_search')
if completed.empty:
    st.info('선택 기간에 완료된 재작업이 없습니다.')
else:
    hours = pd.to_numeric(completed['투입공수'], errors='coerce')
    c1, c2, c3 = st.columns(3)
    from html import escape
    cards = [
        (c1,'done','task_alt','완료 건수',f'{len(completed):,}','건','현재 조회 기간·검색 조건 기준'),
        (c2,'hours','schedule','투입공수',f'{hours.sum():,.2f}','시간','공수가 입력된 항목의 합계'),
        (c3,'cost','calculate','재작업 비용',f'{hours.map(lambda h: calc_amount(h, rate)).sum():,.0f}','원',f'분당임율 {rate:,.0f}원 · 공수 미등록 제외'),
    ]
    for column, kind, icon, label, value, unit, note in cards:
        with column, st.container(key=f'cost_summary_{kind}'):
            st.markdown(f'#### :material/{icon}: {label}')
            st.markdown(f'<div class="cost-summary-value">{escape(value)}<span>{escape(unit)}</span></div>',unsafe_allow_html=True)
            st.caption(note)
    if hours.isna().any():
        st.warning(f'공수 미등록 {int(hours.isna().sum())}건은 비용 합계에서 제외됩니다.')
    display_columns = [c for c in ['id','category','재작업일','모델명','담당자','담당팀','site','serial','투입공수'] if c in completed.columns]
    cost_view = completed[display_columns].copy()
    cost_view['재작업 비용'] = hours.map(lambda h: calc_amount(h, rate))
    _, selected = selectable_table(cost_view, 'cost_table')
    selected_download(selected, '비용리포트', menu='cost')
st.caption('아래 정식 리포트는 선택 기간 전체를 대상으로 생성합니다. 개별 선택 결과는 표 아래 선택 항목 다운로드를 이용하세요.')
if has_permission("cost","download") and st.button("리포트 생성 및 다운로드", type="primary", icon=':material/download:'):
    data = build_report_xlsx(conn, d_from, d_to)
    st.download_button(
        "xlsx 다운로드",
        data=data,
        file_name=f"재작업비용_{d_from.isoformat()}_{d_to.isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
     icon=':material/download:')
    st.success("파일이 준비되었습니다. 시트: 재작업현황 / 대여반납")
