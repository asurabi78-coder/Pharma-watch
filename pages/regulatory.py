"""규제·근거 검색 — 법령명 검색 + 상황·주제 검색(자동) · 국내 공식 우선.

검색 엔진: data_layer.regulatory.lawsearch (정규화·의도판정·fuzzy·출처등급 재정렬).
- 국내 공식 법령/규칙/안내서 우선, WHO=해외 참고규범/SOP=내부 참고자료 분리, 뉴스 제외.
- 가짜 법령명·URL 생성 안 함(canonical + law.go.kr 공식 스킴/공식 데이터만).
- QA 판단·Action Item은 여기서 만들지 않고 'QA 분석가'로 넘김.
임베드 HTML(선명색) + 네이티브 브리지(검색칩/FAQ/QA). 검색은 네이티브 입력+버튼.
"""
from __future__ import annotations

import json
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from data_layer.regulatory import lawsearch as L

_BRIDGE = "PWBRIDGE§"
_AREAS = [
    ("보관·온도", "보관 온도 콜드체인"), ("운송·콜드체인", "운송 콜드체인 온도"),
    ("입고·출고", "입고 출고 출하증명"), ("반품·회수", "반품 회수"),
    ("관리약사", "관리약사 출고"), ("수입·통관", "수입 통관"),
    ("위수탁", "위수탁 품질계약"), ("교육·기록", "교육 기록 자체점검"),
]
_FAQS = ["약사법 도매상 규정", "생물학적제제 판매관리 규칙", "KGSP 반품 규정"]

_DOCTYPE_COLOR = {
    "법률": "law", "시행령": "law", "시행규칙": "law", "규칙": "law",
    "고시": "notice", "행정규칙": "notice",
    "안내서": "guide", "지침": "guide", "내부 SOP": "guide",
    "해외 가이드": "foreign", "AI 추정": "ai", "규정": "guide",
}


def _related_titles(ids):
    out = []
    for rid in ids[:4]:
        e = L.get_entry(rid)
        if e is not None:
            out.append(getattr(e, "canonical_title", "") or e.title)
    return out


def _card(h):
    law_sec = h.section in ("domestic_law", "domestic_rule")
    title = h.canonical_title if (law_sec and h.canonical_title) else h.display_title
    url = h.official_source_url
    if not url:
        url = "https://www.law.go.kr/LSW/lsScListR.do?query=" + quote(h.canonical_title or h.display_title)
        url_official = False
    else:
        url_official = True
    return {
        "id": h.id, "title": title, "doctype": h.document_type,
        "color": _DOCTYPE_COLOR.get(h.document_type, "guide"),
        "status": h.current_status or "현행", "authority": h.issuing_authority,
        "eff": h.effective_date or "—", "promul": h.promulgation_date or "—",
        "why": h.why, "article": h.article or "", "content": (h.content or "")[:600],
        "url": url, "urlOfficial": url_official, "related": _related_titles(h.related_ids),
    }


def _build_payload(query):
    res = L.search(query or "")
    by_sec = {}
    for h in res.hits:
        by_sec.setdefault(h.section, []).append(_card(h))
    sections = []
    for key, label in L._SECTIONS:
        if by_sec.get(key):
            sections.append({"key": key, "label": label, "items": by_sec[key][:6]})
    presets = [{"label": a[0], "query": a[1]} for a in _AREAS] + [{"label": f, "query": f} for f in _FAQS]
    return {
        "query": res.query, "intent": res.intent, "noExact": res.no_exact,
        "count": len(res.hits), "sections": sections, "presets": presets,
        "areaCount": len(_AREAS), "hasQuery": bool(res.query),
        "lawSearchUrl": "https://www.law.go.kr/LSW/lsScListR.do?query=" + quote(res.query) if res.query else "https://www.law.go.kr",
    }


_TEMPLATE = """<!doctype html><html><head><meta charset='utf-8'>
<link href='https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap' rel='stylesheet'>
<link rel='stylesheet' href='https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css'>
<style>
*{box-sizing:border-box;}html,body{margin:0;}
body{font-family:'Pretendard','Noto Sans KR',system-ui,sans-serif;color:#0F172A;background:#fff;font-size:14px;}
.wrap{padding:4px 2px 18px;}
.chips{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:14px;}
.lbl{font-size:12px;color:#94A3B8;}
.fc{font-size:13px;padding:6px 12px;border-radius:9px;border:1px solid #D7DFEA;color:#475569;cursor:pointer;background:#fff;}
.fc.on{background:#2563EB;color:#fff;border-color:#2563EB;}
.layout{display:flex;gap:14px;align-items:flex-start;}
.col{flex:2.33;min-width:0;}.side{flex:1;min-width:230px;}
.noex{background:#FFF7E6;border:1px solid #FFE2A8;color:#92600A;border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:12px;}
.sec{font-size:13px;font-weight:700;margin:14px 0 8px;padding-left:8px;border-left:3px solid #2563EB;}
.sec.foreign{border-left-color:#8B5CF6;color:#6D28D9;}
.sec.internal{border-left-color:#94A3B8;color:#64748B;}
.ev{background:#fff;border:1px solid #D7DFEA;border-radius:12px;padding:12px 14px;margin-bottom:10px;}
.bg{font-size:11px;font-weight:500;padding:2px 9px;border-radius:8px;margin-right:4px;}
.law{background:#DBE7FF;color:#1D4ED8;}
.notice{background:#FFEACC;color:#B45309;}
.guide{background:#E7ECF4;color:#475569;}
.foreign{background:#EDE9FE;color:#6D28D9;}
.ai{background:#FEE2E2;color:#B91C1C;}
.cur{background:#CFF4DF;color:#047857;}
.ref{background:#E7ECF4;color:#64748B;}
.evt{font-size:15px;font-weight:500;}
.evm{font-size:12px;color:#94A3B8;margin:3px 0;}
.why{font-size:12.5px;color:#2563EB;margin:4px 0;}
.row{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;}
.act{font-size:12px;padding:5px 11px;border-radius:8px;border:1px solid #D7DFEA;color:#0F172A;cursor:pointer;background:#fff;}
.act.p{background:#2563EB;color:#fff;border:none;}
.detail{margin-top:8px;padding:9px 11px;background:#F5F8FE;border-radius:8px;font-size:12.5px;color:#3A4761;white-space:pre-wrap;line-height:1.55;}
.sumcard{background:#fff;border:1px solid #D7DFEA;border-radius:14px;overflow:hidden;}
.sumhd{background:#0E1B3A;color:#fff;padding:11px 14px;font-weight:500;}
.sumbd{padding:12px 14px;}
.note{font-size:12px;color:#475569;background:#F1F5FB;border-radius:8px;padding:9px 11px;margin:8px 0;}
.btn{width:100%;border-radius:9px;padding:10px;font-size:13px;cursor:pointer;border:1px solid #D7DFEA;background:#fff;color:#0F172A;}
.btn.p{background:#2563EB;color:#fff;border:none;margin-bottom:6px;}
.faq{display:flex;gap:8px;align-items:center;flex-wrap:wrap;border-top:1px solid #D7DFEA;margin-top:14px;padding-top:10px;}
.fq{font-size:12px;padding:6px 11px;border-radius:9px;background:#EEF3FB;color:#3A4761;cursor:pointer;}
.empty{font-size:13px;color:#94A3B8;padding:16px;border:1px dashed #D7DFEA;border-radius:12px;}
</style></head><body><div class='wrap'>
<div class='chips' id='chips'></div>
<div class='layout'>
<div class='col'><div id='results'></div></div>
<div class='side'><div class='sumcard'><div class='sumhd'>근거 요약</div><div class='sumbd' id='sum'></div></div></div>
</div>
<div class='faq' id='faq'></div></div>
<script>
var D=__DATA__;
function pdoc(){try{return window.parent.document;}catch(e){return null;}}
function act(cmd){var d=pdoc();if(!d)return;var bs=d.querySelectorAll('button');for(var i=0;i<bs.length;i++){if(((bs[i].textContent)||'').trim()===("PWBRIDGE\\u00A7"+cmd)){bs[i].click();return;}}}
function hideBridges(){var d=pdoc();if(!d)return;var bs=d.querySelectorAll('button');for(var i=0;i<bs.length;i++){var t=((bs[i].textContent)||'').trim();if(t.indexOf("PWBRIDGE\\u00A7")===0){var w=bs[i].closest('[data-testid=\\"stButton\\"]')||bs[i].parentElement;if(w){w.style.position='absolute';w.style.left='-99999px';w.style.top='0';w.style.width='1px';w.style.height='1px';w.style.overflow='hidden';}}}}
function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e;}
function renderChips(){
  var c=document.getElementById('chips');c.innerHTML="";c.appendChild(el('span','lbl','업무 분야'));
  D.presets.slice(0,D.areaCount).forEach(function(p,i){var on=(D.query===p.query);var s=el('span','fc'+(on?' on':''),p.label);s.onclick=function(){act('q:'+i);};c.appendChild(s);});
}
function renderResults(){
  var box=document.getElementById('results');box.innerHTML="";
  if(!D.hasQuery){box.innerHTML="<div class='empty'>법령명 또는 실무 상황을 입력하세요. 예: \\"생물학적제제 판매관리 규칙\\" / \\"냉장 의약품 운송 중 온도 이탈\\"</div>";return;}
  if(!D.count){box.innerHTML="<div class='noex'>입력하신 명칭과 정확히 일치하는 공식 법령을 찾지 못했습니다. 검색어를 바꾸거나 업무 분야 칩을 눌러보세요.</div>";return;}
  if(D.noExact){var n=el('div','noex','입력하신 명칭과 정확히 일치하는 공식 법령이 없습니다. 아래는 유사 후보입니다.');box.appendChild(n);}
  D.sections.forEach(function(sec){
    var hd=el('div','sec'+(sec.key==='foreign'?' foreign':(sec.key==='internal'?' internal':'')), sec.label);box.appendChild(hd);
    sec.items.forEach(function(o){
      var card=el('div','ev');
      var rel=(o.related&&o.related.length)?"<span class='act' data-rel='"+o.id+"'>관련 법령 보기</span>":"";
      card.innerHTML="<div style='margin-bottom:5px;'><span class='bg "+o.color+"'>"+o.doctype+"</span>"+
        "<span class='bg "+((o.status==='현행')?'cur':'ref')+"'>"+o.status+"</span></div>"+
        "<div class='evt'>"+o.title+"</div>"+
        "<div class='evm'>소관 "+o.authority+" · 시행 "+o.eff+" · "+o.status+"</div>"+
        "<div class='why'>↳ "+o.why+"</div>"+
        "<div class='row'><span class='act p' data-url='"+o.url+"' data-off='"+(o.urlOfficial?'1':'0')+"'>공식 원문 보기</span>"+
        "<span class='act' data-art='"+o.id+"'>관련 조항 보기</span>"+rel+"</div>"+
        "<div class='detail' id='dt_"+o.id+"' style='display:none;'></div>"+
        "<div class='detail' id='rl_"+o.id+"' style='display:none;'></div>";
      box.appendChild(card);
      card.querySelector('[data-url]').onclick=function(){window.open(o.url,'_blank');};
      card.querySelector('[data-art]').onclick=function(){
        var dt=card.querySelector('#dt_'+CSS.escape(o.id));
        if(dt.style.display==='none'){dt.style.display='block';dt.textContent=(o.article?("근거조문: "+o.article+"\\n\\n"):"")+(o.content||"(원문 평탄화는 라이브 연결 시 확장)");}
        else dt.style.display='none';
      };
      if(o.related&&o.related.length){card.querySelector('[data-rel]').onclick=function(){
        var rl=card.querySelector('#rl_'+CSS.escape(o.id));
        if(rl.style.display==='none'){rl.style.display='block';rl.textContent="관련 법령: "+o.related.join(" · ");}else rl.style.display='none';
      };}
    });
  });
}
function renderSum(){
  var s=document.getElementById('sum');
  if(!D.hasQuery){s.innerHTML="<div style='font-size:13px;color:#94A3B8;'>검색하면 관련 공식 근거 요약이 표시됩니다.</div>";return;}
  var h="<div style='font-size:13px;margin-bottom:8px;'>‘"+(D.query.length>30?D.query.slice(0,30)+'…':D.query)+"’ 에 대한 공식 근거 <b>"+D.count+"건</b>을 찾았습니다.</div>";
  h+="<div class='note'>ℹ 검색 결과는 근거 확인용 보조자료입니다. 회사 업무 영향·SOP 변경·Action Item은 ‘QA 분석가’에서 확정합니다. 최종 판단은 관리약사 또는 품질책임자가 검토해야 합니다.</div>";
  h+="<div class='btn p' id='bqa'>QA 분석가에게 영향 분석 요청</div><div class='btn' id='bsrc'>law.go.kr 통합검색</div>";
  s.innerHTML=h;
  document.getElementById('bqa').onclick=function(){act('qa');};
  document.getElementById('bsrc').onclick=function(){window.open(D.lawSearchUrl,'_blank');};
}
function renderFaq(){
  var f=document.getElementById('faq');f.innerHTML="";var t=el('span',null,'자주 찾는 질문');t.style.cssText='font-size:13px;font-weight:500;';f.appendChild(t);
  D.presets.slice(D.areaCount).forEach(function(p,i){var s=el('span','fq',p.label+' ›');s.onclick=function(){act('q:'+(D.areaCount+i));};f.appendChild(s);});
}
renderChips();renderResults();renderSum();renderFaq();
hideBridges();var _hb=setInterval(hideBridges,400);setTimeout(function(){clearInterval(_hb);},8000);
function _fit(){try{var h=document.body.scrollHeight;if(window.frameElement){window.frameElement.style.height=h+'px';window.frameElement.style.minHeight=h+'px';}}catch(e){}}
_fit();window.addEventListener('load',_fit);setTimeout(_fit,300);setTimeout(_fit,900);var _fi=setInterval(_fit,1200);setTimeout(function(){clearInterval(_fi);},9000);
</script></body></html>"""


def _reg_html(payload):
    return _TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))


def _route_qa(query, payload):
    top = ""
    for sec in payload.get("sections", []):
        if sec["items"]:
            c = sec["items"][0]
            top = f"{c['title']} ({c['doctype']}, {c['authority']})"
            break
    st.session_state["qa_input"] = (f"[규제 근거 질문] {query}\n관련 공식 근거: {top}" if query else top)
    st.session_state.setdefault("nav_history", []).append("regulatory")
    st.session_state.page = "qa_analyst"
    st.rerun()


def _bridge_cmds(payload):
    cmds = ["qa"]
    for i in range(len(payload["presets"])):
        cmds.append(f"q:{i}")
    return list(dict.fromkeys(cmds))


def _handle_bridge(cmd, payload):
    if cmd == "qa":
        _route_qa(payload["query"], payload)
    elif cmd.startswith("q:"):
        try:
            st.session_state["reg_q"] = payload["presets"][int(cmd.split(":", 1)[1])]["query"]
        except Exception:
            pass
        st.rerun()


def render():
    if "reg_q" not in st.session_state:
        st.session_state["reg_q"] = st.session_state.get("reg_query", "") or ""
    q = st.session_state["reg_q"]

    st.markdown("### 규제·근거 검색")
    st.caption("규정 이름을 몰라도 실무 질문으로, 또는 법령명으로 관련 공식 근거를 찾습니다.")
    sc1, sc2 = st.columns([7, 1])
    with sc1:
        qin = st.text_input("검색", value=q, label_visibility="collapsed",
                            placeholder="예: 생물학적제제 판매관리 규칙 / 냉장 의약품 운송 중 온도 이탈이 발생하면?",
                            key="reg_search_box")
    with sc2:
        if st.button("검색", use_container_width=True, key="reg_search_btn"):
            st.session_state["reg_q"] = qin
            st.rerun()

    payload = _build_payload(st.session_state["reg_q"])
    components.html(_reg_html(payload), height=900, scrolling=False)

    if payload["hasQuery"]:
        if st.button("💬 QA 분석가에게 영향 분석 요청", key="reg_quick_qa"):
            _route_qa(payload["query"], payload)

    for cmd in _bridge_cmds(payload):
        if st.button(_BRIDGE + cmd, key="rgb_" + cmd):
            _handle_bridge(cmd, payload)
