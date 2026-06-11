"""법령 어시스턴트 (RAG) — KGSP/GDP 규정 질의응답.

corpus 의 규정 문서를 검색(BM25)해 근거를 찾고, Claude(Haiku)가 그 근거에만
기반해 인용과 함께 답한다. 무거운 임베딩 모델 없이 2GB 서버에서 동작한다.

- 답변은 근거 자료에 한정되며 출처 [번호]를 표기한다.
- 실무 적용 전 원문·QA/법무 검토 필요(분석·참고용, 의사결정 아님).
"""
import streamlit as st

import branding

try:
    from ui.auth import current_user
except Exception:  # noqa: BLE001
    def current_user():  # type: ignore
        return "(local)"


@st.cache_resource(show_spinner=False)
def _load_retriever():
    """검색기(색인 포함)를 1회만 생성. corpus/index 변경 시 캐시 비우면 갱신."""
    from data_layer.rag.retriever import get_retriever
    return get_retriever()


def _refresh_retriever():
    _load_retriever.clear()
    return _load_retriever()


def render():
    st.markdown(f"### 📚 법령 어시스턴트")
    st.caption(
        "KGSP·콜드체인·GDP 규정 문서를 검색해 **근거와 함께** 답합니다. "
        "(자료 기반 참고용 — 의사결정/거부권 없음, 적용 전 QA·법무 검토 필요)"
    )

    # 계정이 바뀌면 대화 기록 초기화
    uid = current_user()
    if st.session_state.get("rag_owner") != uid:
        st.session_state["rag_history"] = []
        st.session_state["rag_owner"] = uid

    try:
        retriever = _load_retriever()
    except Exception as e:  # noqa: BLE001
        st.error("규정 색인을 불러오지 못했습니다.")
        st.caption(f"detail: {type(e).__name__}: {e}")
        return

    # 색인 현황 + 갱신 버튼
    c1, c2 = st.columns([4, 1])
    with c1:
        if retriever.size:
            st.caption(f"📖 색인: 문서 {retriever.doc_count}건 · 청크 {retriever.size}개")
        else:
            st.warning(
                "색인된 규정 문서가 없습니다. `data_layer/rag/corpus/` 에 .md/.txt/.pdf 를 "
                "넣고 `python -m data_layer.rag.ingest` 실행 후 오른쪽 '색인 갱신'을 누르세요."
            )
    with c2:
        if st.button("🔄 색인 갱신", use_container_width=True, key="rag_refresh"):
            retriever = _refresh_retriever()
            st.rerun()

    # 예시 질문
    with st.expander("💡 예시 질문"):
        st.markdown(
            "- 온도 일탈이 발생하면 위탁자에게 언제까지 통보해야 하나요?\n"
            "- KGSP에서 출하증명서에 기재해야 하는 항목은?\n"
            "- 생물학적제제 수송 시 자동온도기록장치 기록은 몇 년 보관하나요?\n"
            "- WHO 기준에서 온도 매핑은 얼마나 자주 하나요?"
        )

    # ── 이전 대화 표시 ──
    history = st.session_state.setdefault("rag_history", [])
    for turn in history:
        with st.chat_message("user"):
            st.markdown(turn["q"])
        with st.chat_message("assistant"):
            st.markdown(turn["a"])
            _render_sources(turn.get("sources", []))

    # ── 입력 ──
    q = st.chat_input("규정에 대해 질문하세요 (예: 온도 일탈 통보 기한은?)")
    if q:
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("규정 검색 + 답변 생성 중..."):
                try:
                    from engines.rag_engine import answer as rag_answer
                    res = rag_answer(q, retriever, k=5, feature="rag_assistant")
                except Exception as e:  # noqa: BLE001
                    st.error("답변 생성에 실패했습니다. .env 의 ANTHROPIC_API_KEY 를 확인하세요.")
                    st.caption(f"detail: {type(e).__name__}: {e}")
                    return
            st.markdown(res.answer)
            sources = [
                {
                    "n": i + 1,
                    "title": h.chunk.title,
                    "section": h.chunk.section,
                    "doc": h.chunk.doc,
                    "text": h.chunk.text,
                    "score": h.score,
                }
                for i, h in enumerate(res.hits)
            ]
            _render_sources(sources)

        history.append({"q": q, "a": res.answer, "sources": sources})

        # 행동 기록 (토큰은 call_claude 내부에서 별도 기록)
        try:
            from data_layer import usage as _usage
            _usage.log_action(uid, "rag_assistant", "법령질의", q[:80])
        except Exception:
            pass

    st.markdown("---")
    st.caption(
        "⚠️ 답변은 색인된 자료 기반의 참고용입니다. 규정 위반 판단·고객 제출 전 "
        "원문과 담당자(QA·법무) 확인이 필요합니다."
    )
    st.caption(branding.FOOTER_NOTE)


def _render_sources(sources: list) -> None:
    if not sources:
        return
    with st.expander(f"🔎 근거 {len(sources)}건 보기"):
        for s in sources:
            st.markdown(f"**[{s['n']}] {s['title']} — {s['section']}**  ·  `{s['doc']}`")
            body = s["text"]
            st.caption(body if len(body) <= 600 else body[:600] + " …")
