"""SOP 보관함 + 규제 스냅샷 + 영향 리포트 저장소 — SQLite (qa_history 패턴 동일).

개정→영향분석의 영속 계층. db/sop_vault.db 에 3개 테이블:
  - sop_docs      : 사용자의 내부 SOP 문서 (계정별 격리)
  - reg_snapshots : 규제 원문 스냅샷 (전역 — 규제는 사용자와 무관)
  - impact_reports: 개정 감지 시 생성된 SOP 영향 리포트 (계정별 격리)

설계 원칙:
  - 스냅샷은 '마지막으로 확인한 규제 원문'의 사본. 다음 스캔에서 현재 원문과
    해시 비교로 변경을 감지하고, 변경 전 점수(prev_score)를 재계산할 근거가 된다.
  - 리포트는 결정론적 엔진 산출물만 저장 (LLM 미사용).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "sop_vault.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sop_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL DEFAULT '(local)',
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reg_snapshots (
    reg_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    captured_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS impact_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL DEFAULT '(local)',
    reg_id TEXT NOT NULL,
    reg_title TEXT NOT NULL,
    change_kind TEXT NOT NULL DEFAULT 'modified',
    sop_id INTEGER NOT NULL,
    sop_title TEXT NOT NULL,
    prev_score INTEGER,
    new_score INTEGER NOT NULL,
    delta INTEGER,
    new_missing TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sop_user ON sop_docs(user);
CREATE INDEX IF NOT EXISTS idx_rep_user ON impact_reports(user, status);
"""


@dataclass
class SopDoc:
    id: int
    title: str
    body: str
    created_at: str
    updated_at: str
    user: str = "(local)"


@dataclass
class RegSnapshot:
    reg_id: str
    title: str
    content: str
    content_hash: str
    captured_at: str


@dataclass
class ImpactReport:
    id: int
    reg_id: str
    reg_title: str
    change_kind: str           # new / modified
    sop_id: int
    sop_title: str
    prev_score: Optional[int]  # 변경 전 적합도 (신규 규제면 None)
    new_score: int
    delta: Optional[int]       # new - prev (신규면 None)
    new_missing: List[str] = field(default_factory=list)  # 새로 미흡해진 절
    status: str = "new"        # new / acknowledged
    created_at: str = ""
    user: str = "(local)"


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else _DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- SOP 문서

def add_sop(title: str, body: str, *, user: str = "(local)",
            db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    now = _now()
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO sop_docs (user, title, body, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ((user or "(local)").strip(), (title or "").strip(),
             (body or "").strip(), now, now),
        )
        return int(cur.lastrowid)


def update_sop(sop_id: int, *, title: Optional[str] = None,
               body: Optional[str] = None, user: str = "(local)",
               db_path: Optional[Path] = None) -> bool:
    init_db(db_path)
    sets, args = ["updated_at = ?"], [_now()]
    if title is not None:
        sets.append("title = ?")
        args.append(title.strip())
    if body is not None:
        sets.append("body = ?")
        args.append(body.strip())
    args += [int(sop_id), (user or "(local)").strip()]
    with _connect(db_path) as conn:
        cur = conn.execute(
            f"UPDATE sop_docs SET {', '.join(sets)} WHERE id = ? AND user = ?",
            args,
        )
        return cur.rowcount > 0


def _row_to_sop(row: sqlite3.Row) -> SopDoc:
    return SopDoc(
        id=int(row["id"]), title=row["title"] or "", body=row["body"] or "",
        created_at=row["created_at"] or "", updated_at=row["updated_at"] or "",
        user=row["user"] or "(local)",
    )


def list_sops(*, user: Optional[str] = "(local)", limit: int = 200,
              db_path: Optional[Path] = None) -> List[SopDoc]:
    """user=None 이면 전 계정 SOP (영향분석 스캔용)."""
    init_db(db_path)
    with _connect(db_path) as conn:
        if user is None:
            rows = conn.execute(
                "SELECT * FROM sop_docs ORDER BY id DESC LIMIT ?", (int(limit),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sop_docs WHERE user = ? ORDER BY id DESC LIMIT ?",
                ((user or "(local)").strip(), int(limit)),
            ).fetchall()
    return [_row_to_sop(r) for r in rows]


def get_sop(sop_id: int, *, user: Optional[str] = None,
            db_path: Optional[Path] = None) -> Optional[SopDoc]:
    init_db(db_path)
    with _connect(db_path) as conn:
        if user is None:
            row = conn.execute(
                "SELECT * FROM sop_docs WHERE id = ?", (int(sop_id),)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM sop_docs WHERE id = ? AND user = ?",
                (int(sop_id), (user or "(local)").strip()),
            ).fetchone()
    return _row_to_sop(row) if row else None


def delete_sop(sop_id: int, *, user: str = "(local)",
               db_path: Optional[Path] = None) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM sop_docs WHERE id = ? AND user = ?",
            (int(sop_id), (user or "(local)").strip()),
        )
        return cur.rowcount > 0


# ---------------------------------------------------------------- 스냅샷

def load_snapshots(db_path: Optional[Path] = None) -> Dict[str, RegSnapshot]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM reg_snapshots").fetchall()
    return {
        r["reg_id"]: RegSnapshot(
            reg_id=r["reg_id"], title=r["title"] or "",
            content=r["content"] or "", content_hash=r["content_hash"] or "",
            captured_at=r["captured_at"] or "",
        )
        for r in rows
    }


def save_snapshot(reg_id: str, title: str, content: str, content_hash: str,
                  db_path: Optional[Path] = None) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO reg_snapshots (reg_id, title, content, content_hash, captured_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(reg_id) DO UPDATE SET "
            "title=excluded.title, content=excluded.content, "
            "content_hash=excluded.content_hash, captured_at=excluded.captured_at",
            (reg_id, title, content, content_hash, _now()),
        )


def snapshot_count(db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM reg_snapshots").fetchone()
    return int(row["n"]) if row else 0


# ---------------------------------------------------------------- 리포트

def save_report(rep: ImpactReport, db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO impact_reports "
            "(user, reg_id, reg_title, change_kind, sop_id, sop_title, "
            " prev_score, new_score, delta, new_missing, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rep.user, rep.reg_id, rep.reg_title, rep.change_kind,
             rep.sop_id, rep.sop_title, rep.prev_score, rep.new_score,
             rep.delta, json.dumps(rep.new_missing, ensure_ascii=False),
             rep.status, _now()),
        )
        return int(cur.lastrowid)


def _row_to_report(row: sqlite3.Row) -> ImpactReport:
    try:
        missing = json.loads(row["new_missing"] or "[]")
    except Exception:
        missing = []
    return ImpactReport(
        id=int(row["id"]), reg_id=row["reg_id"] or "",
        reg_title=row["reg_title"] or "", change_kind=row["change_kind"] or "modified",
        sop_id=int(row["sop_id"]), sop_title=row["sop_title"] or "",
        prev_score=row["prev_score"], new_score=int(row["new_score"]),
        delta=row["delta"], new_missing=missing,
        status=row["status"] or "new", created_at=row["created_at"] or "",
        user=row["user"] or "(local)",
    )


def list_reports(*, user: Optional[str] = "(local)", status: Optional[str] = None,
                 limit: int = 100, db_path: Optional[Path] = None) -> List[ImpactReport]:
    """user=None 이면 전 계정 (다이제스트 집계용)."""
    init_db(db_path)
    sql = "SELECT * FROM impact_reports WHERE 1=1"
    args: list = []
    if user is not None:
        sql += " AND user = ?"
        args.append((user or "(local)").strip())
    if status is not None:
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(int(limit))
    with _connect(db_path) as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_row_to_report(r) for r in rows]


def acknowledge_report(report_id: int, *, user: str = "(local)",
                       db_path: Optional[Path] = None) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE impact_reports SET status = 'acknowledged' "
            "WHERE id = ? AND user = ?",
            (int(report_id), (user or "(local)").strip()),
        )
        return cur.rowcount > 0


def count_new_reports(*, user: Optional[str] = None,
                      db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    sql = "SELECT COUNT(*) AS n FROM impact_reports WHERE status = 'new'"
    args: list = []
    if user is not None:
        sql += " AND user = ?"
        args.append((user or "(local)").strip())
    with _connect(db_path) as conn:
        row = conn.execute(sql, args).fetchone()
    return int(row["n"]) if row else 0
