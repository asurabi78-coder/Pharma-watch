"""개정 → SOP 자동 영향분석 엔진 — 결정론적 (LLM 비용 0).

핵심 아이디어: 규제 모니터링과 SOP 갭분석을 '연결'한다.
  1) 활성 connector 의 현재 규제 원문을 스냅샷(마지막 확인본)과 해시 비교 → 변경 감지
  2) 변경된 규제마다, 보관함의 모든 SOP 에 갭분석을 자동 재실행
  3) 변경 전(스냅샷 원문) 점수 vs 변경 후(현재 원문) 점수를 비교해
     '이 개정으로 귀사 SOP 가 어떻게 부적합해졌는지'를 리포트로 생성
  4) 스냅샷을 현재 원문으로 갱신 (다음 스캔의 기준점)

같은 입력 → 항상 같은 결과. 최초 실행은 기준선(baseline) 저장만 하고
리포트를 만들지 않는다 (모든 규제가 '신규'로 오탐되는 것 방지).

이건 '판단/거부권'이 아니라 '점검 보조'다 — 최종 확인은 QA 담당자 몫.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import List, Optional

from engines import sop_compare as sc
from data_layer import sop_vault as vault
from data_layer.regulatory.models import LawEntry


# ---------------------------------------------------------------- 데이터 구조

@dataclass
class RegChange:
    """감지된 규제 변경 1건."""
    reg_id: str
    title: str
    kind: str                  # new / modified
    old_content: str = ""
    new_content: str = ""
    added_clauses: List[str] = field(default_factory=list)   # 개정으로 추가된 요구사항 절
    removed_clauses: List[str] = field(default_factory=list)  # 삭제된 절


@dataclass
class ScanResult:
    """run_scan() 의 산출물 — UI/다이제스트가 그대로 표시."""
    baseline: bool = False        # 최초 실행(기준선 저장만) 여부
    regs_checked: int = 0
    changes: List[RegChange] = field(default_factory=list)
    reports: List[vault.ImpactReport] = field(default_factory=list)
    sops_analyzed: int = 0


# ---------------------------------------------------------------- 내부 유틸

def _hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


def _collect_entries() -> List[LawEntry]:
    """활성 connector 의 규제 항목 수집 — regulatory_engine 의 수집 로직 재사용."""
    from engines.regulatory_engine import _collect_from_connectors
    from data_layer.regulatory.connectors import get_active_connectors
    entries, _ = _collect_from_connectors(get_active_connectors())
    return entries


def _diff_clauses(old: str, new: str) -> tuple[List[str], List[str]]:
    """절 단위 diff — (추가된 절, 삭제된 절)."""
    old_set = set(sc._split_clauses(old))
    new_set = set(sc._split_clauses(new))
    added = [c for c in sc._split_clauses(new) if c not in old_set]
    removed = [c for c in sc._split_clauses(old) if c not in new_set]
    return added, removed


# ---------------------------------------------------------------- 변경 감지

def detect_changes(entries: List[LawEntry],
                   snapshots: dict) -> List[RegChange]:
    """현재 규제 원문 vs 스냅샷 — 신규/변경 항목만 반환."""
    changes: List[RegChange] = []
    for e in entries:
        content = (e.content or "").strip()
        if not content:
            continue
        snap = snapshots.get(e.id)
        if snap is None:
            changes.append(RegChange(
                reg_id=e.id, title=e.title, kind="new", new_content=content,
                added_clauses=sc._split_clauses(content),
            ))
        elif snap.content_hash != _hash(content):
            added, removed = _diff_clauses(snap.content, content)
            changes.append(RegChange(
                reg_id=e.id, title=e.title, kind="modified",
                old_content=snap.content, new_content=content,
                added_clauses=added, removed_clauses=removed,
            ))
    return changes


# ---------------------------------------------------------------- 영향 분석

def _newly_missing(prev: sc.CompareResult, new: sc.CompareResult) -> List[str]:
    """변경 전엔 문제없었는데 변경 후 미흡/부분이 된 절 (신규 절 포함)."""
    prev_bad = {c.clause for c in prev.clauses if c.status in ("missing", "partial")}
    return [c.clause for c in new.clauses
            if c.status in ("missing", "partial") and c.clause not in prev_bad]


def analyze_change(change: RegChange, sop: vault.SopDoc) -> vault.ImpactReport:
    """변경 1건 × SOP 1건 → 영향 리포트 (결정론적)."""
    new_res = sc.compare(change.new_content, sop.body, reg_title=change.title)
    if change.kind == "modified" and change.old_content:
        prev_res = sc.compare(change.old_content, sop.body, reg_title=change.title)
        prev_score: Optional[int] = prev_res.score
        delta: Optional[int] = new_res.score - prev_res.score
        missing = _newly_missing(prev_res, new_res)
    else:  # 신규 규제 — 비교 기준 없음
        prev_score, delta = None, None
        missing = [c.clause for c in new_res.clauses
                   if c.status in ("missing", "partial")]
    return vault.ImpactReport(
        id=0, reg_id=change.reg_id, reg_title=change.title,
        change_kind=change.kind, sop_id=sop.id, sop_title=sop.title,
        prev_score=prev_score, new_score=new_res.score, delta=delta,
        new_missing=missing, status="new", user=sop.user,
    )


# ---------------------------------------------------------------- 오케스트레이션

def run_scan(*, entries: Optional[List[LawEntry]] = None,
             persist: bool = True) -> ScanResult:
    """변경 감지 → 전 SOP 영향분석 → 리포트 저장 → 스냅샷 갱신.

    - entries=None 이면 활성 connector 에서 수집 (테스트 시 주입 가능).
    - 영향분석은 '전 계정' SOP 대상 — 리포트는 각 SOP 소유자 앞으로 저장된다.
      (한 사용자의 스캔이 스냅샷을 갱신해도 다른 사용자가 알림을 놓치지 않게)
    - persist=False 면 DB 에 쓰지 않고 분석 결과만 반환 (미리보기용).
    """
    if entries is None:
        entries = _collect_entries()

    snapshots = vault.load_snapshots()
    result = ScanResult(regs_checked=len(entries))

    # 최초 실행 — 기준선만 저장, 리포트 없음
    if not snapshots:
        result.baseline = True
        if persist:
            for e in entries:
                content = (e.content or "").strip()
                if content:
                    vault.save_snapshot(e.id, e.title, content, _hash(content))
        return result

    changes = detect_changes(entries, snapshots)
    result.changes = changes
    if not changes:
        return result

    sops = vault.list_sops(user=None)  # 전 계정
    result.sops_analyzed = len(sops)

    for change in changes:
        for sop in sops:
            rep = analyze_change(change, sop)
            # 영향이 실제로 있을 때만 리포트 생성:
            #  - 점수 하락, 또는 새로 미흡해진 절 존재, 또는 신규 규제가 미흡
            meaningful = (
                (rep.delta is not None and rep.delta < 0)
                or rep.new_missing
            )
            if not meaningful:
                continue
            if persist:
                rep.id = vault.save_report(rep)
            result.reports.append(rep)

    # 스냅샷 갱신 — 변경분만 (감지 후 갱신해야 prev 기준이 유지됨)
    if persist:
        for change in changes:
            vault.save_snapshot(change.reg_id, change.title,
                                change.new_content, _hash(change.new_content))

    return result


# ---------------------------------------------------------------- 요약 (다이제스트용)

def digest_lines(*, limit: int = 5) -> List[str]:
    """미확인(new) 영향 리포트를 다이제스트 마크다운 줄로. 없으면 빈 리스트."""
    try:
        reports = vault.list_reports(user=None, status="new", limit=limit)
        total = vault.count_new_reports()
    except Exception:
        return []
    if not reports:
        return []
    lines = [f"## ⚠️ 개정 영향 알림 — 미확인 {total}건"]
    for r in reports:
        if r.delta is not None:
            move = f"{r.prev_score} → {r.new_score}점 ({r.delta:+d})"
        else:
            move = f"신규 규제 · 적합도 {r.new_score}점"
        lines.append(
            f"- 🔴 **{r.sop_title}** ↔ {r.reg_title} — {move}"
            f" · 새 미흡 {len(r.new_missing)}절"
        )
    lines.append("- 상세·보완 문구는 앱의 **개정 영향분석** 메뉴에서 확인하세요.")
    return lines
