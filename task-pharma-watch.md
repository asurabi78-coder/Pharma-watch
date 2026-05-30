# task-pharma-watch.md — 외부용 규제 캘린더 앱 빌드 지시서 (A안: 화이트리스트)

> 작업 방식: **화이트리스트(줄 것만 골라 새 폴더에 담기)**.
> "위험한 파일을 지운다"가 아니라 "허용된 파일만 복사한다". IP가 원본 42개 파일에
> 광범위하게 박혀 있어 삭제 누락 위험이 크므로, 안 담은 IP는 애초에 존재하지 않게 만든다.

---

## 0. 절대 원칙 (위반 시 작업 중단)

1. **3PL Command Center 원본은 내부용 금고다.** `3pl-command-center/` 폴더는 열지도·읽지도·수정하지도 않는다. 작업 세션에 경로를 포함하지 않는다.
2. **외부 제공은 `pharma-watch/` 별도 앱으로만 한다.** 모든 신규/복사 작업은 이 폴더 안에서만 일어난다.
3. **`pharma-watch`에는 원가·수익성·전략·제안서·회의실·Deal Intelligence를 절대 넣지 않는다.** 메뉴 숨김이 아니라 **코드·데이터·import·문서 자체가 존재하지 않아야** 한다.
4. **외부용 QA는 VETO 없는 Regulatory QA Analyst 하나만 둔다.** 내부 9에이전트·거부권·의사결정 로직은 일절 이식 금지.
5. **무료 제공 범위는 캘린더·뉴스·알림·Action Item 추천까지만.**
6. **내부 SOP 자동비교·CAPA 자동작성·대화형 QA 질의는 유료/상위 기능으로만 남긴다** (화면엔 🔒로 보이되 동작 잠금).

> 보조 원칙(고문 교정): **공통 모듈화(shared/)는 지금 하지 않는다.** 기능이 안 굳었으므로 캘린더/뉴스 코드는 그냥 복사해서 시작하고, 두 앱에서 중복이 실제 확인된 뒤에만 나중에 공통화한다.

---

## 1. 폴더 구조 (목표)

```
pharma-watch/                 ← 새로 만드는 외부용 앱. 여기서만 작업
├── app.py                    ← 신규(외부용 경량 라우터)
├── branding.py               ← 화이트라벨 설정(로고·색·이름·푸터)
├── pharmacal-pro.html        ← 캘린더 UI (복사)
├── pages/
│   ├── home.py               ← 신규(외부용 간단 홈)
│   ├── pharmacal.py          ← 캘린더 (복사)
│   ├── newsroom.py           ← 뉴스 (복사)
│   ├── regulatory.py         ← 규제 원문검색 (복사, 선택)
│   └── qa_analyst.py         ← 신규(VETO 없는 분석가)
├── engines/
│   └── regulatory_engine.py  ← (복사)
├── data_layer/
│   ├── news/                 ← (복사, 전체)
│   ├── regulatory/           ← (복사, 전체)
│   └── connectors/
│       ├── base.py           ← (복사)
│       ├── law/              ← (복사)
│       ├── mfds/             ← (복사)
│       └── news/             ← (복사)
├── prompts/
│   └── regulatory_qa_analyst.md  ← 신규(분석가 프롬프트)
├── utils/                    ← claude_client 등 KEEP 의존만 복사
├── db/                       ← 빈 폴더(앱이 새 DB 생성). 기존 .db 복사 금지
├── README.md                 ← IP 고지 포함
└── task-pharma-watch.md      ← 이 문서
```

---

## 2. KEEP — 복사해서 담을 것 (IP 없음 확인됨)

의존성 추적 결과 아래 페이지들은 IP 모듈을 끌어오지 않는다:

| 항목 | 출처(읽기 전용 참조) | 비고 |
|---|---|---|
| `pharmacal.py` + `pharmacal-pro.html` | command-center 백업 | streamlit/pathlib만 의존 |
| `newsroom.py` | command-center 백업 | `data_layer/news/`만 의존 |
| `regulatory.py` (선택) | command-center 백업 | regulatory 전용. IP 없음 |
| `engines/regulatory_engine.py` | 〃 | regulatory 전용 |
| `data_layer/news/`, `data_layer/regulatory/` | 〃 | 전체 |
| `data_layer/connectors/{base,law,mfds,news}` | 〃 | regulatory/news 의존분만 |
| `utils/` 중 KEEP가 실제 import 하는 것 | 〃 | claude_client 등 최소 |

> 복사 후 **각 파일을 grep으로 검사**해서 KEEP 외 모듈을 import하지 않는지 확인(2.1 참조).

### 2.1 import 봉쇄 검증
복사한 모든 `.py` 에 대해 다음이 **0건**이어야 한다:
```
grep -rn "profitability\|proposal\|boardroom\|meeting_engine\|deal_intel\|executive_office\|document_vault\|orchestrator\|consult_engine\|internal_db\|web_research\|debate\|project_store\|tenant_store" pharma-watch/
```
하나라도 걸리면 → 그 import를 끊거나 해당 KEEP 파일을 외부용으로 경량 재작성.

---

## 3. 절대 넣지 않을 것 (REMOVE = 복사 대상에서 제외)

- pages: boardroom, executive_office, profitability, proposal, meeting_history, document_vault, knowledge_center, usage_dashboard, project, login
- engines: profitability_engine, proposal_engine
- agents/ 전체 9개 (qa_gdp_director 포함 — VETO형은 내부 전용)
- core/ 전체 (meeting_engine, orchestrator, consult_engine, agent_registry, tool_registry, event_bus, attendee_recommender, workflow_router, document_classifier, session_manager, token_tracker 등)
- discussion/ 전체
- data_layer: connectors/internal/, connectors/web_research/, document/, schema.py(수익성 필드 포함 시)
- memory/ 전체 (meeting_memory, consult_memory, episodic_memory, strategic_memory, project_store, tenant_store, usage_memory)
- prompts/personas 9개 + prompts/shared 4개
- task/ 의 내부 설계문서 전부 (Business Director, QA-GDP Director, Operations_Architect, Data_Lead, BD_Lead, Project_PM, Profitability_Lead, Contract-SLA Lead, Deal_Intelligence, executive_office_spec, token_monitoring_spec, claude.md, task.md 등) — 이들은 **설계/명세 문서**라 단순 제외
- docs/reference/ 내부 문서(HLB_수익성엔진 등)
- db/ 의 boss_ai.db, 3pl_command.db (내부 데이터)
- tests/ 의 IP 테스트 전부

---

## 4. 신규 작성

### 4.1 `branding.py` (화이트라벨)
```python
APP_NAME    = "Pharma Watch"        # 제휴사명으로 교체 가능
ORG_NAME    = "Regulatory Intelligence"
LOGO_EMOJI  = "💊"
PRIMARY     = "#0ea5a0"             # 포인트 컬러
FOOTER_NOTE = ("본 시스템의 저작권 및 일체의 지식재산권은 [소유자]에 귀속되며, "
               "사용권만 제공됩니다.")
```
- `pharmacal-pro.html` 의 로고/조직명/포인트색을 이 값으로 주입(또는 외부용 HTML 사본에 반영).
- 제휴사별 배포 시 이 파일만 교체.

### 4.2 외부용 `home.py`
- 내부 command-center home 복사 금지(내부 기능 허브라 IP 노출). **새로 작성** — 캘린더/뉴스/알림/분석가 진입 카드만.

### 4.3 `pages/qa_analyst.py` + `prompts/regulatory_qa_analyst.md`
- 규제/뉴스 항목을 입력받아 **영향 요약 + Action Item**만 출력.
- **VETO·의사결정·원가/전략 접근 없음.** 단일 Haiku 호출, 무료 범위는 배치 요약까지.
- 대화형 질의는 🔒(상위 기능 자리표시).

### 4.4 무료/유료 경계 UI
- 무료: 캘린더·뉴스·알림·Action Item 추천.
- 🔒 상위(보이되 잠금): SOP 자동비교, CAPA 자동작성, 대화형 QA 질의.

---

## 5. 완료 기준 (전부 통과해야 종료)

1. `pharma-watch/` 만으로 `streamlit run app.py` 가 **ImportError 없이** 실행됨.
2. KEEP import 봉쇄 grep(2.1) **0건**.
3. IP 키워드 검사 0건:
   `grep -rni "원가\|수익성\|손익\|제안서\|proposal\|deal\|경쟁사\|competitor\|보령\|협상\|profitab" pharma-watch/`
   → 단, `data_layer/regulatory/seed.py`·뉴스 본문에 규제/기사 텍스트로 우연히 포함된 건 **사람이 눈으로 확인**(IP 아님 확인).
4. `agents/`, `core/meeting_engine`, `engines/profitability_engine`, `engines/proposal_engine`, `discussion/`, `memory/meeting_memory` 등 REMOVE 항목이 폴더에 **물리적으로 존재하지 않음**.
5. db/ 에 boss_ai.db, 3pl_command.db 가 **없음**. 앱은 빈 DB를 새로 생성.
6. 원본 `3pl-command-center/` 폴더의 수정시각이 작업 전후 **변동 없음**.
7. IP 고지 한 줄이 footer·README·app.py 주석 **3곳**에 삽입됨.

---

## 6. 작업 순서

1. (사용자) 빈 `pharma-watch/` 폴더 생성. 읽기 전용 참조용으로 `3pl-command-center` 백업본 1개 준비.
2. (Claude Code) KEEP 목록만 백업본 → `pharma-watch`로 복사.
3. import 봉쇄(2.1) 통과할 때까지 끊기/경량화.
4. branding.py·외부 home·qa_analyst·무료/유료 UI 신규 작성.
5. 완료 기준 1~7 전부 검증.
6. README + IP 고지 삽입.

> 참고: A안에서는 이미 만든 `3pl-command-center_QA`(IP 전부 포함된 통째 복사본)는 **목적지로 쓰지 않는다.** 그건 솎아내기(B안)용이었고, 화이트리스트는 깨끗한 새 폴더에 담는 게 안전하다. `_QA`는 읽기 전용 참조 백업으로만 두거나 폐기.

---

## 7. Claude Code 전달 멘트 (그대로 복사)

> `task-pharma-watch.md` **하나만** 작업 지시서로 삼아. 같은 폴더의 다른 `.md`(Deal_Intelligence, Profitability_Lead, executive_office_spec, token_monitoring_spec 등)는 내부 설계문서이니 **읽지도 참고하지도 마라**. 화이트리스트 방식으로, KEEP 목록의 파일만 새 `pharma-watch/` 폴더에 복사해 외부용 규제 캘린더 앱을 만들어라. REMOVE 항목은 폴더에 존재해서는 안 된다. 원본 `3pl-command-center`는 열지도 수정하지도 마라. 완료 기준 1~7을 모두 통과시키고, 통과 결과(grep 0건·실행 성공)를 보고하라.
