"""
Pharma Watch — 다크 네이비 테마 주입.

- 톤: 신뢰감 있는 규제 인텔리전스 대시보드
- 컬러: 다크 네이비 + 포인트 4색(블루/청록/앰버/레드)
- 타이포: DM Serif Display(제목) / DM Mono(수치·코드) / Noto Sans KR(본문)
"""
import streamlit as st
import streamlit.components.v1 as components


# ── 디자인 토큰 ─────────────────────
TOKENS = {
    "bg_0":         "#0a0d14",
    "bg_1":         "#10141f",
    "bg_2":         "#161c2e",
    "border":       "#1f2940",
    "border_strong":"#2a3654",

    "text":         "#f1f5fb",
    "text_2":       "#c4cfe2",
    "text_3":       "#8794ad",

    "accent":       "#3d7aed",
    "accent_soft":  "#1a2a52",
    "qa":           "#2ec4b6",
    "qa_soft":      "#0f3d3a",
    "warn":         "#f5a623",
    "warn_soft":    "#3d2c11",
    "danger":       "#e05252",
    "danger_soft":  "#3d1818",
}


from pathlib import Path

# ── 테마 프리셋 (그날그날 기분대로 — 사이드바에서 선택) ──────────────
# 모든 테마는 TOKENS 와 동일한 키를 가진다. 레이아웃은 동일하고 색만 교체.
THEMES = {
    "네이비 (기본)": dict(TOKENS),
    "인디고 라이트": {
        "bg_0": "#EEF1F8", "bg_1": "#FFFFFF", "bg_2": "#FFFFFF",
        "border": "#E4E8F2", "border_strong": "#D9DEEC",
        "text": "#1E2333", "text_2": "#5B6178", "text_3": "#9AA0B5",
        "accent": "#6D5EF6", "accent_soft": "#ECEAFE",
        "qa": "#12B5A5", "qa_soft": "#DFF6F2",
        "warn": "#C0790F", "warn_soft": "#FDF0DC",
        "danger": "#D8453E", "danger_soft": "#FBE7E6",
    },
    "딥그린 라이트": {
        "bg_0": "#FAFBFA", "bg_1": "#FFFFFF", "bg_2": "#FFFFFF",
        "border": "#E8ECE9", "border_strong": "#DCE3DE",
        "text": "#18211C", "text_2": "#5D6B63", "text_3": "#93A099",
        "accent": "#0E7C5A", "accent_soft": "#E4F1EA",
        "qa": "#0E7C5A", "qa_soft": "#E4F1EA",
        "warn": "#B8730E", "warn_soft": "#FBEFD9",
        "danger": "#C7433C", "danger_soft": "#FAE6E5",
    },
    "소프트 네이비": {
        "bg_0": "#18203A", "bg_1": "#1E2746", "bg_2": "#243054",
        "border": "#2E3A5E", "border_strong": "#3A4870",
        "text": "#EAEEF8", "text_2": "#9AA6C4", "text_3": "#6E7BA0",
        "accent": "#34D6C8", "accent_soft": "#143C44",
        "qa": "#34D6C8", "qa_soft": "#143C44",
        "warn": "#F5B45A", "warn_soft": "#3D3017",
        "danger": "#F08A82", "danger_soft": "#3D2020",
    },
}

# 규제 캘린더(PharmaCal HTML)의 색 변수 override — 액센트/헤더만 교체,
# 카테고리색(법령/식약처/뉴스/마감)과 밝은 표면은 유지해 가독성 보존.
CAL_OVERRIDES = {
    "네이비 (기본)": {},
    "인디고 라이트": {
        "teal": "#6D5EF6", "teal-bright": "#8B7CF8", "teal-glow": "rgba(109,94,246,0.35)",
        "navy-900": "#1E1B3A", "navy-800": "#2A2550", "navy-700": "#352E66",
    },
    "딥그린 라이트": {
        "teal": "#0E7C5A", "teal-bright": "#13A372", "teal-glow": "rgba(14,124,90,0.32)",
        "navy-900": "#0E2A20", "navy-800": "#11392B", "navy-700": "#154A38",
    },
    "소프트 네이비": {
        "teal": "#34D6C8", "teal-bright": "#5FE6DA", "teal-glow": "rgba(52,214,200,0.35)",
        "navy-900": "#10182E", "navy-800": "#18203A", "navy-700": "#222C49",
    },
}

_DEFAULT_THEME = "네이비 (기본)"
_PREF_PATH = Path(__file__).resolve().parent.parent / "db" / "ui_theme.txt"


def _load_pref() -> str:
    try:
        v = _PREF_PATH.read_text(encoding="utf-8").strip()
        return v if v in THEMES else _DEFAULT_THEME
    except Exception:
        return _DEFAULT_THEME


def _save_pref(name: str) -> None:
    try:
        _PREF_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PREF_PATH.write_text(name, encoding="utf-8")
    except Exception:
        pass


def get_active_theme_key() -> str:
    return st.session_state.get("ui_theme") or _load_pref()


def get_active_tokens() -> dict:
    return THEMES.get(get_active_theme_key(), THEMES[_DEFAULT_THEME])


def active_calendar_overrides() -> dict:
    """현재 테마의 캘린더 색 override (pages/pharmacal.py 에서 사용)."""
    return CAL_OVERRIDES.get(get_active_theme_key(), {})


def render_theme_picker() -> None:
    """사이드바 테마 선택. 변경 시 저장 + 즉시 재적용."""
    keys = list(THEMES.keys())
    cur = get_active_theme_key()
    idx = keys.index(cur) if cur in keys else 0
    sel = st.selectbox("🎨 테마", keys, index=idx, key="ui_theme_select")
    if sel != cur:
        st.session_state["ui_theme"] = sel
        _save_pref(sel)
        st.rerun()


def _sanitize_css_for_style_tag(css: str) -> str:
    return css.replace("</style", "<\\/style")


def inject_dark_theme():
    """선택된 테마 + 타이포 + Streamlit 위젯 오버라이드."""
    t = get_active_tokens()
    css = f"""
:root {{
    --bg-0: {t['bg_0']};
    --bg-1: {t['bg_1']};
    --bg-2: {t['bg_2']};
    --border: {t['border']};
    --border-strong: {t['border_strong']};
    --text: {t['text']};
    --text-2: {t['text_2']};
    --text-3: {t['text_3']};
    --accent: {t['accent']};
    --accent-soft: {t['accent_soft']};
    --qa: {t['qa']};
    --qa-soft: {t['qa_soft']};
    --warn: {t['warn']};
    --warn-soft: {t['warn_soft']};
    --danger: {t['danger']};
    --danger-soft: {t['danger_soft']};
}}

/* ── 전역 ── */
html, body, [data-testid="stAppViewContainer"] {{
    background: var(--bg-0) !important;
    color: var(--text) !important;
    font-family: 'Noto Sans KR', system-ui, sans-serif !important;
}}

/* ── 본문 가독성 강화 ── */
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] li,
[data-testid="stAppViewContainer"] span,
[data-testid="stAppViewContainer"] strong,
[data-testid="stAppViewContainer"] em,
[data-testid="stAppViewContainer"] blockquote,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] strong,
[data-testid="stMarkdownContainer"] em,
.stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span {{
    color: var(--text) !important;
}}

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] *,
small, .stCaption {{
    color: var(--text-2) !important;
}}

code, pre {{
    color: var(--text) !important;
    background: var(--bg-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 4px !important;
    padding: 1px 6px !important;
}}
pre code {{
    border: none !important;
    padding: 0 !important;
}}

[data-testid="stAlert"] {{
    background: var(--bg-2) !important;
    border: 1px solid var(--border-strong) !important;
}}
[data-testid="stAlert"] * {{
    color: var(--text) !important;
}}

[data-testid="stSpinner"],
[data-testid="stSpinner"] * {{
    color: var(--text) !important;
    background: transparent !important;
}}

[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stHorizontalBlock"] > [data-testid="stVerticalBlock"] {{
    background: transparent !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: var(--bg-1) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}}

[data-testid="stExpander"] {{
    background: var(--bg-1) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}}
[data-testid="stExpander"] summary {{
    color: var(--text) !important;
}}
[data-testid="stExpander"] * {{
    color: var(--text) !important;
}}

[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label {{
    color: var(--text) !important;
}}

[data-testid="stWidgetLabel"] {{
    color: var(--text-2) !important;
}}

/* ── 메뉴/푸터만 숨김 ── */
#MainMenu, footer {{ visibility: hidden; }}
header [data-testid="stToolbar"],
header [data-testid="stStatusWidget"],
header [data-testid="stDecoration"],
header [data-testid="stHeaderActionElements"] {{ visibility: hidden; }}

/* ── 사이드바 ── */
[data-testid="stSidebar"] {{
    background: var(--bg-1) !important;
    border-right: 1px solid var(--border) !important;
    display: block !important;
    visibility: visible !important;
}}
[data-testid="stSidebarCollapsed"],
[data-testid="stSidebarCollapseButton"] {{
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 999999 !important;
    pointer-events: auto !important;
}}
[data-testid="stSidebar"] * {{ color: var(--text) !important; }}
[data-testid="stSidebar"] .stButton button {{
    background: var(--bg-2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
    font-family: 'Noto Sans KR', sans-serif !important;
    font-weight: 500 !important;
    text-align: left !important;
    transition: all 0.15s !important;
}}
[data-testid="stSidebar"] .stButton button:hover {{
    background: var(--accent-soft) !important;
    border-color: var(--accent) !important;
    color: var(--text) !important;
}}

/* ── 제목 타이포 ── */
h1, h2, h3 {{
    font-family: 'DM Serif Display', 'Noto Serif KR', serif !important;
    color: var(--text) !important;
    letter-spacing: -0.01em;
}}

code, pre, .stCode, [data-testid="stMetricValue"] {{
    font-family: 'DM Mono', 'JetBrains Mono', monospace !important;
}}

[data-testid="stMetric"] {{
    background: var(--bg-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 14px !important;
}}

.stTabs [data-baseweb="tab"] {{
    font-family: 'Noto Sans KR', sans-serif !important;
    color: var(--text-2) !important;
    padding: 12px 16px !important;
}}
.stTabs [aria-selected="true"] {{
    color: var(--text) !important;
    border-bottom-color: var(--accent) !important;
}}

.stButton button {{
    font-family: 'Noto Sans KR', sans-serif !important;
    border-radius: 8px !important;
    background: var(--bg-2) !important;
    color: var(--text) !important;
    border: 1px solid var(--border-strong) !important;
    transition: all 0.15s !important;
}}
.stButton button:hover {{
    border-color: var(--accent) !important;
    background: var(--accent-soft) !important;
}}

.stTextInput input, .stTextArea textarea, .stSelectbox select, .stNumberInput input {{
    background: var(--bg-1) !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
    font-family: 'Noto Sans KR', sans-serif !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(61, 122, 237, 0.15) !important;
}}
"""
    css = _sanitize_css_for_style_tag(css)
    st.html(f"<style>{css}</style>")


def inject_global_css():
    """폰트 로드 (CDN). DM Serif Display + DM Mono + Noto Sans KR."""
    st.html("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Serif+Display&family=Noto+Sans+KR:wght@300;400;500;700&display=swap" rel="stylesheet">
""".strip())


def inject_sidebar_toggle():
    """항상 보이는 사이드바 토글 버튼(☰)을 좌상단에 띄운다.

    Streamlit 버전별로 '펼치기' 컨트롤 testid 가 달라 접은 뒤 다시 못 펴는 문제를
    우회한다. 이 버튼은 네이티브 컨트롤(접기/펴기 중 존재하는 것)을 클릭해 토글한다.
    """
    components.html(
        """
<script>
(function(){
  var doc = window.parent.document;
  function ensureBtn(){
    if (doc.getElementById('pw-sidebar-toggle')) return;
    var btn = doc.createElement('button');
    btn.id = 'pw-sidebar-toggle';
    btn.innerHTML = '☰';
    btn.title = '메뉴 열기/닫기';
    btn.style.cssText = 'position:fixed;top:10px;left:10px;z-index:1000000;'
      + 'width:40px;height:40px;border-radius:9px;border:1px solid #2a3654;'
      + 'background:#161c2e;color:#f1f5fb;font-size:18px;cursor:pointer;'
      + 'box-shadow:0 2px 8px rgba(0,0,0,0.35);';
    btn.onclick = function(){
      var sel = [
        '[data-testid="stSidebarCollapseButton"] button',
        '[data-testid="stSidebarCollapsedControl"] button',
        '[data-testid="stExpandSidebarButton"]',
        '[data-testid="stExpandSidebarButton"] button',
        '[data-testid="stSidebarCollapsedControl"]',
        '[data-testid="collapsedControl"]'
      ];
      for (var i=0;i<sel.length;i++){
        var el = doc.querySelector(sel[i]);
        if (el){ el.click(); return; }
      }
    };
    doc.body.appendChild(btn);
  }
  ensureBtn();
  var t = setInterval(ensureBtn, 1000);
  setTimeout(function(){ clearInterval(t); }, 10000);
})();
</script>
""",
        height=0,
    )
