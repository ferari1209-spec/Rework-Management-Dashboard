import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.auth import require_login
from app.data_access import fetch_items
from app.db import get_connection, ensure_schema
from app.ui import category_selector, inject_css, render_header
from app.table_ui import search_table, selectable_table, selected_download

st.set_page_config(page_title="완료이력", layout="wide")
inject_css()
require_login()
conn = get_connection()
ensure_schema(conn)
from app.auth import require_menu, has_permission
require_menu('history')
render_header()
category = category_selector()

df = fetch_items(conn, category)
done = df[df["status"] == "완료"].copy() if not df.empty else df

with st.container(width=1240, key='history_filters'):
    filter_columns = st.columns(5)
    filter_specs = [('모델명','inventory_2','모델명'), ('담당자','person','담당자'),
                    ('site','location_on','SITE'), ('담당팀','groups','담당팀'),
                    ('구분','filter_list','구분')]
    selected_filters = {}
    for column, (field, icon, label) in zip(filter_columns, filter_specs):
        values = sorted(done[field].dropna().astype(str).unique().tolist()) if field in done else []
        with column:
            selected_filters[field] = st.selectbox(
                f':material/{icon}: {label}', [None] + values,
                format_func=lambda value: '(전체)' if value is None else (value or '(미입력)'),
                key=f'history_filter_{category}_{field}')
    st.caption('5개 필터는 완료 목록과 선택 다운로드에 적용됩니다. 구분은 재작업 이후 처리 결과입니다.')

with st.container(width=460, key='compact_filters'):
    c1, c2 = st.columns(2)
    with c1:
        d_from = st.date_input(':material/calendar_month: 시작일', value=date(date.today().year, 1, 1))
    with c2:
        d_to = st.date_input(':material/calendar_month: 종료일', value=date.today())

if not done.empty:
    dates = pd.to_datetime(done["재작업일"], errors="coerce")
    include_undated = st.checkbox('완료일 미등록 건 포함', value=True)
    missing_count = int(dates.isna().sum())
    if missing_count:
        st.caption(f'완료 표시가 있으나 완료일이 없는 항목 {missing_count:,}건입니다. 완료일 미등록 건은 기간과 관계없이 표시하며 월별 완료 집계에서는 제외합니다.')
    view = done[((dates >= pd.Timestamp(d_from)) & (dates <= pd.Timestamp(d_to))) | (dates.isna() & include_undated)]
else:
    view = done

for field, value in selected_filters.items():
    if value is not None and field in view:
        view = view[view[field].astype('string').eq(value).fillna(False)]
view = search_table(view, f'done_search_{category}', count_label='완료 건수')
_, selected = selectable_table(
    view[
        [c for c in ["id", "재작업일", "입고일", "담당자", "담당팀", "site", "모델명", "serial", "입고수량", "완료수량", "구분", "투입공수"] if c in view.columns]
    ] if not view.empty else view,
    key=f'done_table_{category}',
)
selected_download(selected, f'{category}_완료이력', menu='history')

history_chart = st.container(border=True, key='history_chart')
history_chart.markdown("### 월별 입고수량 vs 월재작업수량")
current_month = pd.Timestamp.today().to_period('M')
with history_chart:
    st.caption('기본 최근 12개월 · 위 목록의 5개 필터·부분 검색·조회 기간과 별도로 집계합니다. 선택한 시작월부터 종료월까지 월 전체를 집계합니다.')
    with st.container(width=460):
        start_col, end_col = st.columns(2)
    chart_start = start_col.date_input(':material/calendar_month: 그래프 시작월', value=(current_month-11).start_time.date(), key='history_chart_start')
    chart_end = end_col.date_input(':material/calendar_month: 그래프 종료월', value=current_month.start_time.date(), key='history_chart_end')
start_month = pd.Timestamp(chart_start).to_period('M')
end_month = pd.Timestamp(chart_end).to_period('M')
if start_month > end_month:
    history_chart.error('그래프 시작월은 종료월보다 늦을 수 없습니다.')
    st.stop()
if df.empty:
    st.stop()
all_df = df.copy()
all_df["입고월"] = pd.to_datetime(all_df["입고일"], errors="coerce").dt.to_period("M")
all_df["완료월"] = pd.to_datetime(all_df["재작업일"], errors="coerce").dt.to_period("M")
in_map = all_df.groupby("입고월")["입고수량"].apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum())
done_map = all_df.groupby("완료월")["완료수량"].apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum())
months = pd.period_range(start_month, end_month, freq='M')
if len(months):
    st.markdown(f'<style>.st-key-history_chart [data-testid="stPlotlyChart"] {{min-width:{max(760,len(months)*64+120)}px}}</style>', unsafe_allow_html=True)
    chart = pd.DataFrame(
        {
            "입고수량": [float(in_map.get(m, 0) or 0) for m in months],
            "월재작업수량": [float(done_map.get(m, 0) or 0) for m in months],
        },
        index=[str(m) for m in months],
    )
    import plotly.graph_objects as go
    fig = go.Figure()
    for column, color, placement in [('입고수량','#729bc0','bottom center'),('월재작업수량','#168fa1','top center')]:
        values = chart[column]
        fig.add_trace(go.Scatter(x=chart.index,y=values,name=column,mode='lines+markers',
            textfont=dict(color=color,size=12),line=dict(color=color,width=3),cliponaxis=False))
    fig.update_layout(height=350,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=30,r=45,t=35,b=45),font=dict(family='Malgun Gothic, sans-serif',color='#203650'),
        legend=dict(orientation='h',y=-.2),hovermode='x unified')
    fig.update_yaxes(rangemode='tozero',gridcolor='#dfe7ee')
    from app.chart_labels import add_monthly_labels
    add_monthly_labels(fig)
    history_chart.caption('상단 숫자: 위 입고 / 아래 완료 (대)')
    history_chart.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False})
