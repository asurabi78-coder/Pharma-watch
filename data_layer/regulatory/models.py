"""규제 데이터 모델 — Phase 9.9 통합 enum (SourceTier 7단계) 사용.

Phase 9.9 마이그레이션 (2026-05-28):
- 구 5단계 등급 enum 제거. `data_layer.connectors.base.SourceTier` 로 일원화.
- 기존 GRADE_LABEL / GRADE_PRIORITY 도 제거. UI 라벨은 `base.TIER_LABEL`, 정렬은
  `SourceTier.priority` property 를 사용한다.
- LawEntry.grade 필드명은 유지 (기존 시드 호환). 타입만 SourceTier.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# 통합 enum / 라벨 — base.connectors 에서 import (단일 출처 원칙)
from data_layer.connectors.base import SourceTier, TIER_LABEL  # noqa: F401  (re-export)


@dataclass
class LawEntry:
    """규제 원문 항목 — 원문과 실무 해석을 분리 저장 (절대 섞지 않음)."""
    id: str
    title: str
    grade: SourceTier
    article: str = ""           # 조문번호 (예: "제15조 제2항")
    effective_date: str = ""    # 시행일 YYYY-MM-DD
    source: str = ""            # 출처 (law.go.kr / MFDS / 내부 SOP 등)
    content: str = ""           # 원문 내용 (절대 가공 금지)
    practical_interpretation: str = ""  # 실무 해석 (원문과 분리)
    tags: List[str] = field(default_factory=list)
    related_ids: List[str] = field(default_factory=list)
    # ── 검색 정확도용 확장 필드 (additive) ──
    canonical_title: str = ""          # 정식 공식 법령명 (URL/표시용)
    aliases: List[str] = field(default_factory=list)   # 약칭·별칭·불완전명
    document_type: str = ""            # 법률/시행령/시행규칙/고시/행정규칙/안내서/내부 SOP/해외 가이드
    issuing_authority: str = ""        # 소관기관
    official_source_url: str = ""      # 공식 원문 URL (생성 금지 — 공식 스킴/데이터만)
    promulgation_date: str = ""        # 공포일
    current_status: str = ""           # 현행/개정예정/폐지/참고
    origin: str = ""                   # domestic/foreign/internal/ai
    scope_tags: List[str] = field(default_factory=list)
    requires_human_review: bool = True  # ph