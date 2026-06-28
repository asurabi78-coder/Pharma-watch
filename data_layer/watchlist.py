"""캘린더 관심목록 — 사용자별 ⭐ 저장 (db/cal_watch.json).

calendar_repo 스키마를 건드리지 않는 독립 저장소. 추가 전용.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import List

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PATH = _PROJECT_ROOT / "db" / "cal_watch.json"
_LOCK = threading.Lock()


def key_for(ev) -> str:
    """이벤트의 안정 키 (UNIQUE(source,ext_key,date) 기반)."""
    base = getattr(ev, "ref_id", "") or getattr(ev, "ext_key", "") or f"id{ev.id}"
    return f"{getattr(ev,'source','')}|{base}|{ev.date}"


def _load() -> dict:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def list_keys(user: str = "(local)") -> List[str]:
    return list(_load().get(user or "(local)", []))


def is_watched(user: str, key: str) -> bool:
    return key in _load().get(user or "(local)", [])


def toggle(user: str, key: str) -> bool:
    """추가/해제 토글 → 추가됐으면 True, 해제됐으면 False."""
    with _LOCK:
        d = _load()
        u = user or "(local)"
        arr = d.get(u, [])
        if key in arr:
            arr.remove(key)
            res = False
        else:
            arr.append(key)
            res = True
        d[u] = arr
        _save(d)
    return res


def count(user: str = "(local)") -> int:
    return len(list_keys(user))
