import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from datetime import date
from html import escape
import streamlit as st
from app.auth import require_login, require_menu
from app.db import get_connection,ensure_schema
from app.ui import inject_css,render_header,category_selector
from app.services.analysis_service import analyze
from app.table_ui import selected_download
from app.ai_ui import personal_ai_settings, render_explanation
from app.services.local_explanation import explain_locally

st.set_page_config(page_title='AI 분석',layout='wide')
inject_css();user=require_login();require_menu('analysis')
conn=get_connection();ensure_schema(conn);render_header()
st.subheader(':material/analytics: AI 분석')
st.caption('기본 통계·이상탐지는 외부 전송 없이 계산합니다. 개인 API 키를 연결하면 AI 해설을 추가로 이용할 수 있습니다.')
personal_ai_settings(user['id'])
category=category_selector()
with st.container(horizontal=True):
    start=st.date_input('분석 시작일',date.today().replace(day=1),width=220)
    end=st.date_input('분석 종료일',date.today(),width=220)
if st.button('분석 실행',type='primary',icon=':material/analytics:'):
    st.session_state['analysis_requested'] = True
    st.session_state.pop('personal_ai_answer', None)
if st.session_state.get('analysis_requested'):
    try:
        result=analyze(conn,user['id'],category,start,end)
    except (ValueError,PermissionError) as exc:
        st.error(str(exc))
    else:
        if result is None:
            st.info('분석할 데이터가 없습니다.')
        else:
            st.caption(f'{category} · 완료/입고 분석 {start} ~ {end} · 재고/품질/반복 기록은 현재 전체 데이터 기준({result["as_of"]})')
            a,b,c=st.columns(3)
            cards = [
                (a,'done','task_alt','기간 내 완료',f'{result["completed"]:,}','건','선택한 분석 기간의 완료 항목'),
                (b,'hours','schedule','기간 내 공수',f'{result["hours"]:,.2f}','시간','완료 항목의 공수 합계 · 공수 미등록 제외'),
                (c,'cost','fact_check','공수 확인 대상',f'{len(result["anomalies"]):,}','건','동일 모델·구분 비교 · 공수 이상 후보'),
            ]
            for column, kind, icon, label, value, unit, note in cards:
                with column, st.container(key=f'cost_summary_{kind}'):
                    st.markdown(f'#### :material/{icon}: {label}')
                    st.markdown(f'<div class="cost-summary-value">{escape(value)}<span>{escape(unit)}</span></div>',unsafe_allow_html=True)
                    st.caption(note)
            st.write(f'선택 기간에 입고 {result["inbound"]:,}건, 완료 {result["completed"]:,}건입니다. 완료 항목 중 공수 미등록 {result["missing_hours"]:,}건은 공수 합계에서 제외했습니다.')
            with st.container(border=True):
                st.subheader(':material/description: 규칙 기반 자동 해설')
                st.caption('규칙 기반 자동 해설입니다. API 키·외부 전송·추가 비용 없이 현재 분석 결과로 작성합니다.')
                for title, explanation in explain_locally(result):
                    st.markdown(f'**{title}**')
                    st.write(explanation)
            tabs=st.tabs(['재고 우선 확인','데이터 품질','공수 이상 후보','시리얼 반복 기록'])
            sections=[('inventory','경과일이 긴 재고부터 표시합니다. 우선 확인 순서이며 완료 가능일 예측은 아닙니다.'),('quality','항목 하나에 여러 확인사항이 있으면 여러 줄로 표시됩니다.'),('anomalies',f'동일 모델·구분, 완료수량이 있는 5건 이상을 대당공수로 비교합니다. IQR 1.5배 범위 밖을 표시하며 오류로 단정하지 않습니다. 비교 자료 부족 {result["insufficient"]:,}건.'),('repeated','같은 시리얼의 반복 기록입니다. 실제 반복 재작업인지 중복 입력인지는 원문을 확인하세요.')]
            for tab,(key,note) in zip(tabs,sections):
                with tab:
                    st.caption(note)
                    frame=result[key]
                    fields=['id','모델명','site','serial','담당팀','입고일','재작업일','입고수량','완료수량','투입공수','age_days','확인사항','대당공수','비교건수','중앙대당공수','하한','상한']
                    detail=frame[[c for c in fields if c in frame]].copy()
                    st.dataframe(detail,hide_index=True,use_container_width=True)
                    # 분석 결과의 다운로드도 메뉴 및 원본 메뉴 권한을 따른다.
                    from app.auth import has_permission
                    if all(has_permission(m,'download') for m in ('inventory','history','cost')):
                        selected_download(detail,f'{category}_분석_{key}',menu='analysis')
            render_explanation(result,start,end)
conn.close()
