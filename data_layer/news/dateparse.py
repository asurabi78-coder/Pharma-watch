"""뉴스 발행일 파서 — HTML 커넥터(데일리팜·약업신문)용 공용 유틸.

RSS 소스(물류신문·메디팜)는 pubDate 가 있어 그대로 쓰지만, HTML 파싱
소스는 목록에 날짜가 텍스트로만 박혀 있다. 기사 링크(anchor) 주변 컨테이너
텍스트에서 날짜 패턴을 찾아 ISO(YYYY-MM-DDТHH:MM:SS) 로 정규화한다.

원칙: 못 찾으면 빈 문자열을 반환한다(추정 금지). 미래 날짜·비현실적 과거는 버린다.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

# 2026-06-11 / 2026.06.11 / 2026/06/11 (4자리 연도)
_FULL = re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")
# 06-11 / 06.11 (연도 생략 — 올해로 보정, 미래면 작년)
_SHORT = re.compile(r"(?<!\d)(\d{1,2})[.\-/](\d{1,2})(?!\d)")
# 06월 11일
_KOR = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
# 시:분 (있으면 함께 사용)
_TIME = re.compile(r"(\d{1,2}):(\d{2})")


def _build(y: int, mo: int, d: int, hh: int = 0, mm: int = 0) -> Optional[str]:
    try:
        dt = datetime(y, mo, d, hh, mm)
    except ValueError:
        return None
    # 미래(수집시각보다 하루 이상 뒤)면 무효 — 파싱 오류로 간주
    if dt > datetime.now().replace(hour=23, minute=59):
        return None
    # 너무 과거(2018 이전)도 목록 파싱 오류로 간주
    if dt.year < 2018:
        return None
    return dt.isoformat(timespec="seconds")


def parse_date(text: str, *, now: Optional[datetime] = None) -> str:
    """텍스트에서 발행일을 찾아 ISO 문자열로. 못 찾으면 ''."""
    if not text:
        return ""
    now = now or datetime.now()

    hh = mm = 0
    tm = _TIME.search(text)
    if tm:
        h, m = int(tm.group(1)), int(tm.group(2))
        if 0 <= h < 24 and 0 <= m < 60:
            hh, mm = h, m

    m = _FULL.search(text)
    if m:
        out = _build(int(m.group(1)), int(m.group(2)), int(m.group(3)), hh, mm)
        # 4자리 연도 날짜가 있으면 그 해석만 신뢰 — 실패해도 MM-DD 로 재해석하지 않음
        return out or ""

    m = _KOR.search(text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        y = now.year
        out = _build(y, mo, d, hh, mm)
        if out is None and y > 2018:  # 미래면 작년
            out = _build(y - 1, mo, d, hh, mm)
        if out:
            return out

    m = _SHORT.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        # MM-DD 로 해석 (월 1~12 범위일 때만)
        if 1 <= a <= 12 and 1 <= b <= 31:
            y = now.year
            out = _build(y, a, b, hh, mm)
            if out is None:
                out = _build(y - 1, a, b, hh, mm)
            if out:
                return out
    return ""


def anchor_date(anchor) -> str:
    """BeautifulSoup anchor 주변 텍스트에서 날짜 추출.

    자기 자신 → 부모 순으로 올라가되, 한 컨테이너에 기사 링크(a[href])가 2개 이상이면
    목록 전체 컨테이너로 올라온 것이므로 멈춘다(형제 기사 날짜 오상속 방지).
    """
    node = anchor
    for level in range(4):
        if node is None:
            break
        # 상위로 올라간 뒤 컨테이너가 여러 기사 링크를 품으면 너무 넓어진 것 → 중단
        if level > 0:
            try:
                if len(node.find_all("a", href=True)) > 1:
                    break
            except Exception:
                pass
        try:
            txt = node.get_text(" ", strip=True)
        except Exception:
            txt = str(node)
        got = parse_date(txt)
        if got:
            return got
        node = getattr(node, "parent", None)
    return ""
