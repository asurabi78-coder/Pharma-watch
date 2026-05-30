"""외부용 홈 — 경량 랜딩. 내부 command-center home 과 무관하게 새로 작성."""
import streamlit as st

import branding


_CARDS = [
    ("📅 규제 캘린더", "법령 시행일·식약처 고시·제출 마감을 달력으로", "pharmacal"),
    ("📰 뉴스 모니터링", "데일리팜·약업신문·물류신문 자동 수집", "newsroom"),
    ("🔍 규제 검색", "KGSP·GDP·GMP 원문 검색", "regulatory"),
    ("🤖 QA 분석가", "규제·뉴스의 QA 영향도 + Action Item 추천", "qa_analyst"),
]


def render():
    st.title(f"{branding.LOGO_EMOJI} {branding.APP_NAME}")
    st.caption(f"{branding.ORG_NAME} · 의약품 규제 인텔리전스")
    st.markdown(
        "의약품 규제·고시·뉴스를 한곳에서 추적하고, QA 영향도와 해야 할 일을 자동으로 정리합니다."
    )
    st.markdown("---")

    cols = st.columns(2)
    for i, (title, desc, key) in enumerate(_CARDS):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(desc)
                if st.button("열기", key="home_open_" + key, use_container_width=True):
                    st.session_state.setdefault("nav_history", []).append("home")
                    st.session_state.page = key
                    st.rerun()

    st.markdown("---")
    st.caption(
        "무료 플랜: 규제 캘린더 · 뉴스 모니터링 · 알림 · Action Item 추천. "
        "🔒 SOP 자동비교 · CAPA 자동작성 · 대화형 QA 질의는 상위 플랜입니다."
    )
    st.caption(branding.FOOTER_NOTE)
