"""개정→영향분석 E2E 테스트 — 임시 DB 사용 (실 DB 미오염).

시나리오:
  1. SOP 등록 (v1 규제를 잘 충족하는 보관 SOP)
  2. 스캔#1 → 기준선 저장 (리포트 0)
  3. 스캔#2 (동일 규제) → 변경 없음
  4. 규제 개정 (자동온도기록장치·분기 점검 요구 추가) → 스캔#3
     → 변경 1건 감지 + 점수 하락 리포트 + 새 미흡 절 식별
  5. 다이제스트에 '개정 영향 알림' 섹션 노출
  6. 확인 처리 → 미확인 0건

실행: python -m scripts.test_impact_e2e
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_layer import sop_vault as vault
from data_layer.connectors.base import SourceTier
from data_layer.regulatory.models import LawEntry
from engines import impact_engine as ie

FAILS = []


def check(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main() -> int:
    # 임시 DB 로 격리
    tmp = Path(tempfile.mkdtemp()) / "test_vault.db"
    vault._DEFAULT_DB_PATH = tmp

    reg_v1 = LawEntry(
        id="kgsp_storage_test",
        title="KGSP 보관 관리 (테스트)",
        grade=SourceTier.LAW,
        content=(
            "의약품을 보관하는 자는 다음 사항을 준수하여야 한다.\n"
            "1. 의약품의 품질이 손상되지 않도록 적절한 온도·습도 조건 유지\n"
            "2. 보관조건 일탈 시 즉시 격리하고 품질평가 실시\n"
            "3. 보관시설은 의약품 특성에 따라 구분 운영"
        ),
    )

    sop_body = (
        "제1조(목적) 본 SOP 는 의약품 보관관리를 규정한다.\n"
        "제2조(온도·습도) 창고는 온도 1~30℃, 습도 35~75%를 유지하며 "
        "온도·습도 조건을 일 2회 기록한다.\n"
        "제3조(일탈) 보관조건 일탈 발생 시 해당 의약품을 즉시 격리하고 "
        "품질평가를 실시한 후 결과를 기록한다.\n"
        "제4조(시설) 보관시설은 의약품 특성(상온·냉장)에 따라 구분 운영한다.\n"
    )

    # 1) SOP 등록
    sop_id = vault.add_sop("보관관리 SOP v1.0", sop_body, user="(local)")
    check("SOP 등록", sop_id > 0, f"id={sop_id}")

    # 2) 스캔#1 — 기준선
    r1 = ie.run_scan(entries=[reg_v1])
    check("스캔#1 = 기준선", r1.baseline and not r1.reports,
          f"regs={r1.regs_checked}")
    check("스냅샷 저장됨", vault.snapshot_count() == 1)

    # 3) 스캔#2 — 변경 없음
    r2 = ie.run_scan(entries=[reg_v1])
    check("스캔#2 = 변경 없음", not r2.baseline and not r2.changes)

    # 4) 규제 개정 — SOP 가 다루지 않는 요구사항 추가
    reg_v2 = LawEntry(
        id=reg_v1.id, title=reg_v1.title, grade=SourceTier.LAW,
        content=reg_v1.content + (
            "\n4. 자동온도기록장치를 설치하고 측정값을 전자적으로 보존\n"
            "5. 수송용기 적격성평가를 분기 1회 실시하고 결과를 보고"
        ),
    )
    r3 = ie.run_scan(entries=[reg_v2])
    check("스캔#3 = 변경 1건 감지", len(r3.changes) == 1,
          f"kind={r3.changes[0].kind if r3.changes else '-'}")
    check("추가 절 식별", len(r3.changes[0].added_clauses) >= 2 if r3.changes else False,
          f"added={r3.changes[0].added_clauses if r3.changes else []}")
    check("영향 리포트 생성", len(r3.reports) == 1)
    if r3.reports:
        rep = r3.reports[0]
        check("점수 하락 감지", rep.delta is not None and rep.delta < 0,
              f"{rep.prev_score} → {rep.new_score} ({rep.delta:+d})")
        check("새 미흡 절 식별", len(rep.new_missing) >= 1,
              f"missing={rep.new_missing}")

    # 5) 다이제스트 통합
    lines = ie.digest_lines()
    check("다이제스트 섹션 생성", any("개정 영향 알림" in l for l in lines),
          (lines[0] if lines else "(빈)"))
    for l in lines:
        print("   |", l)

    # 6) 확인 처리
    reports = vault.list_reports(user="(local)", status="new")
    check("미확인 리포트 조회", len(reports) == 1)
    if reports:
        vault.acknowledge_report(reports[0].id, user="(local)")
    check("확인 처리 후 0건", vault.count_new_reports() == 0)
    check("확인 후 다이제스트 섹션 사라짐", ie.digest_lines() == [])

    # 결정론성 — 같은 입력 재실행 시 동일 결과 (스냅샷이 갱신됐으므로 변경 0)
    r4 = ie.run_scan(entries=[reg_v2])
    check("스냅샷 갱신 확인 (재스캔 변경 0)", not r4.changes)

    print()
    if FAILS:
        print(f"❌ {len(FAILS)} FAIL: {FAILS}")
        return 1
    print("✅ ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
