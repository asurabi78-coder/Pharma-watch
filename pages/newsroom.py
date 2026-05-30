"""Newsroom — Phase B.

3개 사이트 (데일리팜·약업신문·물류신문) 병렬 수집 + SQLite 영속 + 탭/필터/검색.

다음 Phase 예약:
- Phase C: Claude 자동 요약 + 중요도 태깅
- Phase D: '🎯 AI 회의로' 버튼 활성화
- Phase E: 자동 스케줄 + 주간 매거진
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from data_layer.news import SOURCES, fetch_and_save, repo


_RANGE_OPTIONS = {
    "최근 1일":  1,
    "최근 3일":  3,
    "최근 7일":  7,
    "최근 30일": 30,
    "전체":      None,
}


def _render_item_card(
    it,
    *,
    key_prefix: str = "all",
    source_label_override: str = None,
) -> None:
    """단일 뉴스 카드 렌더링.

    같은 기사가 '전체' 탭과 '소스별' 탭에 동시 렌더되므로 버튼 key 가 겹치면
    StreamlitDuplicateElementKey 가 난다. key_prefix 로 탭별 네임스페이스 분리.
    """
    with st.container(border=True):
        head = st.columns([8, 2])
        with head[0]:
            cat_text = f" · {it.category}" if it.category else ""
            published = it.published_at[:16].replace("T", " ") if it.published_at else "—"
            st.markdown(
                f"**[{it.title}]({it.url})**  \n"
                f"<span style='color:#8794ad;font-size:12px'>"
                f"[{source_label_override or it.source_label}]"
                f"{cat_text} · 🕒 {published}"
                f"</span>",
                unsafe_allow_html=True,
            )
            if it.summary:
                st.caption(it.summary)
        with head[1]:
            st.button(
                "🎯 AI 회의로",
                key=f"nr_meet_{key_prefix}_{it.id}",
                use_container_width=True,
                disabled=True,
                help="Phase D 에서 활성화 — 사업회의실 안건으로 전달",
            )
            if st.button(
                "🚫 숨김",
                key=f"nr_hide_{key_prefix}_{it.id}",
                use_container_width=True,
                help="이 기사를 목록에서 숨김 (DB에 표시만)",
            ):
                repo.set_hidden(it.id, True)
                st.toast("숨김 처리됨", icon="✅")
                st.rerun()


def render() -> None:
    st.title("Newsroom")
    st.caption("의약품·물류 도메인 뉴스 — 데일리팜 · 약업신문 · 물류신문")

    # ── 상단 컨트롤 ────────────────────────────
    ctrl = st.columns([2, 2, 2, 4])
    with ctrl[0]:
        per_src = st.number_input(
            "소스당 최대",
            min_value=5, max_value=50, value=15, step=5,
            key="newsroom_per_src",
        )
    with ctrl[1]:
        range_label = st.selectbox(
            "기간",
            options=list(_RANGE_OPTIONS.keys()),
            index=2,  # 최근 7일
            key="newsroom_range",
        )
        days = _RANGE_OPTIONS[range_label]
    with ctrl[2]:
        text_search = st.text_input(
            "🔍 검색", value="",
            placeholder="키워드 (제목·요약)",
            key="newsroom_search",
        )
    with ctrl[3]:
        bcols = st.columns([1, 1])
        with bcols[0]:
            if st.button("🔄 새로고침 (재수집)", use_container_width=True, key="newsroom_fetch"):
                with st.spinner("3개 사이트 동시 수집 중…"):
                    summary = fetch_and_save(per_source_limit=int(per_src))
                st.session_state["newsroom_last_summary"] = summary
                st.session_state["newsroom_last_fetched"] = datetime.now()
                st.rerun()
        with bcols[1]:
            if st.button("🗑 30일 이전 삭제", use_container_width=True, key="newsroom_purge"):
                n = repo.purge_older_than(30)
                st.toast(f"{n}건 정리 완료 (즐겨찾기 제외)", icon="✅")
                st.rerun()

    # ── 마지막 수집 요약 ────────────────────────────
    last_summary = st.session_state.get("newsroom_last_summary")
    last_fetched = st.session_state.get("newsroom_last_fetched")
    if last_summary:
        when = last_fetched.strftime("%Y-%m-%d %H:%M:%S") if last_fetched else "—"
        summary_cells = [
            f"**{label}**: {info['count']}건"
            + (f" ⚠ {info['error']}" if info.get("error") else "")
            for label, info in last_summary["stats"].items()
        ]
        st.caption(
            f"📥 마지막 수집 {when} · "
            f"총 {last_summary['total_fetched']}건 (신규 {last_summary['new']} / 갱신 {last_summary['updated']})  \n"
            + " · ".join(summary_cells)
        )

    total = repo.total_count()
    if total == 0:
        st.info(
            "📭 아직 수집된 뉴스가 없습니다. "
            "위 **🔄 새로고침 (재수집)** 버튼을 눌러 첫 수집을 시작하세요."
        )
        with st.expander("ℹ Phase B 안내", expanded=True):
            st.markdown(
                "**Phase B — 다중 소스 + 영속 + 필터**  \n\n"
                "**수집 소스:**  \n"
                "• 데일리팜 (의약 전문지, HTML)  \n"
                "• 약업신문 (제약·유통, HTML — 유통 카테고리 별도 수집)  \n"
                "• 물류신문 (RSS — 3PL / 콜드체인 / SCM / 물류센터 4개 피드)  \n\n"
                "**저장:** SQLite (`db/news.db`) — 중복 제거, 30일 자동 정리 옵션  \n"
                "**현재 미포함:** MFDS (다음 Phase 에서 별도 처리)  \n\n"
                "**다음 단계:**  \n"
                "• Phase C — Claude 요약·중요도 자동 태깅  \n"
                "• Phase D — '🎯 AI 회의로' 활성화  \n"
                "• Phase E — 매시간 자동 수집 + 주간 매거진"
            )
        return

    tab_labels = ["📰 전체"] + [f"[{s['label']}]" for s in SOURCES]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        items = repo.list_items(
            text_search=text_search.strip() or None,
            days=days,
            limit=200,
        )
        st.caption(f"표시 {len(items)}건 · 보관 총 {total}건")
        if not items:
            st.warning("필터에 맞는 뉴스가 없습니다.")
        for it in items:
            _render_item_card(it, key_prefix="all")

    for i, src in enumerate(SOURCES, 1):
        with tabs[i]:
            items = repo.list_items(
                sources=[src["key"]],
                text_search=text_search.strip() or None,
                days=days,
                limit=100,
            )

            if src["key"] == "yakup":
                cat = st.selectbox(
                    "약업신문 카테고리 필터",
                    options=["전체", "유통", "제약·바이오", "정책", "약사·약학", "글로벌"],
                    key=f"newsroom_cat_{src['key']}",
                )
                if cat != "전체":
                    items = [x for x in items if cat in (x.category or "")]
            elif src["key"] == "klnews":
                cat = st.selectbox(
                    "물류신문 카테고리 필터",
                    options=["전체", "3PL", "콜드체인", "SCM", "물류센터"],
                    key=f"newsroom_cat_{src['key']}",
                )
                if cat != "전체":
                    items = [x for x in items if x.category == cat]

            st.caption(f"표시 {len(items)}건")
            if not items:
                st.warning("이 소스에 필터에 맞는 뉴스가 없습니다.")
            for it in items:
                _render_item_card(it, key_prefix=src["key"])

    st.markdown("---")
    with st.expander("ℹ 저작권 / 데이터 정책", expanded=False):
        st.markdown(
            "이 페이지는 각 사이트의 **공개 RSS / HTML** 에서 제목·링크·짧은 요약만 수집합니다.  \n"
            "본문 전체 복제는 하지 않으며, 모든 카드는 원문 사이트로 직접 링크됩니다.  \n"
            "저작권은 원 발행사에 있습니다."
        )
