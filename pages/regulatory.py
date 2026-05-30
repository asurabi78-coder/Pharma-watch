"""규제 검토실 — KGSP/GDP/GMP 원문 검색 + 실무 해석 분리.

로컬 시드 데이터 + law.go.kr 실연동(키 있을 때).
"""
import streamlit as st

from data_layer.connectors.base import TIER_LABEL, SourceTier
from data_layer.connectors.law import LawGoKrConnector
from data_layer.regulatory.seed import SEED_ENTRIES
from engines.regulatory_engine import search, count_by_grade


def render():
    st.title("규제 검토실")
    st.caption("KGSP / GDP / GMP 원문 검색 + 실무 해석 (로컬 시드).")

    # 상단 — 등급별 분포 미니 대시 (7단계)
    counts = count_by_grade()
    tiers = list(SourceTier)
    cols = st.columns(len(tiers))
    for col, tier in zip(cols, tiers):
        with col:
            label, _ = TIER_LABEL[tier]
            st.metric(label, counts.get(tier, 0))

    st.markdown("---")

    # 검색 입력
    col_q, col_btn = st.columns([4, 1])
    query = col_q.text_input(
        "검색어",
        placeholder="예: 보관 온도 / 출하증명 / 일탈 / 콜드체인 / CAPA",
        label_visibility="collapsed",
        key="reg_query",
    )
    with col_btn:
        st.button("🔍 검색", type="primary", use_container_width=True, key="reg_search_btn")

    # 등급 필터 — 7단계 그룹 헤더 표시
    st.markdown("**등급 필터**")
    selected: list[SourceTier] = []

    st.caption("규정 판단 가능 (단독 근거 사용 가능)")
    compliance_cols = st.columns(4)
    for col, tier in zip(
        compliance_cols,
        [SourceTier.LAW, SourceTier.NOTICE, SourceTier.GUIDE, SourceTier.INTERNAL],
    ):
        label, _ = TIER_LABEL[tier]
        with col:
            if st.checkbox(label, value=True, key="reg_filter_" + tier.value):
                selected.append(tier)

    st.caption("보조 자료 (단독 근거 불가)")
    aux_cols = st.columns(2)
    for col, tier in zip(aux_cols, [SourceTier.OFFICIAL, SourceTier.NEWS]):
        label, _ = TIER_LABEL[tier]
        with col:
            if st.checkbox(label, value=True, key="reg_filter_" + tier.value):
                selected.append(tier)

    st.caption("참고 (확인 필요)")
    ref_cols = st.columns(1)
    for col, tier in zip(ref_cols, [SourceTier.AI]):
        label, _ = TIER_LABEL[tier]
        with col:
            if st.checkbox(label, value=True, key="reg_filter_" + tier.value):
                selected.append(tier)

    st.markdown("---")

    if not query.strip():
        st.info("검색어를 입력하세요. 전체 시드 항목을 보고 싶다면 빈칸 검색 불가 — 키워드 필요.")
        with st.expander("시드 데이터 전체 보기"):
            for entry in SEED_ENTRIES:
                label, _ = TIER_LABEL[entry.grade]
                st.markdown(f"- {label} **{entry.title}** ({entry.article})")
        return

    result = search(query, grade_filter=selected)

    if result.total == 0:
        st.warning(
            f"'{query}' 매칭 결과 없음. 다른 키워드를 시도하거나 등급 필터를 확인하세요."
        )
        return

    st.success(f"{result.total}건 검색됨 — 점수 → 등급(LAW 우선) 순")
    st.caption("⚠️ 사람 검토 필요 — 본 결과는 시드 데이터 기반 초안입니다.")

    for i, entry in enumerate(result.entries):
        label, _ = TIER_LABEL[entry.grade]
        st.markdown(f"### {label} {entry.title}")

        meta_cols = st.columns(3)
        meta_cols[0].caption(f"📋 조문: **{entry.article or '—'}**")
        meta_cols[1].caption(f"📅 시행: **{entry.effective_date or '—'}**")
        meta_cols[2].caption(f"🔗 출처: **{entry.source or '—'}**")

        st.markdown("**원문 근거**")
        st.code(entry.content, language=None)

        if entry.practical_interpretation:
            st.markdown("**실무 해석**")
            st.info(entry.practical_interpretation)

        if entry.tags:
            st.caption("태그: " + " · ".join(entry.tags))

        if entry.requires_human_review:
            st.markdown("🔴 **사람 검토 필요** — 고객 제출 전 담당자(QA·법무) 확인")

        if i < len(result.entries) - 1:
            st.divider()

    # ------------------------------------------------------------------
    # law.go.kr 실시간 검색 (LAW tier)
    # ------------------------------------------------------------------
    st.markdown("---")
    law_tier_label, _ = TIER_LABEL[SourceTier.LAW]
    st.subheader(f"{law_tier_label} law.go.kr 실시간 검색")

    connector = LawGoKrConnector()
    if not connector.is_available():
        st.caption(
            "ℹ️ `LAW_GO_KR_API_KEY` 미설정 — .env 에 발급 ID 를 추가하면 자동 활성화."
        )
    else:
        with st.spinner("law.go.kr 조회 중..."):
            records = connector.search_laws(query, max_results=10)

        if not records:
            st.caption(
                "조회 결과 없음 (또는 일시적 통신 실패). 키워드를 바꿔 다시 시도하세요."
            )
        else:
            st.success(f"law.go.kr {len(records)}건 — 모두 LAW 등급")
            for rec in records:
                title_md = f"### {law_tier_label} {rec.title}"
                if rec.url:
                    title_md = f"### {law_tier_label} [{rec.title}]({rec.url})"
                st.markdown(title_md)
                st.caption(rec.summary or "—")
                if rec.tags:
                    st.caption("태그: " + " · ".join(rec.tags))
