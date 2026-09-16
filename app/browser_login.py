from pathlib import Path
import secrets
from urllib.parse import unquote
import streamlit as st
import streamlit.components.v1 as components

cookie_component = components.declare_component('rework_login_cookie', path=str(Path(__file__).with_name('cookie_component')))


def browser_token():
    token = st.context.cookies.get('rework_login')
    if token:
        return token
    # Some hosted connections do not expose the component's cookies in the
    # initial WebSocket headers. Read the browser before showing login.
    if '_browser_cookie_read' not in st.session_state:
        request_id = st.session_state.setdefault('_cookie_read_request', secrets.token_hex(8))
        result = cookie_component(operation='read', request_id=request_id,
                                  key='login_cookie_read', default=None)
        if not result or result.get('request_id') != request_id:
            st.caption('저장된 로그인 상태를 확인하고 있습니다…')
            st.stop()
        st.session_state['_browser_cookie_read'] = result.get('token', '') if result.get('ok') else ''
        if result.get('ok'):
            st.session_state['_saved_email'] = result.get('remember_email', '')
    return st.session_state['_browser_cookie_read'] or None


def saved_email():
    return st.session_state.get('_saved_email',unquote(st.context.cookies.get('rework_saved_email','')))


def queue_cookie(token=None, remember_email=None):
    st.session_state['_cookie_pending']={'token':token or '', 'operation':'set' if token else 'delete', 'request_id':secrets.token_hex(8), 'remember_email':remember_email}
    if remember_email is not None:
        st.session_state['_saved_email']=remember_email


def flush_cookie():
    pending=st.session_state.get('_cookie_pending')
    if not pending:
        return
    result=cookie_component(**pending,key='login_cookie_'+pending['request_id'],default=None)
    if result and result.get('request_id')==pending['request_id']:
        if not result.get('ok'):
            st.error('로그인 유지 쿠키를 저장할 수 없습니다. 이 사이트의 쿠키를 허용해 주세요.')
            st.stop()
        st.session_state.pop('_cookie_pending',None)
        st.rerun()
    st.caption('로그인 상태를 저장하고 있습니다…')
    st.stop()
