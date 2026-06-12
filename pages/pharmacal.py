"""규제 캘린더 (PharmaCal) — QA 의 관제탑.

v2.2: v2 의 실데이터·기능(저장소·프로필·의무·상태관리) 위에
이전 PharmaCal Pro 의 화면 요소를 복원:
  - KPI 지표 카드 (이번 주 일정 · 조치필요 · 우리 직결 · 이번 달 완료율)
  - 일정 팝업(모달) — 시행일·영향도·원문·실무해석·관련 뉴스 (st.dialog 지원 시)
  - 우측 사이드 패널: AI 규제 브리핑 · D-Day 알림 · 관련 뉴스
"""
import calendar as _cal
import re
from datetime import datetime

import streamlit as st

import branding
from data_layer import calendar_repo as repo
from data_layer import company_profile as profile_mod

_IMPACT_DOT = {"high": "🔴", "mid": "🟠", "low": "⚪"}
_IMPACT_LABEL = {"high": "높음 (우리 직결)", "mid": "보통", "low": "참고"}
_TRACK_BADGE = {"external": "📋 외부 규제", "duty": "🔁 KGSP 의무", "internal": "🏢 사내 일정"}
_KIND_OPTIONS = ["감사", "실태조사", "교육", "제출 마감", "기타"]

# st.dialog — 구버전 streamlit 폴백 (없으면 인라인 표시)
_dialog = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)


def _display_impact(ev, profile) -> str:
    if ev.track == "external":
        return profile_mod.score_impact(ev.tags, ev.impact, profile)
    return ev.impact


def _dday(date_str: str) -> str:
    try:
        d = (datetime.strptime(date_str, "%Y-%m-%d").date()
             - datetime.now().date()).days
        return "오늘" if d == 0 else f"D-{d}" if d > 0 else f"D+{-d}"
    except ValueError:
        return ""


def render():
    st.title("규제 캘린더")
    st.caption(
        "외부 규제 · KGSP 의무 · 사내 일정을 한곳에서 — 놓치면 임팩트 큰 마감을 "
        "미리 알려주는 QA 관제탑입니다."
    )

    profile = profile_mod.load_profile()

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

    now = datetime.now()

    # ---- KPI 지표 카드
    ups7 = [e for e in repo.upcoming(7) if e.status != "done"]
    ups30 = [e for e in repo.upcoming(30) if e.status != "done"]
    action_n = sum(1 for e in ups30 if e.status == "action")
    direct_n = sum(1 for e in ups30 if _display_impact(e, profile) == "high")
    k = st.columns(4)
    k[0].metric("이번 주 일정", f"{len(ups7)}건")
    k[1].metric("🔴 우리 직결 (30일)", f"{direct_n}건")
    k[2].metric("⚠️ 조치필요", f"{action_n}건")
    nearest = min(ups30, key=lambda e: e.date) if ups30 else None
    k[3].metric("가장 임박", _dday(nearest.date) if nearest else "—",
                delta=nearest.title[:18] if nearest else None, delta_color="off")

    # ---- 월 내비게이션 + 트랙 필터
    ym = st.session_state.setdefault("cal_ym", [now.year, now.month])
    nav = st.columns([1, 1, 1, 2, 5])
    with nav[0]:
        if st.button("◀ 이전", key="cal_prev", use_container_width=True):
            ym[1] -= 1
            if ym[1] < 1:
                ym[0], ym[1] = ym[0] - 1, 12
            st.rerun()
    with nav[1]:
        if st.button("오늘", key="cal_today", use_container_width=True):
            ym[0], ym[1] = now.year, now.month
            st.rerun()
    with nav[2]:
        if st.button("다음 ▶", key="cal_next", use_container_width=True):
            ym[1] += 1
            if ym[1] > 12:
                ym[0], ym[1] = ym[0] + 1, 1
            st.rerun()
    with nav[3]:
        st.markdown(f"### {ym[0]}년 {ym[1]}월")
    with nav[4]:
        tcols = st.columns(3)
        show_ext = tcols[0].checkbox("📋 외부 규제", value=True, key="cal_t_ext")
        show_duty = tcols[1].checkbox("🔁 KGSP 의무", value=True, key="cal_t_duty")
        show_int = tcols[2].checkbox("🏢 사내 일정", value=True, key="cal_t_int")

    tracks = [t for t, on in
              [("external", show_ext), ("duty", show_duty), ("internal", show_int)] if on]

    year, month = ym
    last_day = _cal.monthrange(year, month)[1]
    month_events = repo.list_range(
        f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}",
        tracks=tracks or None,
    )
    by_day: dict = {}
    for ev in month_events:
        by_day.setdefault(int(ev.date[8:10]), []).append(ev)

    # ---- 본문: 캘린더(좌) + 사이드 패널(우)
    col_cal, col_side = st.columns([7, 3])

    with col_cal:
        st.markdown(_month_grid_html(year, month, by_day, profile, now),
                    unsafe_allow_html=True)

        # 날짜 상세 — 날짜를 고르면 그날 일정 + 팝업 보기
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

    with col_side:
        _ai_briefing_panel(profile)
        _dday_panel(ups30, profile)
        _news_panel()

    st.markdown("---")
    col_l, col_r = st.columns([6, 4])

    with col_l:
        st.markdown("#### ⏰ 다가오는 마감 (30일)")
        ups = [e for e in ups30 if e.track in (tracks or
               ["external", "duty", "internal"])]
        ups.sort(key=lambda e: (0 if e.status == "action" else 1, e.date))
        if not ups:
            st.success("향후 30일 내 미처리 마감 없음")
        for ev in ups[:15]:
            _event_card(ev, profile)

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


# ---------------------------------------------------------------- 사이드 패널

def _ai_briefing_panel(profile):
    """AI 규제 브리핑 — 무료(결정론적) 기본 + 선택적 Claude 보강."""
    with st.container(border=True):
        st.markdown("##### 🤖 AI 규제 브리핑")
        custom = st.session_state.get("cal_ai_brief")
        if custom:
            st.markdown(custom)
        else:
            ups = [e for e in repo.upcoming(7) if e.status != "done"]
            if not ups:
                st.caption("이번 주 마감 없음 — 다음 주 일정을 미리 점검하기 좋은 주간입니다.")
            else:
                high = [e for e in ups if _display_impact(e, profile) == "high"]
                top = (high or ups)[0]
                st.markdown(
                    f"이번 주 일정 **{len(ups)}건**, 이 중 우리 직결 **{len(high)}건**. "
                    f"최우선은 **{top.title}** ({top.date}, {_dday(top.date)}) 입니다."
                )
                if any(e.track == "duty" for e in ups):
                    st.caption("🔁 KGSP 의무 일정이 포함돼 있습니다 — 기록(교육일지·점검표)까지 챙기세요.")
        if st.button("✨ Claude 브리핑", key="cal_ai_btn", use_container_width=True):
            _make_claude_briefing(profile)
            st.rerun()


def _make_claude_briefing(profile):
    try:
        from utils.claude_client import call_claude
        ups = [e for e in repo.upcoming(14) if e.status != "done"][:10]
        listing = "\n".join(
            f"- {e.date} ({_dday(e.date)}) [{_TRACK_BADGE.get(e.track,'')}] {e.title}"
            for e in ups) or "(일정 없음)"
        handles = ", ".join(profile.get("handles", []))
        system = ("당신은 의약품 유통회사 QA 브리핑 작성자입니다. 주어진 일정만 근거로 "
                  "3~4문장의 한국어 브리핑을 쓰세요. 우선순위와 준비물(기록·증빙)을 짚고, "
                  "근거 없는 내용은 추가하지 마세요.")
        user = f"회사 취급 유형: {handles}\n\n[향후 14일 일정]\n{listing}"
        out = call_claude(system=system, messages=[{"role": "user", "content": user}],
                          max_tokens=400, feature="pharmacal")
        if out and "ANTHROPIC_API_KEY" not in out and "오류" not in out[:20]:
            st.session_state["cal_ai_brief"] = out
    except Exception:
        pass


def _dday_panel(ups30, profile):
    with st.container(border=True):
        st.markdown("##### ⏰ D-Day 알림")
        items = sorted(ups30, key=lambda e: e.date)[:5]
        if not items:
            st.caption("임박한 마감 없음")
        for e in items:
            dot = _IMPACT_DOT.get(_display_impact(e, profile), "🟠")
            st.markdown(f"{dot} **{_dday(e.date)}** · {e.title[:24]}")
            st.caption(f"{e.date} · {_TRACK_BADGE.get(e.track, '')}")


def _news_panel():
    with st.container(border=True):
        st.markdown("##### 📰 관련 뉴스 (최근 7일)")
        items = _recent_news(days=7, limit=5)
        if not items:
            st.caption("수집된 중요 뉴스 없음 — 뉴스 모니터링에서 수집을 실행하세요.")
        for n in items:
            badge = "🔴" if getattr(n, "importance", "") == "high" else "🟠"
            st.markdown(f"{badge} [{n.title}]({n.url})")
            when = (getattr(n, "published_at", "") or "")[:10]
            st.caption(f"{getattr(n, 'source_label', '')} · {when}")


def _recent_news(days=7, limit=5, query_tokens=None):
    try:
        from data_layer.news import repo as news_repo
        items = news_repo.list_items(days=days, importance_in=["high", "mid"],
                                     limit=50)
    except Exception:
        return []
    if query_tokens:
        toks = [t for t in query_tokens if len(t) >= 2]
        items = [n for n in items if any(t in (n.title or "") for t in toks)]
    return items[:limit]


# ---------------------------------------------------------------- 월 그리드

def _month_grid_html(year, month, by_day, profile, now) -> str:
    cal = _cal.Calendar(firstweekday=6)
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


# ---------------------------------------------------------------- 일정 팝업(모달)

def _event_modal_body(ev, profile):
    """이전 Pro 모달 복원 — 시행일·영향도·원문·실무해석·관련 뉴스."""
    imp = _display_impact(ev, profile)
    st.markdown(f"### {_IMPACT_DOT.get(imp,'🟠')} {ev.title}")
    r1, r2, r3 = st.columns(3)
    r1.markdown(f"**시행/기한일**  \n{ev.date} ({_dday(ev.date)})")
    r2.markdown(f"**영향도**  \n{_IMPACT_LABEL.get(imp, imp)}")
    r3.markdown(f"**구분**  \n{_TRACK_BADGE.get(ev.track, '')}")

    entry = None
    if ev.ref_id:
        try:
            from data_layer.regulatory.seed import SEED_ENTRIES
            entry = next((e for e in SEED_ENTRIES if e.id == ev.ref_id), None)
        except Exception:
            entry = None
    if entry is not None:
        meta = " · ".join(x for x in [entry.article, entry.source] if x)
        if meta:
            st.caption(meta)
        st.markdown("**규제 원문**")
        st.code(entry.content or "(원문 없음)", language=None)
        if entry.practical_interpretation:
            st.markdown("**관련 업무 (실무 해석)**")
            st.info(entry.practical_interpretation)
        query = entry.title.split("—")[0].strip()
        toks = list(entry.tags or [])[:4]
    else:
        if ev.tags:
            st.caption("관련 주제: " + ", ".join(str(t) for t in ev.tags))
        if ev.memo:
            st.markdown(f"메모: {ev.memo}")
        query = re.sub(r"(개정 예고|행정 예고|시행)", "", ev.title).strip(" ·")[:30]
        toks = re.findall(r"[가-힣A-Za-z]{2,}", ev.title)[:4]

    news = _recent_news(days=14, limit=3, query_tokens=toks)
    if news:
        st.markdown("**관련 뉴스**")
        for n in news:
            st.markdown(f"- [{n.title}]({n.url})")

    from urllib.parse import quote
    st.markdown(
        f"[🔗 law.go.kr 법령 검색]"
        f"(https://www.law.go.kr/lsSc.do?menuId=1&subMenuId=15&query={quote(query)})"
        f"  ·  [🔗 식약처 고시·행정예고](https://www.mfds.go.kr/brd/m_207/list.do)"
    )


if _dialog:
    _event_modal = _dialog("일정 상세")(_event_modal_body)
else:
    _event_modal = _event_modal_body


# ---------------------------------------------------------------- 이벤트 카드

def _event_card(ev, profile, *, prefix: str = "", show_detail: bool = False):
    imp = _display_impact(ev, profile)
    dot = _IMPACT_DOT.get(imp, "🟠")
    dtxt = _dday(ev.date)
    badge = _TRACK_BADGE.get(ev.track, "")

    with st.container(border=True):
        top = st.columns([7, 1.5, 1.5])
        with top[0]:
            st.markdown(f"{dot} **{ev.title}**")
            st.caption(f"{ev.date} ({dtxt}) · {badge}"
                       + (f" · {ev.memo}" if ev.memo else ""))
        with top[1]:
            st.markdown(f"**{dtxt}**")
        with top[2]:
            if st.button("🔎 상세", key=f"cal{prefix}_modal_{ev.id}",
                         use_container_width=True):
                _event_modal(ev, profile)

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

        # 모달 미지원 구버전 streamlit 대비 — 인라인 세부 보기 유지
        if (show_detail or ev.track == "external") and not _dialog:
            with st.expander("📖 세부 내용 · 관련 법령"):
                _event_modal_body(ev, profile)

        if st.session_state.get("cal_share_target") == (prefix, ev.id):
            _share_panel(ev, profile, prefix)


def _goto_sop_compare(ref_id: str):
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
        if st.button("✨ Claude 다듬기", key=f"{key}_ai"):
            st.session_state[key] = draft_notice(
                ev.title, ev.date, company=profile.get("company", ""),
                ref_id=ev.ref_id, use_claude=True)
            st.rerun()
