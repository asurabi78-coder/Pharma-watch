"""QA 분석 기록 저장소 — SQLite (뉴스 repo 패턴 동일).

QA 분석가 화면의 질문(입력)과 답변을 영속 저장하고, 목록 조회·삭제를 지원한다.
db/qa_history.db 에 단일 테이블 qa_records 로 보관.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "qa_history.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS qa_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_qa_created ON qa_records(created_at DESC);
"""


@dataclass
class QaRecord:
    id: int
    question: str
    answer: str
    created_at: str           # ISO 문자열 (YYYY-MM-DD HH:MM:SS)


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else _DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def save(question: str, answer: str, *, db_path: Optional[Path] = None) -> int:
    """질문+답변 1건 저장 → 생성된 id 반환."""
    init_db(db_path)
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO qa_records (question, answer, created_at) VALUES (?, ?, ?)",
            ((question or "").strip(), (answer or "").strip(), created),
        )
        return int(cur.lastrowid)


def _row_to_record(row: sqlite3.Row) -> QaRecord:
    return QaRecord(
        id=int(row["id"]),
        question=row["question"] or "",
        answer=row["answer"] or "",
        created_at=row["created_at"] or "",
    )


def list_records(*, limit: int = 200, db_path: Optional[Path] = None) -> List[QaRecord]:
    """최신순 기록 목록."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM qa_records ORDER BY datetime(created_at) DESC, id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def get(record_id: int, *, db_path: Optional[Path] = None) -> Optional[QaRecord]:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM qa_records WHERE id = ?", (int(record_id),)
        ).fetchone()
    return _row_to_record(row) if row else None


def delete(record_id: int, *, db_path: Optional[Path] = None) -> bool:
    """단일 기록 삭제 → 삭제됐으면 True."""
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM qa_records WHERE id = ?", (int(record_id),))
        return cur.rowcount > 0


def clear_all(*, db_path: Optional[Path] = None) -> int:
    """전체 삭제 → 삭제된 건수 반환."""
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM qa_records")
        return cur.rowcount


def count(*, db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM qa_records").fetchone()
    return int(row["n"]) if row else 0
