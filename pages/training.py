"""교육·평가 — KGSP 품질관리교육용 시험지 자동 생성 (워드 다운로드).

문항 수·범위·난이도를 정하면 시험지 + 정답·해설지 + 교육일지(서명란)를
한 개의 워드 파일로 만든다. 매달 반복되는 교육·평가 의무를 보조한다.

Claude 키가 있으면 고품질 문항, 없으면 시드 규제 기반 결정론적 문항.
자동 생성 보조 자료 — 사용 전 QA(관리약사) 검토 필요.
"""
from datetime import datetime

import streamlit as st

import branding
from engines import exam_engine as ee


def _user() -> str:
    try:
        from ui.auth import current_user
        return current_user() or "(local)"
    except Exception:
        return "(local)"


def render():
    st.title("교육·평가")
    st.caption(
        "KGSP 품질관리교육용 평가지를 자동 생성합니다 — 시험지 + 정답·해설 + "
        "교육일지(서명란)가 한 워드 파일로 나옵니다. (사용 전 QA 검토 필요)"
    )

    topics = ee.collect_topics()

    with st.form("training_form"):
        c1, c2 = st.columns(2)
        with c1:
            company = st.text_input("회사명", placeholder="예: ○○약품(주)")
            exam_date = st.date_input("교육일자", value=datetime.now()).strftime("%Y-%m-%d")
            trainer = st.text_input("강사/주관 (선택)", placeholder="예: 품질관리부")
        with c2:
            n = st.select_slider("문항 수", options=[5, 10, 15, 20], value=10)
            difficulty = st.selectbox("난이도", ["쉬움", "보통", "어려움"], index=1)
            pass_score = st.number_input("합격 점수", 50, 100, 80, step=5)
            attendees = st.number_input("교육일지 서명란 줄 수", 5, 30, 10, step=5)

        topic_labels = [t[1] for t in topics]
        sel = st.multiselect(
            "출제 범위 (비우면 전체)",
            options=list(range(len(topics))),
            format_func=lambda i: topic_labels[i],
        )
        topic_ids = [topics[i][0] for i in sel] if sel else None

        use_claude = st.checkbox(
            "Claude 로 고품질 문항 생성 (키 필요 — 실패 시 기본 문항으로 자동 대체)",
            value=True,
        )
        submitted = st.form_submit_button("📝 시험지 생성", type="primary")

    if submitted:
        with st.spinner("문항 생성 중…"):
            if use_claude:
                questions, mode = ee.build_with_claude(
                    n=n, topic_ids=topic_ids, difficulty=difficulty)
            else:
                seed = int(datetime.now().strftime("%Y%m%d"))
                questions, mode = ee.build_deterministic(
                    n=n, topic_ids=topic_ids, seed=seed), "deterministic"
        if not questions:
            st.error("문항을 생성하지 못했습니다 — 출제 범위를 넓혀 다시 시도하세요.")
            return
        st.session_state["training_questions"] = questions
        st.session_state["training_meta"] = dict(
            company=company, exam_date=exam_date, trainer=trainer,
            pass_score=int(pass_score), attendees=int(attendees), mode=mode,
        )
        # 사용량 기록
        try:
            from data_layer import usage as _usage
            _usage.log_action(_user(), "training", "시험지 생성",
                              f"{n}문항 · {mode}")
        except Exception:
            pass

    questions = st.session_state.get("training_questions")
    meta = st.session_state.get("training_meta", {})
    if not questions:
        return

    st.markdown("---")
    mode_label = {"claude": "🤖 Claude 생성", "fallback": "⚙️ 기본 문항(폴백)",
                  "deterministic": "⚙️ 기본 문항"}.get(meta.get("mode"), "")
    st.markdown(f"### 미리보기 — {len(questions)}문항  {mode_label}")

    for q in questions:
        with st.container(border=True):
            st.markdown(f"**{q.number}. {q.question}**")
            if q.qtype == "choice":
                for i, opt in enumerate(q.options):
                    st.markdown(f"&nbsp;&nbsp;{ee.CIRCLED[i]} {opt}")
            with st.expander("정답·해설"):
                st.markdown(f"**정답: {q.answer}**")
                if q.explanation:
                    st.caption(q.explanation)

    # 워드 다운로드
    try:
        from utils.docx_builder import build_exam_docx
        data = build_exam_docx(
            questions,
            company=meta.get("company", ""),
            exam_date=meta.get("exam_date", ""),
            trainer=meta.get("trainer", ""),
            pass_score=meta.get("pass_score", 80),
            attendee_rows=meta.get("attendees", 10),
        )
        fname = f"KGSP_교육평가_{meta.get('exam_date','')}.docx"
        st.download_button(
            "⬇️ 워드 파일 다운로드 (시험지+정답해설+교육일지)",
            data=data, file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
    except ImportError:
        st.error("서버에 python-docx 가 없습니다 — "
                 "`pip install python-docx` 후 서비스를 재시작하세요.")

    st.markdown("---")
    st.caption(branding.FOOTER_NOTE)
