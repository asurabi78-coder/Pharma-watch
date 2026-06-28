"""QA 커뮤니티 저장소 — SQLite (qa_history 패턴과 동일 골격).

사용자끼리 묻고 답하는 Q&A 게시판. QA 분석가(AI 답변)와는 별개 기능이다.

★ qa_history 와의 차이:
   - qa_history 는 '계정별 비공개'(본인 것만 보임).
   - qa_community 는 '전 사용자 공유'(모두가 질문/답변을 봄).
     단, 작성자(user)는 소유권 판단(삭제·채택)에만 쓰이고,
     화면에는 닉네임으로 표시된다(회사명 비공개 목적).

데이터: db/qa_community.db, 테이블 2개(questions, answers). 추가 전용 — 기존 DB 무관.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "qa_community.db"


# 카테고리(고정). '전체'는 필터 전용 가상값 — 저장에는 쓰지 않는다.
CATEGORY_ALL = "전체"
CATEGORIES = [
    "KGSP·의약품 유통",
    "보관·콜드체인",
    "수입·통관",
    "관리약사·QA 업무",
    "점검·행정처분",
    "기타",
]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS qa_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL DEFAULT '(local)',
    category TEXT NOT NULL DEFAULT '기타',
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    is_hidden INTEGER NOT NULL DEFAULT 0,
    adopted_answer_id INTEGER
);
CREATE TABLE IF NOT EXISTS qa_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    user TEXT NOT NULL DEFAULT '(local)',
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_hidden INTEGER NOT NULL DEFAULT 0,
    admin_verified INTEGER NOT NULL DEFAULT 0,
    expert_verified INTEGER NOT NULL DEFAULT 0
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_q_created ON qa_questions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_q_category ON qa_questions(category);
CREATE INDEX IF NOT EXISTS idx_a_question ON qa_answers(question_id);
"""


# ── 신뢰도 등급 (화면 배지) ──────────────────────────────────────────────
TRUST_NORMAL = "일반 답변"
TRUST_ADOPTED = "채택된 답변"
TRUST_ADMIN = "관리자 확인"
TRUST_EXPERT = "전문가 확인"


@dataclass
class Question:
    id: int
    user: str
    category: str
    title: str
    body: str
    created_at: str
    views: int = 0
    is_hidden: int = 0
    adopted_answer_id: Optional[int] = None
    answer_count: int = 0


@dataclass
class Answer:
    id: int
    question_id: int
    user: str
    body: str
    created_at: str
    is_hidden: int = 0
    admin_verified: int = 0
    expert_verified: int = 0
    is_adopted: bool = False

    def trust_levels(self) -> List[str]:
        """표시할 신뢰도 배지 목록(복수 가능)."""
        levels: List[str] = []
        if self.is_adopted:
            levels.append(TRUST_ADOPTED)
        if self.admin_verified:
            levels.append(TRUST_ADMIN)
        if self.expert_verified:
            levels.append(TRUST_EXPERT)
        if not levels:
            levels.append(TRUST_NORMAL)
        return levels


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else _DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.executescript(_INDEXES)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── 질문 ────────────────────────────────────────────────────────────────
def create_question(
    title: str,
    body: str,
    category: str,
    *,
    user: str = "(local)",
    db_path: Optional[Path] = None,
) -> int:
    init_db(db_path)
    cat = category if category in CATEGORIES else "기타"
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO qa_questions (user, category, title, body, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                (user or "(local)").strip(),
                cat,
                (title or "").strip(),
                (body or "").strip(),
                _now(),
            ),
        )
        return int(cur.lastrowid)


def _q_from_row(row: sqlite3.Row, answer_count: int = 0) -> Question:
    return Question(
        id=int(row["id"]),
        user=row["user"] or "",
        category=row["category"] or "기타",
        title=row["title"] or "",
        body=row["body"] or "",
        created_at=row["created_at"] or "",
        views=int(row["views"] or 0),
        is_hidden=int(row["is_hidden"] or 0),
        adopted_answer_id=row["adopted_answer_id"],
        answer_count=answer_count,
    )


def list_questions(
    *,
    category: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "recent",            # recent | answers | views
    include_hidden: bool = False,
    limit: int = 300,
    db_path: Optional[Path] = None,
) -> List[Question]:
    """공유 목록 — 모든 사용자 질문. (숨김은 관리자만 include_hidden=True)"""
    init_db(db_path)
    where = []
    params: list = []
    if not include_hidden:
        where.append("q.is_hidden = 0")
    if category and category != CATEGORY_ALL:
        where.append("q.category = ?")
        params.append(category)
    if search and search.strip():
        like = f"%{search.strip()}%"
        where.append("(q.title LIKE ? OR q.body LIKE ?)")
        params.extend([like, like])
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    order = {
        "answers": "answer_count DESC, datetime(q.created_at) DESC",
        "views": "q.views DESC, datetime(q.created_at) DESC",
    }.get(sort, "datetime(q.created_at) DESC, q.id DESC")

    sql = (
        "SELECT q.*, "
        "(SELECT COUNT(*) FROM qa_answers a "
        " WHERE a.question_id = q.id AND a.is_hidden = 0) AS answer_count "
        "FROM qa_questions q "
        f"{where_sql} ORDER BY {order} LIMIT ?"
    )
    params.append(int(limit))
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_q_from_row(r, int(r["answer_count"] or 0)) for r in rows]


def get_question(
    qid: int,
    *,
    include_hidden: bool = False,
    db_path: Optional[Path] = None,
) -> Optional[Question]:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT q.*, "
            "(SELECT COUNT(*) FROM qa_answers a "
            " WHERE a.question_id = q.id AND a.is_hidden = 0) AS answer_count "
            "FROM qa_questions q WHERE q.id = ?",
            (int(qid),),
        ).fetchone()
    if not row:
        return None
    if row["is_hidden"] and not include_hidden:
        return None
    return _q_from_row(row, int(row["answer_count"] or 0))


def increment_views(qid: int, *, db_path: Optional[Path] = None) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE qa_questions SET views = views + 1 WHERE id = ?", (int(qid),)
        )


def delete_question(
    qid: int, *, user: str = "(local)", db_path: Optional[Path] = None
) -> bool:
    """본인 질문만 삭제 — 딸린 답변도 함께 제거."""
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM qa_questions WHERE id = ? AND user = ?",
            (int(qid), (user or "(local)").strip()),
        )
        if cur.rowcount > 0:
            conn.execute("DELETE FROM qa_answers WHERE question_id = ?", (int(qid),))
            return True
    return False


def set_question_hidden(
    qid: int, hidden: bool, *, db_path: Optional[Path] = None
) -> None:
    """관리자 전용 — 질문 숨김/해제."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE qa_questions SET is_hidden = ? WHERE id = ?",
            (1 if hidden else 0, int(qid)),
        )


# ── 답변 ────────────────────────────────────────────────────────────────
def create_answer(
    qid: int,
    body: str,
    *,
    user: str = "(local)",
    db_path: Optional[Path] = None,
) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO qa_answers (question_id, user, body, created_at) "
            "VALUES (?, ?, ?, ?)",
            (int(qid), (user or "(local)").strip(), (body or "").strip(), _now()),
        )
        return int(cur.lastrowid)


def _a_from_row(row: sqlite3.Row, adopted_id: Optional[int]) -> Answer:
    aid = int(row["id"])
    return Answer(
        id=aid,
        question_id=int(row["question_id"]),
        user=row["user"] or "",
        body=row["body"] or "",
        created_at=row["created_at"] or "",
        is_hidden=int(row["is_hidden"] or 0),
        admin_verified=int(row["admin_verified"] or 0),
        expert_verified=int(row["expert_verified"] or 0),
        is_adopted=(adopted_id is not None and aid == int(adopted_id)),
    )


def list_answers(
    qid: int,
    *,
    include_hidden: bool = False,
    db_path: Optional[Path] = None,
) -> List[Answer]:
    """채택 답변이 맨 위, 그 다음 최신순."""
    init_db(db_path)
    with _connect(db_path) as conn:
        qrow = conn.execute(
            "SELECT adopted_answer_id FROM qa_questions WHERE id = ?", (int(qid),)
        ).fetchone()
        adopted_id = qrow["adopted_answer_id"] if qrow else None
        sql = "SELECT * FROM qa_answers WHERE question_id = ?"
        if not include_hidden:
            sql += " AND is_hidden = 0"
        sql += " ORDER BY datetime(created_at) ASC, id ASC"
        rows = conn.execute(sql, (int(qid),)).fetchall()
    answers = [_a_from_row(r, adopted_id) for r in rows]
    answers.sort(key=lambda a: (not a.is_adopted, a.created_at, a.id))
    return answers


def adopt_answer(
    qid: int,
    answer_id: int,
    *,
    user: str = "(local)",
    db_path: Optional[Path] = None,
) -> bool:
    """질문 작성자 본인만 채택 가능. 성공 시 True."""
    init_db(db_path)
    uid = (user or "(local)").strip()
    with _connect(db_path) as conn:
        qrow = conn.execute(
            "SELECT user FROM qa_questions WHERE id = ?", (int(qid),)
        ).fetchone()
        if not qrow or (qrow["user"] or "") != uid:
            return False
        arow = conn.execute(
            "SELECT id FROM qa_answers WHERE id = ? AND question_id = ?",
            (int(answer_id), int(qid)),
        ).fetchone()
        if not arow:
            return False
        conn.execute(
            "UPDATE qa_questions SET adopted_answer_id = ? WHERE id = ?",
            (int(answer_id), int(qid)),
        )
        return True


def unadopt_answer(
    qid: int, *, user: str = "(local)", db_path: Optional[Path] = None
) -> bool:
    """채택 취소 — 질문 작성자 본인만."""
    init_db(db_path)
    uid = (user or "(local)").strip()
    with _connect(db_path) as conn:
        qrow = conn.execute(
            "SELECT user FROM qa_questions WHERE id = ?", (int(qid),)
        ).fetchone()
        if not qrow or (qrow["user"] or "") != uid:
            return False
        conn.execute(
            "UPDATE qa_questions SET adopted_answer_id = NULL WHERE id = ?", (int(qid),)
        )
        return True


def delete_answer(
    answer_id: int, *, user: str = "(local)", db_path: Optional[Path] = None
) -> bool:
    """본인 답변만 삭제. 채택돼 있던 답변이면 채택도 해제."""
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM qa_answers WHERE id = ? AND user = ?",
            (int(answer_id), (user or "(local)").strip()),
        )
        if cur.rowcount > 0:
            conn.execute(
                "UPDATE qa_questions SET adopted_answer_id = NULL "
                "WHERE adopted_answer_id = ?",
                (int(answer_id),),
            )
            return True
    return False


def set_answer_hidden(
    answer_id: int, hidden: bool, *, db_path: Optional[Path] = None
) -> None:
    """관리자 전용 — 답변 숨김/해제."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE qa_answers SET is_hidden = ? WHERE id = ?",
            (1 if hidden else 0, int(answer_id)),
        )


def set_answer_verified(
    answer_id: int,
    *,
    admin: Optional[bool] = None,
    expert: Optional[bool] = None,
    db_path: Optional[Path] = None,
) -> None:
    """관리자 전용 — '관리자 확인'/'전문가 확인' 플래그 토글."""
    init_db(db_path)
    sets = []
    params: list = []
    if admin is not None:
        sets.append("admin_verified = ?")
        params.append(1 if admin else 0)
    if expert is not None:
        sets.append("expert_verified = ?")
        params.append(1 if expert else 0)
    if not sets:
        return
    params.append(int(answer_id))
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE qa_answers SET {', '.join(sets)} WHERE id = ?", params
        )


def count_questions(*, include_hidden: bool = False, db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        sql = "SELECT COUNT(*) AS c FROM qa_questions"
        if not include_hidden:
            sql += " WHERE is_hidden = 0"
        row = conn.execute(sql).fetchone()
    return int(row["c"] or 0)
