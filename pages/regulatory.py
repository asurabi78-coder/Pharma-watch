"""규제 검토실 — KGSP/GDP/GMP 원문 검색 + 실무 해석 분리.

로컬 시드 데이터 + law.go.kr 실연동(키 있을 때).
"""
from urllib.parse import quote

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

    # ── 빠른 주제 선택 (비전문가용) ──
    st.markdown("#### 빠른 주제 선택")
    st.caption("용어를 몰라도 — 관심 주제를 누르면 관련 규정을 바로 찾아줍니다.")
    _QUICK = [
        ("🟢 분야", [
            ("콜드체인", "콜드체인"), ("백신·생물학적제제", "백신"),
            ("완제의약품", "의약품"), ("원료의약품", "원료"), ("의료기기", "의료기기"),
        ]),
        ("🔵 규정 기준", [
            ("KGSP 유통품질", "KGSP"), ("GDP 유통관리", "GDP"),
            ("GMP 제조", "GMP"), ("약사법", "약사법"), ("안전관리 규정", "안전"),
        ]),
        ("🟠 업무 상황", [
            ("보관 온도", "온도"), ("출하증명", "출하증명"), ("온도 일탈", "일탈"),
            ("CAPA 시정·예방", "CAPA"), ("위탁 운영", "위탁"), ("실태조사 제출", "실태조사"),
        ]),
    ]
    for gi, (gname, chips) in enumerate(_QUICK):
        st.caption(gname)
        ccols = st.columns(len(chips))
        for ci, (label, kw) in enumerate(chips):
            with ccols[ci]:
                if st.button(label, key=f"chip_{gi}_{ci}", use_container_width=True):
                    st.session_state["reg_query"] = kw
                    st.rerun()

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
        st.info(
            f"'{query}' — 로컬 시드에는 매칭이 없습니다. 아래 law.go.kr 실시간 결과를 확인하세요."
        )
    else:
        st.success(f"{result.total}건 검색됨 (로컬 시드) — 점수 → 등급(LAW 우선) 순")
        st.caption("⚠️ 사람 검토 필요 — 본 결과는 시드 데이터 기반 초안입니다.")

    for i, entry in enumerate(result.entries):
        label, _ = TIER_LABEL[entry.grade]
        with st.container(border=True):
            head = st.columns([7, 2])
            with head[0]:
                st.markdown(f"**{label} {entry.title}**")
            with head[1]:
                st.markdown(
                    f"<div style='text-align:right;font-size:12px'>📅 "
                    f"<b>{entry.effective_date or '—'}</b></div>",
                    unsafe_allow_html=True,
                )

            st.caption(f"📋 조문 {entry.article or '—'} · 🔗 출처 {entry.source or '—'}")

            # 원문 근거 (절대 가공 금지 — 펼침)
            with st.expander("원문 근거 보기"):
                st.code(entry.content, language=None)

            # 최근 개정 · 실무 해석 (원문과 분리)
            if entry.practical_interpretation:
                st.markdown("**최근 개정 · 실무 해석**")
                st.info(entry.practical_interpretation)

            # 원문 링크 — 실제 URL(법제처 API 연동 시 채워짐)이 있으면 조문으로 바로 연결,
            # 없으면(시드 데이터) 웹 검색으로 연결해 "결과 없음"이 뜨지 않게 한다.
            _real = getattr(entry, "url", None)
            if _real:
                _url, _link_label = _real, "🔗 원문 보기"
            else:
                _url = "https://www.google.com/search?q=" + quote(entry.title + " 의약품 규제")
                _link_label = "🔗 원문 찾기"
            link_col, tag_col = st.columns([1, 3])
            with link_col:
                st.link_button(_link_label, _url, use_container_width=True)
            with tag_col:
                if entry.tags:
                    st.caption("태그: " + " · ".join(entry.tags))

            if entry.requires_human_review:
                st.caption("🔴 사람 검토 필요 — 고객 제출 전 담당자(QA·법무) 확인")

    # ------------------------------------------------------------------
    # law.go.kr 실시간 검색 (법령 + 행정규칙/고시) — 키 있을 때 실데이터
    # ------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📡 law.go.kr 실시간 검색")

    connector = LawGoKrConnector()
    if not connector.is_available():
        st.caption(
            "ℹ️ `LAW_GO_KR_API_KEY` 미설정 — open.law.go.kr 에서 발급 ID 를 받아 "
            ".env 에 넣으면 실시간 법령·고시가 자동으로 표시됩니다."
        )
        return

    with st.spinner("law.go.kr 법령·행정규칙 조회 중..."):
        records = list(connector.search_laws(query, max_results=10))
        try:
            records += list(connector.search_admrules(query, max_results=10))
        except Exception:  # noqa: BLE001
            pass

    # id 기준 중복 제거
    seen, uniq = set(), []
    for r in records:
        if r.id in seen:
            continue
        seen.add(r.id)
        uniq.append(r)

    if not uniq:
        st.caption("조회 결과 없음 (또는 일시적 통신 실패). 키워드를 바꿔 다시 시도하세요.")
        return

    st.success(f"law.go.kr 실시간 {len(uniq)}건 — 공식 법령·고시")
    for rec in uniq:
        tier = rec.tier if isinstance(rec.tier, SourceTier) else SourceTier.LAW
        label, _ = TIER_LABEL[tier]
        with st.container(border=True):
            head = st.columns([7, 2])
            with head[0]:
                st.markdown(f"**{label} {rec.title}**")
            with head[1]:
                st.markdown(
                    f"<div style='text-align:right;font-size:12px'>📅 "
                    f"<b>{rec.published_at or '—'}</b></div>",
                    unsafe_allow_html=True,
                )
            st.caption(f"🔗 출처 {rec.source or 'law.go.kr'} · {rec.summary or '—'}")
            lc, tc = st.columns([1, 3])
            with lc:
                if rec.url:
                    st.link_button("🔗 원문 보기", rec.url, use_container_width=True)
            with tc:
                if rec.tags:
                    st.caption("태그: " + " · ".join(rec.tags))
