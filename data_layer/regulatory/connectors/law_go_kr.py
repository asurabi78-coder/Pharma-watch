"""law.go.kr Open API 어댑터 — RegulatoryConnector wrapper.

활성화 조건: 환경변수 LAW_GO_KR_API_KEY 존재.
"""
from __future__ import annotations

import os
from typing import List, Optional

from data_layer.connectors.base import SourceTier
from data_layer.regulatory.connectors.base import RegulatoryConnector
from data_layer.regulatory.models import LawEntry


class LawGoKrConnector(RegulatoryConnector):
    name = "law.go.kr"
    ENV_KEY = "LAW_GO_KR_API_KEY"

    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.ENV_KEY) or None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def fetch_all(
        self,
        grade_filter: Optional[List[SourceTier]] = None,
    ) -> List[LawEntry]:
        if not self.enabled:
            return []
        raise NotImplementedError(
            "LawGoKrConnector.fetch_all 실 구현 대기. "
            "law.go.kr Open API 호출 + 응답 파싱 + LawEntry 변환 + 캐싱이 필요합니다. "
            "API 키는 환경변수 LAW_GO_KR_API_KEY 에 설정되어 있습니다."
        )

    def fetch_by_id(self, entry_id: str) -> Optional[LawEntry]:
        if not self.enabled:
            return None
        raise NotImplementedError("LawGoKrConnector.fetch_by_id 실 구현 대기.")
