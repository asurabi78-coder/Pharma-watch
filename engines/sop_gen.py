"""SOP 초안 생성 엔진 — 시드 규제 기반 골격 + 선택적 Claude 보강.

회사 정보(취급 유형·주제)를 받아 KGSP 요구사항을 충족하는 SOP 조문을 만든다.
  - 기본(결정론적): 시드 content(요구사항) + 실무해석을 조 단위 골격으로 배치.
  - Claude(키 있을 때): 같은 근거로 더 구체적인 절차 문장을 JSON 생성.
    실패 시 기본 골격으로 자동 폴백.

산출물은 '초안' — 시행 전 품질책임자(관리약사) 검토·승인 필수.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

Section = Tuple[str, str]  # (조 제목, 본문)


def _entries_for(topic_ids: Optional[List[str]]):
    from data_layer.regulatory.seed import SEED_ENTRIES
    entries = [e for e in SEED_ENTRIES if (e.content or "").strip()]
    if topic_ids:
        sel = [e for e in entries if e.id in set(topic_ids)]
        if sel:
            return sel
    return entries[:3]


def build_skeleton(*, company: str = "", topic_ids: Optional[List[str]] = None,
                   handles: Optional[List[str]] = None) -> List[Section]:
    """결정론적 SOP 골격 — 시드 요구사항을 조 단위로 배치."""
    entries = _entries_for(topic_ids)
    handles = handles or []
    co = company or "당사"

    sections: List[Section] = [
        ("제1조 (목적)",
         f"본 절차서는 {co}의 의약품 유통품질 관리기준(KGSP) 준수를 위해 "
         f"{', '.join(e.title.split('—')[-1].strip() for e in entries)} 업무의 "
         "표준 절차를 규정함을 목적으로 한다."),
        ("제2조 (적용범위)",
         f"본 절차서는 {co}가 취급하는 모든 의약품"
         + (f"({', '.join(handles)})" if handles else "")
         + "의 입고·보관·출고 및 관련 품질관리 업무에 적용한다."),
        ("제3조 (책임)",
         "1. 품질책임자(관리약사): 본 절차의 승인, 일탈 시 품질평가, 교육 실시\n"
         "2. 창고/물류 담당자: 본 절차에 따른 일상 업무 수행 및 기록 작성\n"
         "3. 대표자: 본 절차 이행에 필요한 자원(시설·인력) 제공"),
    ]

    art = 4
    for e in entries:
        body_lines = []
        for line in (e.content or "").split("\n"):
            line = line.strip()
            if line:
                body_lines.append(line)
        if e.practical_interpretation:
            body_lines.append(f"[실무 적용] {e.practical_interpretation}")
        if e.article:
            body_lines.append(f"[근거] {e.article}")
        topic = e.title.split("—")[-1].strip()
        sections.append((f"제{art}조 ({topic})", "\n".join(body_lines)))
        art += 1

    sections.append((f"제{art}조 (기록 관리)",
                     "본 절차에 따라 작성된 모든 기록은 작성일로부터 정해진 기간 동안 "
                     "보관하며, 실태조사 시 즉시 제시할 수 있도록 관리한다."))
    sections.append((f"제{art+1}조 (교육)",
                     "품질책임자는 본 절차의 내용을 관련 직원에게 교육하고 "
                     "교육 기록(교육일지·평가 결과)을 보관한다."))
    return sections


def build_with_claude(*, company: str = "", topic_ids: Optional[List[str]] = None,
                      handles: Optional[List[str]] = None,
                      extra_request: str = "") -> Tuple[List[Section], str]:
    """Claude 로 조문 생성 → 실패 시 골격 폴백. 반환 (sections, mode)."""
    skeleton = build_skeleton(company=company, topic_ids=topic_ids, handles=handles)
    try:
        from utils.claude_client import call_claude
    except Exception:
        return skeleton, "fallback"

    entries = _entries_for(topic_ids)
    basis = "\n\n".join(
        f"[{e.title}] ({e.article})\n{e.content}\n실무해석: {e.practical_interpretation}"
        for e in entries
    )[:4500]

    system = (
        "당신은 의약품 유통품질(KGSP) QA 문서 작성 보조자입니다. "
        "주어진 규제 근거를 충족하는 내부 SOP 조문을 작성하세요. "
        "근거에 없는 의무를 만들어내지 마세요. "
        "출력은 반드시 JSON 배열만: "
        '[{"heading":"제1조 (목적)","body":"..."}, ...]. '
        "body 안의 항목 구분은 줄바꿈(\\n)과 1. 2. 3. 번호를 사용. "
        "구체적 수치·주기·담당자를 명시한 실행 가능한 문장으로 작성. "
        "마지막 조는 '기록 관리'와 '교육' 포함."
    )
    user = (f"회사명: {company or '당사'}\n"
            f"취급 유형: {', '.join(handles) if handles else '일반 의약품'}\n"
            + (f"추가 요청: {extra_request}\n" if extra_request else "")
            + f"\n[규제 근거]\n{basis}")
    out = call_claude(system=system, messages=[{"role": "user", "content": user}],
                      max_tokens=3500, feature="sop_generator")
    sections = _parse_sections(out)
    if len(sections) >= 4:
        return sections, "claude"
    return skeleton, "fallback"


def _parse_sections(out: str) -> List[Section]:
    txt = (out or "").strip()
    m = re.search(r"\[.*\]", txt, re.DOTALL)
    if not m:
        return []
    try:
        raw = json.loads(m.group(0))
    except Exception:
        return []
    sections: List[Section] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        h = str(item.get("heading", "")).strip()
        b = str(item.get("body", "")).strip()
        if h and b:
            sections.append((h, b))
    return sections
