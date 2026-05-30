"""데일리팜 커넥터 — Phase A.

전략:
- RSS 없이 메인 페이지 HTML 파싱
- '/user/news/{숫자}' 형식 링크 모두 추출 후 중복 제거
- 제목 = a 태그 텍스트, 너무 짧거나 빈 것은 제외
- 첫 N건만 반환

저작권 정책: 제목 + 링크만 표시. 본문 복제 금지. 출처 명시: "데일리팜"
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from data_layer.news.models import NewsItem


_BASE_URL = "https://www.dailypharm.com"
_LIST_URL = f"{_BASE_URL}/user/news?group=%EC%A2%85%ED%95%A9"  # 종합 카테고리
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_NEWS_PATH_PATTERN = re.compile(r"^/user/news/(\d+)$")
_REQUEST_TIMEOUT = 15.0


def _fetch_html(url: str) -> str:
    """HTML 페이지 가져오기. 실패 시 빈 문자열."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html"},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        return resp.text
    except Exception:
        return ""


def _extract_items(html: str) -> List[NewsItem]:
    """HTML 에서 뉴스 링크 + 제목 추출."""
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    now = datetime.now().isoformat(timespec="seconds")
    items: List[NewsItem] = []
    seen_ids: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        path = href
        if href.startswith("http"):
            if not href.startswith(_BASE_URL):
                continue
            path = href[len(_BASE_URL):]
        m = _NEWS_PATH_PATTERN.match(path)
        if not m:
            continue

        title = a.get_text(strip=True)
        title = re.sub(
            r"\s+(정책·법률|제약·바이오|약국·병원|칼럼·수첩|인물·연재|특집·기획|영상뉴스|그래픽)\s*$",
            "",
            title,
        ).strip()

        if not title or len(title) < 10:
            continue
        if len(title) > 200:
            title = title.split("\n")[0].strip()
            if len(title) < 10:
                continue

        article_id = m.group(1)
        if article_id in seen_ids:
            continue
        seen_ids.add(article_id)

        url_full = urljoin(_BASE_URL, path)
        item_id = f"dailypharm:{article_id}"

        items.append(NewsItem(
            id=item_id,
            title=title,
            url=url_full,
            source="dailypharm",
            source_label="데일리팜",
            fetched_at=now,
        ))

    return items


def fetch(limit: int = 10) -> List[NewsItem]:
    """데일리팜 최신 뉴스 limit 건 반환. 실패 시 빈 리스트."""
    html = _fetch_html(_LIST_URL) or _fetch_html(_BASE_URL)
    items = _extract_items(html)
    return items[:limit]
