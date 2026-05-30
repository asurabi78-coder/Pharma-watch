"""뉴스룸 — Phase B.

3개 사이트 동시 수집 + SQLite 영속.
- 데일리팜 (HTML)
- 약업신문 (HTML — 유통/산업 카테고리 별도)
- 물류신문 (RSS — 3PL/콜드체인/SCM/물류센터)
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from data_layer.news.models import NewsItem
from data_layer.news.connectors.dailypharm import fetch as fetch_dailypharm
from data_layer.news.connectors.yakup import fetch as fetch_yakup
from data_layer.news.connectors.klnews import fetch as fetch_klnews
from data_layer.news import repo


SOURCES = [
    {"key": "dailypharm", "label": "데일리팜", "fetch": fetch_dailypharm, "default_limit": 15},
    {"key": "yakup",      "label": "약업신문", "fetch": fetch_yakup,      "default_limit": 15},
    {"key": "klnews",     "label": "물류신문", "fetch": fetch_klnews,     "default_limit": 15},
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


def fetch_and_save(*, per_source_limit: Optional[int] = None) -> dict:
    """fetch_all + SQLite 저장."""
    items, stats = fetch_all(per_source_limit=per_source_limit)
    new_n, upd_n = repo.upsert(items) if items else (0, 0)
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
    "fetch_all",
    "fetch_and_save",
    "repo",
]
