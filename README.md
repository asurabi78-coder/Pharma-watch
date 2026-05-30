# Pharma Watch

의약품 규제 인텔리전스 — **외부 제공용** 경량 앱. 규제 캘린더 · 뉴스 모니터링 ·
규제 검색 · QA 영향도 분석을 제공합니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

선택: `.env` 에 API 키를 넣으면 실데이터/분석이 활성화됩니다.

```
ANTHROPIC_API_KEY=...     # QA 분석가
LAW_GO_KR_API_KEY=...     # 법제처 규제 검색 (없어도 시드 데이터로 동작)
NAVER_NEWS_ID / NAVER_NEWS_SECRET 등  # 뉴스 (없어도 일부 소스 동작)
```

## 구성 (KEEP only)

- `규제 캘린더` — 법령 시행일·식약처 고시·제출 마감·뉴스 캘린더
- `뉴스 모니터링` — 데일리팜·약업신문·물류신문 자동 수집
- `규제 검색` — KGSP/GDP/GMP 원문 검색
- `QA 분석가` — 규제·뉴스의 QA 영향도 + Action Item (VETO 없는 분석 전용)

## 제외 (이 앱에 존재하지 않음)

원가분석·수익성 엔진·제안서·회의실(Boardroom)·Deal Intelligence·내부 손익·
내부 SOP 등 **핵심 IP 는 이 앱에 코드/데이터 자체가 포함되지 않습니다.**
(3PL Command Center 본체에만 존재)

## 화이트라벨

`branding.py` 한 파일의 값(이름·로고·색·조직명)만 바꾸면 제휴사 전용으로 배포됩니다.

## 지식재산권

본 시스템의 저작권 및 일체의 지식재산권은 소유자에 귀속되며, 사용권만 제공됩니다.
