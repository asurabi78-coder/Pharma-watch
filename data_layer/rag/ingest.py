"""코퍼스 색인 빌더 (CLI).

사용법
------
  python -m data_layer.rag.ingest

corpus/ 의 .md / .txt / .pdf 를 모두 읽어 청크로 자른 뒤
index/chunks.json 으로 저장한다. 페이지·검색기는 이 json 이 있으면
우선 로드한다(없으면 corpus 의 md/txt 를 즉석 색인).

PDF 를 넣으려면 pypdf 가 필요하다(requirements 에 포함). 없으면 PDF 는
건너뛰고 안내만 출력한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

from data_layer.rag.chunking import chunk_document

_RAG_DIR = Path(__file__).resolve().parent
_CORPUS_DIR = _RAG_DIR / "corpus"
_INDEX_DIR = _RAG_DIR / "index"
_INDEX_JSON = _INDEX_DIR / "chunks.json"


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        print(f"  ! pypdf 미설치 — PDF 건너뜀: {path.name} "
              f"(pip install pypdf 후 다시 실행)")
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n\n".join((pg.extract_text() or "") for pg in reader.pages)
    except Exception as e:  # noqa: BLE001
        print(f"  ! PDF 읽기 실패({path.name}): {type(e).__name__}: {e}")
        return ""


def build() -> int:
    if not _CORPUS_DIR.exists():
        print(f"corpus 폴더가 없습니다: {_CORPUS_DIR}")
        return 0

    chunks: List[dict] = []
    idx = 0
    files = sorted(_CORPUS_DIR.glob("*"))
    if not files:
        print("corpus 에 문서가 없습니다. .md/.txt/.pdf 를 넣어주세요.")
    for path in files:
        suf = path.suffix.lower()
        if suf in {".md", ".txt"}:
            text = path.read_text(encoding="utf-8")
        elif suf == ".pdf":
            text = _read_pdf(path)
        else:
            continue
        if not text.strip():
            continue
        doc_chunks = chunk_document(text, path.name)
        for rc in doc_chunks:
            chunks.append({
                "id": str(idx),
                "text": rc.text,
                "doc": rc.doc,
                "title": rc.title,
                "section": rc.section,
            })
            idx += 1
        print(f"  + {path.name}: {len(doc_chunks)} chunks")

    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    _INDEX_JSON.write_text(
        json.dumps({"chunks": chunks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n색인 저장 완료 → {_INDEX_JSON}  (총 {len(chunks)} chunks)")
    return len(chunks)


if __name__ == "__main__":
    n = build()
    sys.exit(0 if n >= 0 else 1)
