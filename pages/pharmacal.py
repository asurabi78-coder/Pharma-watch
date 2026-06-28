"""규제 캘린더 — 개정 법안 라이프사이클 캘린더 (임베드 HTML + 네이티브 브리지).

캘린더 화면은 임베드 HTML 로 렌더(균일 칸 + 법안명 알약, 단계=색, 클릭→상세 in-JS).
iframe 은 상위 이동이 막히므로, 액션(QA질문/관심/관심일정/월이동)은
부모의 '숨겨진 네이티브 버튼'을 iframe 이 클릭하는 브리지로 처리한다(앱 기존 패턴).
관리 기능(프로필·레이더·사내 일정 등록·KPI·AI/뉴스)은 하단 '관리·추가 정보' 펼침에 보존.
"""
import calendar as _cal
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import branding
from data_layer import calendar_repo as repo
from data_layer import company_profile as profile_mod

_IMPACT_DOT = {"high": "🔴", "mid": "🟠", "low": "⚪"}
_IMPACT_LABEL = {"high": "높음 (우리 직결)", "mid": "보통", "low": "참고"}
_TRACK_BADGE = {"external": "📋 외부 규제", "duty": "🔁 KGSP 의무", "internal": "🏢 사내 일정"}
_KIND_OPTIONS = ["감사", "실태조사", "교육", "제출 마감", "기타"]
_WAIT = "원문 확인 가능 · QA 분석 대기"
_BRIDGE = "PWBRIDGE§"

_dialog = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

_STAGE_COLORS = {
    "시행예정": ["#FDECEC", "#C0392B"], "의견마감": ["#FCF3DD", "#B9770E"],
    "공포·고시": ["#E7EEFC", "#2D5BD6"], "안내 적용": ["#E3F4EC", "#1B8A5A"],
    "검토중": ["#EEF1F5", "#6B7480"], "시행": ["#EEF1F5", "#6B7480"],
    "KGSP 의무": ["#E7EEFC", "#2D5BD6"], "사내": ["#F0EAF8", "#7A4FB5"],
}


def _display_impact(ev, profile):
    if ev.track == "external":
        return profile_mod.score_impact(ev.tags, ev.impact, profile)
    return ev.impact


def _dday(date_str):
    try:
        d = (datetime.strptime(date_str, "%Y-%m-%d").date() - datetime.now().date()).days
        return "오늘" if d == 0 else (f"D-{d}" if d > 0 else f"D+{-d}")
    except ValueError:
        return ""


def _event_stage(ev):
    if ev.track == "duty":
        return "KGSP 의무"
    if ev.track == "internal":
        return "사내"
    try:
        d = datetime.strptime(ev.date, "%Y-%m-%d").date()
    except ValueError:
        d = None
    if ev.kind == "law":
        return "시행예정" if (d and d >= datetime.now().date()) else "시행"
    if (ev.title or "").startswith("시행"):
        return "시행예정"
    return "안내 적용"


# ---------------------------------------------------------------- 페이로드

def _bill_detail_dict(bl, watched):
    from data_layer.regulatory import bills as _bills
    cd = _bills.cal_date(bl)
    return {
        "id": f"bill:{bl.id}", "title": bl.title, "stage": bl.stage,
        "dday": _dday(cd) if cd else "", "org": bl.org or "—",
        "no": bl.notice_no or "—", "notice": bl.notice_date or "—",
        "deadline": bl.comment_deadline or "—", "eff": bl.effective_date or "미정",
        "core": bl.core, "impact": bl.impact, "analyzed": bl.analyzed(),
        "url": bl.url, "watched": watched,
    }


def _event_detail_dict(ev, watched):
    entry = None
    if ev.ref_id:
        try:
            from data_layer.regulatory.seed import SEED_ENTRIES
            entry = next((e for e in SEED_ENTRIES if e.id == ev.ref_id), None)
        except Exception:
            entry = None
    core = getattr(entry, "content", "") if entry else ""
    impact = getattr(entry, "practical_interpretation", "") if entry else ""
    return {
        "id": f"event:{ev.id}", "title": ev.title, "stage": _event_stage(ev),
        "dday": _dday(ev.date),
        "org": (getattr(entry, "source", "") if entry else "") or _TRACK_BADGE.get(ev.track, ""),
        "no": "—", "notice": "—", "deadline": "—", "eff": ev.date,
        "core": core, "impact": impact, "analyzed": bool(impact),
        "url": getattr(entry, "url", "") if entry else (ev.url or ""), "watched": watched,
    }


def _build_payload(year, month, profile, user):
    from data_layer.regulatory import bills as _bills
    from data_layer import watchlist
    last_day = _cal.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{last_day:02d}"
    watched = set(watchlist.list_keys(user))

    items_by_day, details = {}, {}
    for bl in _bills.list_in_range(start, end):
        cd = _bills.cal_date(bl)
        if not cd:
            continue
        iid = f"bill:{bl.id}"
        items_by_day.setdefault(int(cd[8:10]), []).append({"id": iid, "name": bl.title, "stage": bl.stage})
        details[iid] = _bill_detail_dict(bl, iid in watched)
    for ev in repo.list_range(start, end):
        iid = f"event:{ev.id}"
        items_by_day.setdefault(int(ev.date[8:10]), []).append({"id": iid, "name": ev.title, "stage": _event_stage(ev)})
        details[iid] = _event_detail_dict(ev, iid in watched)

    weeks = _cal.Calendar(firstweekday=6).monthdayscalendar(year, month)
    now = datetime.now()
    cells = []
    for week in weeks:
        for day in week:
            if day == 0:
                cells.append({"day": 0})
            else:
                cells.append({"day": day,
                              "today": (now.year == year and now.month == month and now.day == day),
                              "items": items_by_day.get(day, [])})

    upcoming = []
    for bl in _bills.upcoming(45):
        cd = _bills.cal_date(bl)
        if cd:
            iid = f"bill:{bl.id}"
            upcoming.append({"id": iid, "name": bl.title, "stage": bl.stage, "date": cd, "dday": _dday(cd)})
            if iid not in details:
                details[iid] = _bill_detail_dict(bl, iid in watched)
    for ev in repo.upcoming(45):
        if ev.status == "done":
            continue
        iid = f"event:{ev.id}"
        upcoming.append({"id": iid, "name": ev.title, "stage": _event_stage(ev), "date": ev.date, "dday": _dday(ev.date)})
        if iid not in details:
            details[iid] = _event_detail_dict(ev, iid in watched)
    upcoming = sorted(upcoming, key=lambda x: x["date"])[:8]

    pm, py = (12, year - 1) if month == 1 else (month - 1, year)
    nm, ny = (1, year + 1) if month == 12 else (month + 1, year)
    return {
        "ym": f"{year:04d}-{month:02d}", "monthLabel": f"{year}년 {month}월",
        "prevYm": f"{py:04d}-{pm:02d}", "nextYm": f"{ny:04d}-{nm:02d}",
        "todayYm": f"{now.year:04d}-{now.month:02d}",
        "cells": cells, "details": details,
        "upcoming": upcoming, "colors": _STAGE_COLORS,
    }


_TEMPLATE = """<!doctype html><html><head><meta charset='utf-8'>
<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap' rel='stylesheet'>
<style>
*{box-sizing:border-box;} html,body{margin:0;}
body{font-family:'Noto Sans KR',system-ui,sans-serif;color:#1C2A46;background:#fff;}
.wrap{padding:4px 2px 18px;}
.hd{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px;gap:10px;}
.title{font-size:24px;font-weight:700;}
.sub{font-size:13px;color:#5B6A86;margin-top:3px;}
.addbtn{background:#2D5BD6;color:#fff;border-radius:8px;padding:9px 14px;font-size:13px;font-weight:500;cursor:pointer;white-space:nowrap;}
.filters{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:12px;}
.chip{font-size:12px;padding:5px 11px;border-radius:8px;border:1px solid #E6EBF3;background:#fff;color:#5B6A86;cursor:pointer;}
.chip.on{background:#2D5BD6;color:#fff;border-color:#2D5BD6;}
.srch{margin-left:auto;display:flex;gap:6px;}
.srch select,.srch input{border:1px solid #E6EBF3;border-radius:8px;padding:6px 10px;font-size:12px;font-family:inherit;color:#1C2A46;}
.nav{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
.nav .b{color:#5B6A86;font-size:15px;border:1px solid #E6EBF3;border-radius:7px;padding:2px 10px;cursor:pointer;}
.nav .m{font-size:18px;font-weight:700;color:#1C2A46;}
.layout{display:flex;gap:14px;align-items:flex-start;}
.calbox{flex:1.7;min-width:0;}
.side{flex:1;min-width:240px;}
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;}
.gh{text-align:center;font-size:12px;color:#93A0B8;padding-bottom:2px;}
.cell{min-height:96px;border:0.5px solid #E6EBF3;border-radius:8px;padding:5px 6px;overflow:hidden;}
.cell.empty{border:none;}
.dn{font-size:12px;font-weight:500;color:#5B6A86;}
.dn.today{background:#2D5BD6;color:#fff;border-radius:999px;padding:1px 6px;}
.pill{margin-top:4px;font-size:11px;line-height:1.25;border-left:3px solid;border-radius:0 4px 4px 0;padding:3px 5px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.card{background:#fff;border:0.5px solid #E6EBF3;border-radius:12px;padding:14px 16px;margin-bottom:12px;}
.badge{font-size:12px;padding:3px 10px;border-radius:8px;}
.row{display:flex;justify-content:space-between;font-size:13px;padding:3px 0;}
.muted{color:#93A0B8;}
.wait{display:flex;align-items:center;gap:8px;background:#E7EEFC;color:#2D5BD6;border-radius:8px;padding:8px 12px;font-size:13px;margin:8px 0;}
.sec{font-size:14px;font-weight:700;margin-top:12px;}
.act{display:flex;gap:8px;margin-top:14px;}
.act div{flex:1;text-align:center;border-radius:8px;padding:9px;font-size:13px;cursor:pointer;}
.act .qa{background:#2D5BD6;color:#fff;}
.act .star{border:1px solid #E6EBF3;color:#1C2A46;}
.upitem{border:0.5px solid #E6EBF3;border-radius:8px;padding:8px 10px;margin-bottom:6px;cursor:pointer;}
.lk{color:#2D5BD6;cursor:pointer;}
</style></head><body><div class='wrap'>
<div class='hd'><div><div class='title'>규제 캘린더</div>
<div class='sub'>의약품 유통·수입·보관 업무에 영향을 주는 예정 일정을 확인합니다.</div></div>
<div class='addbtn' id='addbtn'>+ 관심 일정 추가</div></div>
<div class='filters' id='filters'></div>
<div class='nav' id='nav'></div>
<div class='layout'><div class='calbox'><div class='grid' id='gh'></div>
<div class='grid' id='grid' style='margin-top:6px;'></div></div>
<div class='side' id='side'></div></div></div>
<script>
var D = __DATA__;
var COLORS = D.colors;
var STAGES = ["전체","의견마감","공포·고시","시행예정","안내 적용","검토중"];
var curStage="전체", curSearch="", curSel=null;
function col(s){return COLORS[s]||["#EEF1F5","#6B7480"];}
function pdoc(){try{return window.parent.document;}catch(e){return null;}}
function act(cmd){var d=pdoc();if(!d)return;var bs=d.querySelectorAll('button');for(var i=0;i<bs.length;i++){if(((bs[i].textContent)||'').trim()===("PWBRIDGE\\u00A7"+cmd)){bs[i].click();return;}}}
function hideBridges(){var d=pdoc();if(!d)return;var bs=d.querySelectorAll('button');for(var i=0;i<bs.length;i++){var t=((bs[i].textContent)||'').trim();if(t.indexOf("PWBRIDGE\\u00A7")===0){var w=bs[i].closest('[data-testid=\\"stButton\\"]')||bs[i].parentElement;if(w){w.style.position='absolute';w.style.left='-99999px';w.style.top='0';w.style.width='1px';w.style.height='1px';w.style.overflow='hidden';}}}}
function el(tag,cls,txt){var e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}
function renderFilters(){
  var f=document.getElementById('filters');f.innerHTML="";
  STAGES.forEach(function(s){var c=el('span','chip'+(s===curStage?' on':''),s);c.onclick=function(){curStage=s;renderGrid();renderFilters();};f.appendChild(c);});
  var sr=el('div','srch');sr.innerHTML="<select><option>공식 출처 전체</option></select><input id='q' placeholder='법령·고시 검색'/>";
  f.appendChild(sr);var q=sr.querySelector('#q');q.value=curSearch;q.addEventListener('input',function(e){curSearch=e.target.value.trim();renderGrid();});
}
function renderNav(){
  var n=document.getElementById('nav');n.innerHTML="";
  var p=el('span','b','‹');p.onclick=function(){act('ym:'+D.prevYm);};
  var m=el('span','m',D.monthLabel);
  var nx=el('span','b','›');nx.onclick=function(){act('ym:'+D.nextYm);};
  var t=el('span','b','오늘');t.onclick=function(){act('ym:'+D.todayYm);};
  n.appendChild(p);n.appendChild(m);n.appendChild(nx);n.appendChild(t);
}
function match(it){if(curStage!=="전체"&&it.stage!==curStage)return false;if(curSearch&&it.name.indexOf(curSearch)<0)return false;return true;}
function renderGrid(){
  var gh=document.getElementById('gh');gh.innerHTML="";
  ["일","월","화","수","목","금","토"].forEach(function(d){gh.appendChild(el('div','gh',d));});
  var g=document.getElementById('grid');g.innerHTML="";
  D.cells.forEach(function(c){
    if(c.day===0){g.appendChild(el('div','cell empty'));return;}
    var cell=el('div','cell');var dn=el('span','dn'+(c.today?' today':''),c.day);cell.appendChild(dn);
    var its=(c.items||[]).filter(match);
    its.slice(0,2).forEach(function(it){var cc=col(it.stage);var p=el('div','pill',it.name);
      p.style.borderLeftColor=cc[1];p.style.background=cc[0];p.style.color=cc[1];p.title=it.name;
      p.onclick=function(){curSel=it.id;renderSide();};cell.appendChild(p);});
    if(its.length>2){var mm=el('div',null,'+'+(its.length-2)+'건');mm.style.cssText='font-size:10px;color:#93A0B8;margin-top:2px;';cell.appendChild(mm);}
    g.appendChild(cell);
  });
}
function row(l,v){return "<div class='row'><span class='muted'>"+l+"</span><span>"+v+"</span></div>";}
function renderSide(){
  var s=document.getElementById('side');
  if(curSel&&D.details[curSel]){
    var b=D.details[curSel],c=col(b.stage);
    var core=b.core?"<div style='font-size:13px;line-height:1.6;margin-top:4px;'>"+b.core+"</div>":"<div class='muted' style='font-size:13px;margin-top:4px;'>원문 확인 가능 · QA 분석 대기</div>";
    var imp=b.impact?"<div style='font-size:13px;line-height:1.6;margin-top:4px;'>"+b.impact+"</div>":"<div class='muted' style='font-size:13px;margin-top:4px;'>원문 확인 가능 · QA 분석 대기</div>";
    var urls=b.url?"<span class='lk' id='dxurl'>공식 원문 보기</span>":"<span class='muted' style='font-size:13px;'>원문 링크 없음 · 첨부파일: —</span>";
    s.innerHTML="<div class='card'><div style='display:flex;align-items:center;gap:8px;margin-bottom:6px;'>"+
      "<span class='badge' style='background:"+c[0]+";color:"+c[1]+";'>"+b.stage+"</span>"+
      "<span class='muted' style='font-size:12px;'>"+b.dday+"</span></div>"+
      "<div style='font-size:18px;font-weight:700;line-height:1.35;margin-bottom:8px;'>"+b.title+"</div>"+
      "<div class='muted' style='font-size:12px;margin-bottom:8px;'>소관기관: "+b.org+" · 공고번호: "+b.no+"</div>"+
      "<div style='border-top:0.5px solid #E6EBF3;padding-top:6px;'>"+row("공고일",b.notice)+row("의견마감일",b.deadline)+row("시행일",b.eff)+"</div>"+
      (b.analyzed?"":"<div class='wait'>🕓 원문 확인 가능 · QA 분석 대기</div>")+
      "<div class='sec'>개정 핵심 내용</div>"+core+
      "<div class='sec'>영향받는 업무 · 대상</div>"+imp+
      "<div class='sec'>QA 확인사항 · 권장 Action Item</div><div class='muted' style='font-size:13px;margin-top:4px;'>원문 확인 가능 · QA 분석 대기</div>"+
      "<div class='sec'>공식 원문 · 첨부</div><div style='margin-top:4px;'>"+urls+"</div>"+
      "<div class='act'><div class='qa' id='dxqa'>QA 분석가에게 질문하기</div>"+
      "<div class='star' id='dxstar'>"+(b.watched?"★ 관심 해제":"⭐ 관심 추가")+"</div></div>"+
      "<div style='margin-top:8px;'><span class='muted lk' id='dxclose' style='font-size:12px;'>← 닫기</span></div></div>";
    document.getElementById('dxqa').onclick=function(){act('qa:'+b.id);};
    document.getElementById('dxstar').onclick=function(){act('star:'+b.id);};
    document.getElementById('dxclose').onclick=function(){curSel=null;renderSide();};
    if(b.url){document.getElementById('dxurl').onclick=function(){window.open(b.url,'_blank');};}
  }else{
    s.innerHTML="";
    var c1=el('div','card');c1.appendChild(function(){var h=el('div',null,'다가오는 일정');h.style.cssText='font-weight:700;margin-bottom:8px;';return h;}());
    var ups=(D.upcoming||[]);
    if(!ups.length){c1.appendChild(function(){var m=el('div','muted',' 향후 일정 없음');m.style.fontSize='13px';return m;}());}
    ups.forEach(function(u){var cc=col(u.stage);var it=el('div','upitem');
      it.innerHTML="<span class='badge' style='background:"+cc[0]+";color:"+cc[1]+";font-size:11px;'>"+u.stage+"</span> <span style='font-size:13px;font-weight:500;'>"+u.name+"</span><div class='muted' style='font-size:12px;margin-top:2px;'>"+u.date+" · "+u.dday+"</div>";
      it.onclick=function(){curSel=u.id;renderSide();};c1.appendChild(it);});
    s.appendChild(c1);
    var c2=el('div','card');c2.innerHTML="<div style='font-weight:700;margin-bottom:6px;'>일정 표시 기준</div>"+
      "<div style='font-size:12px;color:#5B6A86;'>● 확정 일정 — 원문에 날짜가 명시됨</div>"+
      "<div style='font-size:12px;color:#5B6A86;'>○ 검토 중 — 예정일이 아직 확정되지 않음</div>"+
      "<div style='font-size:12px;color:#5B6A86;margin-top:6px;'>🔴 시행예정 · 🟡 의견마감 · 🔵 공포·고시 · 🟢 안내 적용 · ⚪ 검토중</div>";
    s.appendChild(c2);
  }
}
document.getElementById('addbtn').onclick=function(){act('manage');};
renderFilters();renderNav();renderGrid();renderSide();
hideBridges();var _hb=setInterval(hideBridges,400);setTimeout(function(){clearInterval(_hb);},8000);
</script></body></html>"""


def _calendar_html(payload):
    return _TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))


# ---------------------------------------------------------------- 라우팅/브리지

def _do_qa(tid, _bills):
    title, body = "", ""
    if tid.startswith("bill:"):
        bl = _bills.get(tid.split(":", 1)[1])
        if bl:
            title, body = bl.title, bl.core
    elif tid.startswith("event:"):
        try:
            eid = int(tid.split(":", 1)[1])
        except ValueError:
            eid = None
        ev = next((e for e in repo.list_range("2000-01-01", "2100-01-01") if e.id == eid), None)
        if ev:
            title = ev.title
            if ev.ref_id:
                try:
                    from data_layer.regulatory.seed import SEED_ENTRIES
                    ent = next((e for e in SEED_ENTRIES if e.id == ev.ref_id), None)
                    body = getattr(ent, "content", "") if ent else ""
                except Exception:
                    body = ""
    st.session_state["qa_input"] = f"[{title}]\n{body}" if body else title
    st.session_state.setdefault("nav_history", []).append("pharmacal")
    st.session_state.page = "qa_analyst"
    st.rerun()


def _bridge_cmds(payload):
    ids = list(payload["details"].keys())
    cmds = ["manage", f"ym:{payload['prevYm']}", f"ym:{payload['nextYm']}", f"ym:{payload['todayYm']}"]
    for i in ids:
        cmds.append(f"qa:{i}")
        cmds.append(f"star:{i}")
    return list(dict.fromkeys(cmds))


def _handle_bridge(cmd, user, _bills):
    from data_layer import watchlist
    if cmd == "manage":
        st.session_state["cal_manage_open"] = True
    elif cmd.startswith("ym:"):
        try:
            y, m = cmd[3:].split("-")
            st.session_state["cal_ym"] = [int(y), int(m)]
        except Exception:
            pass
    elif cmd.startswith("qa:"):
        _do_qa(cmd[3:], _bills)
        return
    elif cmd.startswith("star:"):
        watchlist.toggle(user, cmd[5:])
    st.rerun()


def _quick_actions(payload, user, _bills):
    """캘린더 아래 네이티브 빠른 작업 — iframe 버튼이 안 될 때도 확실히 동작."""
    from data_layer import watchlist
    ids = list(payload["details"].keys())
    if not ids:
        return
    labels = {i: payload["details"][i]["title"] for i in ids}
    st.markdown("###### ⚡ 빠른 작업 — 일정 선택 후 실행")
    qcol = st.columns([5, 2, 2])
    with qcol[0]:
        sel = st.selectbox("일정 선택", ids, format_func=lambda i: labels.get(i, i),
                           key="cal_quick_sel", label_visibility="collapsed")
    with qcol[1]:
        if st.button("💬 QA 분석가에게 질문하기", key="cal_quick_qa", use_container_width=True):
            _do_qa(sel, _bills)
    with qcol[2]:
        w = watchlist.is_watched(user, sel)
        if st.button("★ 관심 해제" if w else "⭐ 관심 추가", key="cal_quick_star",
                     use_container_width=True):
            watchlist.toggle(user, sel)
            st.rerun()


def render():
    profile = profile_mod.load_profile()
    if not st.session_state.get("_cal_synced"):
        try:
            repo.sync_external()
            repo.ensure_duties(profile)
        except Exception:
            pass
        st.session_state["_cal_synced"] = True

    from data_layer.regulatory import bills as _bills
    from ui.auth import current_user
    user = current_user()

    now = datetime.now()
    ym = st.session_state.get("cal_ym", [now.year, now.month])
    year, month = ym[0], ym[1]

    payload = _build_payload(year, month, profile, user)
    components.html(_calendar_html(payload), height=820, scrolling=True)

    _quick_actions(payload, user, _bills)

    with st.expander("⚙️ 관리 · 추가 정보 — 회사 프로필 · 규제 레이더 · 사내 일정 등록 · 지표 · 브리핑",
                     expanded=bool(st.session_state.pop("cal_manage_open", False))):
        _management_section(profile, now)

    # ── 숨겨진 네이티브 브리지 버튼 (iframe 이 클릭) ──
    for cmd in _bridge_cmds(payload):
        if st.button(_BRIDGE + cmd, key="pwb_" + cmd):
            _handle_bridge(cmd, user, _bills)

    st.caption(branding.FOOTER_NOTE)


# ---------------------------------------------------------------- 관리·추가 정보

def _management_section(profile, now):
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

    st.markdown("---")
    with st.expander("🏢 회사 프로필 — 우리 회사 직결 규제만 강조됩니다", expanded=False):
        with st.form("cal_profile"):
            c1, c2 = st.columns(2)
            with c1:
                company = st.text_input("회사명", value=profile.get("company", ""))
                handles = st.multiselect(
                    "취급 유형", profile_mod.HANDLE_OPTIONS,
                    default=[h for h in profile.get("handles", []) if h in profile_mod.HANDLE_OPTIONS])
            with c2:
                si_month = st.number_input("자체점검 실시 월", 1, 12, int(profile.get("self_inspection_month", 11)))
                mp_month = st.number_input("온도 매핑 재검증 월", 1, 12, int(profile.get("mapping_month", 6)))
            if st.form_submit_button("저장", type="primary"):
                profile2 = {"company": company, "handles": handles or ["상온 의약품"],
                            "self_inspection_month": int(si_month), "mapping_month": int(mp_month)}
                profile_mod.save_profile(profile2)
                try:
                    repo.ensure_duties(profile2)
                except Exception:
                    pass
                st.success("저장됨 — 취급 유형에 맞춰 의무 일정과 강조가 갱신됩니다.")
                st.rerun()

    with st.expander("🛰 규제 레이더 — 법제처에서 의약품 제·개정 자동 수집", expanded=False):
        try:
            from data_layer.regulatory import radar
            meta = radar.last_crawl()
            if meta and meta.get("ok"):
                st.caption(f"마지막 수집: {meta.get('at','')} · 신규 {meta.get('added',0)}건")
            else:
                st.caption("아직 수집 이력 없음 — 아래 버튼으로 첫 수집을 실행하세요.")
            if st.button("🛰 지금 수집 실행", key="cal_radar_run", type="primary"):
                with st.spinner("법제처 검색 중…"):
                    res = radar.crawl()
                if res.get("ok"):
                    st.success(f"수집 완료 — 신규 {res['added']}건")
                    st.rerun()
                else:
                    st.error(f"수집 실패: {res.get('reason','네트워크 오류')}")
        except Exception as e:  # noqa: BLE001
            st.caption(f"레이더 모듈 오류: {type(e).__name__}")

    st.markdown("#### ➕ 사내 일정 등록")
    with st.form("cal_add", clear_on_submit=True):
        d = st.date_input("날짜", value=now)
        title = st.text_input("일정명", placeholder="예: 식약처 실태조사, 내부 감사")
        kind = st.selectbox("유형", _KIND_OPTIONS)
        impact = st.select_slider("중요도", ["low", "mid", "high"], value="high",
                                  format_func=lambda v: {"low": "참고", "mid": "보통", "high": "중요"}[v])
        memo = st.text_input("메모 (선택)")
        if st.form_submit_button("등록", type="primary"):
            if title.strip():
                repo.add_manual(d.strftime("%Y-%m-%d"), title.strip(), kind=kind, impact=impact, memo=memo.strip())
                st.success(f"등록됨 — {title}")
                st.rerun()
            else:
                st.warning("일정명을 입력하세요.")

    st.markdown("#### ⏰ 다가오는 마감 (30일) — 상태·메모")
    ups = sorted(ups30, key=lambda e: (0 if e.status == "action" else 1, e.date))
    if not ups:
        st.success("향후 30일 내 미처리 마감 없음")
    for ev in ups[:15]:
        _event_card(ev, profile)

    st.markdown("---")
    c = st.columns(3)
    with c[0]:
        _ai_briefing_panel(profile)
    with c[1]:
        _dday_panel(ups30, profile)
    with c[2]:
        _news_panel()


def _ai_briefing_panel(profile):
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
                st.markdown(f"이번 주 일정 **{len(ups)}건**, 우리 직결 **{len(high)}건**. "
                            f"최우선은 **{top.title}** ({top.date}, {_dday(top.date)}) 입니다.")
        if st.button("✨ Claude 브리핑", key="cal_ai_btn", use_container_width=True):
            _make_claude_briefing(profile)
            st.rerun()


def _make_claude_briefing(profile):
    try:
        from utils.claude_client import call_claude
        ups = [e for e in repo.upcoming(14) if e.status != "done"][:10]
        listing = "\n".join(f"- {e.date} ({_dday(e.date)}) {e.title}" for e in ups) or "(일정 없음)"
        out = call_claude(
            system=("당신은 의약품 유통회사 QA 브리핑 작성자입니다. 주어진 일정만 근거로 "
                    "3~4문장의 한국어 브리핑을 쓰세요. 근거 없는 내용은 추가하지 마세요."),
            messages=[{"role": "user", "content": f"[향후 14일 일정]\n{listing}"}],
            max_tokens=400, feature="pharmacal")
        if out and "ANTHROPIC_API_KEY" not in out:
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
            st.caption(f"{getattr(n, 'source_label', '')} · {(getattr(n, 'published_at', '') or '')[:10]}")


def _recent_news(days=7, limit=5):
    try:
        from data_layer.news import repo as news_repo
        return news_repo.list_items(days=days, importance_in=["high", "mid"], limit=limit)
    except Exception:
        return []


def _event_modal_body(ev, profile):
    imp = _display_impact(ev, profile)
    st.markdown(f"### {_IMPACT_DOT.get(imp,'🟠')} {ev.title}")
    st.markdown(f"**시행/기한일** {ev.date} ({_dday(ev.date)}) · **구분** {_TRACK_BADGE.get(ev.track,'')}")
    if ev.memo:
        st.markdown(f"메모: {ev.memo}")


if _dialog:
    _event_modal = _dialog("일정 상세")(_event_modal_body)
else:
    _event_modal = _event_modal_body


def _event_card(ev, profile, *, prefix="", show_detail=False):
    imp = _display_impact(ev, profile)
    dot = _IMPACT_DOT.get(imp, "🟠")
    with st.container(border=True):
        top = st.columns([7, 1.5, 1.5])
        with top[0]:
            st.markdown(f"{dot} **{ev.title}**")
            st.caption(f"{ev.date} ({_dday(ev.date)}) · {_TRACK_BADGE.get(ev.track,'')}")
        with top[2]:
            if st.button("🔎 상세", key=f"cal{prefix}_modal_{ev.id}", use_container_width=True):
                _event_modal(ev, profile)
        ctl = st.columns([3, 3, 2])
        with ctl[0]:
            cur = ev.status if ev.status in repo.STATUS_LABEL else "todo"
            new_status = st.selectbox("상태", list(repo.STATUS_LABEL),
                                      index=list(repo.STATUS_LABEL).index(cur),
                                      format_func=lambda s: repo.STATUS_LABEL[s],
                                      key=f"cal{prefix}_st_{ev.id}", label_visibility="collapsed")
            if new_status != ev.status:
                repo.update_event(ev.id, status=new_status)
                st.rerun()
        with ctl[1]:
            memo = st.text_input("메모", value=ev.memo, key=f"cal{prefix}_memo_{ev.id}",
                                 label_visibility="collapsed", placeholder="메모…")
            if memo != ev.memo:
                repo.update_event(ev.id, memo=memo)
        with ctl[2]:
            if ev.track == "internal":
                if st.button("🗑️", key=f"cal{prefix}_del_{ev.id}", use_container_width=True):
                    repo.delete_event(ev.id)
                    st.rerun()
