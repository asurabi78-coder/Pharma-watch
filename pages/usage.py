"""사용량 (관리자 전용) — 계정별 토큰·비용·기능 사용 집계.

- Claude(AI) 토큰: 계정별 호출수/입력/출력/총합 + 추정 비용.
- 기능(키) 사용: 계정별로 어떤 기능을 주로 쓰는지(=의존 키) 횟수 집계.
- 기간 필터, 원시 이벤트 CSV 내보내기.

접근 통제: ui.auth.is_admin() 이 True 인 경우만. (관리자 = PHARMA_WATCH_ADMINS)
"""
from __future__ import annotations

import csv
import io
import os

import streamlit as st

from data_layer import usage as repo
from ui.auth import is_admin


# 기능 키 → 화면 라벨
FEATURE_LABELS = {
    "home": "홈",
    "pharmacal": "규제 캘린더",
    "newsroom": "뉴스 모니터링",
    "regulatory": "규제 검색",
    "qa_analyst": "QA 분석가",
    "usage": "사용량(관리자)",
}

# 기능 → 주로 쓰는 외부 키/자원 (사용자가 물어본 "주로 사용하는 키" 매핑)
FEATURE_KEY = {
    "qa_analyst": "Claude (ANTHROPIC_API_KEY)",
    "regulatory": "법제처 (LAW_GO_KR_API_KEY)",
    "newsroom": "네이버/크롤링",
    "pharmacal": "— (외부 호출 거의 없음)",
    "home": "—",
    "usage": "—",
}

# ── 추정 단가 (USD / 100만 토큰) ─────────────────────────────
# 주의: 추정값입니다. 실제 청구는 Anthropic 콘솔 기준입니다.
# 환경변수 PHARMA_WATCH_PRICE_IN / PHARMA_WATCH_PRICE_OUT 로 덮어쓸 수 있습니다.
def _price_in() -> float:
    try:
        return float(os.getenv("PHARMA_WATCH_PRICE_IN", "1.0"))
    except ValueError:
        return 1.0


def _price_out() -> float:
    try:
        return float(os.getenv("PHARMA_WATCH_PRICE_OUT", "5.0"))
    except ValueError:
        return 5.0


_RANGE = {"최근 7일": 7, "최근 30일": 30, "최근 90일": 90, "전체": None}


def _label(feature: str) -> str:
    return FEATURE_LABELS.get(feature, feature or "(미상)")


def _est_cost(in_tok: int, out_tok: int) -> float:
    return in_tok / 1_000_000 * _price_in() + out_tok / 1_000_000 * _price_out()


def render() -> None:
    if not is_admin():
        st.title("사용량")
        st.warning("이 페이지는 관리자만 볼 수 있습니다.")
        st.caption(
            "관리자 계정은 환경변수 `PHARMA_WATCH_ADMINS=아이디1,아이디2` 로 지정합니다."
        )
        return

    st.title("사용량 (관리자)")
    st.caption("계정별 Claude 토큰 사용량과 기능(키) 사용 현황을 집계합니다.")

    top = st.columns([2, 3, 3])
    with top[0]:
        range_label = st.selectbox(
            "기간", options=list(_RANGE.keys()), index=1, key="usage_range"
        )
    days = _RANGE[range_label]

    total_events = repo.total_count()
    if total_events == 0:
        st.info(
            "아직 집계된 사용 기록이 없습니다. "
            "로그인 후 각 메뉴를 사용하거나 QA 분석가에서 분석을 실행하면 기록이 쌓입니다."
        )
        return

    # ── 1) 계정별 Claude 토큰 ─────────────────────────────
    st.markdown("### 1. 계정별 Claude 토큰 사용량")
    token_rows = repo.token_summary(days=days)
    if not token_rows:
        st.caption("이 기간에 Claude 호출 기록이 없습니다. (QA 분석가 미사용)")
    else:
        table = []
        sum_in = sum_out = sum_calls = 0
        sum_cost = 0.0
        for r in token_rows:
            cost = _est_cost(r.input_tokens, r.output_tokens)
            sum_in += r.input_tokens
            sum_out += r.output_tokens
            sum_calls += r.calls
            sum_cost += cost
            table.append({
                "계정": r.account,
                "호출수": r.calls,
                "입력 토큰": f"{r.input_tokens:,}",
                "출력 토큰": f"{r.output_tokens:,}",
                "총 토큰": f"{r.total_tokens:,}",
                "추정 비용($)": f"{cost:,.4f}",
            })
        st.dataframe(table, use_container_width=True, hide_index=True)
        m = st.columns(4)
        m[0].metric("총 호출수", f"{sum_calls:,}")
        m[1].metric("총 입력 토큰", f"{sum_in:,}")
        m[2].metric("총 출력 토큰", f"{sum_out:,}")
        m[3].metric("총 추정 비용", f"${sum_cost:,.4f}")
        st.caption(
            f"추정 단가: 입력 ${_price_in()}/1M · 출력 ${_price_out()}/1M (USD). "
            "추정값이며 실제 청구는 Anthropic 콘솔 기준입니다. "
            "환경변수 PHARMA_WATCH_PRICE_IN / PHARMA_WATCH_PRICE_OUT 로 단가를 조정할 수 있습니다."
        )

    st.markdown("---")

    # ── 2) 계정별 주요 기능(키) ───────────────────────────
    st.markdown("### 2. 계정별 주로 쓰는 기능 (= 의존 키)")
    top_map = repo.top_feature_by_account(days=days)
    feat_rows = repo.feature_summary(days=days)
    if not feat_rows:
        st.caption("이 기간에 기능 사용 기록이 없습니다.")
    else:
        # 2-1. 계정별 1위 기능 요약
        summary = []
        for account, (feature, count) in top_map.items():
            summary.append({
                "계정": account,
                "가장 많이 쓴 기능": _label(feature),
                "주요 키": FEATURE_KEY.get(feature, "—"),
                "횟수": count,
            })
        st.markdown("**계정별 1위 기능**")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        # 2-2. 계정 × 기능 상세 횟수
        st.markdown("**계정 × 기능 상세**")
        detail = [{
            "계정": fr.account,
            "기능": _label(fr.feature),
            "주요 키": FEATURE_KEY.get(fr.feature, "—"),
            "횟수": fr.count,
        } for fr in feat_rows]
        st.dataframe(detail, use_container_width=True, hide_index=True)

        # 2-3. 기능별 전체 사용 차트
        agg: dict = {}
        for fr in feat_rows:
            agg[_label(fr.feature)] = agg.get(_label(fr.feature), 0) + fr.count
        chart_data = [{"기능": k, "횟수": v} for k, v in
                      sorted(agg.items(), key=lambda x: x[1], reverse=True)]
        try:
            st.bar_chart(chart_data, x="기능", y="횟수")
        except Exception:
            pass

    st.markdown("---")

    # ── 3) 행동 상세 + 인기 검색어 ────────────────────────
    st.markdown("### 3. 무엇을 했나 (행동 상세)")
    act_rows = repo.action_summary(days=days)
    if not act_rows:
        st.caption("이 기간에 행동 기록이 없습니다. (검색·재수집·분석 실행 시 쌓임)")
    else:
        st.markdown("**계정 × 행동**")
        st.dataframe(
            [{
                "계정": a.account,
                "기능": _label(a.feature),
                "행동": a.action,
                "횟수": a.count,
            } for a in act_rows],
            use_container_width=True, hide_index=True,
        )

    terms = repo.search_terms(days=days, limit=30)
    if terms:
        st.markdown("**인기 검색어·주제 (무엇을 많이 찾나)**")
        st.dataframe(
            [{
                "검색어/주제": t.term,
                "기능": _label(t.feature),
                "횟수": t.count,
            } for t in terms],
            use_container_width=True, hide_index=True,
        )

    st.markdown("---")

    # ── 4) 원시 이벤트 CSV 내보내기 ───────────────────────
    st.markdown("### 4. 원시 기록 내보내기")
    events = repo.all_events(days=days)
    st.caption(f"이 기간 기록 {len(events):,}건")
    if events:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["시각", "계정", "종류", "기능", "행동", "상세", "모델", "입력토큰", "출력토큰"])
        for e in events:
            w.writerow([
                e["created_at"], e["account"], e["kind"], e["feature"],
                e["action"], e["detail"],
                e["model"], e["input_tokens"], e["output_tokens"],
            ])
        st.download_button(
            "CSV 다운로드",
            data=buf.getvalue().encode("utf-8-sig"),
            file_name=f"pharma_watch_usage_{range_label}.csv",
            mime="text/csv",
            use_container_width=True,
        )
