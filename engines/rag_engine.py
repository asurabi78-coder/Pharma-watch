"""RAG 엔진 — 검색(BM25) + Claude 인용 답변.

흐름: 질문 → 관련 청크 top-k 검색 → 근거 컨텍스트 구성 → Claude(Haiku)가
근거에만 기반해 한국어로 답변 + [n] 인용. 근거 부족 시 모른다고 답한다.

결정론적 검색은 LLM 비용 없이 수행되고, 생성만 Claude 를 1회 호출한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from data_layer.rag.retriever import Hit, Retriever

_SYSTEM = (
    "당신은 의약품 유통품질(KGSP)·콜드체인·GDP 규정 어시스턴트입니다. "
    "아래에 제공된 '근거 자료'에 담긴 내용만 사용해 한국어로 정확하게 답하세요.\n"
    "규칙:\n"
    "1) 근거 자료에 없는 내용은 지어내지 말고 '제공된 자료에서 확인되지 않습니다'라고 답합니다.\n"
    "2) 문장 끝에 사용한 근거를 [1], [2] 처럼 번호로 표기합니다.\n"
    "3) 실무 적용 시 원문·QA/법무 검토가 필요하다는 점을 답변 말미에 한 줄로 덧붙입니다.\n"
    "4) 법적 단정·의사결정·거부권 행사는 하지 않으며, 사실과 절차만 정리합니다.\n"
    "5) 답변은 간결하고 구조적으로, 핵심 위주로 작성합니다."
)

_MAX_CONTEXT_CHARS = 6000


@dataclass
class RagAnswer:
    answer: str
    hits: List[Hit]
    used_context: bool


def _build_context(hits: List[Hit]) -> str:
    blocks = []
    total = 0
    for i, h in enumerate(hits, start=1):
        c = h.chunk
        head = f"[{i}] 출처: {c.title} — {c.section} ({c.doc})"
        body = c.text.strip()
        block = f"{head}\n{body}"
        if total + len(block) > _MAX_CONTEXT_CHARS:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n".join(blocks)


def answer(query: str, retriever: Retriever, k: int = 5, feature: str = "rag_assistant") -> RagAnswer:
    """질문에 대해 검색 + Claude 답변을 생성한다."""
    query = (query or "").strip()
    if not query:
        return RagAnswer(answer="질문을 입력해 주세요.", hits=[], used_context=False)

    hits = retriever.search(query, k=k)
    if not hits:
        return RagAnswer(
            answer=(
                "제공된 규정 자료에서 관련 내용을 찾지 못했습니다. "
                "질문을 더 구체적으로 바꾸거나, corpus 에 관련 문서를 추가한 뒤 "
                "색인을 갱신해 보세요."
            ),
            hits=[],
            used_context=False,
        )

    context = _build_context(hits)
    user_msg = (
        f"# 질문\n{query}\n\n"
        f"# 근거 자료 (이 안의 내용만 사용)\n{context}\n\n"
        "위 근거에 기반해 답하고, 문장 끝에 [번호]로 인용하세요."
    )

    # 지연 import — 페이지/엔진 단독 테스트 시 Streamlit 의존 회피
    from utils.claude_client import call_claude

    out = call_claude(
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        max_tokens=900,
        feature=feature,
    )
    return RagAnswer(answer=out, hits=hits, used_context=True)
