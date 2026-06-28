"""뉴스 분류 — 출처유형 · 업무카테고리 · 긴급판정 · QA 템플릿 (결정론적, LLM 비용 0).

크롤링/저장을 깨지 않는 추가 전용 모듈. 같은 입력 → 항상 같은 결과.
"""
from __future__ import annotations

from typing import List, Tuple
from urllib.parse import urlparse

from data_layer.news import tagging

CATEGORIES = [
    "규제·정책", "회수·판매중지", "안전성·품질", "점검·행정처분",
    "공급중단·부족", "유통·콜드체인", "수입·통관", "백신·NIP", "기타",
]

# ── 출처 유형 ──────────────────────────────────────────────
_MEDIA_KEYS = {"dailypharm", "yakup", "klnews", "medipharm", "hitnews", "medipana"}
_MEDIA_LABELS = {"데일리팜", "약업신문", "물류신문", "메디팜뉴스", "메디파나뉴스", "히트뉴스"}
_OFFICIAL_NAMES = {"식품의약품안전처", "식약처", "의약품안전나라", "국가법령정보센터",
                   "질병관리청", "보건복지부", "관세청"}
_OFFICIAL_DOMAINS = {"mfds.go.kr", "nedrug.mfds.go.kr", "law.go.kr", "kdca.go.kr",
                     "mohw.go.kr", "customs.go.kr", "korea.kr", "assembly.go.kr"}
_ASSOC_NAMES = {"한국의약품유통협회", "한국제약바이오협회", "한국의약품수출입협회"}
_ASSOC_DOMAINS = {"kpta.or.kr", "kpbma.or.kr", "kpea.or.kr"}


def domain_of(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def classify_source_type(source: str, source_label: str, url: str) -> str:
    """출처(발행처) 기준 유형 — 내용이 아니라 매체로 판정."""
    dom = domain_of(url)
    name = (source_label or "").strip()
    if (source or "") in _MEDIA_KEYS or name in _MEDIA_LABELS:
        return "media"
    if name in _OFFICIAL_NAMES or any(d in dom for d in _OFFICIAL_DOMAINS):
        return "official"
    if name in _ASSOC_NAMES or any(d in dom for d in _ASSOC_DOMAINS):
        return "association"
    return "unknown"


# ── 업무 카테고리 (우선순위 순서 = 대표 카테고리 결정) ──────────
_CAT_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("회수·판매중지", ["회수", "리콜", "판매중지", "판매 중지", "출하중지", "출하 정지",
                  "사용중지", "폐기명령", "회수명령", "회수 명령"]),
    ("공급중단·부족", ["공급중단", "공급 중단", "품절", "수급불안", "수급 불안",
                  "공급부족", "공급 부족", "생산중단", "생산 중단", "재고 부족"]),
    ("점검·행정처분", ["행정처분", "과징금", "허가취소", "업무정지", "실태조사",
                  "적발", "위반", "처분", "점검", "감사"]),
    ("안전성·품질", ["안전성", "부작용", "이상사례", "품질부적합", "부적합",
                 "변질", "오염", "무균", "불순물", "발암", "불검출", "회수 검사"]),
    ("수입·통관", ["수입", "통관", "관세", "통관보류", "해외제조소", "수입중단"]),
    ("백신·NIP", ["백신", "NIP", "국가예방접종", "예방접종", "독감백신", "생물학적제제"]),
    ("유통·콜드체인", ["콜드체인", "온도일탈", "온도 일탈", "냉장", "냉동", "수송",
                  "보관", "물류", "로거", "GDP", "KGSP", "3PL", "유통품질"]),
    ("규제·정책", ["개정", "제정", "고시", "행정예고", "입법예고", "법령", "규칙",
                "시행", "가이드라인", "정책", "약사법", "제도", "의견수렴"]),
]


def classify_category(text: str) -> Tuple[str, List[str]]:
    """대표 카테고리 1개 + 보조 태그(매칭된 전체). 우선순위 순서로 대표 결정."""
    matched = [cat for cat, kws in _CAT_KEYWORDS if any(k in text for k in kws)]
    rep = matched[0] if matched else "기타"
    return rep, matched


# ── 긴급 판정 ──────────────────────────────────────────────
_URGENT_KEYWORDS = [
    "회수", "리콜", "회수명령", "판매중지", "판매 중지", "출하중지", "출하 정지",
    "사용중지", "폐기명령", "안전성 속보", "공급중단", "생산중단", "수입중단",
    "통관중단", "통관보류", "품절", "수급불안", "긴급 점검", "긴급점검",
    "리콜명령", "즉시 회수",
]


def assess_urgency(text: str, source_type: str) -> Tuple[bool, str, bool]:
    """(is_urgent, verification_status, urgent_candidate).

    - 공식자료 + 긴급키워드 → 확정(is_urgent=True, official_confirmed)
    - 언론기사 등 + 긴급키워드 → 후보(is_urgent=False, checking)  ※'확인 중'
    - 단순 '긴급/비상/논란'만으로는 후보로 잡지 않음(키워드 목록에 미포함)
    """
    cand = any(k in (text or "") for k in _URGENT_KEYWORDS)
    if not cand:
        return False, "", False
    if source_type == "official":
        return True, "official_confirmed", True
    return False, "checking", True


# ── QA 템플릿 (대표 카테고리 기반, 결정론적) ──────────────────
_QA_TEMPLATES = {
    "회수·판매중지": ("유통 중 제품의 즉시 격리·회수 대상 여부 확인 필요",
                "해당 제품 재고 격리 · 출고 중지 · 거래처 통보 · 반품/회수 진행",
                "입출고 · 재고관리 · 거래처 통보"),
    "공급중단·부족": ("공급 차질에 따른 재고·납기 영향 점검",
                "재고 현황 점검 · 대체품 확보 · 거래처 사전 안내",
                "수급관리 · 구매 · 거래처 대응"),
    "점검·행정처분": ("행정처분/점검 대비 기록·절차 적정성 확인",
                "관련 SOP·기록 점검 · 시정조치 준비",
                "품질보증 · 인허가 · 규정관리"),
    "안전성·품질": ("안전성·품질 이슈의 자사 취급 제품 영향 확인",
               "해당 로트 보관·시험 기록 확인 · 품질평가",
               "품질관리 · 시험 · 보관"),
    "수입·통관": ("수입/통관 차질에 따른 입고 영향 점검",
              "통관 일정·서류 점검 · 대체 통관 검토",
              "수입 · 통관 · 물류"),
    "백신·NIP": ("백신 보관·수송 기준 준수 여부 확인",
             "백신 보관 온도·기록 점검 · 수송 적격성 확인",
             "콜드체인 · 보관 · 수송"),
    "유통·콜드체인": ("콜드체인 유통 기준 영향 확인",
               "온도 모니터링·일탈 기록 점검 · 수송용기 적격성 확인",
               "보관 · 수송 · 온도관리"),
    "규제·정책": ("규제 개정의 자사 업무 영향 검토",
              "개정 내용 확인 · 영향 SOP 식별 · 시행일 관리",
              "규정관리 · 품질보증"),
    "기타": ("QA 관련성 확인 필요", "내용 확인", "—"),
}


def qa_template(rep_category: str) -> Tuple[str, str, str]:
    """(qa_impact, action_items, affected_work)."""
    return _QA_TEMPLATES.get(rep_category, _QA_TEMPLATES["기타"])


# ── QA 관련성 점수 (기존 tagging 점수 재사용) ──────────────────
_EXCLUDE = ["인사", "부음", "동정", "수상", "채용", "공시", "주가", "코스닥",
            "상장", "간담회", "창립", "기념", "실적발표", "신규 임원"]


def qa_relevance_score(text: str) -> int:
    return tagging.score_text(text or "")


def is_qa_relevant(text: str, rep_category: str) -> bool:
    """QA 관련성 통과 여부(보수적). 명백한 비관련(인사·주가·채용 등)만 제외."""
    sc = tagging.score_text(text or "")
    if rep_category != "기타" and sc > 0:
        return True
    if sc >= 3:
        return True
    excl = sum(1 for k in _EXCLUDE if k in (text or ""))
    if excl >= 1 and sc <= 0:
        return False
    return True
