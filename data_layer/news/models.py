"""뉴스 아이템 모델 — Phase A."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NewsItem:
    """단일 뉴스 항목. 출처별 fetcher 가 공통으로 반환하는 형식."""
    id: str                          # 중복 제거용 고유 키 (URL hash 등)
    title: str
    url: str
    source: str                      # "dailypharm" / "yakup" / "mfds" / ...
    source_label: str                # UI 표시용 — "데일리팜"
    category: str = ""               # 사이트 내부 카테고리
    summary: str = ""                # 본문 일부 (있으면)
    published_at: str = ""           # ISO 문자열. 미상이면 ""
    fetched_at: str = ""             # 수집 시점
    tags: List[str] = field(default_factory=list)
    thumbnail: Optional[str] = None  # 썸네일 URL (있으면)
    importance: str = ""             # 결정론적 중요도: high / mid / low (빈값=미평가)
    # ── 분류 체계 확장 (추가 전용) ──
    source_type: str = ""            # official / media / association / unknown
    source_domain: str = ""
    official_source_url: str = ""
    biz_category: str = ""           # 업무 카테고리(대표 1개)
    is_urgent: bool = False
    urgent_candidate: bool = False   # (메모리 전용) 긴급 후보
    verification_status: str = ""    # official_confirmed / checking / ""
    qa_relevance_score: int = 0
    qa_impact: str = ""
    action_items: str = ""
    affected_work: str = ""
    duplicate_group_id: str = ""
    content_hash: str = ""
