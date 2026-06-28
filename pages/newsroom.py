"""뉴스 모니터링 — 출처유형·긴급 분리, 업무 카테고리, 중복통합, QA 카드.

승인된 디자인을 임베드 HTML 로 렌더. 필터는 화면 내(JS), 액션(재수집/QA분석/숨김/기간)은
부모의 숨겨진 네이티브 버튼을 iframe 이 클릭하는 브리지로 처리(캘린더와 동일 패턴).
1단계 백엔드(classify/dedup/repo)를 그대로 사용한다.
"""
from __future__ import annotations

import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from data_layer.news import SOURCES, fetch_and_save, repo

_BRIDGE = "PWBRIDGE§"
_ST_LABEL = {"official": "공식자료", "media": "언론기사", "association": "협회자료", "unknown": "기타 출처"}
_PERIODS = {"최근 1일": 1, "최근 3일": 3, "최근 7일": 7, "최근 30일": 30, "전체": 0}


def _status(it):
    if getattr(it, "is_urgent", False):
        return "urgent", "긴급"
    vs = getattr(it, "verification_status", "")
    if vs == "official_confirmed":
        return "confirmed", "공식 확인"
    if vs == "checking":
        return "checking", "확인 중"
    return "", ""


def _build_payload(period_days):
    days = period_days if period_days and period_days > 0 else None
    items = repo.list_items(days=days, limit=400, include_hidden=False)
    # 중복 통합 → 대표만
    groups = {}
    for it in items:
        groups.setdefault(getattr(it, "duplicate_group_id", "") or it.id, []).append(it)
    reps = []
    for members in groups.values():
        rep = repo.pick_representative(members)
        reps.append((rep, len(members)))
    reps.sort(key=lambda t: (
        0 if getattr(t[0], "is_urgent", False) else 1,
        {"high": 0, "mid": 1, "low": 2}.get(getattr(t[0], "importance", ""), 3),
        "0" if False else "",
    ))
    reps.sort(key=lambda t: (t[0].published_at or t[0].fetched_at), reverse=True)
    reps.sort(key=lambda t: (
        0 if getattr(t[0], "is_urgent", False) else 1,
        {"high": 0, "mid": 1, "low": 2}.get(getattr(t[0], "importance", ""), 3),
    ))

    out = []
    for rep, n in reps[:40]:
        scode, slabel = _status(rep)
        pub = (rep.published_at or rep.fetched_at or "")[:16].replace("T", " ")
        out.append({
            "id": rep.id, "st": rep.source_type or "unknown",
            "stLabel": _ST_LABEL.get(rep.source_type or "unknown", "기타 출처"),
            "status": scode, "statusLabel": slabel,
            "cat": rep.biz_category or "기타", "title": rep.title,
            "src": rep.source_label, "date": pub or "—",
            "sum": rep.summary or "", "qa": rep.action_items or "—",
            "aff": rep.affected_work or "—", "url": rep.url,
            "rel": max(0, n - 1), "urgent": bool(getattr(rep, "is_urgent", False)),
        })

    # 브리핑
    urgent_items = [o for o in out if o["urgent"]]
    watch = [o for o in out if not o["urgent"] and o["status"] in ("confirmed", "checking")][:3]
    from collections import Counter
    cats = Counter(o["cat"] for o in out if o["cat"] != "기타")
    keywords = [c for c, _ in cats.most_common(5)] or ["콜드체인", "회수", "공급중단"]
    brief = {
        "urgentCount": len(urgent_items),
        "urgentTop": [o["title"] for o in urgent_items[:2]] or ["확정 긴급 항목 없음 (확인 중 위주)"],
        "watch": [o["title"] for o in watch],
        "keywords": keywords,
    }
    sources = sorted({o["src"] for o in out})
    return {
        "items": out, "brief": brief, "period": period_days,
        "sources": sources, "stamp": datetime.now().strftime("%m월 %d일"),
    }


_TEMPLATE = """<!doctype html><html><head><meta charset='utf-8'>
<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap' rel='stylesheet'>
<style>
*{box-sizing:border-box;}html,body{margin:0;}
body{font-family:'Noto Sans KR',system-ui,sans-serif;color:#1C2A46;background:#fff;}
.wrap{padding:4px 2px 18px;}
.hd{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;gap:10px;}
.title{font-size:22px;font-weight:700;}
.sub{font-size:13px;color:#5B6A86;margin-top:2px;}
.rf{font-size:12px;color:#5B6A86;cursor:pointer;white-space:nowrap;}
.bar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px;}
.st{font-size:13px;padding:6px 12px;border-radius:8px;border:1px solid #E6EBF3;color:#5B6A86;cursor:pointer;background:#fff;}
.st.on{background:#2D5BD6;color:#fff;border-color:#2D5BD6;}
.urg{font-size:13px;padding:6px 11px;border-radius:8px;border:1px solid #E6A6A6;color:#C0392B;cursor:pointer;display:inline-flex;gap:5px;align-items:center;}
.urg.on{background:#FDECEC;}
.bar select,.bar input{border:1px solid #E6EBF3;border-radius:8px;padding:6px 9px;font-size:12px;font-family:inherit;color:#1C2A46;}
.hint{font-size:12px;color:#93A0B8;margin:4px 0 12px;}
.layout{display:flex;gap:14px;align-items:flex-start;}
.col{flex:1.7;min-width:0;}.side{flex:1;min-width:215px;}
.sectit{font-size:15px;font-weight:700;margin-bottom:8px;}
.card{background:#fff;border:0.5px solid #E6EBF3;border-radius:12px;padding:12px 14px;margin-bottom:10px;}
.badge{font-size:11px;padding:2px 8px;border-radius:8px;}
.cat{font-size:11px;padding:2px 8px;border-radius:8px;background:#F4F7FC;color:#5B6A86;}
.qline{font-size:12.5px;color:#5B6A86;margin-bottom:3px;}
.qval{color:#1C2A46;}
.cbtn{font-size:12px;padding:5px 10px;border-radius:8px;border:0.5px solid #D5DDEC;color:#1C2A46;cursor:pointer;background:#fff;}
.cbtn.p{background:#2D5BD6;color:#fff;border:none;}
.bf{background:#0E1B3A;color:#fff;border-radius:12px;padding:14px 16px;}
.bf .l{font-size:13px;color:#A8B3CC;margin-bottom:4px;}
.kw{font-size:12px;padding:3px 9px;border-radius:8px;background:#1B2A4E;color:#cfe;}
</style></head><body><div class='wrap'>
<div class='hd'><div><div class='title'>뉴스 모니터링</div>
<div class='sub'>의약품 유통·수입·보관 업무에 영향을 주는 소식을 QA 관점으로 정리합니다.</div></div>
<div class='rf' id='refresh'>↻ 재수집</div></div>
<div class='bar'>
<span class='st on' data-st='all'>전체</span>
<span class='st' data-st='official'>공식자료</span>
<span class='st' data-st='media'>언론기사</span>
<span class='urg' id='urg'>⚠ 긴급만 보기</span>
<select id='cat'><option value='all'>카테고리 전체</option></select>
<select id='per'></select>
<select id='src'></select>
<input id='q' placeholder='뉴스·키워드 검색' style='margin-left:auto;width:150px;'/>
</div>
<div class='hint'>출처 유형과 긴급도를 별도로 선택합니다. (예: 공식자료 + 긴급만 보기)</div>
<div class='layout'><div class='col'>
<div class='sectit'>오늘 꼭 볼 소식 <span id='cnt' style='color:#93A0B8;font-size:13px;'></span></div>
<div id='cards'></div></div>
<div class='side' id='side'></div></div></div>
<script>
var D=__DATA__;
var ST={official:["공식자료","#E7EEFC","#2D5BD6"],media:["언론기사","#EEF1F5","#5B6A86"],
        association:["협회자료","#F0EAF8","#7A4FB5"],unknown:["기타 출처","#EEF1F5","#5B6A86"]};
var STA={urgent:["긴급","#FDECEC","#C0392B"],confirmed:["공식 확인","#E3F4EC","#1B8A5A"],checking:["확인 중","#FCF3DD","#B9770E"]};
var PERIODS={"최근 1일":1,"최근 3일":3,"최근 7일":7,"최근 30일":30,"전체":0};
var fSt="all",fUrg=false,fCat="all",fQ="",fSrc="all";
function pdoc(){try{return window.parent.document;}catch(e){return null;}}
function act(cmd){var d=pdoc();if(!d)return;var bs=d.querySelectorAll('button');for(var i=0;i<bs.length;i++){if(((bs[i].textContent)||'').trim()===("PWBRIDGE\\u00A7"+cmd)){bs[i].click();return;}}}
function hideBridges(){var d=pdoc();if(!d)return;var bs=d.querySelectorAll('button');for(var i=0;i<bs.length;i++){var t=((bs[i].textContent)||'').trim();if(t.indexOf("PWBRIDGE\\u00A7")===0){var w=bs[i].closest('[data-testid=\\"stButton\\"]')||bs[i].parentElement;if(w){w.style.position='absolute';w.style.left='-99999px';w.style.top='0';w.style.width='1px';w.style.height='1px';w.style.overflow='hidden';}}}}
function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e;}
function badge(a){return "<span class='badge' style='background:"+a[1]+";color:"+a[2]+";'>"+a[0]+"</span>";}
function initBar(){
  var cats=["all"];D.items.forEach(function(o){if(cats.indexOf(o.cat)<0)cats.push(o.cat);});
  var cs=document.getElementById('cat');cs.innerHTML="";
  cats.forEach(function(c){var o=document.createElement('option');o.value=c;o.textContent=(c==="all"?"카테고리 전체":c);cs.appendChild(o);});
  cs.onchange=function(e){fCat=e.target.value;render();};
  var ps=document.getElementById('per');ps.innerHTML="";
  Object.keys(PERIODS).forEach(function(k){var o=document.createElement('option');o.value=PERIODS[k];o.textContent=k;if(PERIODS[k]===D.period)o.selected=true;ps.appendChild(o);});
  ps.onchange=function(e){act('period:'+e.target.value);};
  var ss=document.getElementById('src');ss.innerHTML="";
  var srcs=["all"].concat(D.sources||[]);
  srcs.forEach(function(x){var o=document.createElement('option');o.value=x;o.textContent=(x==="all"?"출처 전체":x);ss.appendChild(o);});
  ss.onchange=function(e){fSrc=e.target.value;render();};
  document.querySelectorAll('.st').forEach(function(c){c.onclick=function(){fSt=c.dataset.st;document.querySelectorAll('.st').forEach(function(x){x.classList.toggle('on',x===c);});render();};});
  var u=document.getElementById('urg');u.onclick=function(){fUrg=!fUrg;u.classList.toggle('on',fUrg);render();};
  document.getElementById('q').addEventListener('input',function(e){fQ=e.target.value.trim();render();});
  document.getElementById('refresh').onclick=function(){act('refresh');};
}
function match(o){if(fSt!=="all"&&o.st!==fSt)return false;if(fSrc!=="all"&&o.src!==fSrc)return false;if(fUrg&&!o.urgent)return false;if(fCat!=="all"&&o.cat!==fCat)return false;if(fQ&&o.title.indexOf(fQ)<0&&(o.sum||"").indexOf(fQ)<0)return false;return true;}
function render(){
  var rows=D.items.filter(match);
  document.getElementById('cnt').textContent="· "+rows.length+"건";
  var c=document.getElementById('cards');c.innerHTML="";
  if(!rows.length){c.innerHTML="<div style='font-size:13px;color:#93A0B8;padding:14px;'>해당 조건의 소식이 없습니다.</div>";}
  rows.forEach(function(o){
    var s=ST[o.st]||ST.unknown, stt=o.status?STA[o.status]:null;
    var div=el('div','card');
    div.innerHTML=
      "<div style='display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:6px;'>"+
      badge(s)+(stt?badge(stt):"")+"<span class='cat'>"+o.cat+"</span>"+
      (o.rel>0?"<span style='font-size:11px;color:#93A0B8;margin-left:auto;'>관련 보도 "+o.rel+"건</span>":"")+"</div>"+
      "<div style='font-size:15px;font-weight:500;margin-bottom:2px;'>"+o.title+"</div>"+
      "<div style='font-size:12px;color:#93A0B8;margin-bottom:6px;'>["+o.src+"] · "+o.date+"</div>"+
      (o.sum?"<div style='font-size:13px;color:#5B6A86;line-height:1.55;margin-bottom:8px;'>"+o.sum+"</div>":"")+
      "<div class='qline'>QA 확인사항: <span class='qval'>"+o.qa+"</span></div>"+
      "<div class='qline' style='margin-bottom:10px;'>영향 업무: <span class='qval'>"+o.aff+"</span></div>"+
      "<div style='display:flex;gap:6px;'><span class='cbtn p' data-qa='"+o.id+"'>QA 분석</span>"+
      (o.url?"<span class='cbtn' data-url='"+o.url+"'>원문 보기</span>":"")+
      "<span class='cbtn' data-hide='"+o.id+"'>숨김</span></div>";
    c.appendChild(div);
  });
  c.querySelectorAll('[data-qa]').forEach(function(b){b.onclick=function(){act('qa:'+b.getAttribute('data-qa'));};});
  c.querySelectorAll('[data-hide]').forEach(function(b){b.onclick=function(){act('hide:'+b.getAttribute('data-hide'));};});
  c.querySelectorAll('[data-url]').forEach(function(b){b.onclick=function(){window.open(b.getAttribute('data-url'),'_blank');};});
}
function renderSide(){
  var b=D.brief;var h="<div class='bf'>";
  h+="<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;'><span style='font-weight:700;'>오늘의 QA 브리핑</span><span style='font-size:12px;color:#A8B3CC;'>"+D.stamp+"</span></div>";
  h+="<div class='l'>우선 확인 "+b.urgentCount+"건</div>";
  b.urgentTop.forEach(function(t){h+="<div style='font-size:13px;margin-bottom:3px;'><span style='color:#F08A82;'>●</span> "+t+"</div>";});
  h+="<div class='l' style='margin-top:10px;'>놓치면 안 되는 변화</div>";
  if(!b.watch.length)h+="<div style='font-size:13px;color:#A8B3CC;'>해당 없음</div>";
  b.watch.forEach(function(t){h+="<div style='font-size:13px;margin-bottom:2px;'>· "+t+"</div>";});
  h+="<div class='l' style='margin-top:10px;'>관심 키워드</div><div style='display:flex;flex-wrap:wrap;gap:5px;margin-top:4px;'>";
  b.keywords.forEach(function(k){h+="<span class='kw'>"+k+"</span>";});
  h+="</div></div>";
  document.getElementById('side').innerHTML=h;
}
initBar();render();renderSide();
hideBridges();var _hb=setInterval(hideBridges,400);setTimeout(function(){clearInterval(_hb);},8000);
</script></body></html>"""


def _news_html(payload):
    return _TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))


def _find_item(item_id):
    for it in repo.list_items(days=None, limit=1000, include_hidden=True):
        if it.id == item_id:
            return it
    return None


def _do_qa(item_id):
    it = _find_item(item_id)
    if it is not None:
        body = it.summary or ""
        st.session_state["qa_input"] = f"[{it.title}]\n{body}" if body else it.title
        st.session_state.setdefault("nav_history", []).append("newsroom")
        st.session_state.page = "qa_analyst"
    st.rerun()


def _bridge_cmds(payload):
    cmds = ["refresh", "purge"]
    for k, v in _PERIODS.items():
        cmds.append(f"period:{v}")
    for o in payload["items"]:
        cmds.append(f"qa:{o['id']}")
        cmds.append(f"hide:{o['id']}")
    return list(dict.fromkeys(cmds))


def _handle_bridge(cmd):
    if cmd == "refresh":
        with st.spinner("뉴스 수집 중…"):
            try:
                fetch_and_save(per_source_limit=15)
            except Exception:
                pass
        st.rerun()
    elif cmd == "purge":
        repo.purge_older_than(30)
        st.rerun()
    elif cmd.startswith("period:"):
        try:
            st.session_state["news_period"] = int(cmd.split(":", 1)[1])
        except Exception:
            pass
        st.rerun()
    elif cmd.startswith("qa:"):
        _do_qa(cmd.split(":", 1)[1])
    elif cmd.startswith("hide:"):
        repo.set_hidden(cmd.split(":", 1)[1], True)
        st.rerun()


def render():
    period = st.session_state.get("news_period", 30)
    payload = _build_payload(period)
    components.html(_news_html(payload), height=860, scrolling=True)

    _quick_actions(payload)

    # 숨겨진 네이티브 브리지 버튼
    for cmd in _bridge_cmds(payload):
        if st.button(_BRIDGE + cmd, key="nwb_" + cmd):
            _handle_bridge(cmd)


def _quick_actions(payload):
    items = payload["items"]
    if not items:
        st.caption("표시할 뉴스가 없습니다. ‘재수집’으로 수집하세요.")
        return
    labels = {o["id"]: o["title"] for o in items}
    st.markdown("###### ⚡ 빠른 작업 — 기사 선택 후 실행")
    qc = st.columns([5, 2, 2])
    with qc[0]:
        sel = st.selectbox("기사 선택", [o["id"] for o in items],
                           format_func=lambda i: labels.get(i, i)[:40],
                           key="nr_quick_sel", label_visibility="collapsed")
    with qc[1]:
        if st.button("💬 QA 분석", key="nr_quick_qa", use_container_width=True):
            _do_qa(sel)
    with qc[2]:
        if st.button("🚫 숨김", key="nr_quick_hide", use_container_width=True):
            repo.set_hidden(sel, True)
            st.rerun()
