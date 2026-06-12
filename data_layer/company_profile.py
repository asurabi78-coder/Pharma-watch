"""회사 프로필 — 취급 유형·회사 정보 저장 (JSON 파일, db/company_profile.json).

캘린더 임팩트 스코어링·KGSP 의무 자동생성·SOP 생성기 등에서 공유한다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROFILE_PATH = _PROJECT_ROOT / "db" / "company_profile.json"

HANDLE_OPTIONS = [
    "상온 의약품", "냉장(2~8℃)", "냉동(-20℃)", "생물학적제제", "마약류·향정", "위탁(3PL)",
]

_DEFAULT: Dict = {
    "company": "",
    "handles": ["상온 의약품"],
    "self_inspection_month": 11,   # 자체점검 실시 월
    "mapping_month": 6,            # 온도 매핑 재검증 월 (냉장/냉동 시)
}

# 취급 유형 → 관련 규제 태그 키워드 (임팩트 스코어링용)
_HANDLE_TAGS: Dict[str, Set[str]] = {
    "냉장(2~8℃)":  {"콜드체인", "온도", "수송", "로거", "validation"},
    "냉동(-20℃)":  {"콜드체인", "온도", "수송", "로거", "validation"},
    "생물학적제제": {"생물학적제제", "콜드체인", "백신"},
    "마약류·향정":  {"마약류", "NIMS", "향정", "보안"},
    "위탁(3PL)":   {"위탁", "수탁", "SLA", "Quality Agreement"},
}

# 이 태그가 달린 규제는 '해당 유형을 취급할 때만' 의미가 있다 (아니면 참고용)
_EXCLUSIVE_TAGS: Dict[str, str] = {
    "마약류": "마약류·향정",
    "NIMS": "마약류·향정",
    "생물학적제제": "생물학적제제",
    "백신": "생물학적제제",
}


def load_profile() -> Dict:
    try:
        data = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
        out = dict(_DEFAULT)
        out.update({k: v for k, v in data.items() if k in _DEFAULT})
        return out
    except Exception:
        return dict(_DEFAULT)


def save_profile(profile: Dict) -> None:
    _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: profile.get(k, _DEFAULT[k]) for k in _DEFAULT}
    _PROFILE_PATH.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def relevant_keywords(profile: Dict) -> Set[str]:
    """프로필 취급 유형에서 관심 태그 키워드 집합."""
    kws: Set[str] = set()
    for h in profile.get("handles", []):
        kws |= _HANDLE_TAGS.get(h, set())
    return kws


def score_impact(tags: List[str], base_impact: str, profile: Dict) -> str:
    """규제 태그 × 회사 프로필 → 표시 임팩트 (high / mid / low).

    - 우리 취급 유형과 직결되는 태그가 있으면 base 그대로(또는 상향).
    - '마약류'처럼 특정 유형 전용 태그인데 우리가 취급하지 않으면 low(참고).
    - 매칭 정보가 없으면 base 유지.
    """
    tags = [str(t) for t in (tags or [])]
    handles = set(profile.get("handles", []))

    # 전용 태그인데 미취급 → 참고용으로 강등
    for t in tags:
        need = _EXCLUSIVE_TAGS.get(t)
        if need and need not in handles:
            return "low"

    kws = relevant_keywords(profile)
    if kws and any(t in kws for t in tags):
        return "high"  # 우리 직결 — 강조
    return base_impact
