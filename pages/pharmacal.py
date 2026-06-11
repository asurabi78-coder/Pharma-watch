"""규제 캘린더 (PharmaCal) — 의약품 규제 인텔리전스 캘린더.

PharmaCal Pro UI(HTML/CSS/JS)를 그대로 임베드한다. UI 는 원본 그대로 100% 보존.
실데이터(법제처/식약처 크롤링) 연동은 후속 단계에서 /api 로 주입 예정.
현재는 정적 샘플 데이터 기반 데모.
"""
import json
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# 앱 최상단(app.py 옆)에 둔 원본 HTML
_HTML_PATH = Path(__file__).parent.parent / "pharmacal-pro.html"



_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _grade_to_type(grade) -> str:
    """SourceTier → 캘린더 카테고리 type."""
    name = getattr(grade, "name", str(grade))
    if name == "LAW":
        return "law"
    if name in ("NOTICE", "GUIDE"):
        return "kfda"
    return "news"


def _impact_for(grade) -> str:
    name = getattr(grade, "name", str(grade))
    return "high" if name in ("LAW", "NOTICE") else "mid"


def _dynamic_events() -> dict:
    """규제 시드 시행일 + 플레이북 최근변경을 캘린더 이벤트 dict 로 모은다.
    { 'YYYY-MM-DD': [ {type,title,impact}, ... ] }"""
    events: dict = {}

    def _add(date_str, ev):
        if not date_str or not _DATE_RE.match(date_str):
            return
        events.setdefault(date_str, []).append(ev)

    # (1) 규제 시드 시행일
    try:
        from data_layer.regulatory.seed import SEED_ENTRIES
        for e in SEED_ENTRIES:
            d = (e.effective_date or "").strip()
            if not _DATE_RE.match(d):
                continue
            _add(d, {
                "type": _grade_to_type(e.grade),
                "title": e.title,
                "impact": _impact_for(e.grade),
            })
    except Exception:
        pass

    # (2) 플레이북 최근/예정 변경
    try:
        from data_layer.regulatory.playbook_seed import PLAYBOOKS
        kind_type = {"시행": "law", "개정 예고": "kfda", "행정 예고": "kfda", "개정": "kfda"}
        for pb in PLAYBOOKS:
            for c in getattr(pb, "recent_changes", []):
                d = (getattr(c, "date", "") or "").strip()
                if not _DATE_RE.match(d):
                    continue
                _add(d, {
                    "type": kind_type.get(getattr(c, "kind", ""), "news"),
                    "title": f"{getattr(c,'kind','')} · {getattr(c,'summary','')}".strip(" ·"),
                    "impact": "high" if getattr(c, "kind", "") == "시행" else "mid",
                })
    except Exception:
        pass

    return events


def _inject_dynamic_events(html: str) -> str:
    """pharmacal-pro.html 의 const EVENTS = {...}; 정의 직후에 동적 이벤트 merge 스크립트 주입."""
    dyn = _dynamic_events()
    if not dyn:
        return html
    payload = json.dumps(dyn, ensure_ascii=False)
    merge_js = (
        "\n<script>\n"
        "/* Pharma Watch — 규제 시드/플레이북에서 자동 생성된 동적 이벤트 병합 */\n"
        f"(function(){{ var DYN = {payload};\n"
        "  try {\n"
        "    for (var d in DYN) {\n"
        "      if (!EVENTS[d]) EVENTS[d] = [];\n"
        "      DYN[d].forEach(function(ev){\n"
        "        var dup = EVENTS[d].some(function(x){return x.title===ev.title;});\n"
        "        if(!dup) EVENTS[d].push(ev);\n"
        "      });\n"
        "    }\n"
        "  } catch(e) { console.warn('dyn events merge failed', e); }\n"
        "})();\n</script>\n"
    )
    # EVENTS 객체 닫는 '  };' 바로 다음에 삽입 (HOLIDAYS 정의 앞)
    anchor = "\n  };\n  const HOLIDAYS"
    if anchor in html:
        return html.replace(anchor, "\n  };" + merge_js + "  const HOLIDAYS", 1)
    return html


def render():
    st.markdown(
        """
        <style>
          section.main > div.block-container {
            padding-top: 1rem; padding-bottom: 0rem;
            padding-left: 1rem; padding-right: 1rem;
            max-width: 100%;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        html = _HTML_PATH.read_text(encoding="utf-8")
        html = _inject_dynamic_events(html)
    except FileNotFoundError:
        st.error(
            f"PharmaCal HTML 을 찾을 수 없습니다: {_HTML_PATH}\n"
            "앱 최상단(app.py 옆)에 pharmacal-pro.html 이 있는지 확인하세요."
        )
        return

    # 선택한 테마에 맞춰 캘린더 색 변수 교체 (액센트/헤더만; 카테고리색·밝은 표면 유지)
    try:
        from ui.theme import active_calendar_overrides
        for _var, _val in active_calendar_overrides().items():
            html = re.sub(
                r"(--" + re.escape(_var) + r":\s*)[^;]+;",
                r"\g<1>" + _val + ";",
                html,
                count=1,
            )
    except Exception:
        pass

    components.html(html, height=1180, scrolling=True)
