"""Claude 호출 래퍼 (외부용 자립형).

내부 core.api_client 에 의존하지 않고 Anthropic SDK 를 직접 호출한다.
비용 통제: 기본 모델은 Haiku. ANTHROPIC_API_KEY 가 없으면 안내 문자열을 반환한다.
"""
import os
from pathlib import Path

import anthropic
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except Exception:
    pass

# 비용 통제 — 외부 무료 범위는 Haiku 로 충분
MODEL = os.getenv("PHARMA_WATCH_MODEL", "claude-haiku-4-5-20251001")


@st.cache_resource
def get_client() -> "anthropic.Anthropic":
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def call_claude(system: str, messages: list, max_tokens: int = 900) -> str:
    """system + messages 로 단일 호출. 실패해도 문자열을 보장한다."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "ANTHROPIC_API_KEY 가 설정되지 않았습니다. .env 에 키를 추가하면 분석이 활성화됩니다."
    try:
        resp = get_client().messages.create(
            model=MODEL,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
        text = "".join(
            getattr(b, "text", "") for b in resp.content
            if getattr(b, "type", "") == "text"
        ).strip()
        return text or "(빈 응답)"
    except Exception as e:  # noqa: BLE001
        return f"분석 호출 중 오류가 발생했습니다: {type(e).__name__}: {e}"
