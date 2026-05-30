"""data_layer.connectors — Tool/API Architecture skeleton.

도메인:
  - law/  : 국가법령정보센터 (law.go.kr)
모든 connector 는 base.Connector 를 상속. SourceTier 등급은 base 에 정의.
"""
from data_layer.connectors.base import (
    Connector,
    SourceRecord,
    SourceTier,
    StubConnector,
    REGULATORY_GRADE_ALLOWED,
    TIER_LABEL,
    TIER_PRIORITY,
)

__all__ = [
    "Connector",
    "SourceRecord",
    "SourceTier",
    "StubConnector",
    "REGULATORY_GRADE_ALLOWED",
    "TIER_LABEL",
    "TIER_PRIORITY",
]
