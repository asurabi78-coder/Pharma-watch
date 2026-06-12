"""규제 레이더 — 법제처(law.go.kr) 자동 수집 → 필터 → 캘린더 유입.

목적: "시드 몇 건"이 아니라, 약사법 계열 사람 의약품 규제 전체의 제·개정을
매일 자동으로 감시한다. 동물용 의약품·의료기기·화장품·식품 등은 제외.

흐름:
  1) WATCH_LAWS(법령) + WATCH_ADMRULES(행정규칙 키워드)를 law.go.kr 에서 검색
  2) 제목 필터: 의약품 관련만 포함, 제외어(동물용·의료기기 등) 차단
  3) 시행일이 감시 윈도우(과거 60일 ~ 미래 18개월) 안인 항목만
     → 최근 개정됐거나 시행 예정인 규제만 캘린더에 올라간다
  4) calendar_repo 에 upsert (이미 있으면 상태·메모 보존)

네트워크 실패·키 부재 시 조용히 0건 — 앱은 항상 동작한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, date as date_cls
from pathlib import Path
from typing import Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_META_PATH = _PROJECT_ROOT / "db" / "radar_meta.json"

# ---- 감시 대상 (사람 의약품 계열) -------------------------------------
WATCH_LAWS = [
    "약사법",
    "마약류 관리에 관한 법률",
    "의약품 등의 안전에 관한 규칙",
    "생물학적 제제 등의 제조·판매 관리 규칙",
    "약사법 시행규칙",
]
WATCH_ADMRULES = [
    "의약품 유통품질 관리기준",
    "의약품 제조 및 품질관리",
    "생물학적 제제 보관 및 수송",
    "마약류 저장시설",
    "의약품 회수",
    "의약품 표시",
]

# 포함: 제목에 이 중 하나는 있어야 한다 (사람 의약품 관련성)
_INCLUDE = ["의약품", "약사", "마약", "생물학적", "백신", "의약외품", "제약", "한약"]
# 제외: 동물용·의료기기 등 (약사법 계열이라도 비대상)
_EXCLUDE = ["동물용", "동물의약품", "수의", "의료기기", "화장품", "위생용품",
            "건강기능식품", "농약", "사료", "축산"]

# 시행일 감시 윈도우
_PAST_DAYS = 60          # 최근 60일 내 시행(개정)된 것 — 이미 발효된 변경도 알림
_FUTURE_DAYS = 545       # 18개월 내 시행 예정


def title_passes(title: str) -> bool:
    """제목 필터 — 사람 의약품 관련만 통과."""
    t = (title or "").replace("식품의약품안전처", "")  # 기관명 오탐 방지
    if not t.strip():
        return False
    if any(x in t for x in _EXCLUDE):
        return False
    return any(x in t for x in _INCLUDE)


def _in_window(date_str: str, today: Optional[date_cls] = None) -> bool:
    if not date_str or len(date_str) != 10:
        return False
    today = today or datetime.now().date()
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    return (today - timedelta(days=_PAST_DAYS)) <= d \
        <= (today + timedelta(days=_FUTURE_DAYS))


def _enforced_date(record) -> str:
    """SourceRecord.summary 의 '시행 YYYY-MM-DD' 추출 (raw 우선)."""
    raw = getattr(record, "raw", None) or {}
    for key in ("시행일자",):
        v = str(raw.get(key, "") or "").strip()
        if len(v) == 8 and v.isdigit():
            return f"{v[:4]}-{v[4:6]}-{v[6:8]}"
        if len(v) == 10:
            return v
    # summary 폴백: "공포 ... · 시행 YYYY-MM-DD · ..."
    summary = getattr(record, "summary", "") or ""
    for part in summary.split("·"):
        part = part.strip()
        if part.startswith("시행 "):
            return part.replace("시행 ", "").strip()
    return ""


# ---------------------------------------------------------------- 수집

def crawl(*, today: Optional[date_cls] = None, connector=None,
          db_path: Optional[Path] = None) -> Dict:
    """수집 1회 실행 → 캘린더 upsert. 결과 요약 dict 반환.

    connector 주입 가능 (테스트용). 기본은 LawGoKrConnector.
    """
    from data_layer import calendar_repo as cal

    today = today or datetime.now().date()
    if connector is None:
        try:
            from data_layer.connectors.law.law_go_kr import LawGoKrConnector
            connector = LawGoKrConnector()
        except Exception:
            return {"ok": False, "reason": "connector 로드 실패", "added": 0}

    if not connector.is_available():
        return {"ok": False, "reason": "LAW_GO_KR_API_KEY 미설정", "added": 0}

    found: List = []
    errors = 0
    for q in WATCH_LAWS:
        try:
            found += [("law", r) for r in connector.search_laws(q, max_results=10)]
        except Exception:
            errors += 1
    for q in WATCH_ADMRULES:
        try:
            found += [("admrul", r)
                      for r in connector.search_admrules(q, max_results=10)]
        except Exception:
            errors += 1

    seen: set = set()
    added = 0
    matched = 0
    for kind, rec in found:
        rid = f"{kind}-{rec.id}"
        if rid in seen:
            continue
        seen.add(rid)
        if not title_passes(rec.title):
            continue
        d = _enforced_date(rec)
        if not _in_window(d, today):
            continue
        matched += 1
        is_law = (kind == "law")
        before = cal._count(db_path)
        cal.upsert_auto(
            d,
            ("법령 시행 · " if is_law else "고시·행정규칙 시행 · ") + rec.title,
            track="external",
            kind="law" if is_law else "kfda",
            impact="high" if is_law else "mid",
            source="radar",
            ext_key=rid,
            tags=list(getattr(rec, "tags", []) or []),
            url=getattr(rec, "url", "") or "",
            db_path=db_path,
        )
        added += cal._count(db_path) - before

    result = {
        "ok": True, "checked": len(found), "matched": matched,
        "added": added, "errors": errors,
        "at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _save_meta(result)
    return result


# ---------------------------------------------------------------- 메타/다이제스트

def _save_meta(result: Dict) -> None:
    try:
        _META_PATH.parent.mkdir(parents=True, exist_ok=True)
        _META_PATH.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def last_crawl() -> Optional[Dict]:
    try:
        return json.loads(_META_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def digest_lines(*, hours: int = 36, limit: int = 8,
                 db_path: Optional[Path] = None) -> List[str]:
    """최근 수집에서 새로 감지된 제·개정 → 다이제스트 줄. 없으면 빈 리스트."""
    try:
        from data_layer import calendar_repo as cal
        import sqlite3
        p = db_path or cal._DEFAULT_DB_PATH
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(p)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT date, title, url FROM cal_events "
            "WHERE source = 'radar' AND created_at >= ? "
            "ORDER BY date LIMIT ?", (cutoff, int(limit)),
        ).fetchall()
        conn.close()
    except Exception:
        return []
    if not rows:
        return []
    lines = [f"## 🛰 새로 감지된 제·개정 — {len(rows)}건 (법제처 자동 수집)"]
    for r in rows:
        link = f" [원문]({r['url']})" if r["url"] else ""
        lines.append(f"- **{r['date']}** 시행 — {r['title']}{link}")
    lines.append("- 상세·SOP 영향은 앱의 **규제 캘린더**에서 확인하세요.")
    return lines
