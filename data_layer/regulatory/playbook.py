"""주제 플레이북 모델 — 규제 검토실을 '검색'에서 'QA 업무 의사결정'으로.

설계 배경 (2026-06-01 대표님 방향 확정):
- 기존 `LawEntry` 는 *원문 1건* 단위 (검색기 관점). 이 모듈은 그 위에 *업무 시나리오*
  단위를 올린다. QA 담당자가 "온도이탈" 을 누르면 "그래서 뭘 해야 하는가" — 적용 법령 ·
  보고기한 · 체크리스트 · 감사 질문 · 관련 SOP 가 한 화면에 나오게 하는 데이터 골격.

두 축 분리 (절대 합치지 않는다):
  축 1 — 효력(근거 가능성): `SourceTier`. 법령 > 고시/KGSP/GMP > 가이드 > 참고.
          이 축은 "이 자료를 단독 근거로 규정 위반을 판단할 수 있는가" 를 결정한다.
  축 2 — 업무 시나리오: 본 모듈(TopicPlaybook). 화면의 '앞문'은 축 2 지만,
          모든 RegRef 는 축 1 의 tier 를 그대로 달고 다닌다. KGSP 를 '가이드' 로
          강등시키는 일은 없어야 한다 — KGSP/GMP/식약처 고시는 법적 구속력이 있다.

콘텐츠 출처 구분 (Provenance):
  CURATED  — 사람(QA/법무) 검증 완료. 단독 사용 가능.
  AI_DRAFT — AI 초안. 반드시 사람 확인 후 사용 ("확인 필요" 라벨).
  AUTO     — 시스템 자동 수집(규제 캘린더 / law.go.kr). 출처 링크로 검증.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from data_layer.connectors.base import (  # noqa: F401  (re-export 편의)
    SourceTier,
    TIER_LABEL,
)


class Provenance(str, Enum):
    """플레이북 안의 각 콘텐츠 조각이 '어떻게 만들어졌는가'."""

    CURATED = "curated"
    AI_DRAFT = "ai_draft"
    AUTO = "auto"

    @property
    def is_verified(self) -> bool:
        return self is Provenance.CURATED

    @property
    def label(self) -> str:
        return {
            Provenance.CURATED: "검증됨",
            Provenance.AI_DRAFT: "AI 초안 · 확인 필요",
            Provenance.AUTO: "자동 수집",
        }[self]


@dataclass
class RegRef:
    """플레이북이 가리키는 '적용 규정' 1건 (효력 축 tier 보유)."""

    title: str
    tier: SourceTier
    article: str = ""
    url: str = ""                   # 원문 직링크 (law.go.kr / MFDS / WHO)
    effective_date: str = ""
    law_entry_id: str = ""
    key_points: List[str] = field(default_factory=list)  # 핵심 요지 (브리핑용)
    provenance: Provenance = Provenance.AUTO

    @property
    def can_be_sole_basis(self) -> bool:
        return self.tier.can_be_sole_basis_for_compliance


@dataclass
class ReferenceLink:
    """참고 사이트·문서 1건 — 규정 근거는 아니나 실무에 도움되는 자료."""

    title: str
    url: str
    source: str = ""
    note: str = ""
    provenance: Provenance = Provenance.CURATED


@dataclass
class RecentChange:
    """최근/예정 개정."""

    date: str
    summary: str
    kind: str = "개정"
    url: str = ""
    provenance: Provenance = Provenance.AUTO


@dataclass
class KnownIssue:
    """자주 발생하는 실무 이슈 (검색 키워드 연결)."""

    name: str
    keyword: str = ""
    provenance: Provenance = Provenance.CURATED


@dataclass
class AuditQuestion:
    """실사/감사 때 받는 질문."""

    question: str
    hint: str = ""
    provenance: Provenance = Provenance.CURATED


@dataclass
class ChecklistItem:
    """QA 가 수행할 액션 1건."""

    action: str
    detail: str = ""
    related_sop_id: str = ""
    provenance: Provenance = Provenance.CURATED


@dataclass
class TopicPlaybook:
    """업무 시나리오 1개 = 화면의 '주제 버튼' 1개."""

    id: str
    topic: str
    summary: str = ""             # 1~2문장 한 줄 요약
    overview: str = ""            # 개요 — 무엇이고 어떤 법 체계가 적용되는지 몇 줄 설명
    aliases: List[str] = field(default_factory=list)

    reg_refs: List[RegRef] = field(default_factory=list)
    reference_links: List[ReferenceLink] = field(default_factory=list)
    web_query: str = ""
    recent_changes: List[RecentChange] = field(default_factory=list)
    common_issues: List[KnownIssue] = field(default_factory=list)
    audit_questions: List[AuditQuestion] = field(default_factory=list)
    checklist: List[ChecklistItem] = field(default_factory=list)
    related_sop_ids: List[str] = field(default_factory=list)

    report_deadline: str = ""
    audit_impact: str = ""

    requires_human_review: bool = True
    last_reviewed_by: str = ""
    last_reviewed_at: str = ""

    def unverified_items(self) -> List[str]:
        """사람 검증 안 된(AI 초안) 콘텐츠 모음. 화면 경고/분리용."""
        flagged: List[str] = []
        for r in self.reg_refs:
            if r.provenance is Provenance.AI_DRAFT:
                flagged.append(f"규정: {r.title}")
        for i in self.common_issues:
            if i.provenance is Provenance.AI_DRAFT:
                flagged.append(f"이슈: {i.name}")
        for q in self.audit_questions:
            if q.provenance is Provenance.AI_DRAFT:
                flagged.append(f"감사질문: {q.question}")
        for c in self.checklist:
            if c.provenance is Provenance.AI_DRAFT:
                flagged.append(f"체크리스트: {c.action}")
        return flagged

    @property
    def has_unverified(self) -> bool:
        return bool(self.unverified_items())

    @property
    def citable_refs(self) -> List[RegRef]:
        return [r for r in self.reg_refs if r.can_be_sole_basis]
