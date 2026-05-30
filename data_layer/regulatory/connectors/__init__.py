"""규제 데이터 소스 어댑터 패키지 — Phase 8.2.

기본 등록 순서:
  1. SeedConnector (항상 활성, 로컬 시드)
  2. LawGoKrConnector (LAW_GO_KR_API_KEY 있으면 활성)
  3. MfdsConnector    (MFDS_API_KEY        있으면 활성)
"""
from __future__ import annotations

from typing import List

from data_layer.regulatory.connectors.base import RegulatoryConnector
from data_layer.regulatory.connectors.law_go_kr import LawGoKrConnector
from data_layer.regulatory.connectors.mfds import MfdsConnector
from data_layer.regulatory.connectors.seed_connector import SeedConnector


def get_default_connectors() -> List[RegulatoryConnector]:
    """기본 connector 인스턴스 리스트. 매 호출마다 새로 — 환경변수 변경 반영용."""
    return [
        SeedConnector(),
        LawGoKrConnector(),
        MfdsConnector(),
    ]


def get_active_connectors() -> List[RegulatoryConnector]:
    """현재 enabled=True 인 connector 만."""
    return [c for c in get_default_connectors() if c.enabled]


__all__ = [
    "RegulatoryConnector",
    "SeedConnector",
    "LawGoKrConnector",
    "MfdsConnector",
    "get_default_connectors",
    "get_active_connectors",
]
