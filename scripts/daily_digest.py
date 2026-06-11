"""일일 다이제스트 실행 스크립트 — 스케줄러/크론용.

사용:
  python -m scripts.daily_digest            # 뉴스 재수집 + 다이제스트 출력
  python -m scripts.daily_digest --no-fetch # 재수집 없이 DB 기준 다이제스트
  python -m scripts.daily_digest --email    # 생성 후 이메일 발송 시도

결과는 stdout 출력 + db/digest_YYYYMMDD.md 저장.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
except Exception:
    pass

from data_layer import digest


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    do_fetch = "--no-fetch" not in argv
    do_email = "--email" in argv

    if do_fetch:
        try:
            from data_layer.news import fetch_and_save
            summary = fetch_and_save(per_source_limit=15)
            print(f"[fetch] 신규 {summary.get('new',0)} / 갱신 {summary.get('updated',0)}",
                  file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"[fetch] 실패(무시): {type(e).__name__}: {e}", file=sys.stderr)

    # 개정 영향 스캔 — 변경 감지 시 SOP 영향 리포트 생성 (실패해도 다이제스트는 진행)
    try:
        from engines.impact_engine import run_scan
        res = run_scan()
        if res.baseline:
            print(f"[impact] 기준선 저장 — 규제 {res.regs_checked}건", file=sys.stderr)
        else:
            print(f"[impact] 변경 {len(res.changes)}건 / 리포트 {len(res.reports)}건",
                  file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[impact] 실패(무시): {type(e).__name__}: {e}", file=sys.stderr)

    md = digest.build_digest()
    print(md)

    # 저장
    try:
        out = Path(__file__).resolve().parents[1] / "db" / f"digest_{datetime.now():%Y%m%d}.md"
        out.write_text(md, encoding="utf-8")
        print(f"\n[saved] {out}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[save] 실패(무시): {e}", file=sys.stderr)

    if do_email:
        ok, msg = digest.send_email(
            subject=f"[Pharma Watch] 데일리 브리핑 {datetime.now():%Y-%m-%d}", body_md=md)
        print(f"[email] {msg}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
