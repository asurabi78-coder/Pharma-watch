"""개정 영향분석 — 규제가 바뀌면 '우리 SOP 가 어떻게 부적합해졌는지' 자동 감지.

① SOP 보관함: 내부 SOP 를 등록해두면 영향분석의 대상이 된다.
② 변경 스캔: 현재 규제 원문을 마지막 확인본과 비교 → 변경 감지 시
   보관함의 모든 SOP 에 갭분석을 자동 재실행 → 영향 리포트 생성.
③ 리포트: 점수 변동·새로 미흡해진 절을 보여주고, 선택적으로 Claude 가
   보완 문구를 제안한다 (.env 키 있을 때만).

결정론적 점검 보조 — 최종 판단은 QA 담당자.
"""
import streamlit as st

import branding
from data_layer import sop_vault as vault
from engines import impact_engine as ie


def _user() -> str:
    try:
        from ui.auth import current_user
        return current_user() or "(local)"
    except Exception:
        return "(local)"


def _log(action: str, detail: str = "") -> None:
    try:
        from data_layer import usage as _usage
        _usage.log_action(_user(), "impact", action, detail[:80])
    except Exception:
        pass


def render():
    st.title("개정 영향분석")
    st.caption(
        "규제 원문이 바뀌면 보관함의 SOP 전체에 갭분석을 자동 재실행해, "
        "'이번 개정으로 무엇이 부적합해졌는지'를 알려줍니다. "
        "(결정론적 점검 보조 — 최종 판단은 QA 담당자)"
    )

    user = _user()

    tab_reports, tab_vault, tab_scan = st.tabs(
        ["⚠️ 영향 리포트", "📁 SOP 보관함", "🔄 변경 스캔"]
    )

    with tab_vault:
        _render_vault(user)
    with tab_scan:
        _render_scan(user)
    with tab_reports:
        _render_reports(user)

    st.markdown("---")
    st.caption(branding.FOOTER_NOTE)


# ---------------------------------------------------------------- SOP 보관함

def _render_vault(user: str):
    st.markdown("#### SOP 등록")
    st.caption("여기에 등록된 SOP 만 자동 영향분석 대상이 됩니다.")

    with st.form("impact_add_sop", clear_on_submit=True):
        title = st.text_input("SOP 제목", placeholder="예: 보관관리 SOP v1.2")
        body = st.text_area("SOP 본문", height=220,
                            placeholder="내부 SOP 본문을 붙여넣으세요.")
        if st.form_submit_button("등록", type="primary"):
            if not title.strip() or not body.strip():
                st.warning("제목과 본문을 모두 입력하세요.")
            else:
                vault.add_sop(title, body, user=user)
                _log("sop_add", title)
                st.success(f"등록됨 — {title}")
                st.rerun()

    sops = vault.list_sops(user=user)
    st.markdown(f"#### 보관함 ({len(sops)}건)")
    if not sops:
        st.info("등록된 SOP 가 없습니다. 위에서 등록하면 개정 시 자동으로 점검됩니다.")
        return

    for s in sops:
        with st.container(border=True):
            top = st.columns([7, 2, 1])
            with top[0]:
                st.markdown(f"**{s.title}**")
                st.caption(f"등록 {s.created_at} · 수정 {s.updated_at} · {len(s.body)}자")
            with top[1]:
                with st.expander("본문"):
                    st.code(s.body[:3000], language=None)
            with top[2]:
                if st.button("🗑️", key=f"impact_del_{s.id}", help="삭제"):
                    vault.delete_sop(s.id, user=user)
                    _log("sop_delete", s.title)
                    st.rerun()


# ---------------------------------------------------------------- 변경 스캔

def _render_scan(user: str):
    snap_n = vault.snapshot_count()
    sop_n = len(vault.list_sops(user=None))

    c = st.columns(3)
    c[0].metric("스냅샷(기준선) 규제", snap_n)
    c[1].metric("보관함 SOP (전체)", sop_n)
    c[2].metric("미확인 리포트", vault.count_new_reports())

    if snap_n == 0:
        st.info(
            "최초 1회 스캔은 현재 규제 원문을 **기준선**으로 저장합니다. "
            "이후 스캔부터 변경을 감지해 리포트를 만듭니다."
        )

    st.caption(
        "💡 매일 자동 실행하려면 스케줄러에 `python -m scripts.daily_digest` 를 "
        "등록하세요 — 다이제스트 생성 전에 영향 스캔이 함께 돕니다."
    )

    if st.button("🔄 지금 스캔 실행", type="primary", key="impact_scan_run"):
        with st.spinner("규제 변경 감지 + SOP 영향분석 중…"):
            res = ie.run_scan()
        _log("scan", f"changes={len(res.changes)} reports={len(res.reports)}")
        st.session_state["impact_scan_result"] = res

    res = st.session_state.get("impact_scan_result")
    if not res:
        return

    st.markdown("---")
    if res.baseline:
        st.success(f"기준선 저장 완료 — 규제 {res.regs_checked}건의 현재 원문을 "
                   "스냅샷으로 보관했습니다. 다음 스캔부터 변경을 감지합니다.")
        return
    if not res.changes:
        st.success(f"규제 {res.regs_checked}건 점검 — 변경 없음. SOP 는 안전합니다.")
        return

    st.warning(f"변경 감지 {len(res.changes)}건 · SOP {res.sops_analyzed}건 분석 · "
               f"영향 리포트 {len(res.reports)}건 생성")
    for ch in res.changes:
        with st.container(border=True):
            kind = "🆕 신규" if ch.kind == "new" else "✏️ 개정"
            st.markdown(f"**{kind} — {ch.title}**")
            if ch.added_clauses:
                st.caption("추가된 요구사항:")
                for a in ch.added_clauses[:8]:
                    st.markdown(f"- 🟢 {a}")
            if ch.removed_clauses:
                st.caption("삭제된 요구사항:")
                for r in ch.removed_clauses[:8]:
                    st.markdown(f"- ⚪ ~~{r}~~")
    if res.reports:
        st.info("생성된 리포트는 **⚠️ 영향 리포트** 탭에서 확인·처리하세요.")


# ---------------------------------------------------------------- 리포트

def _render_reports(user: str):
    new_reports = vault.list_reports(user=user, status="new")
    old_reports = vault.list_reports(user=user, status="acknowledged", limit=30)

    if not new_reports and not old_reports:
        st.info(
            "아직 리포트가 없습니다. **SOP 보관함**에 SOP 를 등록하고 "
            "**변경 스캔**을 실행하세요 — 규제가 개정되면 여기에 알림이 쌓입니다."
        )
        return

    st.markdown(f"#### 미확인 ({len(new_reports)}건)")
    if not new_reports:
        st.success("미확인 리포트 없음 — 모두 처리되었습니다.")
    for r in new_reports:
        _render_report_card(r, user, ack_button=True)

    if old_reports:
        with st.expander(f"처리 완료 ({len(old_reports)}건)"):
            for r in old_reports:
                _render_report_card(r, user, ack_button=False)


def _render_report_card(r, user: str, *, ack_button: bool):
    with st.container(border=True):
        head = st.columns([7, 3])
        with head[0]:
            kind = "🆕 신규 규제" if r.change_kind == "new" else "✏️ 규제 개정"
            st.markdown(f"**{r.sop_title}** ↔ {r.reg_title}")
            st.caption(f"{kind} · {r.created_at}")
        with head[1]:
            if r.delta is not None:
                st.metric("적합도 변화", f"{r.new_score}점",
                          delta=f"{r.delta:+d}", delta_color="normal")
            else:
                st.metric("적합도", f"{r.new_score}점")

        if r.new_missing:
            st.markdown("**이번 변경으로 새로 미흡해진 절:**")
            for m in r.new_missing[:10]:
                st.markdown(f"- 🔴 {m}")

        btns = st.columns([2, 3, 5])
        with btns[0]:
            if ack_button and st.button("✅ 확인 처리", key=f"impact_ack_{r.id}"):
                vault.acknowledge_report(r.id, user=user)
                _log("ack", f"report#{r.id}")
                st.rerun()
        with btns[1]:
            if r.new_missing and st.button("✍️ 보완 문구 (Claude)",
                                           key=f"impact_fix_{r.id}"):
                _suggest_fixes(r, user)


def _suggest_fixes(r, user: str):
    try:
        from utils.claude_client import call_claude
    except Exception:
        st.info("Claude 보완 제안은 .env 의 ANTHROPIC_API_KEY 설정 시 사용 가능합니다.")
        return
    sop = vault.get_sop(r.sop_id, user=user)
    sop_body = sop.body if sop else ""
    bullet = "\n".join(f"- {m}" for m in r.new_missing)
    system = (
        "당신은 의약품 유통품질(KGSP/GDP) QA 문서 작성 보조자입니다. "
        "규제 개정으로 내부 SOP 가 충족하지 못하게 된 요구사항이 주어집니다. "
        "각 항목마다 SOP 에 바로 넣을 수 있는 1~2문장의 구체적 절차 문구를 한국어로 제안하세요. "
        "법적 단정·의사결정은 하지 말고, 마지막에 'QA 검토 필요' 한 줄을 덧붙입니다."
    )
    user_msg = (f"[개정된 규제] {r.reg_title}\n\n[새로 미흡해진 요구사항]\n{bullet}"
                f"\n\n[현재 SOP 발췌]\n{sop_body[:1500]}")
    with st.spinner("보완 문구 생성 중…"):
        try:
            out = call_claude(system=system,
                              messages=[{"role": "user", "content": user_msg}],
                              max_tokens=800, feature="impact")
            st.markdown("**제안된 보완 문구**")
            st.markdown(out)
        except Exception as e:  # noqa: BLE001
            st.error("Claude 호출 실패 — .env 의 ANTHROPIC_API_KEY 를 확인하세요.")
            st.caption(f"detail: {type(e).__name__}: {e}")
