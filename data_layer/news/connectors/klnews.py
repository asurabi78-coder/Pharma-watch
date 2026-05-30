"""물류신문 (klnews.co.kr) 커넥터 — Phase B.

전략:
- RSS 사용 (HTML 파싱보다 안정적)
- 카테고리별 RSS 분리 제공:
    · 3PL:    /rss/S1N22.xml
    · 콜드체인: /rss/S1N45.xml
    · SCM:    /rss/S1N38.xml
    · 물류센터: /rss/S1N8.xml
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List
from xml.etree import ElementTree as ET

import requests

from data_layer.news.models import NewsItem


_KST = timezone(timedelta(hours=9))

_BASE_URL = "https://www.klnews.co.kr"
_FEEDS = [
    (f"{_BASE_URL}/rss/S1N22.xml", "3PL"),
    (f"{_BASE_URL}/rss/S1N45.xml", "콜드체인"),
    (f"{_BASE_URL}/rss/S1N38.xml", "SCM"),
    (f"{_BASE_URL}/rss/S1N8.xml",  "물류센터"),
]
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_IDXNO_PATTERN = re.compile(r"idxno=(\d+)")
_REQUEST_TIMEOUT = 15.0


def _fetch_xml(url: str) -> str:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml, text/xml"},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        return resp.text
    except Exception:
        return ""


def _parse_pubdate(s: str) -> str:
    """RSS pubDate → KST 기준 timezone-naive ISO 문자열."""
    if not s:
        return ""
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone(_KST).replace(tzinfo=None)
        return dt.isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return ""


def _strip_html_and_cdata(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.DOTALL)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_feed(xml: str, category: str) -> List[NewsItem]:
    if not xml:
        return []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []

    now = datetime.now().isoformat(timespec="seconds")
    items: List[NewsItem] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = _strip_html_and_cdata(item.findtext("description") or "")
        pub = _parse_pubdate(item.findtext("pubDate") or "")

        if not title or not link:
            continue
        m = _IDXNO_PATTERN.search(link)
        if not m:
            continue
        article_id = m.group(1)

        if len(desc) > 150:
            desc = desc[:147].rstrip() + "…"

        items.append(NewsItem(
            id=f"klnews:{article_id}",
            title=title,
            url=link,
            source="klnews",
            source_label="물류신문",
            category=category,
            summary=desc,
            published_at=pub,
            fetched_at=now,
        ))
    return items


def fetch(limit: int = 20) -> List[NewsItem]:
    """물류신문 다중 RSS 피드 수집, 카테고리별로 묶어 중복 제거."""
    seen: set = set()
    out: List[NewsItem] = []
    for url, cat in _FEEDS:
        xml = _fetch_xml(url)
        for it in _parse_feed(xml, cat):
            if it.id in seen:
                continue
            seen.add(it.id)
            out.append(it)
    out.sort(key=lambda x: x.published_at or x.fetched_at or "", reverse=True)
    return out[:limit]
