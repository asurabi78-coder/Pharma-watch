"""규제·근거 검색 엔진 — 정규화·의도판정·fuzzy·출처등급 재정렬 (결정론적).

목표(스펙):
- 법령명 검색(TITLE_LOOKUP) + 상황·주제 검색(TOPIC_DISCOVERY)을 한 입력에서 자동 처리.
- 국내 공식 근거 최우선, WHO=해외 참고규범/SOP=내부 참고자료로 분리, 뉴스 제외.
- 가짜 법령명/URL 생성 금지 — 공식 데이터(canonical_title)와 law.go.kr 공식 스킴만 사용.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import quote

# 기존 시드 항목 메타 보강(시드 파일 미수정) — id → 정식명칭/문서종류/출처구분
_OVERRIDE: Dict[str, dict] = {
    "kgsp_storage": {"canonical": "약사법 시행규칙", "doctype": "시행규칙", "origin": "domestic",
                     "status": "현행", "aliases": ["KGSP", "의약품 유통품질 관리기준", "유통품질관리기준", "보관관리"]},
    "kgsp_release": {"canonical": "약사법 시행규칙", "doctype": "시행규칙", "origin": "domestic",
                     "status": "현행", "aliases": ["KGSP", "출하증명", "유통품질관리기준"]},
    "narcotics_storage": {"canonical": "마약류 관리에 관한 법률", "doctype": "법률", "origin": "domestic",
                          "status": "현행", "aliases": ["마약류관리법", "마약류"]},
    "recall_procedure": {"canonical": "약사법", "doctype": "법률", "origin": "domestic",
                         "status": "현행", "aliases": ["회수", "리콜", "의약품 회수", "폐기"]},
    "contract_outsourcing": {"canonical": "약사법 시행규칙", "doctype": "시행규칙", "origin": "domestic",
                             "status": "현행", "aliases": ["위수탁", "품질계약", "Quality Agreement"]},
    "returns_management": {"canonical": "약사법 시행규칙", "doctype": "시행규칙", "origin": "domestic",
                           "status": "현행", "aliases": ["KGSP", "반품", "재입고", "재판매"]},
    "inventory_expiry": {"canonical": "약사법 시행규칙", "doctype": "시행규칙", "origin": "domestic",
                         "status": "현행", "aliases": ["KGSP", "재고", "유효기간", "FEFO", "선입선출"]},
    "self_inspection": {"canonical": "약사법 시행규칙", "doctype": "안내서", "origin": "domestic",
                        "status": "현행", "aliases": ["자체점검", "실태조사", "KGSP", "audit"]},
    "mfds_transport": {"canonical": "생물학적제제 등의 제조ㆍ판매관리 규칙", "doctype": "안내서", "origin": "domestic",
                       "status": "현행", "aliases": ["생물학적제제", "보관 수송", "콜드체인 안내서", "민원인 안내서"]},
    "change_control": {"canonical": "", "doctype": "안내서", "origin": "domestic", "status": "현행",
                       "aliases": ["변경관리", "change control"]},
    "gmp_deviation": {"canonical": "", "doctype": "안내서", "origin": "domestic", "status": "현행",
                      "aliases": ["GMP", "일탈", "CAPA", "deviation"]},
    "gdp_cold_chain": {"canonical": "", "doctype": "해외 가이드", "origin": "foreign", "status": "참고",
                       "aliases": ["WHO", "GDP", "TRS 961", "콜드체인"],
                       "url": "https://www.who.int/teams/health-product-policy-and-standards/standards-and-specifications"},
    "sop_temp_excursion": {"canonical": "", "doctype": "내부 SOP", "origin": "internal", "status": "참고",
                           "aliases": ["SOP", "온도이탈 절차"]},
    "ai_estimate_sample": {"canonical": "", "doctype": "AI 추정", "origin": "ai", "status": "참고", "aliases": []},
}

# 약칭·동의어 확장 (주제 검색 보강)
_SYNONYMS = {
    "kgsp": "의약품 유통품질 관리기준 약사법 시행규칙",
    "gdp": "유통품질 콜드체인 보관 운송",
    "gmp": "제조 품질 일탈",
    "콜드체인": "콜드체인 냉장 냉동 온도 수송 보관 생물학적제제",
    "온도이탈": "온도 이탈 일탈 격리",
    "온도 이탈": "온도 이탈 일탈 격리",
    "도매상": "도매 유통 약사법",
    "반품": "반품 재입고 재판매 격리",
    "회수": "회수 리콜 폐기",
    "관리약사": "관리약사 약사 출고 책임",
}

_DOMESTIC_LAW_TYPES = {"법률", "시행령", "시행규칙", "규칙"}
_DOMESTIC_RULE_TYPES = {"고시", "행정규칙"}
_GUIDE_TYPES = {"안내서", "지침"}

_SECTIONS = [
    ("domestic_law", "국내 공식 법령"),
    ("domestic_rule", "식약처 고시·행정규칙"),
    ("domestic_guide", "식약처 안내서·지침"),
    ("foreign", "해외 참고규범"),
    ("internal", "내부 참고자료"),
]


@dataclass
class Hit:
    id: str
    canonical_title: str
    display_title: str
    document_type: str
    issuing_authority: str
    official_source_url: str
    promulgation_date: str
    effective_date: str
    current_status: str
    origin: str
    article: str
    content: str
    why: str
    related_ids: List[str]
    section: str
    score: float


@dataclass
class SearchResult:
    query: str
    intent: str
    hits: List[Hit] = field(default_factory=list)
    no_exact: bool = False


def _nospace(s):
    return re.sub(r"\s+", "", (s or "")).lower()


def _meta(e):
    ov = _OVERRIDE.get(e.id, {})
    canonical = getattr(e, "canonical_title", "") or ov.get("canonical", "") or ""
    doctype = getattr(e, "document_type", "") or ov.get("doctype", "")
    origin = getattr(e, "origin", "") or ov.get("origin", "domestic")
    status = getattr(e, "current_status", "") or ov.get("status", "현행")
    aliases = list(getattr(e, "aliases", []) or []) + list(ov.get("aliases", []))
    authority = getattr(e, "issuing_authority", "") or (
        "WHO 등 해외" if origin == "foreign" else
        "내부(예시)" if origin == "internal" else
        "AI 추정" if origin == "ai" else "식품의약품안전처")
    url = getattr(e, "official_source_url", "") or ov.get("url", "")
    if not url and origin == "domestic" and canonical:
        url = "https://www.law.go.kr/법령/" + quote(canonical)
    return canonical, doctype, origin, status, aliases, authority, url


def _section_of(doctype, origin):
    if origin == "foreign":
        return "foreign"
    if origin in ("internal", "ai"):
        return "internal"
    if doctype in _DOMESTIC_RULE_TYPES:
        return "domestic_rule"
    if doctype in _GUIDE_TYPES:
        return "domestic_guide"
    return "domestic_law"


def normalize(q: str):
    nq = (q or "").strip()
    nq = re.sub(r"[\"'“”‘’]+", " ", nq)
    nq = re.sub(r"\s+", " ", nq).strip()
    low = nq.lower()
    expanded = nq
    for k, v in _SYNONYMS.items():
        if k in low:
            expanded += " " + v
    toks = [t for t in re.split(r"[\s·,]+", expanded) if len(t) >= 2]
    return nq, _nospace(nq), toks


_QUESTION_MARKERS = ("어떻", "하나요", "되나요", "있나요", "궁금", "봐야", "무엇", "?", "알려", "방법")
_LAW_SUFFIX = ("법", "법률", "시행령", "시행규칙", "규칙", "고시", "규정", "기준", "지침", "안내서")


def detect_intent(nq, nospace, entries):
    """TITLE_LOOKUP vs TOPIC_DISCOVERY (자동)."""
    low = nq
    if any(m in low for m in _QUESTION_MARKERS):
        return "TOPIC_DISCOVERY"
    # 정식명칭/별칭과의 근접도
    best = 0.0
    for e in entries:
        canonical, *_rest = _meta(e)
        names = [canonical, e.title] + _OVERRIDE.get(e.id, {}).get("aliases", []) + list(getattr(e, "aliases", []) or [])
        for n in names:
            ns = _nospace(n)
            if not ns:
                continue
            if nospace and (nospace in ns or ns in nospace):
                return "TITLE_LOOKUP"
            best = max(best, difflib.SequenceMatcher(None, nospace, ns).ratio())
    if best >= 0.6:
        return "TITLE_LOOKUP"
    # 짧고 법령 접미사로 끝나면 명칭 검색
    if nq.endswith(_LAW_SUFFIX) and len(nq.split()) <= 5:
        return "TITLE_LOOKUP"
    return "TOPIC_DISCOVERY"


def _origin_weight(origin, doctype):
    if origin == "domestic":
        base = 40
        if doctype in _DOMESTIC_LAW_TYPES or doctype in _DOMESTIC_RULE_TYPES:
            base += 15
        return base
    if origin == "foreign":
        return -45
    if origin == "internal":
        return -65
    return -85  # ai


def search(query: str, entries: Optional[list] = None) -> SearchResult:
    if entries is None:
        from data_layer.regulatory.seed import SEED_ENTRIES
        entries = SEED_ENTRIES
    nq, nospace, toks = normalize(query)
    if not nq:
        return SearchResult(query="", intent="TOPIC_DISCOVERY")
    intent = detect_intent(nq, nospace, entries)

    scored: List[Hit] = []
    best_title_ratio = 0.0
    for e in entries:
        canonical, doctype, origin, status, aliases, authority, url = _meta(e)
        names = [n for n in [canonical, e.title] + aliases if n]
        title_score = 0.0
        ratio = 0.0
        matched_name = ""
        for n in names:
            ns = _nospace(n)
            if not ns:
                continue
            if nospace and nospace == ns:
                title_score = max(title_score, 120); matched_name = n
            elif nospace and (nospace in ns or ns in nospace):
                title_score = max(title_score, 95); matched_name = matched_name or n
            r = difflib.SequenceMatcher(None, nospace, ns).ratio()
            if r > ratio:
                ratio = r
                if r >= 0.5 and not matched_name:
                    matched_name = n
        title_score = max(title_score, ratio * 70)
        best_title_ratio = max(best_title_ratio, ratio if (nospace in _nospace(canonical or e.title) or _nospace(canonical or e.title) in nospace or ratio) else ratio)

        # 키워드 매칭
        title_blob = (canonical + " " + e.title + " " + " ".join(aliases)).lower()
        tag_blob = (" ".join(getattr(e, "tags", []) or []) + " " + " ".join(getattr(e, "scope_tags", []) or [])).lower()
        body_blob = ((getattr(e, "content", "") or "") + " " + (getattr(e, "practical_interpretation", "") or "")).lower()
        kw = 0
        hit_terms = []
        for t in toks:
            tl = t.lower()
            if tl in title_blob:
                kw += 14; hit_terms.append(t)
            elif tl in tag_blob:
                kw += 8; hit_terms.append(t)
            elif tl in body_blob:
                kw += 2

        if intent == "TITLE_LOOKUP":
            score = title_score * 1.4 + kw * 0.5
        else:
            score = kw * 1.2 + title_score * 0.5
        score += _origin_weight(origin, doctype)

        if score <= 0:
            continue
        # 일치 이유
        if title_score >= 95:
            why = f"검색어가 ‘{matched_name or canonical or e.title}’ 명칭과 일치"
        elif matched_name:
            why = f"‘{matched_name}’ 와 유사 (명칭 유사도 {int(ratio*100)}%)"
        elif hit_terms:
            why = "관련 키워드: " + ", ".join(dict.fromkeys(hit_terms[:4]))
        else:
            why = "관련 본문 일치"

        scored.append(Hit(
            id=e.id, canonical_title=canonical or e.title, display_title=e.title,
            document_type=doctype or "규정", issuing_authority=authority,
            official_source_url=url, promulgation_date=getattr(e, "promulgation_date", ""),
            effective_date=getattr(e, "effective_date", ""), current_status=status,
            origin=origin, article=getattr(e, "article", ""),
            content=getattr(e, "content", "") or "", why=why,
            related_ids=list(getattr(e, "related_ids", []) or []),
            section=_section_of(doctype, origin), score=round(score, 1),
        ))

    # 정식명칭 기준 중복 제거 (같은 법은 1장, 최고점 유지)
    best = {}
    for h in scored:
        k = (h.canonical_title, h.section) if h.canonical_title else h.id
        if k not in best or h.score > best[k].score:
            best[k] = h
    scored = list(best.values())
    # 섹션 순서 → 점수 순
    sec_order = {k: i for i, (k, _) in enumerate(_SECTIONS)}
    scored.sort(key=lambda h: (sec_order.get(h.section, 9), -h.score))

    no_exact = False
    if intent == "TITLE_LOOKUP":
        exact = any(h.score >= 95 * 1.4 - 1 for h in scored)  # 명칭 일치 존재?
        if not exact and best_title_ratio < 0.55:
            no_exact = True

    return SearchResult(query=nq, intent=intent, hits=scored, no_exact=no_exact)


def get_entry(entry_id: str, entries=None):
    if entries is None:
        from data_layer.regulatory.seed import SEED_ENTRIES
        entries = SEED_ENTRIES
    return next((e for e in entries if e.id == entry_id), None)
