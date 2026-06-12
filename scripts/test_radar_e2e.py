"""규제 레이더 E2E 테스트 — 모의 커넥터 사용 (네트워크·실DB 불필요).

실행: python -m scripts.test_radar_e2e
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_layer import calendar_repo as cal
from data_layer.connectors.base import SourceRecord, SourceTier
from data_layer.regulatory import radar

FAILS = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def _rec(rid, title, enforced_yyyymmdd, kind="법률"):
    return SourceRecord(
        id=rid, title=title, tier=SourceTier.LAW, source="law_go_kr",
        url=f"https://www.law.go.kr/법령/{title}",
        published_at="", content="", summary=f"시행 {enforced_yyyymmdd}",
        tags=[kind], confidence="verified",
        raw={"시행일자": enforced_yyyymmdd.replace("-", "")},
    )


class MockConnector:
    """약사법 개정(미래 시행) + 동물용(제외 대상) + 옛날 개정(윈도우 밖)."""
    def __init__(self, today):
        future = (today + timedelta(days=30)).strftime("%Y-%m-%d")
        recent = (today - timedelta(days=10)).strftime("%Y-%m-%d")
        old = (today - timedelta(days=400)).strftime("%Y-%m-%d")
        self._laws = [
            _rec("L1", "약사법", future),
            _rec("L2", "동물용 의약품 등 취급규칙", future),       # 제외돼야 함
            _rec("L3", "의료기기법", future),                      # 제외돼야 함
            _rec("L4", "마약류 관리에 관한 법률 시행규칙", recent),
            _rec("L5", "약사법 시행령", old),                      # 윈도우 밖
        ]
        self._adm = [
            _rec("A1", "의약품 유통품질 관리기준", future, kind="고시"),
            _rec("A2", "식품등의 표시기준", future, kind="고시"),   # 제외돼야 함
        ]

    def is_available(self):
        return True

    def search_laws(self, query, max_results=10):
        return self._laws

    def search_admrules(self, query, max_results=10):
        return self._adm


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    cal._DEFAULT_DB_PATH = tmp / "cal.db"
    radar._META_PATH = tmp / "radar_meta.json"

    today = date.today()

    # 1) 제목 필터 단위 검증
    check("포함: 약사법", radar.title_passes("약사법"))
    check("포함: KGSP 고시", radar.title_passes("의약품 유통품질 관리기준"))
    check("제외: 동물용", not radar.title_passes("동물용 의약품 등 취급규칙"))
    check("제외: 의료기기", not radar.title_passes("의료기기법"))
    check("제외: 화장품", not radar.title_passes("화장품 안전기준 등에 관한 규정"))
    check("제외: 식품(기관명 오탐 방지)",
          not radar.title_passes("식품등의 표시기준"))
    check("포함: 식약처 의약품 고시",
          radar.title_passes("식품의약품안전처 의약품 회수 규정"))

    # 2) 수집 → 캘린더 유입 (모의 커넥터: 법령 5 × 5쿼리 + 행정규칙 2 × 6쿼리)
    res = radar.crawl(today=today, connector=MockConnector(today))
    check("수집 성공", res["ok"], str(res))
    # 통과해야 하는 것: L1(미래), L4(최근), A1(미래) = 3건
    check("필터+윈도우 후 3건 유입", res["added"] == 3,
          f"matched={res['matched']} added={res['added']}")

    evs = cal.list_range("2000-01-01", "2999-12-31")
    titles = [e.title for e in evs]
    check("약사법 포함", any("약사법" in t and "시행령" not in t for t in titles))
    check("동물용·의료기기 미포함",
          not any("동물용" in t or "의료기기" in t for t in titles))
    check("윈도우 밖(400일 전) 미포함", not any("시행령" in t for t in titles))
    check("원문 URL 저장", all(e.url.startswith("https://www.law.go.kr") for e in evs))
    check("임팩트: 법령=high / 고시=mid",
          any(e.impact == "high" for e in evs) and any(e.impact == "mid" for e in evs))

    # 3) 재수집 — 중복 없음 + 사용자 메모 보존
    cal.update_event(evs[0].id, status="action", memo="법무 검토")
    res2 = radar.crawl(today=today, connector=MockConnector(today))
    check("재수집 중복 없음", res2["added"] == 0, f"+{res2['added']}")
    again = cal.list_range("2000-01-01", "2999-12-31")
    check("재수집 후 메모 보존",
          any(e.memo == "법무 검토" and e.status == "action" for e in again))

    # 4) 다이제스트 줄 생성
    lines = radar.digest_lines(db_path=cal._DEFAULT_DB_PATH)
    check("다이제스트 섹션 생성", bool(lines) and "새로 감지된 제·개정" in lines[0],
          lines[0] if lines else "(빈)")
    for l in lines[:4]:
        print("   |", l)

    # 5) 메타 저장
    meta = radar.last_crawl()
    check("수집 메타 저장", meta is not None and meta.get("ok") is True)

    print()
    if FAILS:
        print(f"❌ {len(FAILS)} FAIL: {FAILS}")
        return 1
    print("✅ ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
