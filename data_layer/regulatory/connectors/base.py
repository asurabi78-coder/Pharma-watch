"""규제 데이터 소스 추상 베이스 — Phase 8.2 어댑터 패턴.

원칙:
- connector 는 *데이터 소스* 만 추상화한다. 스코어링/등급 정렬은 engine 책임.
- 비활성 connector(enabled=False)는 search 시 자동 스킵.
- LLM 호출 절대 금지.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from data_layer.connectors.base import SourceTier
from data_layer.regulatory.models import LawEntry


class RegulatoryConnector(ABC):
    """규제 원문 데이터 소스 어댑터."""

    name: str = "abstract"

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """현재 호출 가능한 상태인지. False면 search 시 스킵."""
        ...

    @abstractmethod
    def fetch_all(
        self,
        grade_filter: Optional[List[SourceTier]] = None,
    ) -> List[LawEntry]:
        """모든 항목 반환. grade_filter 지정 시 해당 등급만."""
        ...

    @abstractmethod
    def fetch_by_id(self, entry_id: str) -> Optional[LawEntry]:
        """ID 로 단일 항목 조회. 없으면 None."""
        ...
