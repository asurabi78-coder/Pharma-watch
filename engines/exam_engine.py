"""KGSP 교육·평가 시험문제 생성 엔진.

두 가지 모드:
  - 기본(결정론적, LLM 비용 0): 시드 규제의 조문·실무해석에서 OX/4지선다 자동 생성.
    같은 입력(범위·문항수·시드값) → 항상 같은 시험지.
  - Claude(키 있을 때): 시드 근거를 주고 더 자연스러운 문항을 JSON 으로 생성.
    실패하면 기본 모드로 자동 폴백.

문항은 교육 보조 목적 — 법적 단정이 아니며 최종 검토는 QA 담당자 몫.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from engines.sop_compare import _split_clauses


@dataclass
class Question:
    number: int
    qtype: str                 # "ox" | "choice"
    question: str
    options: List[str] = field(default_factory=list)  # choice 만 (4개)
    answer: str = ""           # "O"/"X" 또는 "①"~"④"
    explanation: str = ""
    source: str = ""           # 출처 규제 제목


CIRCLED = ["①", "②", "③", "④"]


# ---------------------------------------------------------------- 시드 수집

def collect_topics() -> List[Tuple[str, str]]:
    """(id, title) 목록 — UI 의 범위 선택용."""
    try:
        from data_layer.regulatory.seed import SEED_ENTRIES
        return [(e.id, e.title) for e in SEED_ENTRIES if (e.content or "").strip()]
    except Exception:
        return []


def _entries_for(topic_ids: Optional[List[str]]):
    from data_layer.regulatory.seed import SEED_ENTRIES
    entries = [e for e in SEED_ENTRIES if (e.content or "").strip()]
    if topic_ids:
        sel = [e for e in entries if e.id in set(topic_ids)]
        if sel:
            return sel
    return entries


# ---------------------------------------------------------------- 결정론적 생성

_NUM = re.compile(r"(\d+)")

# X(틀린 문장) 변형 규칙 — 의무를 약화/수치 변경
_FALSIFY_RULES = [
    ("하여야 한다", "할 필요는 없다"),
    ("즉시 격리", "7일 이내에 격리"),
    ("발행하여야", "생략할 수 있으며 발행하지 않아도"),
    ("실시", "생략"),
]


def _falsify(clause: str, rng: random.Random) -> Optional[str]:
    """절을 '틀린 문장'으로 변형. 불가능하면 None."""
    # 1) 수치 변경이 가장 안전한 오답
    nums = _NUM.findall(clause)
    if nums:
        target = rng.choice(nums)
        wrong = str(int(target) * 2 + 1)
        return clause.replace(target, wrong, 1)
    # 2) 의무 약화 치환
    for a, b in _FALSIFY_RULES:
        if a in clause:
            return clause.replace(a, b, 1)
    return None


def _make_ox(entry, clause: str, rng: random.Random, num: int) -> Question:
    make_false = rng.random() < 0.5
    if make_false:
        wrong = _falsify(clause, rng)
        if wrong:
            return Question(
                number=num, qtype="ox",
                question=f"{wrong} (O/X)",
                answer="X",
                explanation=f"올바른 내용: {clause}",
                source=entry.title,
            )
    return Question(
        number=num, qtype="ox",
        question=f"{clause} (O/X)",
        answer="O",
        explanation=f"근거: {entry.title}" + (f" — {entry.article}" if entry.article else ""),
        source=entry.title,
    )


def _make_choice(entry, others, rng: random.Random, num: int) -> Optional[Question]:
    """'다음 중 ~의 요구사항이 아닌 것은?' — 정답은 다른 규제의 절."""
    own = [c for c in _split_clauses(entry.content) if len(c) <= 80]
    pool = []
    for o in others:
        if o.id == entry.id:
            continue
        pool += [(c, o.title) for c in _split_clauses(o.content) if len(c) <= 80]
    if len(own) < 3 or not pool:
        return None
    correct_clauses = rng.sample(own, 3)
    distractor, src = rng.choice(pool)
    options = correct_clauses + [distractor]
    rng.shuffle(options)
    ans_idx = options.index(distractor)
    return Question(
        number=num, qtype="choice",
        question=f"다음 중 「{entry.title}」의 요구사항이 아닌 것은?",
        options=options,
        answer=CIRCLED[ans_idx],
        explanation=f"{CIRCLED[ans_idx]}번은 「{src}」의 내용입니다.",
        source=entry.title,
    )


def build_deterministic(n: int = 10, topic_ids: Optional[List[str]] = None,
                        seed: int = 0) -> List[Question]:
    """결정론적 시험지 — seed 가 같으면 항상 같은 문제."""
    entries = _entries_for(topic_ids)
    rng = random.Random(seed)
    questions: List[Question] = []
    guard = 0
    while len(questions) < n and guard < n * 20:
        guard += 1
        entry = entries[guard % len(entries)] if guard % 3 == 0 else rng.choice(entries)
        all_clauses = [c for c in _split_clauses(entry.content) if 10 <= len(c) <= 120]
        # OX 용은 서술형 절 우선 (명사 나열 조각 제외)
        clauses = [c for c in all_clauses
                   if re.search(r"(한다|하여야|실시|유지|운영|보고|발행|기재|구분|평가|격리)", c)] \
            or all_clauses
        if not clauses:
            continue
        num = len(questions) + 1
        if guard % 2 == 0:
            q = _make_choice(entry, entries, rng, num)
            if q is None:
                q = _make_ox(entry, rng.choice(clauses), rng, num)
        else:
            q = _make_ox(entry, rng.choice(clauses), rng, num)
        # 중복 문항 방지
        if any(prev.question == q.question for prev in questions):
            continue
        questions.append(q)
    return questions


# ---------------------------------------------------------------- Claude 생성

def _seed_context(topic_ids: Optional[List[str]], max_chars: int = 4500) -> str:
    parts = []
    for e in _entries_for(topic_ids):
        parts.append(f"[{e.title}] ({e.article})\n{e.content}\n실무해석: {e.practical_interpretation}")
    return "\n\n".join(parts)[:max_chars]


def build_with_claude(n: int = 10, topic_ids: Optional[List[str]] = None,
                      difficulty: str = "보통") -> Tuple[List[Question], str]:
    """Claude 로 문항 생성 → 실패 시 결정론적 폴백.

    반환: (questions, mode) — mode 는 "claude" 또는 "fallback".
    """
    try:
        from utils.claude_client import call_claude
    except Exception:
        return build_deterministic(n, topic_ids), "fallback"

    system = (
        "당신은 의약품 유통품질(KGSP) 교육 담당자를 돕는 출제 보조자입니다. "
        "주어진 규제 근거만으로 시험 문항을 만드세요. 근거에 없는 내용은 출제하지 않습니다. "
        "출력은 반드시 JSON 배열만 — 다른 텍스트 금지. 각 원소: "
        '{"type":"ox"|"choice","question":"...","options":["...","...","...","..."],'
        '"answer":"O"|"X"|"①"|"②"|"③"|"④","explanation":"...","source":"근거 규제 제목"}. '
        "ox 는 options 를 빈 배열로. choice 는 보기 4개. "
        "문항의 절반 가량은 choice 로, 실무 적용형(상황 제시) 문항을 섞으세요."
    )
    user = (f"난이도: {difficulty}\n문항 수: {n}\n\n[규제 근거]\n"
            f"{_seed_context(topic_ids)}")
    out = call_claude(system=system, messages=[{"role": "user", "content": user}],
                      max_tokens=3000, feature="training")
    qs = _parse_claude_json(out)
    if len(qs) >= max(3, n // 2):
        return qs[:n], "claude"
    return build_deterministic(n, topic_ids), "fallback"


def _parse_claude_json(out: str) -> List[Question]:
    txt = (out or "").strip()
    # 코드펜스/전후 텍스트 제거
    m = re.search(r"\[.*\]", txt, re.DOTALL)
    if not m:
        return []
    try:
        raw = json.loads(m.group(0))
    except Exception:
        return []
    qs: List[Question] = []
    for i, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            continue
        qtype = item.get("type", "ox")
        ans = str(item.get("answer", "")).strip()
        opts = [str(o) for o in (item.get("options") or [])]
        if qtype == "choice" and len(opts) != 4:
            continue
        if qtype == "ox" and ans not in ("O", "X"):
            continue
        if qtype == "choice" and ans not in CIRCLED:
            continue
        q = item.get("question", "").strip()
        if not q:
            continue
        qs.append(Question(
            number=i, qtype=qtype, question=q, options=opts, answer=ans,
            explanation=str(item.get("explanation", "")).strip(),
            source=str(item.get("source", "")).strip(),
        ))
    return qs
