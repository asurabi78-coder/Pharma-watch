"""규제 캘린더 (PharmaCal) — 의약품 규제 인텔리전스 캘린더.

PharmaCal Pro UI(HTML/CSS/JS)를 그대로 임베드한다. UI 는 원본 그대로 100% 보존.
실데이터(법제처/식약처 크롤링) 연동은 후속 단계에서 /api 로 주입 예정.
현재는 정적 샘플 데이터 기반 데모.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# 앱 최상단(app.py 옆)에 둔 원본 HTML
_HTML_PATH = Path(__file__).parent.parent / "pharmacal-pro.html"


def render():
    st.markdown(
        """
        <style>
          section.main > div.block-container {
            padding-top: 1rem; padding-bottom: 0rem;
            padding-left: 1rem; padding-right: 1rem;
            max-width: 100%;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        html = _HTML_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        st.error(
            f"PharmaCal HTML 을 찾을 수 없습니다: {_HTML_PATH}\n"
            "앱 최상단(app.py 옆)에 pharmacal-pro.html 이 있는지 확인하세요."
        )
        return

    components.html(html, height=1180, scrolling=True)
