"""Pharma Watch — 외부 제공용 의약품 규제 인텔리전스 앱 (entry point + router).

3PL Command Center 의 외부 배포 버전(화이트리스트 빌드).
원가·수익성·전략·제안서·회의실·Deal Intelligence 등 내부 IP 는
이 앱에 코드/데이터/import 자체가 존재하지 않는다.

저작권 및 일체의 지식재산권은 소유자에 귀속되며, 사용권만 제공된다.
"""
import importlib
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except Exception:
    pass

import streamlit as st

import branding

st.set_page_config(
    page_title=branding.APP_NAME,
    page_icon=branding.PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# 공통 스타일 (있으면 적용 — 없어도 앱은 동작)
try:
    from ui.theme import inject_global_css, inject_dark_theme, inject_sidebar_toggle
    inject_global_css()
    inject_dark_theme()
    inject_sidebar_toggle()
except Exception:
    pass

# 외부 배포용 로그인 게이트 — ENABLE_AUTH=1 일 때만 동작 (로컬은 기본 통과).
# import 만 보호하고 호출은 보호하지 않는다 (st.stop() 이 정상 전파되도록).
_require_login = None
try:
    from ui.auth import require_login as _require_login
except Exception:
    _require_login = None
if _require_login:
    _require_login()


# 외부 공개 메뉴 — KEEP 만. 내부 메뉴(원가/전략/제안서/회의실)는 존재하지 않음.
PAGES = {
    "home":       ["홈",            "pages.home"],
    "pharmacal":  ["규제 캘린더",   "pages.pharmacal"],
    "newsroom":   ["뉴스 모니터링", "pages.newsroom"],
    "regulatory": ["규제 검색",     "pages.regulatory"],
    "qa_analyst": ["QA 분석가",     "pages.qa_analyst"],
}

# 상위(유료) 기능 — 화면엔 보이되 잠금. (원칙 5·6)
LOCKED = ["SOP 자동비교", "CAPA 자동작성", "대화형 QA 질의"]


if "page" not in st.session_state:
    st.session_state.page = "home"


def _go(key: str) -> None:
    """페이지 이동 + 뒤로가기용 히스토리 기록."""
    cur = st.session_state.get("page")
    if cur and cur != key:
        st.session_state.setdefault("nav_history", []).append(cur)
    st.session_state.page = key
    st.rerun()


def _nav_button(key: str, label: str) -> None:
    is_current = st.session_state.get("page") == key
    btn_type = "primary" if is_current else "secondary"
    if st.button(label, use_container_width=True, type=btn_type, key="nav_" + key):
        _go(key)


with st.sidebar:
    st.markdown(f"### {branding.LOGO_EMOJI} {branding.APP_NAME}")
    st.caption(branding.ORG_NAME)
    st.markdown("---")

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        if st.button("🏠 홈", use_container_width=True, key="nav_home_btn"):
            _go("home")
    with bcol2:
        _hist = st.session_state.get("nav_history", [])
        if st.button("← 뒤로", use_container_width=True, key="nav_back_btn", disabled=not _hist):
            if _hist:
                st.session_state.page = _hist.pop()
                st.rerun()

    st.caption("메뉴")
    for k, info in PAGES.items():
        _nav_button(k, info[0])

    st.markdown("---")
    st.caption("프리미엄 🔒")
    for name in LOCKED:
        st.button(f"🔒 {name}", use_container_width=True, disabled=True, key="locked_" + name)
    st.caption("상위 플랜에서 잠금 해제")

    st.markdown("---")
    try:
        from ui.theme import render_theme_picker
        render_theme_picker()
    except Exception:
        pass

    try:
        from ui.auth import logout_button
        logout_button()
    except Exception:
        pass

    st.caption(branding.ORG_LABEL)
    st.caption(branding.FOOTER_NOTE)


page = st.session_state.get("page", "home")
info = PAGES.get(page, PAGES["home"])
mod = importlib.import_module(info[1])
mod.render()
