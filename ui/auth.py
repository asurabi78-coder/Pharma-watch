"""간단 로그인 게이트 — 외부 배포(AWS 등)용.

- ENABLE_AUTH 가 켜져 있을 때만 동작. 로컬 개발은 기본 off → 그냥 통과.
- 계정은 환경변수 PHARMA_WATCH_USERS 에 "아이디:비번,아이디2:비번2" 형식으로.
- 비번은 평문(서버 env 보관) 또는 sha256 해시("sha256:<hash>") 지원.
- 멀티테넌트(회사별 데이터 분리)는 추후 단계. 여기선 단순 접근 통제만.
"""
import hashlib
import os

import streamlit as st

import branding


def auth_enabled() -> bool:
    return os.getenv("ENABLE_AUTH", "").strip().lower() in ("1", "true", "yes", "on")


def _load_users() -> dict:
    raw = os.getenv("PHARMA_WATCH_USERS", "").strip()
    users: dict = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        uid, pw = pair.split(":", 1)
        if uid.strip():
            users[uid.strip()] = pw.strip()
    # 미설정 시 데모 계정 (배포 전 반드시 교체)
    if not users:
        users = {"demo": "demo1234"}
    return users


def _check(uid: str, pw: str, users: dict) -> bool:
    stored = users.get(uid)
    if stored is None:
        return False
    if stored.startswith("sha256:"):
        return hashlib.sha256(pw.encode("utf-8")).hexdigest() == stored[7:]
    return pw == stored


def require_login() -> None:
    """ENABLE_AUTH 가 켜져 있고 미인증이면 로그인 화면을 띄우고 실행을 중단한다."""
    if not auth_enabled():
        return
    if st.session_state.get("pw_auth"):
        return

    users = _load_users()
    mid = st.columns([1, 1.4, 1])[1]
    with mid:
        st.markdown(f"### {branding.LOGO_EMOJI} {branding.APP_NAME}")
        st.caption(f"{branding.ORG_NAME} — 로그인이 필요합니다")
        uid = st.text_input("아이디", key="login_id")
        pw = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인", type="primary", use_container_width=True, key="login_btn"):
            if _check(uid.strip(), pw, users):
                st.session_state["pw_auth"] = uid.strip()
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        st.caption(branding.FOOTER_NOTE)
    st.stop()


def logout_button() -> None:
    """인증된 상태에서만 로그아웃 버튼 표시 (사이드바에서 호출)."""
    if auth_enabled() and st.session_state.get("pw_auth"):
        st.caption(f"👤 {st.session_state['pw_auth']}")
        if st.button("🚪 로그아웃", use_container_width=True, key="pw_logout"):
            st.session_state.pop("pw_auth", None)
            st.rerun()
