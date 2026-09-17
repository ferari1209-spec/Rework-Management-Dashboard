import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from app.auth import require_login, has_permission
from app.data_access import fetch_items
from app.db import get_connection, ensure_schema
from app.services.inventory import annotate_inventory
from app.services.settings_service import get_threshold_days, get_excluded_status_values
from app.services.kpi_details import previous_inventory, detail_frame, detail_excel
from app.ui import category_selector, inject_css, kpi_card, render_header

st.set_page_config(page_title='개요 · 재작업 통합 관리', layout='wide')
inject_css()
require_login()
conn = get_connection()
ensure_schema(conn)
render_header()
category = category_selector()
df = fetch_items(conn, category)
if df.empty:
    st.info('등록된 데이터가 없습니다. 업로드·검수에서 마스터 또는 입고 장표를 등록하세요.')
    st.stop()
df = annotate_inventory(df, conn)
inv = df[df['is_inventory']].copy()
long_term = inv[inv['is_long_term']]
threshold = get_threshold_days(conn, category)
today = pd.Timestamp.today()
this_month = today.to_period('M')
df['입고월'] = pd.to_datetime(df['입고일'], errors='coerce').dt.to_period('M')
df['완료월'] = pd.to_datetime(df['재작업일'], errors='coerce').dt.to_period('M')
df['입고수량'] = pd.to_numeric(df['입고수량'], errors='coerce').fillna(0)
df['완료수량'] = pd.to_numeric(df['완료수량'], errors='coerce').fillna(0)
inv['수량'] = pd.to_numeric(inv['입고수량'], errors='coerce').fillna(0)
ratio = len(long_term)/len(inv) if len(inv) else 0
cards = [
    ('현재 재고수량', f"{inv['수량'].sum():,.0f}대", 'info', f'미완료 품목 {len(inv):,}건'),
    ('장기재고', f'{len(long_term):,}건', 'warn', f'{threshold}일 이상 · 재고의 {ratio:.1%}'),
    ('이번 달 입고', f"{df.loc[df['입고월']==this_month,'입고수량'].sum():,.0f}대", 'info', f'{today:%Y년 %m월} 입고 기준'),
    ('이번 달 완료', f"{df.loc[df['완료월']==this_month,'완료수량'].sum():,.0f}대", 'ok', f'{today:%Y년 %m월} 재작업일 기준'),
]
previous_month = this_month - 1
prev_inv, prev_long, unknown_count = previous_inventory(df, this_month, threshold, get_excluded_status_values(conn))
current_frames = [inv, long_term, df[df['입고월']==this_month], df[df['완료월']==this_month]]
previous_frames = [prev_inv, prev_long, df[df['입고월']==previous_month], df[df['완료월']==previous_month]]
notes = [
    f'현재 재고와 {previous_month} 말 재고(입고일·완료일로 재구성)를 비교합니다. 현재 설정의 제외 구분과 장기재고 기준을 적용합니다. 과거 상태 변경 이력은 반영되지 않습니다. 날짜 부족으로 전월 재고 판정에서 제외된 항목 {unknown_count:,}건. 전월 상세의 상태는 현재 상태입니다.',
    f'현재 장기재고와 {previous_month} 말 장기재고를 비교합니다. 기준 {threshold}일. 전월 말 재고는 입고일·완료일로 재구성하며 과거 상태 변경 이력은 반영되지 않습니다. 날짜 부족으로 전월 재고 판정에서 제외된 항목 {unknown_count:,}건. 전월 상세의 상태는 현재 상태입니다.',
    f'{this_month} 월간 입고 합계와 {previous_month} 전체 월 입고 합계를 비교합니다. 이번 달은 진행 중이며 같은 경과일 비교가 아닙니다. 입고일 미등록 항목은 제외합니다.',
    f'{this_month} 월간 완료 합계와 {previous_month} 전체 월 완료 합계를 비교합니다. 이번 달은 진행 중이며 같은 경과일 비교가 아닙니다. 완료수량이 있어도 완료일 미등록 항목은 월별 집계에서 제외합니다.',
]

@st.dialog('지표 상세내역', width='large')
def show_kpi_details(index):
    if not has_permission('history' if index == 3 else 'inventory'):
        st.error('상세 조회 권한이 없습니다.')
        return
    st.subheader(f'{category} · {cards[index][0]}')
    st.caption(notes[index])
    for tab, frame in zip(st.tabs(['현재 / 이번 달', f'전월 ({previous_month})']), [current_frames[index], previous_frames[index]]):
        with tab:
            st.caption(f'{len(frame):,}건')
            st.dataframe(detail_frame(frame), hide_index=True, use_container_width=True)
    if has_permission('history' if index == 3 else 'inventory', 'download'):
        st.download_button('현재·전월 상세 엑셀 다운로드', detail_excel(current_frames[index], previous_frames[index], notes[index]), file_name=f'{category}_{cards[index][0]}_{today:%Y%m%d}.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', icon=':material/download:')

for index, (col, args) in enumerate(zip(st.columns(len(cards)), cards)):
    measure = '완료수량' if index == 3 else '입고수량'
    current_value = len(current_frames[index]) if index == 1 else pd.to_numeric(current_frames[index][measure], errors='coerce').fillna(0).sum()
    previous_value = len(previous_frames[index]) if index == 1 else pd.to_numeric(previous_frames[index][measure], errors='coerce').fillna(0).sum()
    delta = current_value - previous_value
    unit = '건' if index == 1 else '대'
    direction = '▲ 증가' if delta > 0 else ('▼ 감소' if delta < 0 else '변동 없음')
    percentage = f' ({abs(delta)/previous_value:.1%})' if previous_value else (' (전월 0 · 비율 산정 불가)' if delta else '')
    baseline = '전월 말 재구성' if index < 2 else '전월'
    comparison = f'{baseline} {previous_value:,.0f}{unit} · {direction} {abs(delta):,.0f}{unit}{percentage}'
    with col:
        kpi_card(args[0], args[1], args[2], args[3] + ' | ' + comparison)
        if st.button(f'{args[0]} 상세보기 ↗', key=f'kpi_detail_{index}', use_container_width=True):
            show_kpi_details(index)
st.caption('전월 비교: 재고는 전월 말 재구성값, 입고·완료는 전월 전체 월 합계입니다. 상세보기에서 집계 기준과 내역을 확인할 수 있습니다.')
st.caption(f'{category}재작업 · 전체 등록 {len(df):,}건 · 완료 이력 {int((df["status"]=="완료").sum()):,}건')

COLORS = ['#18a6b5','#70c9cd','#f4ba45','#ee5865','#c7d1e0']
def chart(fig, height=260):
    fig.update_layout(height=height, margin=dict(l=5,r=10,t=12,b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(family='Malgun Gothic, sans-serif',size=12,color='#566c88'), legend=dict(orientation='h',y=-.17,x=0), hoverlabel=dict(bgcolor='white'))
    fig.update_xaxes(gridcolor='#edf1f7',zeroline=False)
    fig.update_yaxes(gridcolor='#edf1f7',zeroline=False)
    fig.update_layout(margin=dict(l=15,r=70,t=35,b=30))
    for trace in fig.data:
        if trace.type == 'bar':
            values = trace.x if trace.orientation == 'h' else trace.y
            unit = '건' if trace.orientation == 'h' and list(trace.y) == ['0~3개월','3~6개월','6~12개월','12개월+','입고일 미등록'] else '대'
            trace.update(text=[f'<b>{v:,.0f}{unit}</b>' if v else '' for v in values],textposition='outside',textfont=dict(color='#203650',size=12),cliponaxis=False)
        elif trace.type == 'scatter':
            trace.update(mode='lines+markers+text',text=[f'<b>{v:,.0f}대</b>' if v else '' for v in trace.y],textposition='top center',textfont=dict(color='#168fa1',size=12),cliponaxis=False)
        elif trace.type == 'pie':
            total = sum(trace.values)
            trace.update(text=[f'{label}<br><b>{v:,.0f}건 · {v/total:.1%}</b>' if v and total else '' for label,v in zip(trace.labels,trace.values)],textinfo='text',textposition='outside',textfont=dict(color='#203650',size=12),automargin=True)
    # 누적 막대는 구간 내부에 수량을 표시한다.
    if len(fig.data)>1 and all(t.type=='bar' and t.orientation=='h' for t in fig.data):
        fig.update_traces(textposition='auto',insidetextfont=dict(color='white'),selector=dict(type='bar'))
    if any(t.type=='scatter' for t in fig.data):
        fig.update_yaxes(rangemode='tozero')
        for trace in fig.data:
            if trace.type=='bar':
                trace.update(text=None,textposition='none')
            elif trace.type=='scatter':
                trace.update(mode='lines+markers',text=None)
        fig.update_layout(hovermode='x unified')
    if any(t.type=='scatter' for t in fig.data):
        from app.chart_labels import add_monthly_labels
        add_monthly_labels(fig)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar':False})

left,right = st.columns([1.35,1])
with left, st.container(border=True, key='age_panel'):
    st.markdown('### 재고 연령 분포')
    st.caption('입고일부터의 경과 기간 · 미완료 품목 건수')
    order=['0~3개월','3~6개월','6~12개월','12개월+','입고일 미등록']
    counts=inv['age_bucket'].fillna('입고일 미등록').value_counts().reindex(order,fill_value=0)
    fig=go.Figure(go.Bar(x=counts.values,y=order,orientation='h',marker_color=COLORS,text=[f'{v:,}건' for v in counts.values],textposition='auto',hovertemplate='%{y}: %{x:,}건<extra></extra>'))
    fig.update_yaxes(autorange='reversed')
    chart(fig)
with right, st.container(border=True, key='status_panel'):
    st.markdown('### 현재 재고 상태')
    st.caption(f'장기재고 기준 {threshold}일 · 미완료 품목 기준')
    missing=int(inv['age_days'].isna().sum())
    normal=len(inv)-len(long_term)-missing
    if inv.empty:
        st.info('현재 재고가 없습니다.')
    else:
        fig=go.Figure(go.Pie(labels=['정상 재고','장기재고','입고일 미등록'],values=[normal,len(long_term),missing],hole=.72,marker_colors=[COLORS[0],COLORS[3],COLORS[4]],sort=False,textinfo='none',hovertemplate='%{label}: %{value:,}건 (%{percent})<extra></extra>'))
        fig.add_annotation(text=f'<b>{len(inv):,}</b><br>재고 품목',x=.5,y=.5,showarrow=False,font=dict(size=22,color='#203650'))
        chart(fig)
    if missing: st.caption(f'입고일 미등록 {missing:,}건은 재고에 포함되며 장기재고 판정에서 제외됩니다.')

with st.container(border=True, key='team_panel'):
    st.markdown('### 담당팀별 재고 현황')
    st.caption('팀별 재고수량과 장기재고수량 비교 · 단위: 대')
    if inv.empty:
        st.info('현재 재고가 없습니다.')
    else:
        inv['담당팀 표시']=inv['담당팀'].fillna('미지정')
        inv['재고 상태']=inv.apply(lambda r: '입고일 미등록' if pd.isna(r['age_days']) else ('장기재고' if r['is_long_term'] else '정상 재고'),axis=1)
        teams=inv.groupby(['담당팀 표시','재고 상태'],as_index=False)['수량'].sum()
        fig=px.bar(teams,x='수량',y='담당팀 표시',color='재고 상태',orientation='h',color_discrete_map={'정상 재고':COLORS[0],'장기재고':COLORS[3],'입고일 미등록':COLORS[4]},labels={'담당팀 표시':'','수량':'재고수량 (대)'})
        chart(fig,max(210,inv['담당팀 표시'].nunique()*38+80))

left,right=st.columns([1.35,1])
with left,st.container(border=True,key='trend_panel'):
    st.markdown('### 월별 입고 · 재작업 완료')
    st.caption('최근 12개월 · 상단 숫자: 위 입고 / 아래 완료 (대)')
    months=pd.period_range(this_month-11,this_month,freq='M')
    inbound=df.groupby('입고월')['입고수량'].sum().reindex(months,fill_value=0)
    done=df.groupby('완료월')['완료수량'].sum().reindex(months,fill_value=0)
    fig=go.Figure()
    fig.add_trace(go.Bar(name='입고수량',x=months.astype(str),y=inbound,marker_color='#b5dce9'))
    fig.add_trace(go.Scatter(name='완료수량',x=months.astype(str),y=done,mode='lines+markers',line=dict(color='#168fa1',width=3)))
    chart(fig)
with right,st.container(border=True,key='site_panel'):
    st.markdown('### SITE별 재고 상위 10곳')
    st.caption('현재 재고수량 기준 · 단위: 대')
    if inv.empty: st.info('현재 재고가 없습니다.')
    else:
        site=inv.groupby(inv['site'].fillna('미지정'))['수량'].sum().nlargest(10).sort_values()
        chart(go.Figure(go.Bar(x=site.values,y=site.index,orientation='h',marker_color='#729bc0',hovertemplate='%{y}: %{x:,}대<extra></extra>')))

with st.container(border=True, key='completion_result_panel'):
    st.markdown('### 처리 결과별 완료수량')
    st.caption('선택한 분류의 전체 누적 완료 내역 · 구분별 완료수량 합계 · 단위: 대')
    completed = df[df['status'] == '완료'].copy()
    if not completed.empty:
        results = completed['구분'].fillna('').astype(str).str.strip().replace('', '미지정')
        types=completed.groupby(results)['완료수량'].sum().sort_values(ascending=False)
        fig=go.Figure(go.Bar(
            x=types.values, y=types.index, orientation='h', marker_color=COLORS[0],
            hovertemplate='%{y}: %{x:,.0f}대<extra></extra>',
        ))
        fig.update_yaxes(autorange='reversed', automargin=True)
        fig.update_xaxes(title_text='완료수량 (대)', rangemode='tozero',
                         range=[0, max(float(types.max()) * 1.15, 1)])
        chart(fig, max(240, len(types) * 45 + 90))
    else: st.caption('완료된 내역이 없습니다.')

with st.container(border=True,key='detail_panel'):
    st.markdown('### 장기재고 상세')
    st.caption('오래된 입고 순 · 입고일 수정 및 완료 처리는 재고현황에서 진행하세요.')
    if long_term.empty: st.success('설정된 기준에 해당하는 장기재고가 없습니다.')
    else:
        detail=long_term.sort_values('age_days',ascending=False)[['입고일','모델명','site','담당자','담당팀','입고수량','age_days','구분']].rename(columns={'site':'SITE','age_days':'경과일'})
        st.dataframe(detail,hide_index=True,use_container_width=True,column_config={'경과일':st.column_config.NumberColumn(format='%d일')})
conn.close()
