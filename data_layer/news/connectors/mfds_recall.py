"""식품의약품안전처 의약품 회수·판매중지 정보 — 공식 출처 (data.go.kr OpenAPI).

활성화: .env 에 MFDS_RECALL_API_KEY (data.go.kr serviceKey) 설정 시 동작.
미설정/오류 시 [] 반환 → 다른 수집을 깨지 않음. 출처유형은 자동 official.
데이터셋: data.go.kr 15059114 (의약품 회수·판매중지 정보).
※ 응답 태그명은 명세에 따라 다를 수 있어 다중 폴백으로 방어. 키 적용 후 1회 점검 권장.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import List
from xml.etree import ElementTree as ET

import requests

from data_layer.news.models import NewsItem

_KST = timezone(timedelta(hours=9))
_BASE = os.getenv(
    "MFDS_RECALL_API_URL",
    "http://apis.data.go.kr/1471000/DrugRecallSaleStopInfoService01/getDrugRecallSaleStopInfo",
)
_DETAIL = "https://nedrug.mfds.go.kr/pbp/CCBAB01"
_TIMEOUT = 15.0


def _key() -> str:
    return (os.getenv("MFDS_RECALL_API_KEY") or os.getenv("DATA_GO_KR_KEY") or "").strip()


def _first(it, tags):
    for t in tags:
        e = it.find(t)
        if e is not None and e.text and e.text.strip():
            return e.text.strip()
    return ""


def fetch(limit: int = 20) -> List[NewsItem]:
    key = _key()
    if not key:
        return []
    try:
        resp = requests.get(
            _BASE,
            params={"serviceKey": key, "type": "xml", "pageNo": 1,
                    "numOfRows": min(int(limit), 100)},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception:
        return []

    now_iso = datetime.now(_KST).replace(tzinfo=None).isoformat(timespec="seconds")
    items: List[NewsItem] = []
    for it in root.iter("item"):
        prod = _first(it, ["PRDUCT", "PRDLST_NM", "itemName", "ITEM_NAME"])
        comp = _first(it, ["ENTRPS", "BSSH_NM", "ENTP_NAME"])
        reason = _first(it, ["DSUSE_REASON", "RECALL_REASON", "reason"])
        date = _first(it, ["DSUSE_BSE_DE", "RECALL_DE", "recallDate", "DSUSE_DT"])
        if not prod:
            continue
        title = f"{prod} 회수·판매중지" + (f" — {reason}" if reason else "")
        ts = ""
        d = (date or "").replace(".", "-").replace("/", "-")
        if len(d) == 8 and d.isdigit():
            d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        if len(d) == 10:
            ts = f"{d}T00:00:00"
        uid = "mfdsrecall_" + hashlib.sha1((prod + comp + (date or "")).encode("utf-8")).hexdigest()[:14]
        items.append(NewsItem(
            id=uid, title=title, url=_DETAIL, source="mfds_recall",
            source_label="식품의약품안전처", category="회수·판매중지",
            summary=(f"{comp} · {reason}").strip(" ·"),
            published_at=ts, fetched_at=now_iso,
        ))
        if len(items) >= int(limit):
            break
    return items
