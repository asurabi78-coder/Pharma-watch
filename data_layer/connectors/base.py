"""Connector 표준 인터페이스 — Phase 10 Tool/API Architecture.

원칙:
- Connector 는 *데이터 소스만* 추상화한다. 스코어링/등급 정렬·LLM 호출은 engine 책임.
- LLM 호출 절대 금지. 외부 API/파일/DB 만 다룬다.
- skeleton 단계: fetch() 는 stub 으로 빈 dict 또는 NotImplementedError 가 표준.
- 모든 결과는 SourceTier 가 부여된다. Agent 가 보는 모든 정보는 등급이 있어야 한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SourceTier(str, Enum):
    """Phase 9.9 / Phase 10 출처 효력 등급 — 7종 통합 enum.

    구 5단계 등급 enum (regulatory 모듈) 과 7단계 등급 enum (connector 모듈) 을
    Phase 9.9 에서 본 enum 으로 통합. UI 라벨·정렬·필터·규정 판단 가능 여부 모두
    이 enum 으로 일원화.

    LAW       — 법 / 시행령 / 시행규칙 (효력 1순위)
    NOTICE    — 행정규칙 · 고시 · 공고
    GUIDE     — 안내서 · 지침 (법적 의무 X, 실무 참고)
    INTERNAL  — 회사 SOP · 내부 메모 · 과거 회의록 (SLA·계약 결합으로 OFFICIAL 보다 위)
    OFFICIAL  — 고객사·임대인·공급사·관청의 공식 자료 (보조 근거)
    NEWS      — 언론·뉴스·블로그 (배경 컨텍스트 한정)
    AI        — LLM 추정 / 외부 데이터 부재 (최후 보조)
    """

    LAW = "LAW"
    NOTICE = "NOTICE"
    GUIDE = "GUIDE"
    OFFICIAL = "OFFICIAL"
    NEWS = "NEWS"
    INTERNAL = "INTERNAL"
    AI = "AI"

    @property
    def priority(self) -> int:
        """권위 우선순위 점수. 높을수록 강함. 정렬에 쓸 때는 -priority 또는 reverse=True."""
        return TIER_PRIORITY[self]

    @property
    def can_be_sole_basis_for_compliance(self) -> bool:
        """규정 판단(QA / Contract VETO)의 단독 근거로 사용 가능한가.

        OFFICIAL / NEWS / AI 는 보조 컨텍스트로만 허용 — 단독으로 위반 판단 불가.
        """
        return self in REGULATORY_GRADE_ALLOWED


# 규정 판단(QA / Contract VETO)의 최종 근거로 사용 가능한 등급.
# NEWS / AI / OFFICIAL 은 "보조 컨텍스트" 일 뿐 규정 위반 판단 근거가 될 수 없다.
REGULATORY_GRADE_ALLOWED: set = {
    SourceTier.LAW,
    SourceTier.NOTICE,
    SourceTier.GUIDE,
    SourceTier.INTERNAL,
}

# 출처 권위 점수 — 명세 §2.2 (Phase 9.9). 높을수록 권위 강함.
# LAW > NOTICE > GUIDE > INTERNAL > OFFICIAL > NEWS > AI.
# INTERNAL > OFFICIAL: 내부 SOP 는 SLA·계약 직접 반영, 외부 OFFICIAL 은 보조 근거.
TIER_PRIORITY: Dict[SourceTier, int] = {
    SourceTier.LAW: 100,
    SourceTier.NOTICE: 90,
    SourceTier.GUIDE: 80,
    SourceTier.INTERNAL: 70,
    SourceTier.OFFICIAL: 50,
    SourceTier.NEWS: 30,
    SourceTier.AI: 10,
}

# UI 라벨 (이모지 + 표시명 + 색상 토큰)
TIER_LABEL: Dict[SourceTier, tuple] = {
    SourceTier.LAW:      ("🔴 법령",      "danger"),
    SourceTier.NOTICE:   ("🟠 고시",      "warn"),
    SourceTier.GUIDE:    ("🔵 가이드",    "accent"),
    SourceTier.OFFICIAL: ("🟣 공식자료",  "info"),
    SourceTier.NEWS:     ("🟡 뉴스/웹",   "muted"),
    SourceTier.INTERNAL: ("⚫ 내부",      "neutral"),
    SourceTier.AI:       ("🟢 AI 추정",  "qa"),
}


@dataclass
class SourceRecord:
    """모든 connector 가 반환하는 단일 정보 단위.

    원문(content)과 실무 해석(practical_interpretation)은 절대 섞지 않는다.
    Agent 는 tier 가 REGULATORY_GRADE_ALLOWED 에 포함될 때만 규정 판단에 사용한다.
    """

    id: str
    title: str
    tier: SourceTier
    source: str = ""              # 출처 식별자 (law.go.kr / customer_official 등)
    url: str = ""                 # 원본 링크 (있으면)
    published_at: str = ""        # 발간/발효 일자 YYYY-MM-DD
    content: str = ""             # 원문 (가공 금지)
    summary: str = ""             # connector 가 추출한 요약 (LLM 금지)
    tags: List[str] = field(default_factory=list)
    confidence: str = "verified"  # verified / estimated / unverified
    raw: Dict[str, Any] = field(default_factory=dict)  # 원본 응답 보존


class Connector(ABC):
    """모든 외부 API / 파일 / DB 커넥터의 표준 모양.

    Subclass 가 반드시 정의:
      - name        : 표준 출처 식별자 (예: "law_go_kr", "kakao_news")
      - tier        : 이 connector 가 반환하는 정보의 기본 등급
      - is_available(): API 키·의존성·네트워크 검사
      - fetch(**params) -> List[SourceRecord]: 정보 조회

    skeleton 단계(Phase 10) 에서는 fetch() 가 NotImplementedError 또는 빈 리스트로
    되어 있어도 무방. 실제 호출은 Phase 11 이후에서 채운다.
    """

    name: str = "abstract"
    tier: SourceTier = SourceTier.AI

    @abstractmethod
    def is_available(self) -> bool:
        """현재 호출 가능한 상태인지 (키·의존성 OK 여부)."""
        ...

    @abstractmethod
    def fetch(self, **params) -> List[SourceRecord]:
        """조회 수행. 실패 시 빈 리스트 또는 raise. LLM 호출 금지."""
        ...

    def describe(self) -> Dict[str, Any]:
        """connector 메타데이터 — tool_registry / UI 디버그용."""
        return {
            "name": self.name,
            "tier": self.tier.value if isinstance(self.tier, SourceTier) else str(self.tier),
            "available": self.is_available(),
            "class": type(self).__name__,
        }


class StubConnector(Connector):
    """Phase 10 skeleton 기본 구현 — 실제 호출 없이 등록·권한 매트릭스 테스트만 가능.

    모든 6개 도메인(law/mfds/web_research/news/document_vault/internal) 의
    초기 connector 는 이 stub 을 상속받아 fetch() 가 빈 리스트를 반환한다.
    Phase 11+ 에서 각자 실제 API 클라이언트로 교체.
    """

    name: str = "stub"
    tier: Sou