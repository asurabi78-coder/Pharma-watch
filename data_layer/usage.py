"""사용량 기록 저장소 — SQLite (qa_history 패턴 동일).

계정별로 두 가지를 한 줄씩 누적 기록한다.
- kind='claude'  : Claude(AI) 호출 1건. model/input_tokens/output_tokens 포함.
- kind='feature' : 기능(페이지) 진입 1건. feature=페이지 키.

집계는 관리자 '사용량' 페이지(pages/usage.py)에서 사용한다.
db/usage.db 단일 테이블 usage_events 로 보관.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "usage.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account       TEXT NOT NULL,
    kind          TEXT NOT NULL,           -- 'claude' | 'feature' | 'action'
    feature       TEXT NOT NULL DEFAULT '',
    action        TEXT NOT NULL DEFAULT '', -- 행동 이름 (검색/재수집/분석 등)
    detail        TEXT NOT NULL DEFAULT '', -- 행동 상세 (검색어 등)
    model         TEXT NOT NULL DEFAULT '',
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_created  ON usage_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_account  ON usage_events(account);
CREATE INDEX IF NOT EXISTS idx_usage_kind     ON usage_events(kind);
"""

# 구버전 테이블(action/detail 컬럼 없음) 자동 마이그레이션용
_MIGRATE_COLS = {"action": "TEXT NOT NULL DEFAULT ''", "detail": "TEXT NOT NULL DEFAULT ''"}


@dataclass
class TokenRow:
    account: str
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class FeatureRow:
    account: str
    feature: str
    count: int


@dataclass
class ActionRow:
    account: str
    feature: str
    action: str
    count: int


@dataclass
class TermRow:
    term: str
    feature: str
    count: int


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else _DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        # 기존 DB에 새 컬럼이 없으면 추가 (데이터 보존)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(usage_events)").fetchall()}
        for col, ddl in _MIGRATE_COLS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE usage_events ADD COLUMN {col} {ddl}")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── 기록 ────────────────────────────────────────────────
def log_claude(
    account: str,
    feature: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    db_path: Optional[Path] = None,
) -> None:
    """Claude 호출 1건 기록. 실패해도 앱 흐름을 막지 않는다(호출부에서 try)."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO usage_events "
            "(account, kind, feature, model, input_tokens, output_tokens, created_at) "
            "VALUES (?, 'claude', ?, ?, ?, ?, ?)",
            (
                (account or "(unknown)").strip(),
                (feature or "").strip(),
                (model or "").strip(),
                int(input_tokens or 0),
                int(output_tokens or 0),
                _now(),
            ),
        )


def log_feature(
    account: str,
    feature: str,
    *,
    db_path: Optional[Path] = None,
) -> None:
    """기능(페이지) 진입 1건 기록."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO usage_events "
            "(account, kind, feature, action, detail, model, input_tokens, output_tokens, created_at) "
            "VALUES (?, 'feature', ?, '', '', '', 0, 0, ?)",
            ((account or "(unknown)").strip(), (feature or "").strip(), _now()),
        )


def log_action(
    account: str,
    feature: str,
    action: str,
    detail: str = "",
    *,
    db_path: Optional[Path] = None,
) -> None:
    """기능 안에서의 구체 행동 1건 기록 (예: 검색/재수집/분석 + 검색어).

    detail 은 너무 길지 않게 200자로 자른다(검색어 등).
    """
    init_db(db_path)
    detail = (detail or "").strip()[:200]
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO usage_events "
            "(account, kind, feature, action, detail, model, input_tokens, output_tokens, created_at) "
            "VALUES (?, 'action', ?, ?, ?, '', 0, 0, ?)",
            (
                (account or "(unknown)").strip(),
                (feature or "").strip(),
                (action or "").strip(),
                detail,
                _now(),
            ),
        )


# ── 집계 ────────────────────────────────────────────────
def _since_clause(days: Optional[int]):
    """기간 필터용 (where_sql, params). days=None 이면 전체."""
    if not days:
        return "", []
    cutoff = (datetime.now() - timedelta(days=int(days))).strftime("%Y-%m-%d %H:%M:%S")
    return " AND created_at >= ?", [cutoff]


def token_summary(*, days: Optional[int] = None, db_path: Optional[Path] = None) -> List[TokenRow]:
    """계정별 Claude 토큰 합계 (호출수/입력/출력/총합), 총합 내림차순."""
    init_db(db_path)
    where, params = _since_clause(days)
    sql = (
        "SELECT account, COUNT(*) AS calls, "
        "       SUM(input_tokens) AS in_tok, SUM(output_tokens) AS out_tok "
        "FROM usage_events WHERE kind='claude'" + where +
        " GROUP BY account ORDER BY (SUM(input_tokens)+SUM(output_tokens)) DESC"
    )
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    out: List[TokenRow] = []
    for r in rows:
        it = int(r["in_tok"] or 0)
        ot = int(r["out_tok"] or 0)
        out.append(TokenRow(r["account"], int(r["calls"] or 0), it, ot, it + ot))
    return out


def feature_summary(*, days: Optional[int] = None, db_path: Optional[Path] = None) -> List[FeatureRow]:
    """계정×기능별 사용 횟수, 횟수 내림차순."""
    init_db(db_path)
    where, params = _since_clause(days)
    sql = (
        "SELECT account, feature, COUNT(*) AS cnt "
        "FROM usage_events WHERE kind='feature'" + where +
        " GROUP BY account, feature ORDER BY account, cnt DESC"
    )
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [FeatureRow(r["account"], r["feature"] or "", int(r["cnt"] or 0)) for r in rows]


def top_feature_by_account(*, days: Optional[int] = None, db_path: Optional[Path] = None) -> dict:
    """계정별 '가장 많이 쓴 기능' 한 개 → {account: (feature, count)}."""
    best: dict = {}
    for fr in feature_summary(days=days, db_path=db_path):
        if fr.account not in best:  # 이미 cnt 내림차순 정렬이라 첫 항목이 최다
            best[fr.account] = (fr.feature, fr.count)
    return best


def action_summary(*, days: Optional[int] = None, db_path: Optional[Path] = None) -> List["ActionRow"]:
    """계정×기능×행동별 횟수, 횟수 내림차순."""
    init_db(db_path)
    where, params = _since_clause(days)
    sql = (
        "SELECT account, feature, action, COUNT(*) AS cnt "
        "FROM usage_events WHERE kind='action'" + where +
        " GROUP BY account, feature, action ORDER BY cnt DESC"
    )
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [ActionRow(r["account"], r["feature"] or "", r["action"] or "", int(r["cnt"] or 0)) for r in rows]


def search_terms(*, days: Optional[int] = None, limit: int = 30, db_path: Optional[Path] = None) -> List["TermRow"]:
    """입력값(검색어·주제 등 detail)별 빈도 — 무엇을 많이 찾는지. 빈 detail 제외."""
    init_db(db_path)
    where, params = _since_clause(days)
    sql = (
        "SELECT detail AS term, feature, COUNT(*) AS cnt "
        "FROM usage_events WHERE kind='action' AND detail <> ''" + where +
        " GROUP BY detail, feature ORDER BY cnt DESC LIMIT ?"
    )
    with _connect(db_path) as conn:
        rows = conn.execute(sql, params + [int(limit)]).fetchall()
    return [TermRow(r["term"], r["feature"] or "", int(r["cnt"] or 0)) for r in rows]


def accounts(*, db_path: Optional[Path] = None) -> List[str]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT account FROM usage_events ORDER BY account"
        ).fetchall()
    return [r["account"] for r in rows]


def total_count(*, db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM usage_events").fetchone()
    return int(row["n"]) if row else 0


def all_events(*, days: Optional[int] = None, limit: int = 5000, db_path: Optional[Path] = None) -> List[sqlite3.Row]:
    """원시 이벤트 (CSV 내보내기용), 최신순."""
    init_db(db_path)
    where, params = _since_clause(days)
    sql = (
        "SELECT created_at, account, kind, feature, action, detail, model, input_tokens, output_tokens "
        "FROM usage_events WHERE 1=1" + where +
        " ORDER BY datetime(created_at) DESC, id DESC LIMIT ?"
    )
    with _connect(db_path) as conn:
        return conn.execute(sql, params + [int(limit)]).fetchall()


def clear_all(*, db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM usage_events")
        return cur.rowcount
