"""규제 캘린더 v2 E2E 테스트 — 임시 DB/프로필 사용 (실 데이터 미오염).

실행: python -m scripts.test_calendar_e2e
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_layer import calendar_repo as repo
from data_layer import company_profile as cp

FAILS = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    repo._DEFAULT_DB_PATH = tmp / "cal.db"
    cp._PROFILE_PATH = tmp / "profile.json"

    today = date.today()

    # 1) 프로필 저장/로드
    cp.save_profile({"company": "테스트약품", "handles": ["상온 의약품", "냉장(2~8℃)"],
                     "self_inspection_month": 11, "mapping_month": 6})
    prof = cp.load_profile()
    check("프로필 저장/로드", prof["company"] == "테스트약품"
          and "냉장(2~8℃)" in prof["handles"])

    # 2) 임팩트 스코어링
    s1 = cp.score_impact(["콜드체인", "온도"], "mid", prof)
    s2 = cp.score_impact(["마약류", "NIMS"], "high", prof)   # 마약류 미취급
    s3 = cp.score_impact(["KGSP", "보관"], "high", prof)     # 일반 — base 유지
    check("직결 규제 강조 (콜드체인→high)", s1 == "high", s1)
    check("미취급 강등 (마약류→low)", s2 == "low", s2)
    check("일반 유지 (보관→high)", s3 == "high", s3)

    # 3) 외부 규제 동기화 — 시드/플레이북 유입
    n = repo.sync_external()
    check("외부 규제 동기화", n > 0, f"{n}건 유입")
    n2 = repo.sync_external()
    check("재동기화 중복 없음", n2 == 0, f"+{n2}건")

    # 4) KGSP 의무 자동 생성 — 냉장 취급 → 수송용기/온도매핑 포함, 마약류 제외
    d = repo.ensure_duties(prof, horizon_days=365, today=today)
    check("의무 일정 생성", d > 0, f"{d}건")
    end = (today + timedelta(days=365)).strftime("%Y-%m-%d")
    duties = [e for e in repo.list_range(today.strftime("%Y-%m-%d"), end)
              if e.track == "duty"]
    kinds = {e.kind for e in duties}
    check("정기 교육 포함", "edu_monthly" in kinds, sorted(kinds))
    check("냉장 의무 포함 (수송용기·온도매핑)",
          "carrier_qual" in kinds and "temp_mapping" in kinds)
    check("마약류 의무 제외 (미취급)", "narc_check" not in kinds)
    d2 = repo.ensure_duties(prof, horizon_days=365, today=today)
    check("의무 재생성 중복 없음", d2 == 0, f"+{d2}건")

    # 5) 사내 일정 등록 + 상태/메모 + 삭제
    d_str = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    eid = repo.add_manual(d_str, "식약처 실태조사", kind="실태조사", impact="high")
    check("사내 일정 등록", eid > 0)
    repo.update_event(eid, status="action", memo="증빙 바인더 준비")
    ups = repo.upcoming(30, today=today)
    mine = next((e for e in ups if e.id == eid), None)
    check("상태/메모 갱신", mine is not None and mine.status == "action"
          and "바인더" in mine.memo)

    # 6) 상태 보존 — 동기화가 사용자 메모를 덮어쓰지 않음
    duty_ev = duties[0]
    repo.update_event(duty_ev.id, status="done", memo="완료함")
    repo.ensure_duties(prof, horizon_days=365, today=today)
    again = [e for e in repo.list_range(duty_ev.date, duty_ev.date)
             if e.id == duty_ev.id][0]
    check("동기화 후 상태·메모 보존", again.status == "done" and again.memo == "완료함")

    # 7) 공유문 초안 (결정론적)
    from engines.notice_gen import draft_notice
    txt = draft_notice("KGSP 보관 관리 개정", "2026-07-01",
                       company="테스트약품", ref_id="kgsp_storage", use_claude=False)
    check("공유문 초안 생성", "사내 공유" in txt and "2026-07-01" in txt
          and "온도" in txt, f"{len(txt)}자")

    # 8) 다이제스트 통합 — 사내 일정·의무 노출 (검증본 로직 시뮬레이션)
    found = [e for e in repo.upcoming(30, today=today)
             if e.track in ("duty", "internal") and e.status != "done"]
    check("다이제스트 대상 일정 존재", any("실태조사" in e.title for e in found),
          f"{len(found)}건")

    print()
    if FAILS:
        print(f"❌ {len(FAILS)} FAIL: {FAILS}")
        return 1
    print("✅ ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
