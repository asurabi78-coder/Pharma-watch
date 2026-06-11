"""뉴스 중요도 자동 태깅 — 결정론적 키워드 스코어러 (LLM 비용 0).

철학: '그럴듯한 요약' 대신 고정 공식. 같은 입력 → 항상 같은 등급.
규제·품질·콜드체인 실무 관점에서 '지금 봐야 하는가'를 점수화한다.

등급:
  high (🔴) — 의무·제재·시행·회수 등 즉시 영향
  mid  (🟠) — 개정 논의·가이드·점검 등 추적 대상
  low  (⚪) — 일반 산업·인사·동향

점수는 키워드 가중치 합. 임계값은 모듈 상단 상수로 고정(투명).
"""
from __future__ import annotations

from typing import List, Tuple

# (키워드, 가중치) — 실무 영향이 큰 단어일수록 높게.
_WEIGHTS: List[Tuple[str, int]] = [
    # 즉시 영향 (강)
    ("의무화", 5), ("의무", 3), ("시행", 4), ("시행일", 4),
    ("회수", 5), ("리콜", 5), ("폐기명령", 5), ("판매중지", 5), ("허가취소", 5),
    ("과징금", 5), ("행정처분", 5), ("처벌", 4), ("벌칙", 4),
    ("전면 시행", 5), ("의무 적용", 5),
    # 규제 변경 (중강)
    ("개정", 3), ("제정", 3), ("고시", 3), ("행정예고", 4), ("입법예고", 4),
    ("개정안", 3), ("신설", 3), ("강화", 3), ("의견수렴", 2),
    ("가이드라인", 2), ("지침", 2), ("기준 변경", 3), ("규칙 개정", 4),
    # 품질·콜드체인 도메인 (중)
    ("콜드체인", 3), ("온도 일탈", 4), ("온도일탈", 4), ("냉장", 2), ("냉동", 2),
    ("GDP", 2), ("KGSP", 2), ("GMP", 2), ("CAPA", 3), ("일탈", 3),
    ("품질부적합", 4), ("부적합", 3), ("변질", 3), ("오염", 3),
    ("마약류", 3), ("생물학적제제", 3), ("백신", 2), ("바이오의약품", 2),
    ("실태조사", 3), ("점검", 2), ("감사", 2), ("자료제출", 2), ("보고 마감", 3),
    ("수급", 2), ("품절", 3), ("공급중단", 4), ("수급불안", 3),
    # 약하게 (배경)
    ("논의", 1), ("검토", 1), ("발표", 1), ("도입", 1),
]

# 음(-) 가중치 — 실무 영향 낮은 기사 톤 다운.
_NEGATIVE: List[Tuple[str, int]] = [
    ("인사", -3), ("부음", -4), ("동정", -3), ("수상", -2), ("기념", -2),
    ("창립", -2), ("간담회", -1), ("축사", -2), ("인터뷰", -1),
]

HIGH_THRESHOLD = 7
MID_THRESHOLD = 3

_LABEL = {
    "high": ("🔴 높음", "high"),
    "mid":  ("🟠 보통", "mid"),
    "low":  ("⚪ 낮음", "low"),
}


def score_text(text: str) -> int:
    """제목(+요약+카테고리) 문자열의 중요도 점수. 결정론적."""
    if not text:
        return 0
    t = text
    total = 0
    for kw, w in _WEIGHTS:
        if kw in t:
            total += w
    for kw, w in _NEGATIVE:
        if kw in t:
            total += w
    return total


def grade(text: str) -> str:
    """점수 → 등급 문자열 (high/mid/low)."""
    s = score_text(text)
    if s >= HIGH_THRESHOLD:
        return "high"
    if s >= MID_THRESHOLD:
        return "mid"
    return "low"


def grade_item(item) -> str:
    """NewsItem → 등급. 제목+요약+카테고리를 합쳐 평가."""
    blob = " ".join(filter(None, [
        getattr(item, "title", ""),
        getattr(item, "summary", ""),
        getattr(item, "category", ""),
    ]))
    return grade(blob)


def label(importance: str) -> Tuple[str, str]:
    """등급 → (표시라벨, 색토큰). 미평가/미상은 빈 라벨."""
    return _LABEL.get(importance or "", ("", "low"))


def apply(items) -> None:
    """NewsItem 리스트에 importance 를 in-place 부여."""
    for it in items:
        try:
            it.importance = grade_item(it)
        except Exception:
            it.importance = ""
