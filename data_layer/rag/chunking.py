"""문서 → 청크 분할.

마크다운/일반 텍스트를 표제(heading) 기준으로 섹션화하고, 섹션을 다시
목표 길이(기본 ~700자) 단위로 자른다. 청크마다 출처 문서·섹션 표제를
메타데이터로 보존하여 인용(citation)에 사용한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")

# 청크 목표/최대 길이(문자 기준). 한국어는 토큰이 짧아 문자 기준이 단순·안전.
_TARGET = 700
_MAX = 1100


@dataclass
class RawChunk:
    text: str
    doc: str          # 문서 파일명 (예: kgsp.md)
    title: str        # 문서 제목 (첫 H1 또는 파일명)
    section: str      # 가장 가까운 표제
    meta: dict = field(default_factory=dict)


def _split_paragraphs(text: str) -> List[str]:
    # 빈 줄 기준 문단 분리. 리스트 항목은 줄 단위 유지.
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_document(text: str, doc: str) -> List[RawChunk]:
    """단일 문서 텍스트를 청크 리스트로."""
    lines = text.splitlines()
    title = doc
    # 첫 H1 을 제목으로
    for ln in lines:
        m = _HEADING.match(ln.strip())
        if m and len(m.group(1)) == 1:
            title = m.group(2).strip()
            break

    chunks: List[RawChunk] = []
    section = title
    buf: List[str] = []
    buf_len = 0

    def flush():
        nonlocal buf, buf_len
        if not buf:
            return
        body = "\n\n".join(buf).strip()
        if body:
            chunks.append(RawChunk(text=body, doc=doc, title=title, section=section))
        buf = []
        buf_len = 0

    # 표제로 섹션을 끊고, 섹션 안에서 문단을 누적
    blocks: List[tuple] = []  # (is_heading, text)
    cur: List[str] = []
    for ln in lines:
        m = _HEADING.match(ln.strip())
        if m:
            if cur:
                blocks.append((False, "\n".join(cur)))
                cur = []
            blocks.append((True, m.group(2).strip()))
        else:
            cur.append(ln)
    if cur:
        blocks.append((False, "\n".join(cur)))

    for is_heading, content in blocks:
        if is_heading:
            flush()
            section = content or section
            continue
        for para in _split_paragraphs(content):
            # 한 문단이 최대치를 넘으면 문장 단위로 추가 분할
            pieces = _hard_wrap(para)
            for piece in pieces:
                if buf_len + len(piece) > _MAX and buf:
                    flush()
                buf.append(piece)
                buf_len += len(piece)
                if buf_len >= _TARGET:
                    flush()
    flush()
    return chunks


def _hard_wrap(para: str) -> List[str]:
    if len(para) <= _MAX:
        return [para]
    # 문장 경계(. ! ? 。 줄바꿈)로 자른 뒤 누적
    sents = re.split(r"(?<=[.!?。])\s+|\n", para)
    out: List[str] = []
    cur = ""
    for s in sents:
        if not s:
            continue
        if len(cur) + len(s) > _MAX and cur:
            out.append(cur.strip())
            cur = ""
        cur += (" " if cur else "") + s
    if cur.strip():
        out.append(cur.strip())
    return out or [para[:_MAX]]
