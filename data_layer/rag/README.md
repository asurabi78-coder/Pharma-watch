# 법령 어시스턴트 (RAG) — 사용·운영 안내

KGSP·콜드체인·GDP 규정 문서를 검색(BM25)해 근거와 함께 Claude(Haiku)가 답하는 기능.
무거운 임베딩 모델·외부 벡터DB 없이 **2GB 서버에서 바로 동작**한다.

## 구성

```
data_layer/rag/
├─ corpus/           ← 규정 문서를 여기에 둠 (.md / .txt / .pdf)   ※ 커밋 대상
│   ├─ kgsp.md
│   ├─ biologics_coldchain.md
│   ├─ who_gdp.md
│   └─ deviation_capa.md
├─ index/            ← 생성된 색인(chunks.json). .gitignore 처리(커밋 안 함)
├─ chunking.py       ← 문서→청크 분할
├─ retriever.py      ← 자체 BM25 검색기(한글 bigram 토크나이저)
└─ ingest.py         ← 색인 빌더(CLI)
engines/rag_engine.py ← 검색 + Claude 인용 답변
pages/rag_assistant.py← 화면(채팅 UI)
```

## 문서 추가하는 법

1. `data_layer/rag/corpus/` 에 규정 파일을 넣는다.
   - **.md / .txt**: 별도 작업 없이 앱이 즉시 색인(앱에서 "🔄 색인 갱신" 클릭).
   - **.pdf**: 아래 인제스트를 한 번 실행해야 반영된다(`pypdf` 필요).
2. (PDF가 있을 때) 색인 빌드:
   ```
   python -m data_layer.rag.ingest
   ```
3. 앱 화면에서 "🔄 색인 갱신" 클릭 또는 서비스 재시작.

## 동작 원리

- 질문 → BM25로 관련 청크 top-5 검색(LLM 비용 0) → 그 근거만 Claude에 전달 →
  근거 기반 한국어 답변 + `[번호]` 인용. 근거에 없으면 "확인되지 않습니다"로 답한다.
- 비용: 질문당 Claude 1회 호출(Haiku). 검색은 무료.

## 한계와 주의

- 키워드(BM25) 검색이라 동의어·의미 검색은 임베딩 방식보다 약하다. 질문에 핵심 용어를
  포함하면 정확도가 올라간다.
- 답변은 **색인된 자료 기반 참고용**. 규정 위반 판단·고객 제출 전 원문과 QA·법무 검토 필요.

## (선택) 벡터(임베딩) 백엔드로 업그레이드

서버 메모리를 4GB 이상으로 키우면 의미 검색이 가능한 벡터 백엔드로 교체할 수 있다.
`sentence-transformers`(또는 임베딩 API) + `chromadb` 를 설치하고 retriever 를
벡터 버전으로 교체하면 된다. 현재 기본값은 메모리 안전을 위해 BM25.
```
