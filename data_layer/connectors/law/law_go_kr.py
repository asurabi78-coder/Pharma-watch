"""국가법령정보센터(law.go.kr) connector.

- .env 의 LAW_GO_KR_API_KEY 자동 로드
- search_laws(query) — 법령 검색 (target=law, tier=LAW)
- search_admrules(query) — 행정규칙 검색 (target=admrul, tier=NOTICE)
- get_law_content(law_id) — 법령 본문 조회 (lawService.do)
- 네트워크/파싱/키 부재 모두 빈 리스트 fallback

활용신청: https://open.law.go.kr/LSO/openApi/cuAskList.do
주의: API 키는 "발급 ID" 형태 (이메일 prefix). 일반적 API key 와 다르다.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from data_layer.connectors.base import Connector, SourceRecord, SourceTier

# 모듈 import 시 .env 1회 로드 (override=False 로 테스트 친화).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=False)

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.law.go.kr/DRF/lawSearch.do"
_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"
_DEFAULT_TIMEOUT_SEC = 10


def _fmt_date(yyyymmdd: str) -> str:
    """law.go.kr 의 YYYYMMDD 문자열을 YYYY-MM-DD 로. 형식 불일치 시 원본 반환."""
    if not yyyymmdd:
        return ""
    s = str(yyyymmdd).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _human_law_url(kind: str, title: str) -> str:
    """사람이 여는 law.go.kr permalink. DRF API 엔드포인트(OC 키 노출/본문 미신청 위험)
    대신 사용한다. kind="법령" / "행정규칙". 제목 비면 메인으로 폴백."""
    title = (title or "").strip()
    if not title:
        return "https://www.law.go.kr"
    return f"https://www.law.go.kr/{quote(kind)}/{quote(title)}"


def _sanitize_for_log(text: str) -> str:
    """로그·예외 메시지에서 OC(키) 파라미터 값을 마스킹."""
    if not text:
        return text
    import re
    return re.sub(r"(OC=)[^\s&]+", r"\1***REDACTED***", str(text))


class LawGoKrConnector(Connector):
    """법령 검색 (target=law) + 행정규칙 검색 (target=admrul) + 본문 조회."""

    name = "law_go_kr"
    tier = SourceTier.LAW

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = _DEFAULT_TIMEOUT_SEC,
        base_url: str = _BASE_URL,
        service_url: str = _SERVICE_URL,
    ) -> None:
        self._explicit_key = api_key
        self._timeout = timeout
        self._base_url = base_url
        self._service_url = service_url

    def _resolve_key(self) -> str:
        if self._explicit_key:
            return self._explicit_key
        return os.getenv("LAW_GO_KR_API_KEY", "") or ""

    def is_available(self) -> bool:
        return bool(self._resolve_key())

    # ------------------------------------------------------------------
    # search_laws (target=law, tier=LAW)
    # ------------------------------------------------------------------
    def search_laws(self, query: str, max_results: int = 10) -> List[SourceRecord]:
        """약사법·의약품 관련 법령 등 키워드 검색. 실패 시 빈 리스트."""
        key = self._resolve_key()
        if not key:
            logger.debug("law_go_kr: API key not configured — returning empty.")
            return []
        if not query or not query.strip():
            return []

        try:
            resp = requests.get(
                self._base_url,
                params={
                    "OC": key,
                    "target": "law",
                    "type": "JSON",
                    "query": query.strip(),
                    "display": max(1, min(int(max_results or 10), 100)),
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "law_go_kr search_laws failed (%s): %s",
                type(exc).__name__, _sanitize_for_log(str(exc)),
            )
            return []

        return self._parse_law_search(data, max_results=max_results)

    # ------------------------------------------------------------------
    # search_admrules (target=admrul, tier=NOTICE)
    # ------------------------------------------------------------------
    def search_admrules(self, query: str, max_results: int = 10) -> List[SourceRecord]:
        """행정규칙(고시·훈령·예규) 검색 — KGSP / 식약처 고시 등. 실패 시 빈 리스트."""
        key = self._resolve_key()
        if not key:
            logger.debug("law_go_kr: API key not configured — returning empty.")
            return []
        if not query or not query.strip():
            return []

        try:
            resp = requests.get(
                self._base_url,
                params={
                    "OC": key,
                    "target": "admrul",
                    "type": "JSON",
                    "query": query.strip(),
                    "display": max(1, min(int(max_results or 10), 100)),
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "law_go_kr search_admrules failed (%s): %s",
                type(exc).__name__, _sanitize_for_log(str(exc)),
            )
            return []

        return self._parse_admrul_search(data, max_results=max_results)

    # ------------------------------------------------------------------
    # get_law_content (lawService.do, 본문 조회)
    # ------------------------------------------------------------------
    def get_law_content(
        self,
        law_id: str,
        *,
        id_type: str = "MST",
    ) -> Optional[SourceRecord]:
        """단일 법령 본문 조회. 실패 시 None."""
        key = self._resolve_key()
        if not key:
            logger.debug("law_go_kr: API key not configured — returning None.")
            return None
        if not law_id or not str(law_id).strip():
            return None
        if id_type not in {"MST", "ID"}:
            raise ValueError(f"id_type must be 'MST' or 'ID', got {id_type!r}")

        try:
            resp = requests.get(
                self._service_url,
                params={
                    "OC": key,
                    "target": "law",
                    "type": "JSON",
                    id_type: str(law_id).strip(),
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning(
                "law_go_kr get_law_content failed (%s): %s",
                type(exc).__name__, _sanitize_for_log(str(exc)),
            )
            return None

        return self._parse_law_content(data, requested_id=law_id)

    # ------------------------------------------------------------------
    # Connector ABC — fetch wrapper (target 분기)
    # ------------------------------------------------------------------
    def fetch(self, **params) -> List[SourceRecord]:
        """target 으로 분기. 기본은 search_laws."""
        target = params.get("target", "law")
        if target == "admrul":
            return self.search_admrules(
                query=params.get("query", ""),
                max_results=params.get("max_results", 10),
            )
        if target == "law_content":
            law_id = params.get("law_id", "")
            if not law_id:
                return []
            rec = self.get_law_content(law_id, id_type=params.get("id_type", "MST"))
            return [rec] if rec else []
        return self.search_laws(
            query=params.get("query", ""),
            max_results=params.get("max_results", 10),
        )

    # ------------------------------------------------------------------
    # 파싱 — 응답 스키마 변경에 견디도록 defensive 하게.
    # ------------------------------------------------------------------
    def _parse_law_search(self, data: dict, max_results: int) -> List[SourceRecord]:
        try:
            payload = data.get("LawSearch", {})
        except AttributeError:
            return []
        if not isinstance(payload, dict):
            return []

        laws = payload.get("law", [])
        if isinstance(laws, dict):
            laws = [laws]
        if not isinstance(laws, list):
            return []

        records: List[SourceRecord] = []
        for item in laws[: max(1, int(max_results or 10))]:
            if not isinstance(item, dict):
                continue
            title = (item.get("법령명한글") or "").strip()
            if not title:
                continue
            # 표시용 링크는 사람용 permalink (DRF API 주소는 raw 에 보존).
            url = _human_law_url("법령", title)
            promulgated = _fmt_date(item.get("공포일자", ""))
            enforced = _fmt_date(item.get("시행일자", ""))
            ministry = (item.get("소관부처명") or "").strip()
            kind = (item.get("법령구분명") or "").strip()

            summary_parts = []
            if promulgated:
                summary_parts.append(f"공포 {promulgated}")
            if enforced:
                summary_parts.append(f"시행 {enforced}")
            if ministry:
                summary_parts.append(f"소관 {ministry}")

            records.append(
                SourceRecord(
                    id=str(item.get("법령일련번호") or item.get("법령ID") or title),
                    title=title,
                    tier=SourceTier.LAW,
                    source="law_go_kr",
                    url=url,
                    published_at=promulgated,
                    content="",
                    summary=" · ".join(summary_parts),
                    tags=[t for t in [kind] if t],
                    confidence="verified",
                    raw=item,
                )
            )
        return records

    def _parse_admrul_search(self, data: dict, max_results: int) -> List[SourceRecord]:
        """행정규칙 검색 결과 파싱 — tier=NOTICE."""
        try:
            payload = data.get("AdmRulSearch", {})
        except AttributeError:
            return []
        if not isinstance(payload, dict):
            return []

        items = payload.get("admrul", [])
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            return []

        records: List[SourceRecord] = []
        for item in items[: max(1, int(max_results or 10))]:
            if not isinstance(item, dict):
                continue
            title = (item.get("행정규칙명") or "").strip()
            if not title:
                continue
            # 표시용 링크는 사람용 permalink (DRF API 주소는 raw 에 보존).
            url = _human_law_url("행정규칙", title)
            issued = _fmt_date(item.get("발령일자", ""))
            enforced = _fmt_date(item.get("시행일자", ""))
            agency = (item.get("발령기관명") or "").strip()
            kind = (item.get("행정규칙종류") or "").strip()

            summary_parts = []
            if issued:
                summary_parts.append(f"발령 {issued}")
            if enforced:
                summary_parts.append(f"시행 {enforced}")
            if agency:
                summary_parts.append(f"발령기관 {agency}")

            records.append(
                SourceRecord(
                    id=str(item.get("행정규칙일련번호") or item.get("행정규칙ID") or title),
                    title=title,
                    tier=SourceTier.NOTICE,
                    source="law_go_kr",
                    url=url,
                    published_at=issued,
                    content="",
                    summary=" · ".join(summary_parts),
                    tags=[t for t in [kind] if t],
                    confidence="verified",
                    raw=item,
                )
            )
        return records

    def _parse_law_content(self, data: dict, requested_id: str) -> Optional[SourceRecord]:
        """법령 본문 응답 → SourceRecord(tier=LAW)."""
        if not isinstance(data, dict) or not data:
            return None

        payload = data.get("법령") or data.get("LawService") or data
        if not isinstance(payload, dict):
            return None

        basic = payload.get("기본정보", payload) if isinstance(payload, dict) else {}
        if not isinstance(basic, dict):
            basic = {}

        title = (basic.get("법령명_한글") or basic.get("법령명한글") or "").strip()
        if not title:
            title = (payload.get("법령명") or "").strip()
        if not title:
            return None

        promulgated = _fmt_date(basic.get("공포일자") or "")
        enforced = _fmt_date(basic.get("시행일자") or "")
        ministry = (basic.get("소관부처") or {}).get("content", "") if isinstance(basic.get("소관부처"), dict) else (basic.get("소관부처") or "")
        ministry = str(ministry).strip()

        content_lines = [f"# {title}"]
        if promulgated:
            content_lines.append(f"공포: {promulgated}")
        if enforced:
            content_lines.append(f"시행: {enforced}")
        if ministry:
            content_lines.append(f"소관: {ministry}")
        content_lines.append("")
        content_lines.append("(본문 평탄화는 다음 단계에서 정밀화. raw 필드에 원본 보존.)")

        summary_parts = []
        if promulgated:
            summary_parts.append(f"공포 {promulgated}")
        if enforced:
            summary_parts.append(f"시행 {enforced}")
        if ministry:
            summary_parts.append(f"소관 {ministry}")

        return SourceRecord(
            id=str(requested_id),
            title=title,
            tier=SourceTier.LAW,
            source="law_go_kr",
            url="",
            published_at=promulgated,
            content="\n".join(content_lines),
            summary=" · ".join(summary_parts),
            tags=[],
            confidence="verified",
            raw=payload,
        )
