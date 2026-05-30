"""규제 검색 엔진 — 키워드 매칭 + 등급 우선 정렬 (결정론적, LLM 미사용).

- 기본은 활성 connector(SeedConnector + 키 있는 외부 어댑터)에서 항목 수집.
- entries= 인자는 backward compat (직접 LawEntry 리스트 주면 그것만 검색).
- 외부 connector 가 NotImplementedError 를 던지면 그 connector 만 스킵하고 진행.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from data_layer.connectors.base import SourceTier
from data_layer.regulatory.models import LawEntry
from data_layer.regulatory.seed import SEED_ENTRIES
from data_layer.regulatory.connectors import (
    RegulatoryConnector,
    get_active_connectors,
)


@dataclass
class SearchResult:
    query: str
    entries: List[LawEntry] = field(default_factory=list)
    total: int = 0
    sources: List[str] = field(default_factory=list)


def _score(entry: LawEntry, q: str) -> int:
    """간단 매칭 점수 — 제목/태그가 본문보다 높은 가중치."""
    q = q.lower()
    score = 0
    if q in entry.title.lower():
        score += 10
    for tag in entry.tags:
        if q in tag.lower():
            score += 5
    if q in entry.content.lower():
        score += 2
    if q in entry.practical_interpretation.lower():
        score += 1
    return score


def _collect_from_connectors(
    connectors: List[RegulatoryConnector],
    grade_filter: Optional[List[SourceTier]] = None,
) -> tuple[List[LawEntry], List[str]]:
    """활성 connector 에서 entries 모으기. 실패한 connector 는 건너뛴다."""
    pooled: List[LawEntry] = []
    contributed: List[str] = []
    seen_ids: set[str] = set()
    for c in connectors:
        if not c.enabled:
            continue
        try:
            items = c.fetch_all(grade_filter=grade_filter)
        except NotImplementedError:
            continue
        except Exception:
            continue
        added = 0
        for entry in items:
            if entry.id in seen_ids:
                continue
            seen_ids.add(entry.id)
            pooled.append(entry)
            added += 1
        if added:
            contributed.append(c.name)
    return pooled, contributed


def search(
    query: str,
    grade_filter: Optional[List[SourceTier]] = None,
    entries: Optional[List[LawEntry]] = None,
    connectors: Optional[List[RegulatoryConnector]] = None,
) -> SearchResult:
    """키워드 검색 — 빈 query면 빈 결과."""
    if not query or not query.strip():
        return SearchResult(query=query or "")

    sources: List[str] = []
    if entries is not None:
        source = entries
    else:
        active = connectors if connectors is not None else get_active_connectors()
        source, sources = _collect_from_connectors(active, grade_filter)

    q = query.strip()

    candidates = []
    for entry in source:
        if grade_filter and entry.grade not in grade_filter:
            continue
        score = _score(entry, q)
        if score > 0:
            candidates.append((score, entry))

    candidates.sort(
        key=lambda t: (-t[0], -t[1].grade.priority)
    )

    return SearchResult(
        query=q,
        entries=[c[1] for c in candidates],
        total=len(candidates),
        sources=sources,
    )


def get_by_id(
    entry_id: str,
    entries: Optional[List[LawEntry]] = None,
    connectors: Optional[List[RegulatoryConnector]] = None,
) -> Optional[LawEntry]:
    """ID 로 항목 조회."""
    if entries is not None:
        for entry in entries:
            if entry.id == entry_id:
                return entry
        return None

    active = connectors if connectors is not None else get_active_connectors()
    for c in active:
        if not c.enabled:
            continue
        try:
            hit = c.fetch_by_id(entry_id)
        except NotImplementedError:
            continue
        except Exception:
            continue
        if hit is not None:
            return hit
    return None


def count_by_grade(
    entries: Optional[List[LawEntry]] = None,
    connectors: Optional[List[RegulatoryConnector]] = None,
) -> dict:
    """등급별 항목 수 집계. 기본 동작은 활성 connector 의 union."""
    if entries is None:
        active = connectors if connectors is not None else get_active_connectors()
        entries, _ = _collect_from_connectors(active)
    counts = {tier: 0 for tier in SourceTier}
    for entry in entries:
        counts[entry.grade] = counts.get(entry.grade, 0) + 1
    return counts
