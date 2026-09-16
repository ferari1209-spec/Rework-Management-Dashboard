"""공통 UI: 헤더, 카테고리 탭, 팔레트."""

from __future__ import annotations

from pathlib import Path
from html import escape
from datetime import date
import base64
from functools import lru_cache

import streamlit as st

from app.auth import can_edit, current_user, is_admin, logout

PALETTE = {
    "page": "#F7F9FB",
    "card": "#FFFFFF",
    "info_bg": "#EAF3FB",
    "info_fg": "#0C447C",
    "warn_bg": "#FAEEDA",
    "warn_fg": "#633806",
    "ok_bg": "#E1F5EE",
    "ok_fg": "#085041",
    "alert_bg": "#FCEBEB",
    "alert_fg": "#791F1F",
}

@lru_cache(maxsize=4)
def image_uri(name: str) -> str:
    path = Path(__file__).resolve().parent.parent / name
    return 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def logo_html() -> str:
    return f'<img class="atec-logo" src="{image_uri("에이텍컴퓨터 로고.png")}" alt="ATEC 에이텍컴퓨터">'


def inject_css() -> None:
    st.markdown('<style>' + Path(__file__).with_name('dashboard.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)
    st.markdown('<style>.stApp:has(.st-key-auth_card)::before {background-image:url("' + image_uri('배경이미지_글씨만.png') + '");}</style>', unsafe_allow_html=True)

def render_header() -> None:
    user = current_user()
    identity = escape(f"{user.get('name')} · {user.get('role')}") if user else '재작업 통합 관리'
    with st.container(key="rework_header"):
        st.markdown(f'<div class="rework-banner"><div class="rework-heading"><div class="rework-brand">{logo_html()}</div><div class="rework-title"><span>재작업 통합 관리 대시보드</span><span class="rework-title-en">(Integrated Rework Management Dashboard)</span></div><div class="rework-subtitle">완제품 · 대여 재작업의 입고부터 완료까지</div></div><div class="rework-slogan"><div class="slogan-technology">Technology</div><div class="slogan-intro">ATEC의 기술은</div><div class="slogan-message">새로운 <strong>정보통신 문화</strong>를 <strong>창조</strong>합니다.</div></div><div class="rework-meta">기준일 {date.today():%Y.%m.%d}<br>{identity}</div></div>', unsafe_allow_html=True)
        if user:
            if st.button("로그아웃", key="logout", width=150, icon=":material/logout:"):
                logout()


def category_selector() -> str:
    if "category" not in st.session_state:
        st.session_state["category"] = "완제품"
    choice = st.segmented_control(
        "카테고리",
        ["완제품", "대여"],
        default=st.session_state["category"],
        format_func=lambda x: "완제품재작업" if x == "완제품" else "대여재작업",
    )
    st.session_state["category"] = choice or st.session_state["category"]
    return st.session_state["category"]


def kpi_card(label: str, value, kind: str = "info", note: str = "") -> None:
    klass = {"info": "", "warn": "warn", "ok": "ok", "alert": "alert"}.get(kind, "")
    st.markdown(
        f'<div class="kpi-card {klass}"><div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{escape(str(value))}</div><div class="kpi-note">{escape(note)}</div></div>',
        unsafe_allow_html=True,
    )


def guard_admin() -> None:
    if not is_admin():
        st.error("관리자만 접근할 수 있는 화면입니다.")
        st.stop()


def guard_edit() -> bool:
    return can_edit()
