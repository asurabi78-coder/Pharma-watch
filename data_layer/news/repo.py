"""뉴스 SQLite 저장소 — 분류 체계 확장.

추가 전용: 기존 컬럼/동작 유지 + 분류 필드 컬럼 추가(ALTER) + 백필.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from data_layer.news.models import NewsItem

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "news.db"

# 신규 분류 컬럼 (이름 → SQL 정의). 마이그레이션에서 없으면 ADD.
_EXTRA_COLUMNS = {
    "source_type": "TEXT DEFAULT ''",
    "source_domain": "TEXT DEFAULT ''",
    "official_source_url": "TEXT DEFAULT ''",
    "biz_category": "TEXT DEFAULT ''",
    "is_urgent": "INTEGER DEFAULT 0",
    "verification_status": "TEXT DEFAULT ''",
    "qa_relevance_score": "INTEGER DEFAULT 0",
    "qa_impact": "TEXT DEFAULT ''",
    "action_items": "TEXT DEFAULT ''",
    "affected_work": "TEXT DEFAULT ''",
    "duplicate_group_id": "TEXT DEFAULT ''",
    "content_hash": "TEXT DEFAULT ''",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    source_label TEXT NOT NULL,
    category TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    fetched_at TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    thumbnail TEXT DEFAULT '',
    is_starred INTEGER DEFAULT 0,
    is_hidden INTEGER DEFAULT 0,
    importance TEXT DEFAULT '',
    source_type TEXT DEFAULT '',
    source_domain TEXT DEFAULT '',
    official_source_url TEXT DEFAULT '',
    biz_category TEXT DEFAULT '',
    is_urgent INTEGER DEFAULT 0,
    verification_status TEXT DEFAULT '',
    qa_relevance_score INTEGER DEFAULT 0,
    qa_impact TEXT DEFAULT '',
    action_items TEXT DEFAULT '',
    affected_work TEXT DEFAULT '',
    duplicate_group_id TEXT DEFAULT '',
    content_hash TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_news_source_ts ON news_items(source, COALESCE(published_at, fetched_at) DESC);
CREATE INDEX IF NOT EXISTS idx_news_fetched ON news_items(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_category ON news_items(category);
"""


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else _DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(news_items)")}
        if "importance" not in cols:
            conn.execute("ALTER TABLE news_items ADD COLUMN importance TEXT DEFAULT ''")
            cols.add("importance")
        for name, ddl in _EXTRA_COLUMNS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE news_items ADD COLUMN {name} {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_stype ON news_items(source_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_group ON news_items(duplicate_group_id)")


_INSERT_COLS = [
    "id", "title", "url", "source", "source_label", "category", "summary",
    "published_at", "fetched_at", "tags", "thumbnail", "importance",
    "source_type", "source_domain", "official_source_url", "biz_category",
    "is_urgent", "verification_status", "qa_relevance_score", "qa_impact",
    "action_items", "affected_work", "duplicate_group_id", "content_hash",
]


def _item_values(it: NewsItem) -> tuple:
    g = lambda n, d="": getattr(it, n, d)  # noqa: E731
    return (
        it.id, it.title, it.url, it.source, it.source_label, it.category, it.summary,
        it.published_at, it.fetched_at, json.dumps(it.tags, ensure_ascii=False),
        it.thumbnail or "", g("importance", "") or "",
        g("source_type", ""), g("source_domain", ""), g("official_source_url", ""),
        g("biz_category", ""), 1 if g("is_urgent", False) else 0,
        g("verification_status", ""), int(g("qa_relevance_score", 0) or 0),
        g("qa_impact", ""), g("action_items", ""), g("affected_work", ""),
        g("duplicate_group_id", ""), g("content_hash", ""),
    )


def upsert(items: Iterable[NewsItem], *, db_path: Optional[Path] = None):
    init_db(db_path)
    new_n = upd_n = 0
    with _connect(db_path) as conn:
        for it in items:
            exists = conn.execute("SELECT id FROM news_items WHERE id = ?", (it.id,)).fetchone()
            if exists is None:
                ph = ",".join(["?"] * len(_INSERT_COLS))
                conn.execute(
                    f"INSERT INTO news_items ({','.join(_INSERT_COLS)}) VALUES ({ph})",
                    _item_values(it),
                )
                new_n += 1
            else:
                # 분류 필드는 항상 갱신, 사용자 상태(starred/hidden)는 보존
                conn.execute(
                    """
                    UPDATE news_items SET
                        title=?, summary=?,
                        published_at=COALESCE(NULLIF(?, ''), published_at),
                        fetched_at=?, tags=?, thumbnail=?,
                        category=COALESCE(NULLIF(?, ''), category),
                        importance=COALESCE(NULLIF(?, ''), importance),
                        source_type=?, source_domain=?,
                        official_source_url=COALESCE(NULLIF(?, ''), official_source_url),
                        biz_category=?, is_urgent=?, verification_status=?,
                        qa_relevance_score=?, qa_impact=?, action_items=?,
                        affected_work=?, duplicate_group_id=?, content_hash=?
                     WHERE id=?
                    """,
                    (
                        it.title, it.summary, it.published_at, it.fetched_at,
                        json.dumps(it.tags, ensure_ascii=False), it.thumbnail or "",
                        it.category, getattr(it, "importance", "") or "",
                        getattr(it, "source_type", ""), getattr(it, "source_domain", ""),
                        getattr(it, "official_source_url", ""), getattr(it, "biz_category", ""),
                        1 if getattr(it, "is_urgent", False) else 0,
                        getattr(it, "verification_status", ""),
                        int(getattr(it, "qa_relevance_score", 0) or 0),
                        getattr(it, "qa_impact", ""), getattr(it, "action_items", ""),
                        getattr(it, "affected_work", ""), getattr(it, "duplicate_group_id", ""),
                        getattr(it, "content_hash", ""), it.id,
                    ),
                )
                upd_n += 1
    return new_n, upd_n


def _row_to_item(row: sqlite3.Row) -> NewsItem:
    keys = row.keys()
    def gv(k, d=""):
        return row[k] if k in keys and row[k] is not None else d
    try:
        tags = json.loads(gv("tags", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        tags = []
    return NewsItem(
        id=row["id"], title=row["title"], url=row["url"], source=row["source"],
        source_label=row["source_label"], category=gv("category", ""),
        summary=gv("summary", ""), published_at=gv("published_at", ""),
        fetched_at=gv("fetched_at", ""), tags=tags,
        thumbnail=gv("thumbnail", "") or None, importance=gv("importance", ""),
        source_type=gv("source_type", ""), source_domain=gv("source_domain", ""),
        official_source_url=gv("official_source_url", ""), biz_category=gv("biz_category", ""),
        is_urgent=bool(gv("is_urgent", 0)), verification_status=gv("verification_status", ""),
        qa_relevance_score=int(gv("qa_relevance_score", 0) or 0),
        qa_impact=gv("qa_impact", ""), action_items=gv("action_items", ""),
        affected_work=gv("affected_work", ""), duplicate_group_id=gv("duplicate_group_id", ""),
        content_hash=gv("content_hash", ""),
    )


def list_items(
    *,
    sources: Optional[List[str]] = None,
    source_type: Optional[str] = None,
    biz_category: Optional[str] = None,
    is_urgent: Optional[bool] = None,
    category_keyword: Optional[str] = None,
    text_search: Optional[str] = None,
    days: Optional[int] = None,
    include_hidden: bool = False,
    importance_in: Optional[List[str]] = None,
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> List[NewsItem]:
    init_db(db_path)
    where: List[str] = []
    params: list = []
    if sources:
        where.append(f"source IN ({','.join(['?']*len(sources))})")
        params.extend(sources)
    if source_type:
        where.append("source_type = ?")
        params.append(source_type)
    if biz_category:
        where.append("biz_category = ?")
        params.append(biz_category)
    if is_urgent is not None:
        where.append("is_urgent = ?")
        params.append(1 if is_urgent else 0)
    if category_keyword:
        where.append("category LIKE ?")
        params.append(f"%{category_keyword}%")
    if text_search:
        where.append("(title LIKE ? OR summary LIKE ?)")
        params.extend([f"%{text_search}%", f"%{text_search}%"])
    if days is not None and days > 0:
        threshold = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        where.append("substr(COALESCE(NULLIF(published_at, ''), fetched_at), 1, 19) >= ?")
        params.append(threshold)
    if importance_in:
        where.append(f"importance IN ({','.join(['?']*len(importance_in))})")
        params.extend(importance_in)
    if not include_hidden:
        where.append("is_hidden = 0")
    sql = "SELECT * FROM news_items"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY substr(COALESCE(NULLIF(published_at, ''), fetched_at), 1, 19) DESC,"
            " id DESC LIMIT ?")
    params.append(int(limit))
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_item(r) for r in rows]


def count_by_source(*, db_path: Optional[Path] = None):
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT source, source_label, COUNT(*) AS n FROM news_items "
                            "WHERE is_hidden = 0 GROUP BY source").fetchall()
    return {r["source_label"]: r["n"] for r in rows}


def total_count(*, include_hidden: bool = False, db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        sql = "SELECT COUNT(*) FROM news_items" + ("" if include_hidden else " WHERE is_hidden = 0")
        row = conn.execute(sql).fetchone()
    return int(row[0]) if row else 0


def set_hidden(item_id: str, hidden: bool, *, db_path: Optional[Path] = None) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute("UPDATE news_items SET is_hidden = ? WHERE id = ?",
                           (1 if hidden else 0, item_id))
    return cur.rowcount > 0


def set_starred(item_id: str, starred: bool, *, db_path: Optional[Path] = None) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute("UPDATE news_items SET is_starred = ? WHERE id = ?",
                           (1 if starred else 0, item_id))
    return cur.rowcount > 0


def purge_older_than(days: int, *, db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    threshold = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM news_items "
            "WHERE substr(COALESCE(NULLIF(published_at, ''), fetched_at), 1, 19) < ? "
            "AND is_starred = 0", (threshold,))
    return cur.rowcount


def pick_representative(group_items: List[NewsItem]) -> NewsItem:
    """그룹 대표: 공식자료 > 공식연결 언론 > 가장 먼저 보도된 신뢰 매체."""
    def rank(it):
        if it.source_type == "official":
            return (0, it.published_at or it.fetched_at)
        if it.official_source_url:
            return (1, it.published_at or it.fetched_at)
        return (2, it.published_at or it.fetched_at)
    return sorted(group_items, key=rank)[0]


def reconcile_official(*, db_path: Optional[Path] = None) -> int:
    """중복그룹에 공식자료가 있으면 같은 그룹의 언론기사를 공식 확인·긴급 확정으로 승격.

    - official_source_url = 공식자료 URL
    - verification_status = official_confirmed
    - is_urgent = 공식자료의 긴급 여부
    """
    from collections import defaultdict
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM news_items").fetchall()
        groups = defaultdict(list)
        for r in rows:
            groups[(r["duplicate_group_id"] or r["id"])].append(r)
        n = 0
        for members in groups.values():
            offs = [m for m in members if (m["source_type"] or "") == "official"]
            if not offs:
                continue
            off = offs[0]
            off_urgent = int(off["is_urgent"] or 0)
            for m in members:
                if (m["source_type"] or "") == "official":
                    continue
                conn.execute(
                    "UPDATE news_items SET official_source_url=?, "
                    "verification_status='official_confirmed', is_urgent=? WHERE id=?",
                    (off["url"], off_urgent, m["id"]))
                n += 1
    return n


def backfill_classification(*, db_path: Optional[Path] = None) -> int:
    """기존 행에 분류 필드 백필(파괴적이지 않음 — 컬럼 업데이트만)."""
    from data_layer.news import classify as C, dedup as D
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM news_items").fetchall()
        items = [{"id": r["id"], "title": r["title"],
                  "ts": (r["published_at"] or r["fetched_at"])} for r in rows]
        groups = D.assign_groups(items)
        n = 0
        for r in rows:
            blob = " ".join(filter(None, [r["title"], r["summary"] or "", r["category"] or ""]))
            stype = C.classify_source_type(r["source"], r["source_label"], r["url"])
            rep, cats = C.classify_category(blob)
            isu, vs, _ = C.assess_urgency(blob, stype)
            imp, act, aff = C.qa_template(rep)
            try:
                tags = json.loads(r["tags"] or "[]")
            except Exception:
                tags = []
            tags = list(dict.fromkeys(tags + cats))
            conn.execute(
                """UPDATE news_items SET source_type=?, source_domain=?, biz_category=?,
                   tags=?, is_urgent=?, verification_status=?, qa_impact=?, action_items=?,
                   affected_work=?, qa_relevance_score=?, content_hash=?, duplicate_group_id=?
                   WHERE id=?""",
                (stype, C.domain_of(r["url"]), rep, json.dumps(tags, ensure_ascii=False),
                 1 if isu else 0, vs, imp, act, aff, C.qa_relevance_score(blob),
                 D.content_hash(r["title"]), groups.get(r["id"], D.content_hash(r["title"])),
                 r["id"]))
            n += 1
    return n
