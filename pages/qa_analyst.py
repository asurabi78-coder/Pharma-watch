"""Regulatory QA Analyst — VETO 없는 외부용 분석가.

규제/뉴스 항목의 QA 영향도와 Action Item 만 정리한다.
내부 9에이전트·거부권·의사결정·원가/전략 로직은 일절 없음 (원칙 4).

분석 결과는 자동으로 기록 저장되고(저장소: data_layer.qa_history),
하단 '저장된 분석 기록'에서 다시 보거나 개별/전체 삭제할 수 있다.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import branding
from data_layer import qa_history
from ui import theme as _theme
from ui.auth import current_user

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "regulatory_qa_analyst.md"


def _load_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "당신은 의약품 규제 QA 분석가입니다. 입력된 규제/뉴스가 입출고 QA·콜드체인·"
            "GDP 유통에 미치는 영향을 요약하고, 해야 할 일(Action Item)을 목록으로 제시하세요. "
            "의사결정이나 거부권 행사는 하지 않습니다."
        )


# ── 제목 아이콘 (A · 뉴럴 코어) — iframe 렌더(확실), 테마 색 주입 ──────────
def _title_html() -> str:
    t = _theme.get_active_tokens()
    qa = t.get("qa", "#2ec4b6")
    ac = t.get("accent", "#3d7aed")
    bg = t.get("bg_1", "#10141f")
    tx = t.get("text", "#f1f5fb")
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Noto+Serif+KR:wght@400&display=swap" rel="stylesheet">
<style>html,body{{margin:0;background:transparent;overflow:hidden;}}</style></head>
<body><div style="display:flex;align-items:center;gap:12px;">
<svg width="46" height="46" viewBox="0 0 100 100" style="flex:0 0 auto;">
<polygon points="50,8 86,29 86,71 50,92 14,71 14,29" fill="none" stroke="{qa}" stroke-width="4" stroke-linejoin="round"/>
<g stroke="{qa}" stroke-width="2" opacity="0.45">
<line x1="50" y1="50" x2="50" y2="30"/><line x1="50" y1="50" x2="34" y2="44"/><line x1="50" y1="50" x2="66" y2="44"/><line x1="50" y1="50" x2="38" y2="66"/><line x1="50" y1="50" x2="62" y2="66"/><line x1="34" y1="44" x2="50" y2="30"/><line x1="66" y1="44" x2="50" y2="30"/></g>
<g fill="{ac}"><circle cx="50" cy="30" r="3.6"/><circle cx="34" cy="44" r="3.6"/><circle cx="66" cy="44" r="3.6"/><circle cx="38" cy="66" r="3.6"/><circle cx="62" cy="66" r="3.6"/></g>
<circle cx="50" cy="50" r="6.5" fill="{bg}" stroke="{qa}" stroke-width="3"/></svg>
<span style="font-family:'DM Serif Display','Noto Serif KR',serif;font-size:33px;color:{tx};letter-spacing:-0.01em;line-height:1;">QA 분석가</span>
</div></body></html>"""


def _hex_lum(h: str) -> float:
    h = h.lstrip("#")
    if len(h) != 6:
        return 0.0
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


# 뉴럴 컨스텔레이션 로딩 — 테마(밝음/어두움)에 따라 색·배경 자동 전환.
_LOADER_TEMPLATE = """<!doctype html><html><head><meta charset='utf-8'><style>
html{background:transparent;}
body{margin:0;font-family:'Noto Sans KR',system-ui,sans-serif;}
.pwpanel{background:__BG__;border:1px solid __BORDER__;border-radius:12px;overflow:hidden;padding-bottom:6px;}
</style></head><body>
<div class="pwpanel">
<canvas id="pwl" style="width:100%;height:150px;display:block;"></canvas>
<div style="text-align:center;font-size:12px;letter-spacing:.2em;color:__QA__;padding:2px 0 4px;">QA 영향도 분석 중</div>
</div>
<script>
(function(){
var DARK=__DARK__,QA='__QA__',AC='__AC__';
var cv=document.getElementById('pwl'),ctx=cv.getContext('2d');
var H=150,dpr=Math.min(window.devicePixelRatio||1,2),W=420,N=40,pts=[],edges=[],ripples=[],start=performance.now();
function build(){
  W=cv.clientWidth||420;cv.width=W*dpr;cv.height=H*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);
  pts=[];var cx=W/2,cy=H/2,Rx=Math.min(W*0.42,260),Ry=H*0.42;
  for(var i=0;i<N;i++){var r=Math.sqrt((i+0.5)/N),th=i*2.39996;
    pts.push({bx:cx+r*Rx*Math.cos(th),by:cy+r*Ry*Math.sin(th),ph:Math.random()*6.28,sp:0.35+Math.random()*0.4,am:1.6+Math.random()*2.4,x:0,y:0});}
  edges=[];var th2=Math.min(W,H*1.6)*0.2;
  for(var a=0;a<N;a++)for(var b=a+1;b<N;b++){var dx=pts[a].bx-pts[b].bx,dy=pts[a].by-pts[b].by,dd=Math.sqrt(dx*dx+dy*dy);if(dd<th2)edges.push({a:a,b:b,w:1-dd/th2});}
}
function draw(now){
  var t=(now-start)/1000,cx=W/2,cy=H/2;ctx.clearRect(0,0,W,H);
  for(var i=0;i<N;i++){var p=pts[i];p.x=p.bx+Math.cos(t*p.sp+p.ph)*p.am;p.y=p.by+Math.sin(t*p.sp*1.1+p.ph)*p.am;}
  if(ripples.length===0||t-ripples[ripples.length-1].t0>2.9)ripples.push({t0:t});
  ripples=ripples.filter(function(r){return t-r.t0<2.8;});
  function glow(px,py){var g=0,dist=Math.sqrt((px-cx)*(px-cx)+(py-cy)*(py-cy));
    for(var k=0;k<ripples.length;k++){var age=t-ripples[k].t0,wf=age*120,b=Math.max(0,1-Math.abs(dist-wf)/42)*Math.max(0,1-age/2.8);if(b>g)g=b;}return g;}
  ctx.lineCap='round';
  for(var e=0;e<edges.length;e++){var E=edges[e],A=pts[E.a],B=pts[E.b],gg=glow((A.x+B.x)/2,(A.y+B.y)/2);
    if(DARK){ctx.globalAlpha=(0.045+0.32*gg)*E.w;ctx.strokeStyle=gg>0.25?'#9af0e6':QA;ctx.lineWidth=gg>0.4?1.3:0.7;}
    else{ctx.globalAlpha=(0.10+0.42*gg)*E.w;ctx.strokeStyle=gg>0.3?AC:QA;ctx.lineWidth=gg>0.4?1.2:0.7;}
    ctx.beginPath();ctx.moveTo(A.x,A.y);ctx.lineTo(B.x,B.y);ctx.stroke();}
  ctx.globalAlpha=1;
  for(var n=0;n<N;n++){var p=pts[n],gg=glow(p.x,p.y);
    if(DARK){ctx.shadowBlur=5+13*gg;ctx.shadowColor=gg>0.3?'#bafff5':AC;ctx.fillStyle=gg>0.3?'#dffffb':QA;ctx.globalAlpha=0.45+0.55*gg;
      ctx.beginPath();ctx.arc(p.x,p.y,1.4+2.2*gg,0,6.2832);ctx.fill();}
    else{if(gg>0.08){ctx.globalAlpha=0.16*gg;ctx.fillStyle=QA;ctx.beginPath();ctx.arc(p.x,p.y,3+7*gg,0,6.2832);ctx.fill();}
      ctx.globalAlpha=0.3+0.6*gg;ctx.fillStyle=gg>0.45?AC:QA;ctx.beginPath();ctx.arc(p.x,p.y,1.4+1.8*gg,0,6.2832);ctx.fill();}}
  ctx.shadowBlur=0;ctx.globalAlpha=1;requestAnimationFrame(draw);
}
build();if(window.ResizeObserver)new ResizeObserver(build).observe(cv);requestAnimationFrame(draw);
})();
</script></body></html>"""


def _loader_html() -> str:
    t = _theme.get_active_tokens()
    bg = t.get("bg_1", "#10141f")
    border = t.get("border", "#1f2940")
    qa = t.get("qa", "#2ec4b6")
    ac = t.get("accent", "#3d7aed")
    dark = "true" if _hex_lum(bg) < 0.5 else "false"
    return (
        _LOADER_TEMPLATE
        .replace("__BG__", bg)
        .replace("__BORDER__", border)
        .replace("__QA__", qa)
        .replace("__AC__", ac)
        .replace("__DARK__", dark)
    )


def render():
    components.html(_title_html(), height=60)

    # 계정이 바뀌면(다른 ID 로그인) 이전 화면 상태(질문/답변/입력)를 비운다.
    _uid = current_user()
    if st.session_state.get("qa_owner") != _uid:
        for _k in ("qa_last_q", "qa_last_a", "qa_saved_notice", "qa_save_err", "qa_input"):
            st.session_state.pop(_k, None)
        st.session_state["qa_owner"] = _uid

    st.caption(
        "규제·고시·뉴스 항목의 QA 영향도와 해야 할 일을 정리합니다. "
        "(분석·요약 전용 — 의사결정/거부권 없음)"
    )

    text = st.text_area(
        "분석할 규제·고시·뉴스 내용을 붙여넣으세요",
        height=160,
        placeholder="예: 의약품 등의 안전에 관한 규칙 개정 — 입출고 시 품질책임자(QA) 입회 요건 신설 ...",
        key="qa_input",
    )

    if st.button("영향도 분석", type="primary", key="qa_run"):
        if not text.strip():
            st.warning("분석할 내용을 입력하세요.")
        else:
            try:
                from utils.claude_client import call_claude

                loader = st.empty()
                with loader.container():
                    components.html(_loader_html(), height=192)
                try:
                    out = call_claude(
                        system=_load_prompt(),
                        messages=[{"role": "user", "content": text.strip()}],
                        max_tokens=900,
                        feature="qa_analyst",
                    )
                finally:
                    loader.empty()
                # 분석 실행 행동 기록 (토큰은 call_claude 내부에서 별도 기록)
                try:
                    from data_layer import usage as _usage
                    from ui.auth import current_user as _cur
                    _usage.log_action(_cur(), "qa_analyst", "영향도분석", text.strip()[:80])
                except Exception:
                    pass
                # 결과를 세션에 보관(삭제 등 rerun 후에도 유지) + 기록 자동 저장
                st.session_state["qa_last_q"] = text.strip()
                st.session_state["qa_last_a"] = out
                try:
                    qa_history.save(text.strip(), out, user=_uid)
                    st.session_state["qa_saved_notice"] = True
                except Exception as e:  # noqa: BLE001
                    st.session_state["qa_saved_notice"] = False
                    st.session_state["qa_save_err"] = f"{type(e).__name__}: {e}"
            except Exception as e:  # noqa: BLE001
                st.error("분석 호출에 실패했습니다. .env 의 ANTHROPIC_API_KEY 설정을 확인하세요.")
                st.caption(f"detail: {type(e).__name__}: {e}")

    # ── 최근 분석 결과 (rerun 후에도 유지) ──
    last_a = st.session_state.get("qa_last_a")
    if last_a:
        st.markdown("---")
        st.markdown("#### 분석 결과")
        if st.session_state.pop("qa_saved_notice", False):
            st.success("✅ 기록에 저장되었습니다. 아래 '저장된 분석 기록'에서 다시 볼 수 있어요.")
        elif st.session_state.get("qa_save_err"):
            st.warning(f"기록 저장 실패: {st.session_state.pop('qa_save_err')}")
        st.markdown(last_a)

    # ── 저장된 분석 기록 (목록 + 삭제) — 현재 계정 것만 ──
    _render_history(_uid)

    st.markdown("---")
    st.caption("🔒 대화형 연속 질의 · SOP 자동비교 · CAPA 자동작성은 상위 플랜 기능입니다.")
    st.caption(branding.FOOTER_NOTE)


def _render_history(user: str):
    st.markdown("---")
    try:
        total = qa_history.count(user=user)
        records = qa_history.list_records(user=user, limit=200) if total else []
    except Exception as e:  # noqa: BLE001
        st.warning(f"기록을 불러오지 못했습니다: {type(e).__name__}: {e}")
        return

    col_t, col_clear = st.columns([4, 1])
    with col_t:
        st.markdown(f"#### 📁 저장된 분석 기록 ({total}건)")
    with col_clear:
        if total:
            if st.session_state.get("qa_confirm_clear"):
                if st.button("⚠️ 전체삭제 확정", type="primary",
                             use_container_width=True, key="qa_clear_yes"):
                    qa_history.clear_all(user=user)
                    st.session_state.pop("qa_confirm_clear", None)
                    st.session_state.pop("qa_last_a", None)
                    st.session_state.pop("qa_last_q", None)
                    st.rerun()
            else:
                if st.button("🗑 전체 삭제", use_container_width=True, key="qa_clear_ask"):
                    st.session_state["qa_confirm_clear"] = True
                    st.rerun()

    if st.session_state.get("qa_confirm_clear"):
        st.warning("전체 기록을 삭제합니다. 되돌릴 수 없어요. 오른쪽 '전체삭제 확정'을 누르세요.")
        if st.button("취소", key="qa_clear_cancel"):
            st.session_state.pop("qa_confirm_clear", None)
            st.rerun()

    if not records:
        st.caption("아직 저장된 기록이 없습니다. 위에서 분석하면 자동으로 저장됩니다.")
        return

    for rec in records:
        q_head = rec.question if len(rec.question) <= 50 else rec.question[:50] + "…"
        with st.expander(f"🕑 {rec.created_at} · {q_head}"):
            st.markdown("**질문 / 입력**")
            st.code(rec.question, language=None)
            st.markdown("**분석 결과**")
            st.markdown(rec.answer)
            if st.button("🗑 이 기록 삭제", key=f"qa_del_{rec.id}"):
                qa_history.delete(rec.id, user=user)
                st.rerun()
