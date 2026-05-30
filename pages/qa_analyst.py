"""Regulatory QA Analyst — VETO 없는 외부용 분석가.

규제/뉴스 항목의 QA 영향도와 Action Item 만 정리한다.
내부 9에이전트·거부권·의사결정·원가/전략 로직은 일절 없음 (원칙 4).
"""
from pathlib import Path

import streamlit as st

import branding

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "regulatory_qa_analyst.md"


def _load_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "당신은 의약품 규제 QA 분석가입니다. 입력된 규제/뉴스가 입출고 QA·콜드체인·"
            "GDP 유통에 미치는 영향을 요약하고, 해야 할 일(Action Item)을 목록으로 제시하세요. "
            "의사결정이나 거부권 행사는 하지 않습니다."
        )


def render():
    st.title("🤖 QA 분석가")
    st.caption(
        "규제·고시·뉴스 항목의 QA 영향도와 해야 할 일을 정리합니다. "
        "(분석·요약 전용 — 의사결정/거부권 없음)"
    )

    text = st.text_area(
        "분석할 규제·고시·뉴스 내용을 붙여넣으세요",
        height=160,
        placeholder="예: 의약품 등의 안전에 관한 규칙 개정 — 입출고 시 품질책임자(QA) 입회 요건 신설 ...",
        key="qa_input",
    )

    if st.button("영향도 분석", type="primary", key="qa_run"):
        if not text.strip():
            st.warning("분석할 내용을 입력하세요.")
            return
        try:
            from utils.claude_client import call_claude

            with st.spinner("QA 영향도 분석 중..."):
                out = call_claude(
                    system=_load_prompt(),
                    messages=[{"role": "user", "content": text.strip()}],
                    max_tokens=900,
                )
            st.markdown(out)
        except Exception as e:  # noqa: BLE001
            st.error(
                "분석 호출에 실패했습니다. .env 의 ANTHROPIC_API_KEY 설정을 확인하세요."
            )
            st.caption(f"detail: {type(e).__name__}: {e}")

    st.markdown("---")
    st.caption("🔒 대화형 연속 질의 · SOP 자동비교 · CAPA 자동작성은 상위 플랜 기능입니다.")
    st.caption(branding.FOOTER_NOTE)
