"""규제 검색 — 업무 시나리오 중심 QA 의사결정 지원.

전환 (2026-06-01): '검색기' → 'QA 업무 브리핑'.
  - 앞문은 *주제(플레이북)*. 콜드체인을 누르면 ①관련 규제현황 ②핵심 가이드라인
    ③참고 사이트·문서 + 보고기한·체크리스트·감사질문이 한 화면에.
  - 두 축 분리: 화면은 업무 시나리오로 묶되, 각 규정 카드엔 효력 등급(SourceTier) 뱃지.
  - 원문은 law.go.kr/MFDS/WHO 직링크 (구글 우회 제거).
  - 키워드 검색 + law.go.kr 실시간은 '보조 경로' 로 유지.
"""
from collections import Counter

import streamlit as st

from data_layer.connectors.base import TIER_LABEL, SourceTier
from data_layer.connectors.law import LawGoKrConnector
from data_layer.regulatory.playbook import Provenance, TopicPlaybook
from data_layer.regulatory.playbook_seed import PLAYBOOKS, get_playbook
from engines.regulatory_engine import search


_TIER_HEX = {
    SourceTier.LAW:      ("#A32D2D", "#FCEBEB"),
    SourceTier.NOTICE:   ("#854F0B", "#FAEEDA"),
    SourceTier.GUIDE:    ("#185FA5", "#E6F1FB"),
    SourceTier.INTERNAL: ("#444441", "#F1EFE8"),
    SourceTier.OFFICIAL: ("#534AB7", "#EEEDFE"),
    SourceTier.NEWS:     ("#854F0B", "#FAEEDA"),
    SourceTier.AI:       ("#0F6E56", "#E1F5EE"),
}

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


def render():
    st.title("규제 검색")
    st.caption("KGSP / GDP / GMP — 업무 시나리오 중심 QA 의사결정 지원.")

    _render_trend_strip()
    st.markdown("---")

    # ── 빠른 주제 선택 (칩) ──
    st.markdown("#### 빠른 주제 선택")
    st.caption("주제를 누르면 적용 규정·보고기한·체크리스트·참고문서가 한 화면에 나옵니다.")
    for gi, (gname, chips) in enumerate(_QUICK):
        st.caption(gname)
        ccols = st.columns(len(chips))
        for ci, (label, kw) in enumerate(chips):
            with ccols[ci]:
                if st.button(label, key=f"chip_{gi}_{ci}", use_container_width=True):
                    _route(kw)

    st.markdown("---")

    # ── 키워드 검색 (보조) ──
    col_q, col_btn = st.columns([4, 1])
    query = col_q.text_input(
        "검색어",
        placeholder="주제에 없는 키워드 — 예: 출하증명 / CAPA / 데이터로거",
        label_visibility="collapsed",
        key="reg_query_input",
    )
    if col_btn.button("🔍 검색", type="secondary", use_container_width=True, key="reg_search_btn"):
        _route(query)

    st.markdown("---")

    # ── 라우팅 ──
    topic_id = st.session_state.get("reg_topic")
    active_query = st.session_state.get("reg_query", "")

    if topic_id:
        pb = get_playbook(topic_id)
        if pb is not None:
            _render_playbook(pb)
            return

    if active_query:
        _render_keyword_results(active_query)
        return

    st.info("위 주제 버튼을 누르거나, 키워드를 검색하세요.")
    st.caption(
        "예: **콜드체인**(또는 온도 이탈)을 누르면 적용 법령(law.go.kr 직링크)·핵심 가이드라인·"
        "참고문서·보고기한·체크리스트가 한 번에 나옵니다."
    )


def _route(term: str):
    """칩/검색어를 플레이북(시나리오) 또는 키워드 검색으로 분기."""
    term = (term or "").strip()
    if not term:
        return
    matched = get_playbook(term)
    if matched is not None:
        st.session_state["reg_topic"] = matched.id
        st.session_state["reg_query"] = ""
    else:
        st.session_state["reg_topic"] = None
        st.session_state["reg_query"] = term
    st.rerun()


# ════════════════════════════════════════════════════════════════
# 이번 달 동향
# ════════════════════════════════════════════════════════════════


def _render_trend_strip():
    changes = [(pb, c) for pb in PLAYBOOKS for c in pb.recent_changes]
    kinds = Counter(c.kind for _, c in changes)
    cols = st.columns(3)
    cols[0].metric("시행", kinds.get("시행", 0))
    cols[1].metric("개정 예고", kinds.get("개정 예고", 0))
    cols[2].metric("행정 예고 (의견수렴)", kinds.get("행정 예고", 0))
    st.caption("출처: 규제 캘린더 / law.go.kr 시행일 (자동 수집) — 주제 플레이북 기준")
    for pb, c in sorted(changes, key=lambda t: t[1].date):
        line = f"**{c.kind}** · {c.date} — {c.summary}  _(주제: {pb.topic})_"
        if c.url:
            line += f"  [원문 ↗]({c.url})"
        st.caption(line)


# ════════════════════════════════════════════════════════════════
# 시나리오 뷰 (브리핑)
# ════════════════════════════════════════════════════════════════


def _badge(text: str, fg: str, bg: str) -> str:
    return (
        f"<span style='font-size:12px;font-weight:500;padding:2px 10px;"
        f"border-radius:8px;background:{bg};color:{fg};'>{text}</span>"
    )


def _render_playbook(pb: TopicPlaybook):
    """레퍼런스 파인더 — 주제의 적용 법령·고시·가이드라인·참고문서를 찾아 보여준다.
    (업무 처리용 체크리스트·이슈·SOP·실사질문·보고기한은 이 페이지에서 다루지 않는다.)"""
    verified = bool(pb.last_reviewed_by)
    ver_badge = (
        _badge(f"✅ 검증 · {pb.last_reviewed_by}", "#0F6E56", "#E1F5EE")
        if verified
        else _badge("⚠ QA 검증 전 초안", "#854F0B", "#FAEEDA")
    )

    st.markdown(f"### {pb.topic}")
    st.markdown(ver_badge, unsafe_allow_html=True)

    # 개요
    overview = pb.overview or pb.summary
    if overview:
        st.markdown("**개요**")
        st.info(overview)

    unverified = pb.unverified_items()
    if unverified:
        st.warning(
            "⚠️ 사람 검증 전(AI 초안) 항목 있음 — 사용 전 확인 필요:\n\n"
            + "\n".join(f"- {u}" for u in unverified)
        )

    laws = [r for r in pb.reg_refs if r.tier in (SourceTier.LAW, SourceTier.INTERNAL)]
    notices = [r for r in pb.reg_refs if r.tier == SourceTier.NOTICE]
    guides = [r for r in pb.reg_refs if r.tier == SourceTier.GUIDE]

    if laws:
        st.markdown("#### ⚖️ 법적 근거 (법령)")
        for ref in laws:
            _render_ref_card(ref)

    if notices:
        st.markdown("#### 📋 관련 고시")
        for ref in notices:
            _render_ref_card(ref)

    if guides:
        st.markdown("#### 📘 가이드라인")
        st.caption("법적 의무는 아니나 인증·실사 시 적용되는 국제/국내 가이드라인 요지.")
        for ref in guides:
            _render_ref_card(ref)

    # 🔎 law.go.kr 관련 법령·고시 더 찾기 (on-demand 버튼)
    st.markdown("#### 🔎 law.go.kr 에서 관련 법령·고시 더 찾기")
    q = pb.web_query or pb.topic
    done_key = f"reg_live_done_{pb.id}"
    if st.button(f"🔍 '{q}' 관련 법령·고시 검색", key=f"reg_live_{pb.id}"):
        st.session_state[done_key] = True
    if st.session_state.get(done_key):
        _render_live_law(q)

    if pb.recent_changes:
        st.markdown("#### 📅 최근·예정 개정")
        for c in pb.recent_changes:
            msg = f"**{c.kind}** · {c.date} — {c.summary}"
            if c.url:
                msg += f"  [원문 ↗]({c.url})"
            st.warning(msg)

    st.markdown("#### 📄 참고 사이트·문서")
    if pb.reference_links:
        for rl in pb.reference_links:
            src = f" · {rl.source}" if rl.source else ""
            tag = "" if rl.provenance.is_verified else "  ⚠ 확인 필요"
            st.markdown(f"- 📄 [{rl.title}]({rl.url}){src}{tag}")
            if rl.note:
                st.caption(rl.note)
    else:
        st.caption("등록된 참고 문서가 없습니다.")

    _render_web_aux(pb)

    st.divider()
    st.caption("⚠️ 사람 검토 필요 — 고객 제출·실사 대응 전 담당자(QA·법무) 확인.")


def _current_ip() -> str:
    """현재 공인 IP (law.go.kr IP 등록 안내용). 실패 시 빈 문자열."""
    try:
        import requests
        return requests.get("https://api.ipify.org", timeout=3).text.strip()
    except Exception:  # noqa: BLE001
        return ""


def _render_live_law(query: str):
    """law.go.kr 실시간 — 법령 + 행정규칙. 막히면 IP 등록 안내(현재 공인 IP 표시)."""
    connector = LawGoKrConnector()
    if not connector.is_available():
        st.caption("ℹ️ `LAW_GO_KR_API_KEY` 미설정 — .env 에 발급 ID 를 넣으면 자동 활성화.")
        return

    with st.spinner("law.go.kr 조회 중..."):
        records = list(connector.search_laws(query, max_results=8))
        try:
            records += list(connector.search_admrules(query, max_results=8))
        except Exception:  # noqa: BLE001
            pass

    seen, uniq = set(), []
    for r in records:
        if r.id in seen:
            continue
        seen.add(r.id)
        uniq.append(r)

    if uniq:
        st.success(f"law.go.kr {len(uniq)}건 — 공식 법령·고시 (원문 직링크)")
        for rec in uniq:
            tier = rec.tier if isinstance(rec.tier, SourceTier) else SourceTier.LAW
            label, _ = TIER_LABEL[tier]
            st.markdown(f"- {label} **{rec.title}**")
            cap = rec.summary or ""
            if rec.url:
                cap += f"  ·  [원문 보기]({rec.url})"
            if cap.strip():
                st.caption(cap)
        return

    # 결과 없음 → IP 차단 가능성 안내
    ip = _current_ip()
    st.warning(
        "결과가 없거나 **law.go.kr 인증이 막혔을 수 있어요.**\n\n"
        + (f"현재 공인 IP: **{ip}**\n\n" if ip else "")
        + "유동 IP 가 바뀌면 차단됩니다 → open.law.go.kr 마이페이지 → 신청 수정 → "
        "**서버 IP주소**에 위 IP 를 추가 등록하세요."
    )


def _render_ref_card(ref):
    label, _ = TIER_LABEL[ref.tier]
    fg, bg = _TIER_HEX.get(ref.tier, ("#5F5E5A", "#F1EFE8"))
    sole = (
        _badge("단독 인용 가능", "#0F6E56", "#E1F5EE")
        if ref.can_be_sole_basis
        else _badge("참고용", "#5F5E5A", "#F1EFE8")
    )
    with st.container(border=True):
        st.markdown(_badge(label, fg, bg) + " &nbsp; " + sole, unsafe_allow_html=True)
        st.markdown(f"**{ref.title}**")
        meta = ref.article
        if ref.effective_date:
            meta += f" · 시행 {ref.effective_date}"
        if meta.strip():
            st.caption(meta)
        if ref.key_points:
            for kp in ref.key_points:
                st.markdown(f"- {kp}")
        if ref.url:
            st.link_button("🔗 원문 보기 (직접 이동)", ref.url)
        else:
            st.caption("🔒 사내 문서 (원문 링크 없음)")


def _render_web_aux(pb: TopicPlaybook):
    """참고(웹) — 수집된 뉴스(news.repo)에서 키워드 매칭. NEWS 등급(보조, 단독 불가)."""
    st.markdown("**참고 (웹) · 🟡 확인 필요**")
    st.caption("뉴스·웹 자료는 배경 컨텍스트용 — 규정 위반 판단의 단독 근거로 사용 불가.")

    terms = []
    if pb.web_query:
        terms += pb.web_query.split()
    terms += pb.aliases[:2]
    seen_t, clean_terms = set(), []
    for t in terms:
        t = t.strip()
        if len(t) >= 2 and t not in seen_t:
            seen_t.add(t)
            clean_terms.append(t)
    clean_terms = clean_terms[:4]

    items, seen = [], set()
    try:
        from data_layer.news import repo
        for t in clean_terms:
            for it in repo.list_items(text_search=t, limit=5, days=180):
                if it.id in seen:
                    continue
                seen.add(it.id)
                items.append(it)
            if len(items) >= 5:
                break
    except Exception:
        items = []

    if not items:
        st.caption("최근 수집된 관련 뉴스가 없습니다. ‘뉴스 모니터링’에서 수집하면 여기에 표시됩니다.")
        return
    for it in items[:5]:
        when = f" · {it.published_at[:10]}" if it.published_at else ""
        label = getattr(it, "source_label", "") or it.source
        st.markdown(f"- [{it.title}]({it.url}) · {label}{when}")


# ════════════════════════════════════════════════════════════════
# 보조 경로 — 키워드 검색 + law.go.kr 실시간
# ════════════════════════════════════════════════════════════════


def _render_keyword_results(query: str):
    st.markdown(f"#### 🔍 키워드 검색 — '{query}'")
    st.caption("주제 플레이북에 없는 항목은 여기서 원문 단위로 검색됩니다.")

    result = search(query)
    if result.total:
        st.success(f"로컬 시드 {result.total}건")
        for entry in result.entries:
            label, _ = TIER_LABEL[entry.grade]
            with st.container(border=True):
                st.markdown(f"**{label} {entry.title}**")
                meta = entry.article
                if entry.effective_date:
                    meta += f" · 시행 {entry.effective_date}"
                st.caption(meta)
                with st.expander("원문 근거 보기"):
                    st.code(entry.content, language=None)
                if entry.practical_interpretation:
                    st.info(entry.practical_interpretation)
                _real = getattr(entry, "url", None)
                if _real:
                    st.link_button("🔗 원문 보기", _real)
    else:
        st.info(f"'{query}' — 로컬 시드에는 매칭이 없습니다. 아래 law.go.kr 실시간 결과를 확인하세요.")

    # law.go.kr 실시간 (법령 + 행정규칙)
    st.markdown("---")
    st.subheader("📡 law.go.kr 실시간 검색")
    connector = LawGoKrConnector()
    if not connector.is_available():
        st.caption("ℹ️ `LAW_GO_KR_API_KEY` 미설정 — .env 에 발급 ID 를 넣으면 자동 활성화.")
        return

    with st.spinner("law.go.kr 법령·행정규칙 조회 중..."):
        records = list(connector.search_laws(query, max_results=10))
        try:
            records += list(connector.search_admrules(query, max_results=10))
        except Exception:  # noqa: BLE001
            pass

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
            st.markdown(f"**{label} {rec.title}**")
            st.caption(f"🔗 출처 {rec.source or 'law.go.kr'} · {rec.summary or '—'}")
            if rec.url:
                st.link_button("🔗 원문 보기", rec.url)
