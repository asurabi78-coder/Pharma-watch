"""SOP 자동비교 — 내부 SOP 가 규제 요구사항을 어디까지 충족하는지 갭 점검.

결정론적 엔진(engines.sop_compare)으로 절 단위 충족/부분/미흡을 판정한다.
선택적으로 Claude 가 '미흡' 절에 대해 보완 문구를 제안한다(.env 키 있을 때만).

이 기능은 점검 보조이며 최종 판단은 QA 담당자 몫이다.
"""
import streamlit as st

import branding
from engines import sop_compare as sc


def _status_badge(status: str) -> str:
    m = {
        "covered": ("✅ 충족", "#0F6E56", "#E1F5EE"),
        "partial": ("🟠 부분", "#854F0B", "#FAEEDA"),
        "missing": ("🔴 미흡", "#A32D2D", "#FCEBEB"),
    }
    label, fg, bg = m.get(status, ("—", "#5F5E5A", "#F1EFE8"))
    return (
        f"<span style='font-size:12px;font-weight:600;padding:2px 9px;"
        f"border-radius:8px;background:{bg};color:{fg};'>{label}</span>"
    )


def _load_seed():
    try:
        from data_layer.regulatory.seed import SEED_ENTRIES
        return list(SEED_ENTRIES)
    except Exception:
        return []


def render():
    st.title("SOP 자동비교")
    st.caption(
        "내부 SOP 를 규제 요구사항과 절(clause) 단위로 비교해 충족·부분·미흡을 점검합니다. "
        "(결정론적 점검 보조 — 최종 판단은 QA 담당자)"
    )

    seed = _load_seed()
    seed_titles = [e.title for e in seed]

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### ① 비교할 규제")
        mode = st.radio(
            "규제 원문 소스",
            ["시드 규제에서 선택", "직접 붙여넣기"],
            horizontal=True,
            key="sopc_mode",
        )
        reg_text = ""
        reg_title = "규제 원문"
        if mode == "시드 규제에서 선택" and seed:
            idx = st.selectbox(
                "규제 선택",
                options=list(range(len(seed))),
                format_func=lambda i: seed_titles[i],
                key="sopc_seed_idx",
            )
            entry = seed[idx]
            reg_text = entry.content or ""
            reg_title = entry.title
            with st.expander("규제 원문 보기", expanded=False):
                st.code(reg_text, language=None)
        else:
            reg_text = st.text_area(
                "규제 원문 붙여넣기",
                height=200,
                placeholder="요구사항이 담긴 규제·고시 원문을 붙여넣으세요 (번호 목록이면 더 정확).",
                key="sopc_reg_text",
            )

    with col_r:
        st.markdown("#### ② 우리 SOP")
        sop_text = st.text_area(
            "내부 SOP 텍스트",
            height=260,
            placeholder="점검할 내부 SOP 본문을 붙여넣으세요.",
            key="sopc_sop_text",
        )

    if st.button("🔍 갭 분석 실행", type="primary", key="sopc_run"):
        if not reg_text.strip() or not sop_text.strip():
            st.warning("규제 원문과 SOP 텍스트를 모두 입력하세요.")
        else:
            res = sc.compare(reg_text, sop_text, reg_title=reg_title)
            st.session_state["sopc_result"] = res
            st.session_state["sopc_sop_cache"] = sop_text
            # 사용량 기록
            try:
                from data_layer import usage as _usage
                from ui.auth import current_user as _cur
                _usage.log_action(_cur(), "sop_compare", "갭분석",
                                  f"{reg_title[:40]} · {res.score}점")
            except Exception:
                pass

    res = st.session_state.get("sopc_result")
    if res:
        _render_result(res)

    st.markdown("---")
    st.caption(branding.FOOTER_NOTE)


def _render_result(res):
    st.markdown("---")
    st.markdown(f"### 결과 — {res.reg_title}")

    m = st.columns(4)
    m[0].metric("적합도 점수", f"{res.score}/100")
    m[1].metric("✅ 충족", res.covered)
    m[2].metric("🟠 부분", res.partial)
    m[3].metric("🔴 미흡", res.missing)

    st.progress(res.score / 100)
    if res.score >= 80:
        st.success("대체로 충족 — 부분/미흡 항목만 보완하면 됩니다.")
    elif res.score >= 50:
        st.warning("절반 수준 충족 — 미흡 항목 보완이 필요합니다.")
    else:
        st.error("충족도가 낮습니다 — SOP 보완이 시급합니다.")

    st.markdown("#### 요구사항별 점검")
    for i, c in enumerate(res.clauses, 1):
        with st.container(border=True):
            top = st.columns([8, 2])
            with top[0]:
                st.markdown(f"**{i}. {c.clause}**")
            with top[1]:
                st.markdown(_status_badge(c.status), unsafe_allow_html=True)
            cap = f"매칭률 {int(c.coverage*100)}% · "
            if c.matched:
                cap += "근거: " + ", ".join(c.matched)
            else:
                cap += "SOP 에서 관련 표현을 찾지 못함"
            st.caption(cap)

    missing = [c for c in res.clauses if c.status in ("missing", "partial")]
    if missing:
        st.markdown("#### 🔴 보완 필요 항목")
        for c in missing:
            st.markdown(f"- {c.clause}")

        # 선택적 Claude 보완 문구 제안
        if st.button("✍️ 미흡 항목 보완 문구 제안 (Claude)", key="sopc_suggest"):
            _suggest_fixes(res, missing)


def _suggest_fixes(res, missing):
    try:
        from utils.claude_client import call_claude
    except Exception:
        st.info("Claude 보완 제안은 .env 의 ANTHROPIC_API_KEY 설정 시 사용 가능합니다.")
        return
    sop = st.session_state.get("sopc_sop_cache", "")
    bullet = "\n".join(f"- {c.clause}" for c in missing)
    system = (
        "당신은 의약품 유통품질(KGSP/GDP) QA 문서 작성 보조자입니다. "
        "주어진 '미흡 요구사항'을 충족하도록 내부 SOP 에 추가할 문장을 한국어로 제안하세요. "
        "각 항목마다 SOP 에 바로 넣을 수 있는 1~2문장의 구체적 절차 문구를 작성합니다. "
        "법적 단정·의사결정은 하지 말고, 마지막에 'QA 검토 필요' 한 줄을 덧붙입니다."
    )
    user = f"[규제] {res.reg_title}\n\n[미흡 요구사항]\n{bullet}\n\n[현재 SOP 발췌]\n{sop[:1500]}"
    with st.spinner("보완 문구 생성 중…"):
        try:
            out = call_claude(system=system,
                              messages=[{"role": "user", "content": user}],
                              max_tokens=800, feature="sop_compare")
            st.markdown("#### 제안된 보완 문구")
            st.markdown(out)
        except Exception as e:  # noqa: BLE001
            st.error("Claude 호출 실패 — .env 의 ANTHROPIC_API_KEY 를 확인하세요.")
            st.caption(f"detail: {type(e).__name__}: {e}")
