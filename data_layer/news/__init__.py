"""뉴스룸 — Phase B.

4개 사이트 동시 수집 + SQLite 영속.
- 데일리팜 (HTML)
- 약업신문 (HTML — 유통/산업 카테고리 별도)
- 물류신문 (RSS — 3PL/콜드체인/SCM/물류센터)
- 메디팜뉴스 (RSS — 정책/의료·병원/약사·약국/제약·바이오/라이프)
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from data_layer.news.models import NewsItem
from data_layer.news.connectors.dailypharm import fetch as fetch_dailypharm
from data_layer.news.connectors.yakup import fetch as fetch_yakup
from data_layer.news.connectors.klnews import fetch as fetch_klnews
from data_layer.news.connectors.medipharm import fetch as fetch_medipharm
from data_layer.news.connectors.mfds_recall import fetch as fetch_mfds_recall
from data_layer.news import repo


SOURCES = [
    {"key": "mfds_recall", "label": "식품의약품안전처", "fetch": fetch_mfds_recall, "default_limit": 30, "official": True},
    {"key": "dailypharm", "label": "데일리팜",   "fetch": fetch_dailypharm, "default_limit": 15},
    {"key": "yakup",      "label": "약업신문",   "fetch": fetch_yakup,      "default_limit": 15},
    {"key": "klnews",     "label": "물류신문",   "fetch": fetch_klnews,     "default_limit": 15},
    {"key": "medipharm",  "label": "메디팜뉴스", "fetch": fetch_medipharm,  "default_limit": 15},
]


def fetch_all(*, per_source_limit: Optional[int] = None) -> tuple:
    """모든 소스 병렬 수집. (items, stats) 반환."""
    stats: dict = {s["label"]: {"count": 0, "error": None} for s in SOURCES}
    items: List[NewsItem] = []

    def _call(src):
        limit = per_source_limit if per_source_limit is not None else src["default_limit"]
        try:
            res = src["fetch"](limit=limit)
            return src, res, None
        except Exception as exc:
            return src, [], f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=len(SOURCES)) as ex:
        for src, res, err in ex.map(_call, SOURCES):
            if err:
                stats[src["label"]]["error"] = err
            else:
                stats[src["label"]]["count"] = len(res)
                items.extend(res)

    return items, stats


def process_items(items: List[NewsItem]) -> List[NewsItem]:
    """수집된 기사 후처리 — 출처유형·카테고리·긴급·QA템플릿·중복그룹(결정론적)."""
    from data_layer.news import classify as C, dedup as D, tagging
    try:
        recent = repo.list_items(days=4, include_hidden=True, limit=500)
    except Exception:
        recent = []
    existing = [{"id": r.id, "title": r.title,
                 "ts": (r.published_at or r.fetched_at),
                 "gid": getattr(r, "duplicate_group_id", "")} for r in recent]
    for it in items:
        blob = " ".join(filter(None, [it.title, it.summary, it.category]))
        it.source_type = C.classify_source_type(it.source, it.source_label, it.url)
        it.source_domain = C.domain_of(it.url)
        rep, cats = C.classify_category(blob)
        it.biz_category = rep
        it.tags = list(dict.fromkeys((it.tags or []) + cats))
        it.is_urgent, it.verification_status, it.urgent_candidate = C.assess_urgency(blob, it.source_type)
        it.qa_impact, it.action_items, it.affected_work = C.qa_template(rep)
        it.qa_relevance_score = C.qa_relevance_score(blob)
        if not getattr(it, "importance", ""):
            it.importance = tagging.grade(blob)
        it.content_hash = D.content_hash(it.title)
        ts_it = it.published_at or it.fetched_at
        gid = None
        for ex in existing:
            if D._within(ex["ts"], ts_it, D.WINDOW_HOURS) and \
               D.similarity(ex["title"], it.title) >= D.SIM_THRESHOLD:
                gid = ex["gid"] or D.content_hash(ex["title"])
                break
        it.duplicate_group_id = gid or it.content_hash
        existing.append({"id": it.id, "title": it.title, "ts": ts_it, "gid": it.duplicate_group_id})
    return items


def fetch_and_save(*, per_source_limit: Optional[int] = None) -> dict:
    """fetch_all + 중요도 태깅 + SQLite 저장."""
    items, stats = fetch_all(per_source_limit=per_source_limit)
    # 결정론적 후처리: 출처유형·카테고리·긴급·QA템플릿·중복그룹·중요도
    try:
        process_items(items)
    except Exception:
        pass
    new_n, upd_n = repo.upsert(items) if items else (0, 0)
    try:
        repo.reconcile_official()
    except Exception:
        pass
    return {
        "stats": stats,
        "total_fetched": len(items),
        "new": new_n,
        "updated": upd_n,
    }


__all__ = [
    "NewsItem",
    "SOURCES",
    "fetch_dailypharm",
    "fetch_yakup",
    "fetch_klnews",
    "fetch_medipharm",
    "fetch_all",
    "fetch_and_save",
    "repo",
]
