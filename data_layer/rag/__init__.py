"""RAG (검색 증강 생성) — KGSP/GDP 법령 어시스턴트 백엔드.

설계 원칙
---------
- 무거운 임베딩 모델·torch·외부 벡터DB 없이 2GB 서버에서 바로 동작.
- 기본 검색기는 자체 구현 BM25(순수 파이썬, 추가 의존성 0).
- 한글은 문자 bigram + 영문/숫자 단어 토큰으로 색인 → konlpy/Java 불필요.
- 답변 생성은 기존 utils.claude_client(Claude Haiku) 재사용 → 키·비용 통일.

확장
----
- 서버를 키우면 RAG_BACKEND=vector 로 Chroma+임베딩 백엔드로 교체 가능(문서 참조).
- corpus/ 에 .md/.txt/.pdf 를 넣고 `python -m data_layer.rag.ingest` 로 색인 갱신.
"""

from data_layer.rag.retriever import Retriever, get_retriever, Chunk  # noqa: F401
