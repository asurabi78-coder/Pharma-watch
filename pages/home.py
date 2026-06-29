"""외부용 홈 — 목업 기반 대시보드 랜딩.

구성: 상단 검색 → 히어로 → (좌) 핵심 기능 2×2 + 최근 업데이트 / (우) QA 커뮤니티 패널.
모든 데이터는 실제 소스 사용:
  - 최근 업데이트: data_layer.digest 의 다가오는 규제 일정
  - QA 커뮤니티 미리보기: data_layer.qa_community 최신 질문
기존 라우팅(st.session_state.page) 과 nav_history 규약을 그대로 따른다.
"""
import streamlit as st

import branding


# 좌측 2×2 핵심 기능 (QA 커뮤니티는 우측 패널이라 제외)
_FEATURE_CARDS = [
    ("📅", "규제 캘린더", "시행일과 마감일을 확인합니다", "pharmacal"),
    ("📰", "뉴스 모니터링", "제약·유통 주요 뉴스를 확인합니다", "newsroom"),
    ("🔍", "규제 검색", "KGSP·GDP·GMP 근거를 검색합니다", "regulatory"),
    ("🧭", "QA 분석가", "업무 영향도와 해야 할 일을 정리합니다", "qa_analyst"),
]

# 최근 업데이트 종류 → 칩 라벨
_KIND_TAG = {
    "시행": "시행", "변경": "변경", "개정": "개정",
    "KGSP 의무": "의무", "사내 일정": "일정", "일정": "일정",
}


def _go(key: str) -> None:
    st.session_state.setdefault("nav_history", []).append("home")
    st.session_state.page = key
    st.rerun()


def _go_question(qid: int) -> None:
    """QA 커뮤니티 특정 질문 상세로 이동."""
    st.session_state["qc_view"] = "detail"
    st.session_state["qc_qid"] = int(qid)
    _go("qa_community")


def _chip(label: str, *, fg: str = "var(--accent)", bg: str = "var(--accent-soft)") -> str:
    return (
        f"<span style='display:inline-block;padding:2px 9px;border-radius:8px;"
        f"font-size:11px;font-weight:600;color:{fg};background:{bg};'>{label}</span>"
    )


def render():
    # ── 상단 검색 ──────────────────────────────────────────────
    sc1, sc2 = st.columns([6, 1])
    with sc1:
        q = st.text_input(
            "검색", key="home_search", label_visibility="collapsed",
            placeholder="규제·뉴스·커뮤니티 질문을 검색하세요",
        )
    with sc2:
        do_search = st.button("검색", use_container_width=True, key="home_search_btn")
    if (do_search or q) and q.strip():
        # 규제 검색 페이지로 검색어 전달 (reg_query 규약)
        st.session_state["reg_topic"] = None
        st.session_state["reg_query"] = q.strip()
        _go("regulatory")

    # ── 히어로 ────────────────────────────────────────────────
    st.markdown(
        "<div style='margin:8px 0 2px;'>"
        + _chip("오늘의 QA")
        + "</div>"
        "<div style='font-family:\"Noto Sans KR\",system-ui,sans-serif;"
        "font-weight:800;font-size:34px;line-height:1.2;color:var(--text);"
        "letter-spacing:-0.02em;margin:6px 0 4px;'>"
        "필요한 규제 정보만 빠르게 확인하세요</div>",
        unsafe_allow_html=True,
    )
    st.caption("규제 변화부터 실무 질문까지 한곳에서 확인합니다.")
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    # ── 본문 2단 ──────────────────────────────────────────────
    left, right = st.columns([2, 1.15], gap="large")
    with left:
        _render_features()
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        _render_recent_updates()
    with right:
        _render_community_panel()

    st.markdown("---")
    st.caption(branding.ORG_LABEL)
    st.caption(branding.FOOTER_NOTE)


def _render_features():
    st.markdown("#### 핵심 기능")
    cols = st.columns(2)
    for i, (icon, title, desc, key) in enumerate(_FEATURE_CARDS):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(
                    f"<div style='font-size:24px;line-height:1;margin-bottom:6px;'>{icon}</div>"
                    f"<div style='font-weight:700;font-size:15px;color:var(--text);'>{title}</div>"
                    f"<div style='font-size:12.5px;color:var(--text-2);margin-top:2px;"
                    f"min-height:34px;'>{desc}</div>",
                    unsafe_allow_html=True,
                )
                if st.button("열기  →", key="home_open_" + key,
                             use_container_width=True):
                    _go(key)


def _render_recent_updates():
    st.markdown("#### 최근 업데이트")
    rows = []
    try:
        from data_layer import digest as _digest
        rows = _digest._upcoming_regulatory(window_days=120)[:4]
    except Exception:
        rows = []

    if not rows:
        with st.container(border=True):
            st.caption("예정된 규제 일정이 없습니다. (시드/수집 후 표시됩니다)")
        return

    from datetime import datetime as _dt
    _today = _dt.now().date()

    def _dday(ds):
        try:
            d = (_dt.strptime(ds, "%Y-%m-%d").date() - _today).days
            return "오늘" if d == 0 else (f"D-{d}" if d > 0 else f"D+{-d}")
        except Exception:
            return ""

    with st.container(border=True):
        for idx, (date, kind, title) in enumerate(rows):
            tag = _KIND_TAG.get(kind, kind or "안내")
            disp = title if len(title) <= 40 else title[:40] + "…"
            dd = _dday(date)
            urgent = dd.startswith("D-") and dd[2:].isdigit() and int(dd[2:]) <= 14
            ddcol = "var(--danger)" if urgent else "var(--text-3)"
            st.markdown(
                "<div style='display:grid;grid-template-columns:74px 1fr 90px 52px;gap:10px;"
                "align-items:center;padding:7px 0;font-size:13px;'>"
                f"{_chip(tag, fg='var(--warn)', bg='var(--warn-soft)')}"
                f"<span style='color:var(--text);overflow:hidden;text-overflow:ellipsis;"
                f"white-space:nowrap;'>{disp}</span>"
                f"<span style='color:var(--text-2);font-size:12px;'>{date}</span>"
                f"<span style='color:{ddcol};font-size:12px;font-weight:600;text-align:right;'>{dd}</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            if idx < len(rows) - 1:
                st.markdown(
                    "<div style='border-top:1px solid var(--border);'></div>",
                    unsafe_allow_html=True,
                )


def _render_community_panel():
    with st.container(border=True):
        head = st.columns([3, 1])
        with head[0]:
            st.markdown(
                "<div style='font-weight:800;font-size:17px;color:var(--text);'>"
                "💬 QA 커뮤니티</div>",
                unsafe_allow_html=True,
            )
        with head[1]:
            if st.button("전체보기 ›", key="home_qc_all", use_container_width=True):
                _go("qa_community")

        st.caption("실무에서 궁금한 점을 묻고 경험을 나눠보세요.")

        questions = []
        try:
            from data_layer import qa_community as qc
            questions = qc.list_questions(sort="recent", limit=3)
        except Exception:
            questions = []

        if not questions:
            st.markdown(
                "<div style='font-size:13px;color:var(--text-2);padding:8px 0;'>"
                "아직 등록된 질문이 없습니다. 첫 질문을 남겨보세요.</div>",
                unsafe_allow_html=True,
            )
        else:
            for i, ques in enumerate(questions):
                title = ques.title if len(ques.title) <= 40 else ques.title[:40] + "…"
                st.markdown(
                    f"<div style='font-weight:600;font-size:14px;color:var(--text);"
                    f"margin-top:6px;'>{title}</div>"
                    f"<div style='display:flex;align-items:center;justify-content:space-between;"
                    f"margin-top:4px;'>{_chip(ques.category, fg='var(--qa)', bg='var(--qa-soft)')}"
                    f"<span style='font-size:12px;color:var(--text-3);'>답변 "
                    f"{ques.answer_count} ›</span></div>",
                    unsafe_allow_html=True,
                )
                if st.button("보기", key=f"home_qc_{ques.id}",
                             use_container_width=True):
                    _go_question(ques.id)
                if i < len(questions) - 1:
                    st.markdown(
                        "<div style='border-top:1px solid var(--border);margin:8px 0;'></div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        if st.button("＋  질문하기", type="primary", use_container_width=True,
                     key="home_qc_ask"):
            st.session_state["qc_open_write"] = True
            _go("qa_community")
