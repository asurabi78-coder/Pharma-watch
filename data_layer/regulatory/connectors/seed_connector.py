"""정적 시드 데이터 소스 — SEED_ENTRIES wrap.

항상 enabled=True. 외부 의존성/네트워크 없음.
"""
from __future__ import annotations

from typing import List, Optional

from data_layer.connectors.base import SourceTier
from data_layer.regulatory.connectors.base import RegulatoryConnector
from data_layer.regulatory.models import LawEntry
from data_layer.regulatory.seed import SEED_ENTRIES


class SeedConnector(RegulatoryConnector):
    name = "seed"

    @property
    def enabled(self) -> bool:
        return True

    def fetch_all(
        self,
        grade_filter: Optional[List[SourceTier]] = None,
    ) -> List[LawEntry]:
        if grade_filter is None:
            return list(SEED_ENTRIES)
        return [e for e in SEED_ENTRIES if e.grade in grade_filter]

    def fetch_by_id(self, entry_id: str) -> Optional[LawEntry]:
        for e in SEED_ENTRIES:
            if e.id == entry_id:
                return e
        return None
