"""Regulatory QA Analyst — VETO 없는 외부용 분석가.

규제/뉴스 항목의 QA 영향도와 Action Item 만 정리한다.
내부 9에이전트·거부권·의사결정·원가/전략 로직은 일절 없음 (원칙 4).

분석 결과는 자동으로 기록 저장되고(저장소: data_layer.qa_history),
하단 '저장된 분석 기록'에서 다시 보거나 개별/전체 삭제할 수 있다.
"""
from pathlib import Path

import streamlit as st

import branding
from data_layer import qa_history

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
        else:
            try:
                from utils.claude_client import call_claude

                with st.spinner("QA 영향도 분석 중..."):
                    out = call_claude(
                        system=_load_prompt(),
                        messages=[{"role": "user", "content": text.strip()}],
                        max_tokens=900,
                        feature="qa_analyst",
                    )
                # 분석 실행 행동 기록 (토큰은 call_claude 내부에서 별도 기록)
                try:
                    from data_layer import usage as _usage
                    from ui.auth import current_user as _cur
                    _usage.log_action(_cur(), "qa_analyst", "영향도분석", text.strip()[:80])
                except Exception:
                    pass
                # 결과를 세션에 보관(삭제 등 rerun 후에도 유지) + 기록 자동 저장
                st.session_state["qa_last_q"] = text.strip()
                st.session_state["qa_last_a"] = out
                try:
                    qa_history.save(text.strip(), out)
                    st.session_state["qa_saved_notice"] = True
                except Exception as e:  # noqa: BLE001
                    st.session_state["qa_saved_notice"] = False
                    st.session_state["qa_save_err"] = f"{type(e).__name__}: {e}"
            except Exception as e:  # noqa: BLE001
                st.error("분석 호출에 실패했습니다. .env 의 ANTHROPIC_API_KEY 설정을 확인하세요.")
                st.caption(f"detail: {type(e).__name__}: {e}")

    # ── 최근 분석 결과 (rerun 후에도 유지) ──
    last_a = st.session_state.get("qa_last_a")
    if last_a:
        st.markdown("---")
        st.markdown("#### 분석 결과")
        if st.session_state.pop("qa_saved_notice", False):
            st.success("✅ 기록에 저장되었습니다. 아래 '저장된 분석 기록'에서 다시 볼 수 있어요.")
        elif st.session_state.get("qa_save_err"):
            st.warning(f"기록 저장 실패: {st.session_state.pop('qa_save_err')}")
        st.markdown(last_a)

    # ── 저장된 분석 기록 (목록 + 삭제) ──
    _render_history()

    st.markdown("---")
    st.caption("🔒 대화형 연속 질의 · SOP 자동비교 · CAPA 자동작성은 상위 플랜 기능입니다.")
    st.caption(branding.FOOTER_NOTE)


def _render_history():
    st.markdown("---")
    try:
        total = qa_history.count()
        records = qa_history.list_records(limit=200) if total else []
    except Exception as e:  # noqa: BLE001
        st.warning(f"기록을 불러오지 못했습니다: {type(e).__name__}: {e}")
        return

    col_t, col_clear = st.columns([4, 1])
    with col_t:
        st.markdown(f"#### 📁 저장된 분석 기록 ({total}건)")
    with col_clear:
        if total:
            if st.session_state.get("qa_confirm_clear"):
                if st.button("⚠️ 전체삭제 확정", type="primary",
                             use_container_width=True, key="qa_clear_yes"):
                    qa_history.clear_all()
                    st.session_state.pop("qa_confirm_clear", None)
                    st.session_state.pop("qa_last_a", None)
                    st.session_state.pop("qa_last_q", None)
                    st.rerun()
            else:
                if st.button("🗑 전체 삭제", use_container_width=True, key="qa_clear_ask"):
                    st.session_state["qa_confirm_clear"] = True
                    st.rerun()

    if st.session_state.get("qa_confirm_clear"):
        st.warning("전체 기록을 삭제합니다. 되돌릴 수 없어요. 오른쪽 '전체삭제 확정'을 누르세요.")
        if st.button("취소", key="qa_clear_cancel"):
            st.session_state.pop("qa_confirm_clear", None)
            st.rerun()

    if not records:
        st.caption("아직 저장된 기록이 없습니다. 위에서 분석하면 자동으로 저장됩니다.")
        return

    for rec in records:
        q_head = rec.question if len(rec.question) <= 50 else rec.question[:50] + "…"
        with st.expander(f"🕑 {rec.created_at} · {q_head}"):
            st.markdown("**질문 / 입력**")
            st.code(rec.question, language=None)
            st.markdown("**분석 결과**")
            st.markdown(rec.answer)
            if st.button("🗑 이 기록 삭제", key=f"qa_del_{rec.id}"):
                qa_history.delete(rec.id)
                st.rerun()
