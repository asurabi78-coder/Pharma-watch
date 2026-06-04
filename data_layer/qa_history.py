"""QA 분석 기록 저장소 — SQLite (뉴스 repo 패턴 동일).

QA 분석가 화면의 질문(입력)과 답변을 영속 저장하고, 목록 조회·삭제를 지원한다.
db/qa_history.db 에 단일 테이블 qa_records 로 보관.

★ 계정별 분리: 모든 조회/저장/삭제는 user(로그인 ID) 기준으로 격리된다.
   기존(컬럼 없던) 레코드는 마이그레이션 시 '(local)' 로 채워진다.
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
    user TEXT NOT NULL DEFAULT '(local)',
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# 인덱스는 마이그레이션(user 컬럼 보장) 이후에 생성해야 한다.
_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_qa_created ON qa_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qa_user ON qa_records(user);
"""


@dataclass
class QaRecord:
    id: int
    question: str
    answer: str
    created_at: str           # ISO 문자열 (YYYY-MM-DD HH:MM:SS)
    user: str = ""


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else _DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """기존 테이블에 user 컬럼이 없으면 추가 (구버전 DB 호환)."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(qa_records)").fetchall()]
    if cols and "user" not in cols:
        conn.execute(
            "ALTER TABLE qa_records ADD COLUMN user TEXT NOT NULL DEFAULT '(local)'"
        )


def init_db(db_path: Optional[Path] = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        conn.executescript(_INDEXES)


def save(
    question: str,
    answer: str,
    *,
    user: str = "(local)",
    db_path: Optional[Path] = None,
) -> int:
    """질문+답변 1건을 해당 계정 소유로 저장 → 생성된 id 반환."""
    init_db(db_path)
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO qa_records (user, question, answer, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                (user or "(local)").strip(),
                (question or "").strip(),
                (answer or "").strip(),
                created,
            ),
        )
        return int(cur.lastrowid)


def _row_to_record(row: sqlite3.Row) -> QaRecord:
    keys = row.keys()
    return QaRecord(
        id=int(row["id"]),
        question=row["question"] or "",
        answer=row["answer"] or "",
        created_at=row["created_at"] or "",
        user=(row["user"] if "user" in keys else "") or "",
    )


def list_records(
    *,
    user: str = "(local)",
    limit: int = 200,
    db_path: Optional[Path] = None,
) -> List[QaRecord]:
    """해당 계정의 최신순 기록 목록."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM qa_records WHERE user = ? "
            "ORDER BY datetime(created_at) DESC, id DESC LIMIT ?",
            ((user or "(local)").strip(), int(limit)),
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def get(
    record_id: int,
    *,
    user: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Optional[QaRecord]:
    """단일 기록. user 를 주면 그 계정 소유일 때만 반환."""
    init_db(db_path)
    with _connect(db_path) as conn:
        if user is None:
            row = conn.execute(
                "SELECT * FROM qa_records WHERE id = ?", (int(record_id),)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM qa_records WHERE id = ? AND user = ?",
                (int(record_id), (user or "(local)").strip()),
            ).fetchone()
    return _row_to_record(row) if row else None


def delete(
    record_id: int,
    *,
    user: str = "(local)",
    db_path: Optional[Path] = None,
) -> bool:
    """단일 기록 삭제 — 본인 소유만. 삭제됐으면 True."""
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM qa_records WHERE id = ? AND user = ?",
            (int(record_id), (user or "(local)").strip()),
        )
        return cur.rowcount > 0


def clear_all(*, user: str = "(local)", db_path: Optional[Path] = None) -> int:
    """해당 계정의 기록만 전체 삭제 → 삭제된 건수 반환."""
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM qa_records WHERE user = ?", ((user or "(local)").strip(),)
        )
        return cur.rowcount


def count(*, user: str = "(local)", db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM qa_records WHERE user = ?",
            ((user or "(local)").strip(),),
        ).fetchone()
    return int(row["n"]) if row else 0
