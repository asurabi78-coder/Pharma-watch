"""메디팜뉴스 (medipharmnews.com) 커넥터 — Phase B.

전략:
- RSS 사용 (HTML 파싱보다 안정적, 엔디소프트 CMS — klnews·yakup 과 동일 계열)
- 섹션별 RSS 분리 수집 (sc_section_code = 피드 번호):
    · 정책:       /rss/S1N1.xml
    · 의료/병원:  /rss/S1N2.xml
    · 약사/약국:  /rss/S1N3.xml
    · 제약/바이오: /rss/S1N4.xml
    · 라이프:     /rss/S1N5.xml
- 섹션 피드가 비활성/오류일 경우 전체기사 피드(/rss/allArticle.xml) 로 폴백.
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

_BASE_URL = "https://www.medipharmnews.com"
_FEEDS = [
    (f"{_BASE_URL}/rss/S1N1.xml", "정책"),
    (f"{_BASE_URL}/rss/S1N2.xml", "의료·병원"),
    (f"{_BASE_URL}/rss/S1N3.xml", "약사·약국"),
    (f"{_BASE_URL}/rss/S1N4.xml", "제약·바이오"),
    (f"{_BASE_URL}/rss/S1N5.xml", "라이프"),
]
_FALLBACK_FEED = (f"{_BASE_URL}/rss/allArticle.xml", "전체")
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
            id=f"medipharm:{article_id}",
            title=title,
            url=link,
            source="medipharm",
            source_label="메디팜뉴스",
            category=category,
            summary=desc,
            published_at=pub,
            fetched_at=now,
        ))
    return items


def fetch(limit: int = 20) -> List[NewsItem]:
    """메디팜뉴스 섹션별 RSS 수집, 중복 제거 후 최신순 정렬.

    섹션 피드가 하나도 안 잡히면 전체기사 피드로 폴백한다.
    """
    seen: set = set()
    out: List[NewsItem] = []
    for url, cat in _FEEDS:
        xml = _fetch_xml(url)
        for it in _parse_feed(xml, cat):
            if it.id in seen:
                continue
            seen.add(it.id)
            out.append(it)

    # 섹션 피드가 전부 비었으면 전체기사 피드로 폴백
    if not out:
        url, cat = _FALLBACK_FEED
        xml = _fetch_xml(url)
        for it in _parse_feed(xml, cat):
            if it.id in seen:
                continue
            seen.add(it.id)
            out.append(it)

    out.sort(key=lambda x: x.published_at or x.fetched_at or "", reverse=True)
    return out[:limit]
