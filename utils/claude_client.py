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


def _log_usage(resp, feature: str = "") -> None:
    """응답의 토큰 사용량을 현재 로그인 계정 기준으로 기록. 실패는 무시(앱 흐름 보호)."""
    try:
        usage = getattr(resp, "usage", None)
        in_tok = int(getattr(usage, "input_tokens", 0) or 0)
        out_tok = int(getattr(usage, "output_tokens", 0) or 0)
        account = st.session_state.get("pw_auth") or "(local)"
        feat = feature or st.session_state.get("page") or "qa_analyst"
        from data_layer import usage as usage_repo
        usage_repo.log_claude(account, feat, MODEL, in_tok, out_tok)
    except Exception:
        pass


def call_claude(system: str, messages: list, max_tokens: int = 900,
                feature: str = "") -> str:
    """system + messages 로 단일 호출. 실패해도 문자열을 보장한다.

    feature: 사용량 집계용 기능 이름(미지정 시 현재 페이지로 추정).
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "ANTHROPIC_API_KEY 가 설정되지 않았습니다. .env 에 키를 추가하면 분석이 활성화됩니다."
    try:
        resp = get_client().messages.create(
            model=MODEL,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
        _log_usage(resp, feature)
        text = "".join(
            getattr(b, "text", "") for b in resp.content
            if getattr(b, "type", "") == "text"
        ).strip()
        return text or "(빈 응답)"
    except Exception as e:  # noqa: BLE001
        return f"분석 호출 중 오류가 발생했습니다: {type(e).__name__}: {e}"
