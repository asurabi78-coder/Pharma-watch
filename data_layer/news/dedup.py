"""뉴스 중복 통합 — 제목 정규화 · content_hash · 72시간 유사도 그룹핑 (결정론적)."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Dict, List

_BRACKET = re.compile(r"\[[^\]]*\]|\([^)]*\)")
_PUNCT = re.compile(r"[\"'“”‘’·,…\.\-–—:;!?_/]+")
_WS = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    t = title or ""
    t = _BRACKET.sub(" ", t)
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip().lower()
    return t


def content_hash(title: str) -> str:
    return hashlib.sha1(normalize_title(title).encode("utf-8")).hexdigest()[:16]


def _tokens(title: str):
    return set(w for w in normalize_title(title).split() if len(w) >= 2)


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


SIM_THRESHOLD = 0.6
WINDOW_HOURS = 72


def _parse_ts(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:19])
    except Exception:
        return None


def _within(a: str, b: str, hours: int) -> bool:
    da, db = _parse_ts(a), _parse_ts(b)
    if da is None or db is None:
        return True  # 시각 미상이면 윈도우 제약 없이 비교
    return abs((da - db).total_seconds()) <= hours * 3600


def assign_groups(items: List[dict]) -> Dict[str, str]:
    """items: [{id, title, ts}] → {id: duplicate_group_id}. 그리디·결정론적."""
    ordered = sorted(items, key=lambda x: x.get("ts") or "")
    groups: List[dict] = []
    out: Dict[str, str] = {}
    for it in ordered:
        title = it.get("title", "")
        ts = it.get("ts", "")
        placed = False
        for g in groups:
            if _within(g["ts"], ts, WINDOW_HOURS) and similarity(g["title"], title) >= SIM_THRESHOLD:
                out[it["id"]] = g["gid"]
                g["members"].append(it["id"])
                placed = True
                break
        if not placed:
            gid = content_hash(title)
            groups.append({"gid": gid, "title": title, "ts": ts, "members": [it["id"]]})
            out[it["id"]] = gid
    return out
