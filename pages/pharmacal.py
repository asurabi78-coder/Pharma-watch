"""규제 캘린더 (PharmaCal) — QA 의 관제탑.

v2: 정적 HTML 임베드 제거 → 데이터 기반 네이티브 재구축.
  - 세 트랙: 외부 규제(자동) · KGSP 의무(프로필 기반 자동) · 사내 일정(직접 등록)
  - 회사 프로필 기반 임팩트 스코어링 (우리 직결=🔴 / 일반=🟠 / 참고=⚪)
  - 일정별 상태(예정/조치필요/완료) + 메모
  - 규제 일정 → SOP 자동비교 / 개정 영향분석 / 사내 공유문 초안 연결
"""
import calendar as _cal
from datetime import datetime, timedelta

import streamlit as st

import branding
from data_layer import calendar_repo as repo
from data_layer import company_profile as profile_mod

_IMPACT_DOT = {"high": "🔴", "mid": "🟠", "low": "⚪"}
_TRACK_BADGE = {"external": "📋 외부 규제", "duty": "🔁 KGSP 의무", "internal": "🏢 사내 일정"}
_KIND_OPTIONS = ["감사", "실태조사", "교육", "제출 마감", "기타"]


def _display_impact(ev, profile) -> str:
    if ev.track == "external":
        return profile_mod.score_impact(ev.tags, ev.impact, profile)
    return ev.impact


def render():
    st.title("규제 캘린더")
    st.caption(
        "외부 규제 · KGSP 의무 · 사내 일정을 한곳에서 — 놓치면 임팩트 큰 마감을 "
        "미리 알려주는 QA 관제탑입니다."
    )

    profile = profile_mod.load_profile()

    # ---- 자동 유입 (세션당 1회 — upsert 라 중복 없음)
    if not st.session_state.get("_cal_synced"):
        try:
            repo.sync_external()
            repo.ensure_duties(profile)
        except Exception:
            pass
        st.session_state["_cal_synced"] = True

    # ---- 회사 프로필
    with st.expander("🏢 회사 프로필 — 우리 회사 직결 규제만 강조됩니다", expanded=False):
        with st.form("cal_profile"):
            c1, c2 = st.columns(2)
            with c1:
                company = st.text_input("회사명", value=profile.get("company", ""))
                handles = st.multiselect(
                    "취급 유형", profile_mod.HANDLE_OPTIONS,
                    default=[h for h in profile.get("handles", [])
                             if h in profile_mod.HANDLE_OPTIONS],
                )
            with c2:
                si_month = st.number_input("자체점검 실시 월", 1, 12,
                                           int(profile.get("self_inspection_month", 11)))
                mp_month = st.number_input("온도 매핑 재검증 월", 1, 12,
                                           int(profile.get("mapping_month", 6)))
            if st.form_submit_button("저장", type="primary"):
                profile = {
                    "company": company, "handles": handles or ["상온 의약품"],
                    "self_inspection_month": int(si_month),
                    "mapping_month": int(mp_month),
                }
                profile_mod.save_profile(profile)
                try:
                    repo.ensure_duties(profile)
                except Exception:
                    pass
                st.success("저장됨 — 취급 유형에 맞춰 의무 일정과 강조가 갱신됩니다.")
                st.rerun()

    # ---- 월 내비게이션 + 트랙 필터
    now = datetime.now()
    ym = st.session_state.setdefault("cal_ym", [now.year, now.month])
    nav = st.columns([1, 1, 3, 5])
    with nav[0]:
        if st.button("◀ 이전", key="cal_prev", use_container_width=True):
            ym[1] -= 1
            if ym[1] < 1:
                ym[0], ym[1] = ym[0] - 1, 12
            st.rerun()
    with nav[1]:
        if st.button("다음 ▶", key="cal_next", use_container_width=True):
            ym[1] += 1
            if ym[1] > 12:
                ym[0], ym[1] = ym[0] + 1, 1
            st.rerun()
    with nav[2]:
        st.markdown(f"### {ym[0]}년 {ym[1]}월")
    with nav[3]:
        tcols = st.columns(3)
        show_ext = tcols[0].checkbox("📋 외부 규제", value=True, key="cal_t_ext")
        show_duty = tcols[1].checkbox("🔁 KGSP 의무", value=True, key="cal_t_duty")
        show_int = tcols[2].checkbox("🏢 사내 일정", value=True, key="cal_t_int")

    tracks = [t for t, on in
              [("external", show_ext), ("duty", show_duty), ("internal", show_int)] if on]

    # ---- 이번 달 이벤트
    year, month = ym
    last_day = _cal.monthrange(year, month)[1]
    month_events = repo.list_range(
        f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}",
        tracks=tracks or None,
    )
    by_day: dict = {}
    for ev in month_events:
        by_day.setdefault(int(ev.date[8:10]), []).append(ev)

    # ---- 월 그리드 (HTML)
    st.markdown(_month_grid_html(year, month, by_day, profile, now),
                unsafe_allow_html=True)

    # ---- 날짜 상세 — 날짜를 고르면 그날 일정의 세부 내용·관련 법령 표시
    st.markdown("#### 🔍 날짜 상세")
    from datetime import date as _date
    sel_default = now.date() if (now.year == year and now.month == month) \
        else _date(year, month, 1)
    sel = st.date_input("날짜 선택", value=sel_default, key="cal_detail_date",
                        label_visibility="collapsed")
    sel_str = sel.strftime("%Y-%m-%d")
    day_evs = repo.list_range(sel_str, sel_str, tracks=tracks or None)
    if not day_evs:
        st.caption(f"{sel_str} — 일정 없음")
    else:
        for ev in day_evs:
            _event_card(ev, profile, prefix="d", show_detail=True)

    st.markdown("---")
    col_l, col_r = st.columns([6, 4])

    # ---- 좌: 다가오는 마감 (D-30, 액션 중심)
    with col_l:
        st.markdown("#### ⏰ 다가오는 마감 (30일)")
        ups = [e for e in repo.upcoming(30) if e.track in (tracks or
               ["external", "duty", "internal"])]
        ups = [e for e in ups if e.status != "done"]
        # 조치필요 우선 → 임박순
        ups.sort(key=lambda e: (0 if e.status == "action" else 1, e.date))
        if not ups:
            st.success("향후 30일 내 미처리 마감 없음")
        for ev in ups[:15]:
            _event_card(ev, profile)

    # ---- 우: 사내 일정 등록
    with col_r:
        st.markdown("#### ➕ 사내 일정 등록")
        with st.form("cal_add", clear_on_submit=True):
            d = st.date_input("날짜", value=now)
            title = st.text_input("일정명", placeholder="예: 식약처 실태조사, 내부 감사")
            kind = st.selectbox("유형", _KIND_OPTIONS)
            impact = st.select_slider("중요도", ["low", "mid", "high"], value="high",
                                      format_func=lambda v: {"low": "참고", "mid": "보통",
                                                             "high": "중요"}[v])
            memo = st.text_input("메모 (선택)")
            if st.form_submit_button("등록", type="primary"):
                if title.strip():
                    repo.add_manual(d.strftime("%Y-%m-%d"), title.strip(),
                                    kind=kind, impact=impact, memo=memo.strip())
                    st.success(f"등록됨 — {title}")
                    st.rerun()
                else:
                    st.warning("일정명을 입력하세요.")

        done_cnt = sum(1 for e in month_events if e.status == "done")
        st.caption(f"이번 달 일정 {len(month_events)}건 · 완료 {done_cnt}건")

    st.markdown("---")
    st.caption(branding.FOOTER_NOTE)


# ---------------------------------------------------------------- 월 그리드

def _month_grid_html(year, month, by_day, profile, now) -> str:
    cal = _cal.Calendar(firstweekday=6)  # 일요일 시작
    weeks = cal.monthdayscalendar(year, month)
    today_d = now.day if (now.year == year and now.month == month) else -1

    head = "".join(
        f"<th style='padding:6px;color:{c};font-size:12px;'>{w}</th>"
        for w, c in [("일", "#c44"), ("월", "#666"), ("화", "#666"), ("수", "#666"),
                     ("목", "#666"), ("금", "#666"), ("토", "#46c")]
    )
    rows = []
    for week in weeks:
        tds = []
        for day in week:
            if day == 0:
                tds.append("<td style='border:1px solid #eee;'></td>")
                continue
            is_today = (day == today_d)
            bg = "#FFF8E1" if is_today else "#fff"
            chips = ""
            for ev in by_day.get(day, [])[:3]:
                imp = _display_impact(ev, profile)
                dot = _IMPACT_DOT.get(imp, "🟠")
                strike = "text-decoration:line-through;opacity:.5;" \
                    if ev.status == "done" else ""
                chips += (f"<div style='font-size:10.5px;{strike}margin-top:2px;"
                          f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>"
                          f"{dot} {ev.title[:18]}</div>")
            more = len(by_day.get(day, [])) - 3
            if more > 0:
                chips += f"<div style='font-size:10px;color:#999;'>+{more}건</div>"
            num_style = ("background:#E8590C;color:#fff;border-radius:50%;"
                         "padding:1px 6px;" if is_today else "color:#444;")
            tds.append(
                f"<td style='border:1px solid #eee;vertical-align:top;"
                f"padding:4px;height:74px;background:{bg};'>"
                f"<span style='font-size:12px;font-weight:600;{num_style}'>{day}</span>"
                f"{chips}</td>"
            )
        rows.append("<tr>" + "".join(tds) + "</tr>")

    return (
        "<table style='width:100%;border-collapse:collapse;table-layout:fixed;"
        "background:#fff;border:1px solid #ddd;border-radius:8px;'>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        "<div style='font-size:11px;color:#888;margin:6px 0 14px 2px;'>"
        "🔴 우리 회사 직결 · 🟠 일반 · ⚪ 참고(미취급 유형) · 취소선 = 완료</div>"
    )


# ---------------------------------------------------------------- 이벤트 카드

def _event_card(ev, profile, *, prefix: str = "", show_detail: bool = False):
    imp = _display_impact(ev, profile)
    dot = _IMPACT_DOT.get(imp, "🟠")
    try:
        dleft = (datetime.strptime(ev.date, "%Y-%m-%d").date()
                 - datetime.now().date()).days
        dtxt = "오늘" if dleft == 0 else f"D-{dleft}"
    except ValueError:
        dtxt = ""
    badge = _TRACK_BADGE.get(ev.track, "")

    with st.container(border=True):
        top = st.columns([8, 2])
        with top[0]:
            st.markdown(f"{dot} **{ev.title}**")
            st.caption(f"{ev.date} ({dtxt}) · {badge}"
                       + (f" · {ev.memo}" if ev.memo else ""))
        with top[1]:
            st.markdown(f"**{dtxt}**")

        ctl = st.columns([3, 3, 2, 2])
        with ctl[0]:
            cur = ev.status if ev.status in repo.STATUS_LABEL else "todo"
            new_status = st.selectbox(
                "상태", list(repo.STATUS_LABEL),
                index=list(repo.STATUS_LABEL).index(cur),
                format_func=lambda s: repo.STATUS_LABEL[s],
                key=f"cal{prefix}_st_{ev.id}", label_visibility="collapsed",
            )
            if new_status != ev.status:
                repo.update_event(ev.id, status=new_status)
                st.rerun()
        with ctl[1]:
            memo = st.text_input("메모", value=ev.memo, key=f"cal{prefix}_memo_{ev.id}",
                                 label_visibility="collapsed", placeholder="메모…")
            if memo != ev.memo:
                repo.update_event(ev.id, memo=memo)
        with ctl[2]:
            if ev.track == "external" and ev.ref_id:
                if st.button("📑 SOP 비교", key=f"cal{prefix}_sop_{ev.id}",
                             use_container_width=True):
                    _goto_sop_compare(ev.ref_id)
        with ctl[3]:
            if ev.track == "internal":
                if st.button("🗑️", key=f"cal{prefix}_del_{ev.id}",
                             use_container_width=True):
                    repo.delete_event(ev.id)
                    st.rerun()
            elif ev.track == "external":
                if st.button("📢 공유문", key=f"cal{prefix}_share_{ev.id}",
                             use_container_width=True):
                    st.session_state["cal_share_target"] = (prefix, ev.id)

        # 세부 내용 · 관련 법령
        if show_detail or ev.track == "external":
            _detail_expander(ev, prefix)

        # 공유문 초안 패널
        if st.session_state.get("cal_share_target") == (prefix, ev.id):
            _share_panel(ev, profile, prefix)


def _goto_sop_compare(ref_id: str):
    """규제 일정 → SOP 자동비교 (해당 규제 미리 선택)."""
    try:
        from data_layer.regulatory.seed import SEED_ENTRIES
        idx = next((i for i, e in enumerate(SEED_ENTRIES) if e.id == ref_id), None)
        if idx is not None:
            st.session_state["sopc_seed_idx"] = idx
            st.session_state["sopc_mode"] = "시드 규제에서 선택"
    except Exception:
        pass
    st.session_state.setdefault("nav_history", []).append("pharmacal")
    st.session_state.page = "sop_compare"
    st.rerun()


def _detail_expander(ev, prefix: str = ""):
    """세부 내용 · 관련 법령 — 시드 규제는 원문·실무해석, 그 외는 주제·검색 링크."""
    from urllib.parse import quote
    entry = None
    if ev.ref_id:
        try:
            from data_layer.regulatory.seed import SEED_ENTRIES
            entry = next((e for e in SEED_ENTRIES if e.id == ev.ref_id), None)
        except Exception:
            entry = None

    with st.expander("📖 세부 내용 · 관련 법령"):
        if entry is not None:
            meta = " · ".join(x for x in [entry.article, entry.source] if x)
            if meta:
                st.caption(meta)
            st.markdown("**규제 원문**")
            st.code(entry.content or "(원문 없음)", language=None)
            if entry.practical_interpretation:
                st.markdown("**실무 해석**")
                st.info(entry.practical_interpretation)
            query = entry.title.split("—")[0].strip()
        else:
            if ev.tags:
                st.caption("관련 주제: " + ", ".join(str(t) for t in ev.tags))
            st.markdown(f"**{ev.title}**")
            st.caption("플레이북(주제별 변경 추적) 항목 — 상세 원문은 법령 검색으로 확인하세요.")
            query = (ev.title.replace("개정 예고", "").replace("행정 예고", "")
                     .replace("시행", "").strip(" ·"))[:30]

        st.markdown(
            f"[🔗 law.go.kr 에서 관련 법령 검색]"
            f"(https://www.law.go.kr/lsSc.do?menuId=1&subMenuId=15&query={quote(query)})"
            f"  ·  [🔗 식약처 고시·행정예고]"
            f"(https://www.mfds.go.kr/brd/m_207/list.do)"
        )


def _share_panel(ev, profile, prefix: str = ""):
    from engines.notice_gen import draft_notice
    key = f"cal{prefix}_share_text_{ev.id}"
    if key not in st.session_state:
        st.session_state[key] = draft_notice(
            ev.title, ev.date, company=profile.get("company", ""),
            ref_id=ev.ref_id, use_claude=False)
    st.markdown("**📢 사내 공유문 초안** (발송 전 QA 검토 필요)")
    txt = st.text_area("공유문", value=st.session_state[key], height=260,
                       key=f"{key}_edit", label_visibility="collapsed")
    b = st.columns([2, 2, 6])
    with b[0]:
        st.download_button("⬇️ 텍스트 저장", data=txt,
                           file_name=f"사내공유문_{ev.date}.txt",
                           key=f"{key}_dl")
    with b[1]:
        if st.button("✨ Claude 다듬기", key=f"{key}_ai"):  # noqa: SIM102
            st.session_state[key] = draft_notice(
                ev.title, ev.date, company=profile.get("company", ""),
                ref_id=ev.ref_id, use_claude=True)
            st.rerun()
