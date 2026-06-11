"""약업신문 (yakup.com) 커넥터 — Phase B.

전략:
- 메인 페이지 + 유통 카테고리(cat=12&cat2=125) 별도 fetch
- 'nid={숫자}' 패턴으로 기사 ID 추출
- 카테고리 라벨이 a 태그 텍스트에 포함된 경우 추출
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from data_layer.news.models import NewsItem
from data_layer.news.dateparse import anchor_date


_BASE_URL = "https://www.yakup.com"
_MAIN_URL = f"{_BASE_URL}/"
_DISTRIBUTION_URL = f"{_BASE_URL}/news/index.html?cat=12&cat2=125"  # 유통
_INDUSTRY_URL = f"{_BASE_URL}/news/index.html?cat=12"  # 산업 전체
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_NID_PATTERN = re.compile(r"[?&]nid=(\d+)")
_CATEGORY_PREFIX_PATTERN = re.compile(
    r"^(정책|산업\s*/\s*[^\s]+|산업|병원·의료|약사·약학|글로벌|웰에이징|특집|인터뷰|영상뉴스|PEOPLE|부음|인사)\s+"
)
_REQUEST_TIMEOUT = 15.0


def _fetch_html(url: str) -> str:
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


def _split_category_and_title(raw: str) -> tuple[str, str]:
    """'산업 / 유통 RNA가 쏘아 올린 꿈…' → ('산업 / 유통', 'RNA가 쏘아 올린 꿈…')"""
    raw = re.sub(r"\s+", " ", raw).strip()
    m = _CATEGORY_PREFIX_PATTERN.match(raw)
    if m:
        cat = m.group(1).strip()
        title = raw[m.end():].strip()
        return cat, title
    return "", raw


def _extract_items(html: str) -> List[NewsItem]:
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now().isoformat(timespec="seconds")
    items: List[NewsItem] = []
    seen_ids: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _NID_PATTERN.search(href)
        if not m:
            continue
        article_id = m.group(1)

        if "mode=view" not in href and "?mode=view" not in href:
            continue

        raw_text = a.get_text(" ", strip=True)
        raw_text = re.sub(r"[\|\-]{2,}", " ", raw_text)
        raw_text = re.sub(r"\s+", " ", raw_text).strip()

        if not raw_text or len(raw_text) < 10:
            continue
        if len(raw_text) > 250:
            raw_text = raw_text.split("\n")[0].strip()

        category, title = _split_category_and_title(raw_text)
        if len(title) > 120:
            title = title.split(" ")
            short = []
            for w in title:
                short.append(w)
                if sum(len(s) + 1 for s in short) > 80:
                    break
            title = " ".join(short).rstrip("…") + "…"

        if not title or len(title) < 8:
            continue

        if article_id in seen_ids:
            continue
        seen_ids.add(article_id)

        url_full = urljoin(_BASE_URL, href)
        item_id = f"yakup:{article_id}"
        published = anchor_date(a)

        items.append(NewsItem(
            id=item_id,
            title=title,
            url=url_full,
            source="yakup",
            source_label="약업신문",
            category=category,
            published_at=published,
            fetched_at=now,
        ))
    return items


def fetch(limit: int = 15) -> List[NewsItem]:
    """약업신문 최신 뉴스 limit 건. 메인 + 유통 + 산업 합치고 중복 제거."""
    seen: set[str] = set()
    out: List[NewsItem] = []
    for url in (_MAIN_URL, _DISTRIBUTION_URL, _INDUSTRY_URL):
        html = _fetch_html(url)
        for it in _extract_items(html):
            if it.id in seen:
                continue
            seen.add(it.id)
            out.append(it)
            if len(out) >= limit:
                return out
    return out
