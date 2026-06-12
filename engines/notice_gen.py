"""사내 공유문(공문) 초안 생성 — 규제 변경을 현업 부서에 전파.

기본은 결정론적 템플릿(LLM 비용 0). Claude 키가 있으면 내용을 다듬는다.
산출물은 초안 — 발송 전 QA(품질책임자) 검토 필수.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def _find_seed(ref_id: str):
    try:
        from data_layer.regulatory.seed import SEED_ENTRIES
        for e in SEED_ENTRIES:
            if e.id == ref_id:
                return e
    except Exception:
        pass
    return None


def draft_notice(title: str, event_date: str, *, company: str = "",
                 ref_id: str = "", use_claude: bool = False) -> str:
    """사내 공유문 초안 텍스트 생성."""
    entry = _find_seed(ref_id) if ref_id else None
    co = company or "당사"
    today = datetime.now().strftime("%Y-%m-%d")

    summary = ""
    action = ""
    if entry is not None:
        summary = (entry.content or "").strip()
        if entry.practical_interpretation:
            action = entry.practical_interpretation.strip()

    base = (
        f"[사내 공유] 규제 변경 안내\n"
        f"\n"
        f"수신: 물류·창고·영업 등 관련 부서\n"
        f"발신: 품질관리부(QA)\n"
        f"일자: {today}\n"
        f"\n"
        f"1. 제목: {title}\n"
        f"2. 시행/기한일: {event_date}\n"
        f"\n"
        f"3. 주요 내용:\n"
        + (f"{summary}\n" if summary else "(내용 요약을 입력하세요)\n")
        + "\n"
        f"4. 당사 적용 사항:\n"
        + (f"{action}\n" if action else "(부서별 조치 사항을 입력하세요)\n")
        + "\n"
        f"5. 요청 사항:\n"
        f"  - 각 부서는 상기 내용을 소속 직원에게 전파하여 주시기 바랍니다.\n"
        f"  - 관련 SOP 개정이 필요한 경우 QA로 회신 바랍니다.\n"
        f"\n"
        f"{co} 품질관리부\n"
        f"\n"
        f"※ 본 문서는 자동 생성 초안입니다 — 발송 전 품질책임자 검토 필요."
    )

    if not use_claude:
        return base

    try:
        from utils.claude_client import call_claude
        system = (
            "당신은 의약품 유통회사 QA 의 사내 공문 작성 보조자입니다. "
            "주어진 초안을 더 명확하고 정중한 사내 공유문으로 다듬으세요. "
            "형식(번호 항목)은 유지하고, 근거 없는 내용을 추가하지 마세요. "
            "마지막 '자동 생성 초안' 안내 문구는 유지합니다."
        )
        out = call_claude(system=system,
                          messages=[{"role": "user", "content": base}],
                          max_tokens=900, feature="pharmacal")
        # 호출 실패 시 call_claude 가 오류 문자열을 반환 → 기본 템플릿 유지
        if out and "오류" not in out[:30] and "ANTHROPIC_API_KEY" not in out:
            return out
    except Exception:
        pass
    return base
