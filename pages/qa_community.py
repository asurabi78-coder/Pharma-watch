"""QA 커뮤니티 — 제약·의약품 유통 QA 담당자 실무 Q&A 게시판.

사용자끼리 질문을 올리고 답변/경험을 공유한다. QA 분석가(AI 답변)와 별개.
- 질문 목록 · 검색/분류 · 질문 작성 · 상세보기 · 답변 작성 · 답변 채택
- 회사명 비공개(닉네임=로그인 ID 로 표시)
- 신뢰도 배지(일반/채택/관리자 확인/전문가 확인)
- 관리자(is_admin)는 부적절·위험 글을 숨김 처리
- 모든 질문 하단에 실무 참고용 안내문구 고정
"""
import streamlit as st

import branding
from data_layer import qa_community as qc
from ui.auth import current_user, is_admin


_DISCLAIMER = (
    "커뮤니티 답변은 **실무 참고용**입니다. 최종 규제 해석과 품질 판단은 "
    "**관리약사 또는 품질책임자**가 확인해야 합니다."
)

_TRUST_STYLE = {
    qc.TRUST_ADOPTED: ("✅", "#2ec4b6"),
    qc.TRUST_ADMIN:   ("🛡", "#3d7aed"),
    qc.TRUST_EXPERT:  ("🎓", "#a06bdc"),
    qc.TRUST_NORMAL:  ("💬", "#7a869a"),
}


def _badge(label: str) -> str:
    icon, color = _TRUST_STYLE.get(label, ("💬", "#7a869a"))
    return (
        f"<span style='display:inline-block;padding:1px 8px;border-radius:10px;"
        f"font-size:11px;background:{color}22;color:{color};"
        f"border:1px solid {color}55;margin-right:4px;'>{icon} {label}</span>"
    )


def _log(action: str, detail: str) -> None:
    """행동 로그 — 실패해도 무시(기능에 영향 없음)."""
    try:
        from data_layer import usage as _usage
        _usage.log_action(current_user(), "qa_community", action, detail[:80])
    except Exception:
        pass


# ── 렌더 진입점 ──────────────────────────────────────────────────────────
def render():
    st.title("💬 QA 커뮤니티")
    st.caption(
        "제약·의약품 유통 QA 담당자끼리 실무 질문과 경험을 나누는 공간입니다. "
        "(규정 기반 즉시 답변이 필요하면 ‘QA 분석가’를 이용하세요.)"
    )

    st.session_state.setdefault("qc_view", "list")
    st.session_state.setdefault("qc_qid", None)

    if st.session_state["qc_view"] == "detail" and st.session_state.get("qc_qid"):
        _render_detail(int(st.session_state["qc_qid"]))
    else:
        _render_list()


def _go_list():
    st.session_state["qc_view"] = "list"
    st.session_state["qc_qid"] = None


def _go_detail(qid: int):
    st.session_state["qc_view"] = "detail"
    st.session_state["qc_qid"] = int(qid)


# ── 목록 화면 ────────────────────────────────────────────────────────────
def _render_list():
    admin = is_admin()

    # 질문 작성
    with st.expander("✍️ 질문 작성", expanded=st.session_state.pop("qc_open_write", False)):
        with st.form("qc_new_q", clear_on_submit=True):
            title = st.text_input("제목", key="qc_q_title",
                                  placeholder="예: 냉장 의약품 입고 시 온도 일탈 처리 절차 문의")
            category = st.selectbox("카테고리", qc.CATEGORIES, key="qc_q_cat")
            body = st.text_area("내용", height=140, key="qc_q_body",
                                placeholder="상황과 궁금한 점을 구체적으로 적어주세요.")
            submitted = st.form_submit_button("질문 등록", type="primary")
            if submitted:
                if not title.strip() or not body.strip():
                    st.warning("제목과 내용을 모두 입력하세요.")
                else:
                    try:
                        qid = qc.create_question(
                            title, body, category, user=current_user()
                        )
                        _log("질문등록", title.strip())
                        st.success("질문이 등록되었습니다.")
                        _go_detail(qid)
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"등록 실패: {type(e).__name__}: {e}")

    # 필터 줄
    fc1, fc2, fc3 = st.columns([2, 2, 1.2])
    with fc1:
        cat = st.selectbox(
            "카테고리", [qc.CATEGORY_ALL] + qc.CATEGORIES, key="qc_filter_cat"
        )
    with fc2:
        search = st.text_input("검색", key="qc_filter_search",
                              placeholder="제목·내용 검색")
    with fc3:
        sort_label = st.selectbox("정렬", ["최신순", "답변순", "조회순"], key="qc_sort")
    sort = {"최신순": "recent", "답변순": "answers", "조회순": "views"}[sort_label]

    try:
        questions = qc.list_questions(
            category=cat, search=search, sort=sort, include_hidden=admin
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"목록을 불러오지 못했습니다: {type(e).__name__}: {e}")
        return

    st.markdown(f"**질문 {len(questions)}건**")
    st.markdown("---")

    if not questions:
        st.caption("아직 질문이 없습니다. 위 ‘질문 작성’으로 첫 질문을 남겨보세요.")
    for q in questions:
        with st.container(border=True):
            top = st.columns([5, 1])
            with top[0]:
                hidden_tag = " 🚫숨김" if q.is_hidden else ""
                adopted_tag = " ✅채택완료" if q.adopted_answer_id else ""
                st.markdown(
                    f"`{q.category}`{hidden_tag}{adopted_tag}  \n"
                    f"**{q.title}**"
                )
                st.caption(
                    f"👤 {q.user}  ·  🕑 {q.created_at}  ·  "
                    f"👁 {q.views}  ·  💬 답변 {q.answer_count}"
                )
            with top[1]:
                if st.button("보기", key=f"qc_open_{q.id}",
                             use_container_width=True):
                    _go_detail(q.id)
                    st.rerun()

    st.markdown("---")
    st.info(_DISCLAIMER, icon="ℹ️")
    st.caption(branding.FOOTER_NOTE)


# ── 상세 화면 ────────────────────────────────────────────────────────────
def _render_detail(qid: int):
    admin = is_admin()
    me = current_user()

    if st.button("← 목록으로", key="qc_back"):
        _go_list()
        st.rerun()

    q = qc.get_question(qid, include_hidden=admin)
    if not q:
        st.warning("질문을 찾을 수 없거나 숨김 처리되었습니다.")
        st.info(_DISCLAIMER, icon="ℹ️")
        return

    # 조회수 1회 증가(세션 중 같은 질문 중복 카운트 방지)
    seen = st.session_state.setdefault("qc_seen", set())
    if qid not in seen:
        try:
            qc.increment_views(qid)
            seen.add(qid)
            q.views += 1
        except Exception:
            pass

    is_owner = (q.user == me)

    st.markdown(f"### {q.title}")
    st.markdown(
        f"`{q.category}`  ·  👤 {q.user}  ·  🕑 {q.created_at}  ·  👁 {q.views}"
    )
    if q.is_hidden:
        st.warning("🚫 이 질문은 관리자에 의해 숨김 처리되었습니다.")
    with st.container(border=True):
        st.markdown(q.body)

    # 작성자/관리자 컨트롤
    ctl = st.columns(3)
    if is_owner:
        with ctl[0]:
            if st.button("🗑 질문 삭제", key="qc_del_q", use_container_width=True):
                qc.delete_question(qid, user=me)
                _log("질문삭제", q.title)
                _go_list()
                st.rerun()
    if admin:
        with ctl[1]:
            if q.is_hidden:
                if st.button("👁 숨김 해제", key="qc_unhide_q",
                             use_container_width=True):
                    qc.set_question_hidden(qid, False)
                    st.rerun()
            else:
                if st.button("🚫 질문 숨김", key="qc_hide_q",
                             use_container_width=True):
                    qc.set_question_hidden(qid, True)
                    st.rerun()

    st.markdown("---")

    # 답변 목록
    try:
        answers = qc.list_answers(qid, include_hidden=admin)
    except Exception as e:  # noqa: BLE001
        st.error(f"답변을 불러오지 못했습니다: {type(e).__name__}: {e}")
        answers = []

    st.markdown(f"#### 답변 {len([a for a in answers if not a.is_hidden])}건")
    if not answers:
        st.caption("아직 답변이 없습니다. 아래에서 첫 답변을 남겨보세요.")

    for a in answers:
        with st.container(border=True):
            badges = "".join(_badge(b) for b in a.trust_levels())
            if a.is_hidden:
                badges += "<span style='font-size:11px;color:#d9534f;'>🚫 숨김</span>"
            st.markdown(badges, unsafe_allow_html=True)
            st.markdown(a.body)
            st.caption(f"👤 {a.user}  ·  🕑 {a.created_at}")

            arow = st.columns(4)
            # 채택(질문 작성자만)
            if is_owner and not q.is_hidden:
                with arow[0]:
                    if a.is_adopted:
                        if st.button("채택 취소", key=f"qc_unadopt_{a.id}",
                                     use_container_width=True):
                            qc.unadopt_answer(qid, user=me)
                            st.rerun()
                    else:
                        if st.button("✅ 채택", key=f"qc_adopt_{a.id}",
                                     type="primary", use_container_width=True):
                            qc.adopt_answer(qid, a.id, user=me)
                            _log("답변채택", q.title)
                            st.rerun()
            # 본인 답변 삭제
            if a.user == me:
                with arow[1]:
                    if st.button("🗑 삭제", key=f"qc_dela_{a.id}",
                                 use_container_width=True):
                        qc.delete_answer(a.id, user=me)
                        st.rerun()
            # 관리자 컨트롤
            if admin:
                with arow[2]:
                    if a.is_hidden:
                        if st.button("👁 숨김해제", key=f"qc_unhidea_{a.id}",
                                     use_container_width=True):
                            qc.set_answer_hidden(a.id, False)
                            st.rerun()
                    else:
                        if st.button("🚫 숨김", key=f"qc_hidea_{a.id}",
                                     use_container_width=True):
                            qc.set_answer_hidden(a.id, True)
                            st.rerun()
                with arow[3]:
                    with st.popover("🛡 검증"):
                        av = st.checkbox("관리자 확인", value=bool(a.admin_verified),
                                         key=f"qc_av_{a.id}")
                        ev = st.checkbox("전문가 확인", value=bool(a.expert_verified),
                                         key=f"qc_ev_{a.id}")
                        if st.button("적용", key=f"qc_vapply_{a.id}"):
                            qc.set_answer_verified(a.id, admin=av, expert=ev)
                            st.rerun()

    # 답변 작성
    if not q.is_hidden:
        st.markdown("---")
        with st.form(f"qc_new_a_{qid}", clear_on_submit=True):
            ans = st.text_area("답변 작성", height=120, key=f"qc_a_body_{qid}",
                               placeholder="실제 경험이나 처리 방식을 공유해주세요.")
            if st.form_submit_button("답변 등록", type="primary"):
                if not ans.strip():
                    st.warning("답변 내용을 입력하세요.")
                else:
                    try:
                        qc.create_answer(qid, ans, user=me)
                        _log("답변등록", q.title)
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"답변 등록 실패: {type(e).__name__}: {e}")

    st.markdown("---")
    st.info(_DISCLAIMER, icon="ℹ️")
    st.caption(branding.FOOTER_NOTE)
