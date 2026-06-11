"""SOP ↔ 규제 요구사항 자동비교 엔진 — 결정론적 (LLM 비용 0, 선택적 보강).

목적: 사용자의 내부 SOP 텍스트가 특정 규제(시드 LawEntry 또는 붙여넣은 원문)의
요구사항을 어디까지 충족하는지 '갭'을 찾아 보여준다.

방식(고정 공식):
1) 규제 원문을 '요구사항 절(clause)' 단위로 분해 (번호 목록 1./2., 문장 단위).
2) 각 절에서 핵심 키워드를 추출(불용어 제거, 2자 이상 토큰).
3) SOP 텍스트에 키워드가 얼마나 등장하는지 비율(coverage) 계산.
4) 임계값으로 충족/부분/미흡 판정. 같은 입력 → 항상 같은 결과.

이건 '판단/거부권'이 아니라 '점검 보조'다 — 최종 확인은 QA 담당자 몫.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# 한국어 조사/불용어 — 키워드에서 제외 (의미 약한 토큰)
_STOPWORDS = {
    "다음", "사항", "경우", "관련", "대한", "위한", "따라", "통해", "또는", "그리고",
    "있다", "한다", "하여야", "하여", "되어", "된다", "수", "등", "및", "이상", "이내",
    "각", "해당", "모든", "필요", "실시", "작성", "관리", "기록", "유지", "확인", "조치",
    "준수", "구분", "운영", "여부", "보관", "처리", "발생", "대상", "기준", "절차",
}

_CLAUSE_SPLIT = re.compile(r"(?:^|\n)\s*(?:\d+[.)]|[-•·])\s*")
_TOKEN = re.compile(r"[가-힣]{2,}|[A-Za-z]{2,}|\d+(?:℃|도|시간|일|개월|년)")

# 흔한 한국어 조사 — 어간 매칭 시 끝에서 제거
_JOSA = ("으로써", "에게서", "으로", "에서", "에게", "께서", "이나", "라도", "부터", "까지",
         "마다", "조차", "처럼", "보다", "을", "를", "이", "가", "은", "는", "의", "에",
         "와", "과", "도", "로", "만", "랑", "야", "여", "고")

# 요구사항이 아닌 머리말(preamble) 패턴 — 점검 대상에서 제외
_PREAMBLE = re.compile(r"(다음.{0,4}(사항|같다|따른다)|준수하여야\s*한다$|갖추어야\s*한다$)")


@dataclass
class ClauseResult:
    clause: str
    keywords: List[str]
    matched: List[str]
    coverage: float
    status: str  # covered / partial / missing


@dataclass
class CompareResult:
    reg_title: str
    clauses: List[ClauseResult] = field(default_factory=list)
    covered: int = 0
    partial: int = 0
    missing: int = 0

    @property
    def total(self) -> int:
        return len(self.clauses)

    @property
    def score(self) -> int:
        """0~100 점수 — covered=1, partial=0.5 가중 평균."""
        if not self.clauses:
            return 0
        return round(100 * (self.covered + 0.5 * self.partial) / self.total)


def _split_clauses(text: str) -> List[str]:
    """규제 원문 → 요구사항 절 리스트."""
    text = (text or "").strip()
    if not text:
        return []
    parts = _CLAUSE_SPLIT.split(text)
    clauses: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 번호목록이 아니면 문장 단위로도 분해
        for sent in re.split(r"[.\n]", p):
            sent = sent.strip()
            if len(sent) >= 6 and not _PREAMBLE.search(sent):  # 짧은/머리말 조각 제외
                clauses.append(sent)
    return clauses


def _stem(tok: str) -> str:
    """토큰 끝의 조사를 제거한 어간. 한글 토큰에만 적용."""
    if not tok or not ("가" <= tok[0] <= "힣"):
        return tok
    for j in _JOSA:
        if tok.endswith(j) and len(tok) - len(j) >= 2:
            return tok[: -len(j)]
    return tok


def _keywords(clause: str) -> List[str]:
    toks = _TOKEN.findall(clause)
    seen, out = set(), []
    for t in toks:
        stem = _stem(t)
        if stem in _STOPWORDS or stem in seen or len(stem) < 2:
            continue
        seen.add(stem)
        out.append(stem)
    return out


def compare(reg_text: str, sop_text: str, *, reg_title: str = "규제 원문") -> CompareResult:
    """규제 원문 vs SOP — 갭 분석. 결정론적."""
    sop = sop_text or ""
    res = CompareResult(reg_title=reg_title)
    for clause in _split_clauses(reg_text):
        kws = _keywords(clause)
        if not kws:
            continue
        matched = [k for k in kws if k in sop]  # kws 는 어간 — SOP 원문에 substring 매칭
        cov = len(matched) / len(kws) if kws else 0.0
        if cov >= 0.6:
            status = "covered"
            res.covered += 1
        elif cov >= 0.3:
            status = "partial"
            res.partial += 1
        else:
            status = "missing"
            res.missing += 1
        res.clauses.append(ClauseResult(
            clause=clause, keywords=kws, matched=matched,
            coverage=round(cov, 2), status=status,
        ))
    return res


def compare_with_entry(entry, sop_text: str) -> CompareResult:
    """LawEntry 와 SOP 비교 — 원문(content) + 실무해석을 요구사항 소스로."""
    reg_text = getattr(entry, "content", "") or ""
    return compare(reg_text, sop_text, reg_title=getattr(entry, "title", "규제"))
