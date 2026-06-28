"""규제 개정 법안(법령 라이프사이클) — 예시 시드.

각 법안은 단계(의견마감/공포·고시/시행예정/안내 적용/검토중)와
공고번호·공고일·의견마감일·시행일·개정 핵심·영향 업무를 가진다.

※ 예시 시드(임시) — law.go.kr/MFDS 실연동으로 대체 예정. 사람 검토 필수.
   analyzed()=True 인 항목만 개정핵심/영향업무가 채워져 있고,
   나머지는 화면에서 '원문 확인 가능 · QA 분석 대기'로 표시된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

STAGES = ["의견마감", "공포·고시", "시행예정", "안내 적용", "검토중"]


@dataclass
class Bill:
    id: str
    title: str
    stage: str
    org: str = "식품의약품안전처"
    notice_no: str = ""
    notice_date: str = ""
    comment_deadline: str = ""
    effective_date: str = ""
    core: str = ""
    impact: str = ""
    url: str = ""
    tags: List[str] = field(default_factory=list)

    def analyzed(self) -> bool:
        return bool(self.core or self.impact)


def cal_date(bl: "Bill") -> str:
    """단계별 달력 배치 기준일."""
    if bl.stage in ("시행예정", "안내 적용"):
        return bl.effective_date or bl.notice_date or bl.comment_deadline
    if bl.stage == "의견마감":
        return bl.comment_deadline or bl.notice_date
    return bl.notice_date or bl.comment_deadline or bl.effective_date


SEED_BILLS: List[Bill] = [
    Bill(
        id="amend_safety_rule",
        title="의약품 등의 안전에 관한 규칙 일부개정령안",
        stage="시행예정",
        notice_no="제2026-312호",
        notice_date="2026-05-30",
        comment_deadline="2026-06-19",
        effective_date="2026-07-14",
        core="콜드체인 의약품 2~8℃ 온도 일탈 발생 시 보고 절차를 강화하고, 운송 중 모니터링 데이터의 보관기간을 명시한다.",
        impact="냉장 의약품 입출고·수송 담당과 품질책임자(QA) — 온도 일탈 보고·기록 SOP 개정 및 데이터 보관 점검이 필요하다.",
        tags=["콜드체인", "온도일탈", "보고"],
    ),
    Bill(
        id="amend_bio_transport",
        title="생물학적제제 보관·수송 관리 규칙 개정",
        stage="공포·고시",
        notice_no="제2026-289호",
        notice_date="2026-07-08",
        effective_date="2026-10-08",
        core="보관시설·수송차량·수송용기의 자동온도기록장치 설치 의무 범위를 확대하고, 검교정 기록 보관기간을 2년으로 명시한다.",
        impact="냉장·냉동 수송 담당과 품질팀 — 수송용기 적격성평가 주기와 로거 검교정 일정을 재점검해야 한다.",
        tags=["생물학적제제", "수송", "로거"],
    ),
    Bill(
        id="amend_pharmacist_rule",
        title="약사법 시행규칙 일부개정안",
        stage="의견마감",
        notice_no="제2026-271호",
        notice_date="2026-06-12",
        comment_deadline="2026-07-03",
        tags=["약사법", "유통"],
    ),
    Bill(
        id="amend_kgsp",
        title="의약품 유통품질 관리기준(KGSP) 개정",
        stage="안내 적용",
        notice_no="제2026-298호",
        notice_date="2026-06-22",
        effective_date="2026-07-22",
        tags=["KGSP", "유통품질"],
    ),
    Bill(
        id="amend_narcotics",
        title="마약류 관리에 관한 법률 시행규칙 개정",
        stage="검토중",
        notice_no="—",
        notice_date="2026-06-30",
        tags=["마약류", "NIMS"],
    ),
    Bill(
        id="amend_import_customs",
        title="수입 의약품 통관검사 고시 개정",
        stage="공포·고시",
        notice_no="제2026-260호",
        notice_date="2026-06-18",
        effective_date="2026-09-18",
        tags=["수입", "통관"],
    ),
    Bill(
        id="amend_labeling",
        title="의약품 표시·기재 기준 개정",
        stage="의견마감",
        notice_no="제2026-305호",
        notice_date="2026-07-10",
        comment_deadline="2026-08-05",
        tags=["표시기재"],
    ),
]


def all_bills() -> List[Bill]:
    return list(SEED_BILLS)


def get(bill_id: str) -> Optional[Bill]:
    return next((b for b in SEED_BILLS if b.id == bill_id), None)


def list_in_range(start: str, end: str) -> List[Bill]:
    out = []
    for b in SEED_BILLS:
        d = cal_date(b)
        if d and start <= d <= end:
            out.append(b)
    return out


def upcoming(days: int = 45) -> List[Bill]:
    today = datetime.now().date()
    end = today + timedelta(days=days)
    out = []
    for b in SEED_BILLS:
        d = cal_date(b)
        if not d:
            continue
        try:
            dd = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= dd <= end:
            out.append(b)
    return out
