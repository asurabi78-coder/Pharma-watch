"""뉴스 SQLite 저장소 — Phase B.

테이블:
  news_items(id, title, url, source, source_label, category, summary,
             published_at, fetched_at, tags, thumbnail, is_starred, is_hidden)

upsert 정책: ON CONFLICT(id) DO UPDATE — 제목·요약·published_at 갱신
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
    is_hidden INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_news_source_ts
    ON news_items(source, COALESCE(published_at, fetched_at) DESC);

CREATE INDEX IF NOT EXISTS idx_news_fetched
    ON news_items(fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_category
    ON news_items(category);
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


def upsert(items: Iterable[NewsItem], *, db_path: Optional[Path] = None):
    init_db(db_path)
    new_n = 0
    upd_n = 0
    with _connect(db_path) as conn:
        for it in items:
            existing = conn.execute(
                "SELECT id FROM news_items WHERE id = ?", (it.id,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO news_items (
                        id, title, url, source, source_label, category,
                        summary, published_at, fetched_at, tags, thumbnail
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        it.id, it.title, it.url, it.source, it.source_label,
                        it.category, it.summary, it.published_at, it.fetched_at,
                        json.dumps(it.tags, ensure_ascii=False), it.thumbnail or "",
                    ),
                )
                new_n += 1
            else:
                conn.execute(
                    """
                    UPDATE news_items
                       SET title = ?, summary = ?,
                           published_at = COALESCE(NULLIF(?, ''), published_at),
                           fetched_at = ?, tags = ?, thumbnail = ?,
                           category = COALESCE(NULLIF(?, ''), category)
                     WHERE id = ?
                    """,
                    (
                        it.title, it.summary, it.published_at, it.fetched_at,
                        json.dumps(it.tags, ensure_ascii=False), it.thumbnail or "",
                        it.category, it.id,
                    ),
                )
                upd_n += 1
    return new_n, upd_n


def _row_to_item(row: sqlite3.Row) -> NewsItem:
    try:
        tags = json.loads(row["tags"] or "[]")
    except (json.JSONDecodeError, TypeError):
        tags = []
    return NewsItem(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        source=row["source"],
        source_label=row["source_label"],
        category=row["category"] or "",
        summary=row["summary"] or "",
        published_at=row["published_at"] or "",
        fetched_at=row["fetched_at"] or "",
        tags=tags,
        thumbnail=row["thumbnail"] or None,
    )


def list_items(
    *,
    sources: Optional[List[str]] = None,
    category_keyword: Optional[str] = None,
    text_search: Optional[str] = None,
    days: Optional[int] = None,
    include_hidden: bool = False,
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> List[NewsItem]:
    """뉴스 조회 — 다양한 필터."""
    init_db(db_path)
    where: List[str] = []
    params: list = []

    if sources:
        placeholders = ",".join(["?"] * len(sources))
        where.append(f"source IN ({placeholders})")
        params.extend(sources)

    if category_keyword:
        where.append("category LIKE ?")
        params.append(f"%{category_keyword}%")

    if text_search:
        where.append("(title LIKE ? OR summary LIKE ?)")
        params.append(f"%{text_search}%")
        params.append(f"%{text_search}%")

    if days is not None and days > 0:
        threshold = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        where.append(
            "substr(COALESCE(NULLIF(published_at, ''), fetched_at), 1, 19) >= ?"
        )
        params.append(threshold)

    if not include_hidden:
        where.append("is_hidden = 0")

    sql = "SELECT * FROM news_items"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (
        " ORDER BY substr(COALESCE(NULLIF(published_at, ''), fetched_at), 1, 19) DESC,"
        " id DESC LIMIT ?"
    )
    params.append(int(limit))

    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_item(r) for r in rows]


def count_by_source(*, db_path: Optional[Path] = None):
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT source, source_label, COUNT(*) AS n FROM news_items "
            "WHERE is_hidden = 0 GROUP BY source"
        ).fetchall()
    return {r["source_label"]: r["n"] for r in rows}


def total_count(*, include_hidden: bool = False, db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        if include_hidden:
            row = conn.execute("SELECT COUNT(*) FROM news_items").fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM news_items WHERE is_hidden = 0").fetchone()
    return int(row[0]) if row else 0


def set_hidden(item_id: str, hidden: bool, *, db_path: Optional[Path] = None) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE news_items SET is_hidden = ? WHERE id = ?",
            (1 if hidden else 0, item_id),
        )
    return cur.rowcount > 0


def set_starred(item_id: str, starred: bool, *, db_path: Optional[Path] = None) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE news_items SET is_starred = ? WHERE id = ?",
            (1 if starred else 0, item_id),
        )
    return cur.rowcount > 0


def purge_older_than(days: int, *, db_path: Optional[Path] = None) -> int:
    """N일 이전 항목 삭제. 즐겨찾기는 보존."""
    init_db(db_path)
    threshold = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM news_items "
            "WHERE substr(COALESCE(NULLIF(published_at, ''), fetched_at), 1, 19) < ? "
            "AND is_starred = 0",
            (threshold,),
        )
    return cur.rowcount
