"""규제 캘린더 이벤트 저장소 — SQLite (db/calendar.db).

세 트랙의 일정을 한 테이블에 보관:
  - external : 외부 규제 (시드 시행일·플레이북 변경 — sync_external 로 자동 유입)
  - duty     : KGSP 의무 주기 (회사 프로필 기반 자동 생성 — ensure_duties)
  - internal : 사내 일정 (감사·실태조사·교육 등 — 사용자가 직접 등록)

자동 유입은 UNIQUE(source, ext_key, date) upsert(DO NOTHING) 라서
사용자가 남긴 상태(status)·메모(memo)를 절대 덮어쓰지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date as date_cls
from pathlib import Path
from typing import Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "db" / "calendar.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    title TEXT NOT NULL,
    track TEXT NOT NULL DEFAULT 'internal',
    kind TEXT DEFAULT '',
    impact TEXT DEFAULT 'mid',
    status TEXT DEFAULT 'todo',
    memo TEXT DEFAULT '',
    source TEXT DEFAULT 'manual',
    ext_key TEXT DEFAULT '',
    ref_id TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TEXT,
    updated_at TEXT,
    UNIQUE(source, ext_key, date)
);
CREATE INDEX IF NOT EXISTS idx_cal_date ON cal_events(date);
"""

STATUS_LABEL = {"todo": "예정", "action": "조치필요", "done": "완료"}
TRACK_LABEL = {"external": "외부 규제", "duty": "KGSP 의무", "internal": "사내 일정"}


@dataclass
class CalEvent:
    id: int
    date: str
    title: str
    track: str = "internal"
    kind: str = ""
    impact: str = "mid"
    status: str = "todo"
    memo: str = ""
    source: str = "manual"
    ext_key: str = ""
    ref_id: str = ""
    tags: List[str] = field(default_factory=list)


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


def _row_to_event(row: sqlite3.Row) -> CalEvent:
    try:
        tags = json.loads(row["tags"] or "[]")
    except Exception:
        tags = []
    return CalEvent(
        id=int(row["id"]), date=row["date"], title=row["title"] or "",
        track=row["track"] or "internal", kind=row["kind"] or "",
        impact=row["impact"] or "mid", status=row["status"] or "todo",
        memo=row["memo"] or "", source=row["source"] or "manual",
        ext_key=row["ext_key"] or "", ref_id=row["ref_id"] or "", tags=tags,
    )


# ---------------------------------------------------------------- 쓰기

def upsert_auto(date: str, title: str, *, track: str, kind: str, impact: str,
                source: str, ext_key: str, ref_id: str = "",
                tags: Optional[List[str]] = None,
                db_path: Optional[Path] = None) -> None:
    """자동 유입(외부규제/의무) — 이미 있으면 건드리지 않는다(상태·메모 보존)."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO cal_events "
            "(date, title, track, kind, impact, status, memo, source, ext_key, "
            " ref_id, tags, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'todo', '', ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(source, ext_key, date) DO NOTHING",
            (date, title, track, kind, impact, source, ext_key, ref_id,
             json.dumps(tags or [], ensure_ascii=False), _now(), _now()),
        )


def add_manual(date: str, title: str, *, kind: str = "custom",
               impact: str = "mid", memo: str = "",
               db_path: Optional[Path] = None) -> int:
    """사내 일정 직접 등록."""
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO cal_events "
            "(date, title, track, kind, impact, status, memo, source, ext_key, "
            " ref_id, tags, created_at, updated_at) "
            "VALUES (?, ?, 'internal', ?, ?, 'todo', ?, 'manual', ?, '', '[]', ?, ?)",
            (date, title, kind, impact, memo,
             f"manual-{datetime.now().timestamp()}", _now(), _now()),
        )
        return int(cur.lastrowid)


def update_event(event_id: int, *, status: Optional[str] = None,
                 memo: Optional[str] = None,
                 db_path: Optional[Path] = None) -> bool:
    init_db(db_path)
    sets, args = ["updated_at = ?"], [_now()]
    if status is not None:
        sets.append("status = ?")
        args.append(status)
    if memo is not None:
        sets.append("memo = ?")
        args.append(memo)
    args.append(int(event_id))
    with _connect(db_path) as conn:
        cur = conn.execute(
            f"UPDATE cal_events SET {', '.join(sets)} WHERE id = ?", args)
        return cur.rowcount > 0


def delete_event(event_id: int, db_path: Optional[Path] = None) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM cal_events WHERE id = ?", (int(event_id),))
        return cur.rowcount > 0


# ---------------------------------------------------------------- 읽기

def list_range(start: str, end: str, *, tracks: Optional[List[str]] = None,
               db_path: Optional[Path] = None) -> List[CalEvent]:
    init_db(db_path)
    sql = "SELECT * FROM cal_events WHERE date >= ? AND date <= ?"
    args: list = [start, end]
    if tracks:
        sql += f" AND track IN ({','.join('?' * len(tracks))})"
        args += tracks
    sql += " ORDER BY date, id"
    with _connect(db_path) as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_row_to_event(r) for r in rows]


def upcoming(days: int = 30, *, today: Optional[date_cls] = None,
             db_path: Optional[Path] = None) -> List[CalEvent]:
    today = today or datetime.now().date()
    start = today.strftime("%Y-%m-%d")
    end = (today + timedelta(days=days)).strftime("%Y-%m-%d")
    return list_range(start, end, db_path=db_path)


# ---------------------------------------------------------------- 자동 유입

def _dedup_external(db_path: Optional[Path] = None) -> int:
    """과거 버그(불안정 hash 키)로 생긴 중복 정리 — 같은 (날짜, 제목)은 1건만 유지.

    사용자가 상태/메모를 남긴 행을 우선 보존하고, 없으면 가장 오래된 행을 남긴다.
    """
    init_db(db_path)
    removed = 0
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, date, title, status, memo FROM cal_events "
            "WHERE track = 'external' ORDER BY id"
        ).fetchall()
        groups: dict = {}
        for r in rows:
            groups.setdefault((r["date"], r["title"]), []).append(r)
        for dup in groups.values():
            if len(dup) < 2:
                continue
            # 보존 우선순위: 상태/메모가 있는 행 → 가장 오래된 행
            touched = [r for r in dup if (r["status"] or "todo") != "todo"
                       or (r["memo"] or "")]
            keep = touched[0] if touched else dup[0]
            for r in dup:
                if r["id"] != keep["id"]:
                    conn.execute("DELETE FROM cal_events WHERE id = ?", (r["id"],))
                    removed += 1
    return removed


def sync_external(db_path: Optional[Path] = None) -> int:
    """규제 시드 시행일 + 플레이북 변경 → external 트랙 upsert. 추가건수 반환."""
    init_db(db_path)
    _dedup_external(db_path)
    before = _count(db_path)
    try:
        from data_layer.regulatory.seed import SEED_ENTRIES
        for e in SEED_ENTRIES:
            d = (e.effective_date or "").strip()
            if len(d) == 10:
                grade = getattr(e.grade, "name", "")
                upsert_auto(
                    d, e.title, track="external",
                    kind="law" if grade == "LAW" else "kfda",
                    impact="high" if grade in ("LAW", "NOTICE") else "mid",
                    source="seed", ext_key=e.id, ref_id=e.id,
                    tags=list(e.tags or []), db_path=db_path,
                )
    except Exception:
        pass
    try:
        from data_layer.regulatory.playbook_seed import PLAYBOOKS
        for pb in PLAYBOOKS:
            for c in getattr(pb, "recent_changes", []):
                d = (getattr(c, "date", "") or "").strip()
                if len(d) != 10:
                    continue
                kind = getattr(c, "kind", "")
                title = f"{kind} · {getattr(c, 'summary', '')}".strip(" ·")
                upsert_auto(
                    d, title, track="external",
                    kind="law" if kind == "시행" else "kfda",
                    impact="high" if kind == "시행" else "mid",
                    source="playbook",
                    ext_key=f"{pb.topic}-{hashlib.md5(title.encode('utf-8')).hexdigest()[:10]}",
                    tags=[pb.topic], db_path=db_path,
                )
    except Exception:
        pass
    return _count(db_path) - before


# ---- KGSP 의무 주기 템플릿: (id, 제목, 주기, 조건 handles 또는 None=항상)
DUTY_TEMPLATES = [
    ("edu_monthly",   "KGSP 정기 교육·평가 실시", "monthly", None),
    ("narc_check",    "마약류 재고 점검·NIMS 보고 확인", "monthly", ["마약류·향정"]),
    ("carrier_qual",  "수송용기 적격성평가 (분기)", "quarterly",
     ["냉장(2~8℃)", "냉동(-20℃)", "생물학적제제"]),
    ("self_inspect",  "자체점검(자율점검) 실시 — 실태조사 대비", "yearly", None),
    ("temp_mapping",  "보관창고 온도 매핑 재검증", "yearly",
     ["냉장(2~8℃)", "냉동(-20℃)"]),
]


def _duty_dates(period: str, duty_id: str, profile: Dict,
                today: date_cls, horizon_days: int) -> List[str]:
    """주기 → 향후 horizon 내 예정일 목록 (결정론적)."""
    end = today + timedelta(days=horizon_days)
    out: List[str] = []
    if period == "monthly":
        y, m = today.year, today.month
        for _ in range(horizon_days // 28 + 2):
            d = date_cls(y, m, 25)
            if today <= d <= end:
                out.append(d.strftime("%Y-%m-%d"))
            m += 1
            if m > 12:
                m, y = 1, y + 1
    elif period == "quarterly":
        for month in (1, 4, 7, 10):
            for year in (today.year, today.year + 1):
                d = date_cls(year, month, 15)
                if today <= d <= end:
                    out.append(d.strftime("%Y-%m-%d"))
    elif period == "yearly":
        month = int(profile.get("self_inspection_month", 11)) \
            if duty_id == "self_inspect" else int(profile.get("mapping_month", 6))
        if duty_id not in ("self_inspect", "temp_mapping"):
            month = 9
        for year in (today.year, today.year + 1):
            try:
                d = date_cls(year, month, 10)
            except ValueError:
                continue
            if today <= d <= end:
                out.append(d.strftime("%Y-%m-%d"))
    return out


def ensure_duties(profile: Dict, *, horizon_days: int = 365,
                  today: Optional[date_cls] = None,
                  db_path: Optional[Path] = None) -> int:
    """프로필 기반 KGSP 의무 일정을 향후 horizon 만큼 자동 생성(upsert)."""
    today = today or datetime.now().date()
    handles = set(profile.get("handles", []))
    before = _count(db_path)
    for duty_id, title, period, cond in DUTY_TEMPLATES:
        if cond and not (handles & set(cond)):
            continue
        for d in _duty_dates(period, duty_id, profile, today, horizon_days):
            upsert_auto(d, title, track="duty", kind=duty_id, impact="high",
                        source="duty", ext_key=duty_id, db_path=db_path)
    return _count(db_path) - before


def _count(db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM cal_events").fetchone()
    return int(row["n"]) if row else 0
