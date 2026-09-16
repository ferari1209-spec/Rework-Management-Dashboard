"""로그인, 회원가입, 승인."""

from __future__ import annotations

import sqlite3

import bcrypt
import streamlit as st

from app.db import get_connection
from app.services import login_sessions
from app.browser_login import browser_token, queue_cookie, saved_email
from app.services.account_service import normalize_email, email_available, reset_password

BOOTSTRAP_LOGIN_ID = "admin"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def ensure_bootstrap_admin(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
    if row["n"] > 0:
        return
    st.subheader("첫 관리자 계정 설정")
    st.caption("최초 한 번만 설정합니다. 이후 가입자는 관리자 승인을 받아야 합니다.")
    with st.form("bootstrap"):
        name = st.text_input("관리자 이름")
        login = st.text_input("관리자 이메일", placeholder="name@company.com")
        password = st.text_input("관리자 비밀번호 (8자 이상)", type="password")
        confirm = st.text_input("비밀번호 확인", type="password")
        if st.form_submit_button("관리자 계정 만들기", type="primary"):
            try:
                login=normalize_email(login)
            except ValueError as exc:
                st.error(str(exc))
                st.stop()
            if not name.strip() or not login.strip() or len(password) < 8 or len(password.encode()) > 72 or password != confirm:
                st.error("이름·아이디와 8자 이상 비밀번호(UTF-8 72바이트 이하), 비밀번호 확인을 입력하세요.")
            else:
                with conn:
                    conn.execute("BEGIN IMMEDIATE")
                    if not conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                        conn.execute("INSERT INTO users(name,login_id,email,password_hash,role,approved,can_upload) VALUES(?,?,?,?,'관리자',1,1)", (name.strip(), login, login, hash_password(password)))
                st.rerun()
    st.stop()


def register_user(conn: sqlite3.Connection, payload: dict) -> tuple[bool, str]:
    try:
        email=normalize_email(payload.get('email',payload.get('login_id')))
    except ValueError as exc:
        return False,str(exc)
    payload={**payload,'login_id':email}
    if not all(str(payload.get(k, "")).strip() for k in ("company", "name", "team", "position", "login_id")):
        return False, "회사명, 이름, 팀, 직책, 아이디를 모두 입력하세요."
    if len(payload.get("password", "")) < 8 or len(payload["password"].encode()) > 72:
        return False, "비밀번호는 8자 이상, UTF-8 72바이트 이하여야 합니다."
    if not email_available(conn,email):
        return False, "이미 사용 중인 이메일입니다."
    conn.execute(
        """
        INSERT INTO users (company, name, team, position, login_id, email, password_hash, role, approved, can_upload)
        VALUES (?, ?, ?, ?, ?, ?, ?, '일반', 0, 0)
        """,
        (
            payload.get("company"),
            payload["name"],
            payload.get("team"),
            payload.get("position"),
            payload["login_id"],
            email,
            hash_password(payload["password"]),
        ),
    )
    conn.commit()
    return True, "가입이 접수되었습니다. 관리자 승인 후 이용할 수 있습니다."


def authenticate(conn: sqlite3.Connection, login_id: str, password: str) -> tuple[dict | None, str]:
    try:
        email=normalize_email(login_id)
    except ValueError as exc:
        return None,str(exc)
    row = conn.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    if row is None:
        return None, "아이디 또는 비밀번호가 올바르지 않습니다."
    if not verify_password(password, row["password_hash"]):
        return None, "아이디 또는 비밀번호가 올바르지 않습니다."
    if not row["approved"]:
        return None, "승인된 계정만 이용 가능합니다. 관리자 승인을 기다려 주세요."
    return dict(row), ""


def current_user() -> dict | None:
    user = st.session_state.get("user")
    token = st.session_state.get('_login_token') or (None if st.session_state.get('_logged_out') else browser_token())
    conn = get_connection()
    try:
        if token:
            restored = login_sessions.resolve(conn, token)
            if restored:
                st.session_state['user'] = restored
                st.session_state['_login_token'] = token
                return restored
            st.session_state.pop('user',None)
            st.session_state.pop('_login_token',None)
            return None
        if not user:
            return None
        row = conn.execute("SELECT * FROM users WHERE id=? AND approved=1", (user["id"],)).fetchone()
        if row is None:
            st.session_state.pop("user", None)
            return None
        return dict(row)
    finally:
        conn.close()


def logout():
    remembered=saved_email()
    token=st.session_state.get('_login_token') or browser_token()
    if token:
        conn=get_connection()
        try:
            login_sessions.revoke(conn,token)
        finally:
            conn.close()
    st.session_state.clear()
    st.session_state['_saved_email']=remembered
    st.session_state['_logged_out']=True
    queue_cookie()
    st.rerun()


def is_admin() -> bool:
    user = current_user()
    return bool(user and user.get("role") == "관리자")


def can_edit() -> bool:
    return has_permission('inventory','edit')


def can_upload() -> bool:
    return has_permission('upload','edit')


def has_permission(menu, action='view'):
    from app.services.permissions import allowed
    return allowed(current_user(), menu, action)


def require_menu(menu):
    require_login()
    if not has_permission(menu):
        st.error('이 메뉴의 조회 권한이 없습니다.')
        st.stop()


def require_login() -> dict | None:
    user = current_user()
    if user:
        return user
    st.warning("로그인이 필요합니다. 홈 화면에서 로그인하세요.")
    st.stop()


def render_auth_screen(conn: sqlite3.Connection) -> None:
    st.markdown("### 로그인")
    st.caption("승인된 계정만 이용 가능합니다.")
    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
    with tab_login:
        with st.form('login_form', enter_to_submit=True, border=False):
            login_id = st.text_input("아이디 (이메일)", value=saved_email(), placeholder="name@company.com", key="login_id")
            password = st.text_input("비밀번호", type="password", key="login_pw")
            remember=st.checkbox('아이디 저장',value=bool(saved_email()),help='이 브라우저에 이메일만 30일간 저장합니다. 비밀번호는 저장하지 않습니다.')
            with st.container(horizontal=True, gap='small'):
                submitted=st.form_submit_button("로그인", type="primary")
                find_password=st.form_submit_button('비밀번호 찾기', type='primary')
        if submitted:
            user, message = authenticate(conn, login_id.strip(), password)
            if user:
                st.session_state["user"] = user
                token=login_sessions.issue(conn,user['id'])
                st.session_state['_login_token']=token
                st.session_state.pop('_logged_out',None)
                queue_cookie(token,remember_email=user['email'] if remember else '')
                st.rerun()
            else:
                st.error(message)
    with tab_signup:
        company = st.text_input("회사명", placeholder="예: 에이텍컴퓨터")
        name = st.text_input("이름", placeholder="예: 홍길동")
        team = st.text_input("팀", placeholder="예: 생산관리팀")
        position = st.text_input("직책", placeholder="예: 책임")
        new_id = st.text_input("E-mail (로그인 아이디)", placeholder="name@company.com", key="signup_id")
        st.caption('아이디는 이메일 형식(name@company.com)으로 입력해야 가입할 수 있습니다.')
        new_pw = st.text_input("비밀번호", type="password", key="signup_pw", placeholder="8자 이상 입력")
        confirm_pw = st.text_input('비밀번호 확인', type='password', key='signup_pw_confirm', placeholder='비밀번호 재입력')
        if st.button("가입 신청", type="primary"):
            if new_pw != confirm_pw:
                st.error('비밀번호 확인이 일치하지 않습니다.')
            elif not name.strip() or not new_id.strip() or not new_pw:
                st.error("이름, 아이디, 비밀번호는 필수입니다.")
            else:
                ok, message = register_user(
                    conn,
                    {
                        "company": company.strip(),
                        "name": name.strip(),
                        "team": team.strip(),
                        "position": position.strip(),
                        "login_id": new_id.strip(),
                        "password": new_pw,
                    },
                )
                if ok:
                    st.success(message)
                else:
                    st.error(message)
    @st.dialog('비밀번호 찾기')
    def show_password_reset():
        st.info('관리자가 본인 확인 후 재설정 코드를 발급하므로 시간이 소요될 수 있습니다. 관리자에게 문의해 주세요.')
        st.caption('비밀번호는 복구 대신 새로 설정합니다. 관리자에게 본인 확인 후 재설정 코드를 받아 입력하세요. 코드는 30분 동안 한 번만 사용할 수 있습니다.')
        with st.form('reset_password'):
            email=st.text_input('등록 이메일',placeholder='name@company.com')
            code=st.text_input('관리자가 발급한 재설정 코드')
            new_password=st.text_input('새 비밀번호',type='password')
            repeated=st.text_input('새 비밀번호 확인',type='password')
            if st.form_submit_button('비밀번호 재설정'):
                if new_password!=repeated:
                    st.error('새 비밀번호 확인이 일치하지 않습니다.')
                else:
                    try:
                        reset_password(conn,email,code,new_password)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.success('비밀번호를 변경했습니다. 새 비밀번호로 로그인하세요.')
    if find_password:
        show_password_reset()
