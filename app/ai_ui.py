import hashlib
import json
import streamlit as st
from app.services.ai_explanation import aggregate_summary, explain, FOCUSES


def reset_personal_ai():
    for key in ('personal_ai_key', 'personal_ai_answer', 'personal_ai_consent'):
        st.session_state.pop(key, None)


def personal_ai_settings(user_id):
    if st.session_state.get('personal_ai_owner') != user_id:
        reset_personal_ai()
        st.session_state['personal_ai_owner'] = user_id
        st.session_state.pop('analysis_requested', None)
    with st.expander('개인 API 키 · AI 기능 확장', expanded=True):
        st.info('개인 OpenAI API 키를 입력하면 통계 결과 해설, 이상 원인 가설, 재고·데이터 품질 개선 제안 등 AI 기능을 더 폭넓게 사용할 수 있습니다. 키 없이도 기본 통계·이상탐지 분석을 이용할 수 있습니다.')
        st.text_input('개인 OpenAI API 키', type='password', key='personal_ai_key',
                      placeholder='본인의 API 키 입력', width=460)
        st.caption('키는 현재 접속 세션에서만 사용하며 DB·파일에 저장하지 않습니다. 로그아웃하거나 키 지우기를 누르면 제거됩니다. 세션이 끊기면 다시 입력해야 합니다.')
        st.button('키 지우기', on_click=reset_personal_ai)
        st.caption('AI 해설 실행 시 집계 수치가 OpenAI로 전송되며 개인 API 계정에 사용 요금이 발생할 수 있습니다. 이름·SITE·시리얼·원본 행은 보내지 않습니다. 응답 저장은 요청하지 않지만 제공사의 데이터 처리 정책이 적용됩니다.')


def render_explanation(result, start, end):
    st.subheader(':material/auto_awesome: AI 확장 분석')
    summary = aggregate_summary(result, start, end)
    focus = st.selectbox('분석 관점', FOCUSES, width=320)
    signature = hashlib.sha256((json.dumps(summary, sort_keys=True) + focus).encode()).hexdigest()
    with st.expander('AI에 전송할 집계 내용 확인'):
        st.json(summary)
    consent = st.checkbox('위 집계 수치를 OpenAI에 전송하여 AI 해설을 받겠습니다.', key='personal_ai_consent')
    key = st.session_state.get('personal_ai_key', '')
    if st.button('AI 해설 실행', type='primary', disabled=not (key.strip() and consent)):
        st.session_state.pop('personal_ai_answer', None)
        with st.spinner('집계 수치를 분석하고 있습니다…'):
            try:
                answer = explain(key, summary, focus)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state['personal_ai_answer'] = (signature, answer)
    saved = st.session_state.get('personal_ai_answer')
    if saved and saved[0] == signature:
        st.caption('AI가 작성한 참고 의견입니다. 원인 가설은 실제 데이터와 담당자 확인이 필요합니다.')
        # Plain text prevents model-generated remote images/links from loading.
        st.text(saved[1])
