"""경량 검색기 — 순수 파이썬 BM25 (추가 의존성 0).

- 한글: 문자 bigram + 단일 음절, 영문/숫자: 단어 토큰으로 색인.
  konlpy/Java 없이도 한국어 규정 텍스트에서 충분한 재현율을 낸다.
- corpus/ 의 .md/.txt 를 즉석에서 색인(첫날부터 동작)하거나, ingest 가
  만들어 둔 index/chunks.json(.pdf 포함)이 있으면 그것을 우선 로드한다.
- 인덱스 빌드는 가볍지만, 페이지에서는 st.cache_resource 로 1회만 만든다.

벡터(임베딩) 백엔드로 바꾸려면 RAG_BACKEND=vector + 별도 모듈을 쓰면 되나,
2GB 서버 기본값은 이 키워드 백엔드다(메모리 안전).
"""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from data_layer.rag.chunking import chunk_document

_RAG_DIR = Path(__file__).resolve().parent
_CORPUS_DIR = _RAG_DIR / "corpus"
_INDEX_JSON = _RAG_DIR / "index" / "chunks.json"

_HANGUL = re.compile(r"[가-힣]+")
_WORD = re.compile(r"[a-zA-Z0-9]+")

_K1 = 1.5
_B = 0.75


def tokenize(text: str) -> List[str]:
    """한글 bigram + 영문/숫자 단어. 소문자화."""
    if not text:
        return []
    text = text.lower()
    toks: List[str] = _WORD.findall(text)
    for run in _HANGUL.findall(text):
        if len(run) == 1:
            toks.append(run)
        else:
            toks.extend(run[i : i + 2] for i in range(len(run) - 1))
    return toks


@dataclass
class Chunk:
    id: str
    text: str
    doc: str
    title: str
    section: str


@dataclass
class Hit:
    chunk: Chunk
    score: float


class Retriever:
    """BM25 색인 + 검색."""

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self._tf: List[Dict[str, int]] = []
        self._len: List[int] = []
        self._df: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._avglen: float = 0.0
        self._build()

    def _build(self) -> None:
        n = len(self.chunks)
        total_len = 0
        for ch in self.chunks:
            toks = tokenize(ch.text + " " + ch.section + " " + ch.title)
            tf: Dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            self._tf.append(tf)
            self._len.append(len(toks))
            total_len += len(toks)
            for t in tf:
                self._df[t] = self._df.get(t, 0) + 1
        self._avglen = (total_len / n) if n else 0.0
        for t, df in self._df.items():
            # BM25 idf (floor 0 으로 음수 방지)
            self._idf[t] = max(0.0, math.log((n - df + 0.5) / (df + 0.5) + 1.0))

    def search(self, query: str, k: int = 5, min_score: float = 0.0) -> List[Hit]:
        if not self.chunks:
            return []
        q_terms = tokenize(query)
        if not q_terms:
            return []
        # 질의어 가중치(빈도)
        q_tf: Dict[str, int] = {}
        for t in q_terms:
            q_tf[t] = q_tf.get(t, 0) + 1

        scored: List[Tuple[float, int]] = []
        for i, tf in enumerate(self._tf):
            dl = self._len[i] or 1
            s = 0.0
            for t, qf in q_tf.items():
                f = tf.get(t)
                if not f:
                    continue
                idf = self._idf.get(t, 0.0)
                denom = f + _K1 * (1 - _B + _B * dl / (self._avglen or 1))
                s += idf * (f * (_K1 + 1)) / denom
            if s > min_score:
                scored.append((s, i))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [Hit(chunk=self.chunks[i], score=round(sc, 4)) for sc, i in scored[:k]]

    @property
    def size(self) -> int:
        return len(self.chunks)

    @property
    def doc_count(self) -> int:
        return len({c.doc for c in self.chunks})


# --------------------------------------------------------------------------
# 인덱스 로딩 — ingest 결과(json) 우선, 없으면 corpus 즉석 색인
# --------------------------------------------------------------------------
def _load_from_json() -> Optional[List[Chunk]]:
    if not _INDEX_JSON.exists():
        return None
    try:
        data = json.loads(_INDEX_JSON.read_text(encoding="utf-8"))
        items = data.get("chunks", data) if isinstance(data, dict) else data
        out: List[Chunk] = []
        for i, c in enumerate(items):
            out.append(
                Chunk(
                    id=str(c.get("id", i)),
                    text=c.get("text", ""),
                    doc=c.get("doc", ""),
                    title=c.get("title", c.get("doc", "")),
                    section=c.get("section", ""),
                )
            )
        return [c for c in out if c.text.strip()]
    except Exception:
        return None


def _load_from_corpus() -> List[Chunk]:
    out: List[Chunk] = []
    if not _CORPUS_DIR.exists():
        return out
    idx = 0
    for path in sorted(_CORPUS_DIR.glob("*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for rc in chunk_document(text, path.name):
            out.append(
                Chunk(id=str(idx), text=rc.text, doc=rc.doc, title=rc.title, section=rc.section)
            )
            idx += 1
    return out


def load_chunks() -> List[Chunk]:
    """ingest json → corpus 순으로 청크 로드."""
    chunks = _load_from_json()
    if chunks:
        return chunks
    return _load_from_corpus()


def get_retriever() -> Retriever:
    """검색기 1개 생성(색인 포함). 페이지에서는 st.cache_resource 로 감싼다."""
    return Retriever(load_chunks())
