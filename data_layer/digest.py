"""일일 다이제스트 빌더 — '오늘 봐야 할 것'을 한 장으로.

구성:
  (1) 최근 N일 중요(high/mid) 뉴스
  (2) 향후 N일 내 규제 시행/마감 일정 (시드 시행일 + 플레이북 변경)
  (3) 개정 영향 알림 (미확인 SOP 영향 리포트가 있을 때만)

LLM 없이 동작(결정론적). 결과는 마크다운 문자열.
선택적으로 SMTP 로 이메일 발송(.env: PW_SMTP_HOST/PORT/USER/PASS/FROM/TO).
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import List, Optional

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _upcoming_regulatory(window_days: int = 30, today: Optional[datetime] = None) -> List[tuple]:
    """향후 window_days 내 규제 일정. [(date_str, label, title)] 정렬 반환."""
    today = today or datetime.now()
    horizon = today + timedelta(days=window_days)
    out: List[tuple] = []

    def _in_window(d: str) -> bool:
        if not _DATE_RE.match(d):
            return False
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            return False
        return today.date() <= dt.date() <= horizon.date()

    try:
        from data_layer.regulatory.seed import SEED_ENTRIES
        for e in SEED_ENTRIES:
            d = (e.effective_date or "").strip()
            if _in_window(d):
                out.append((d, "시행", e.title))
    except Exception:
        pass

    try:
        from data_layer.regulatory.playbook_seed import PLAYBOOKS
        for pb in PLAYBOOKS:
            for c in getattr(pb, "recent_changes", []):
                d = (getattr(c, "date", "") or "").strip()
                if _in_window(d):
                    out.append((d, getattr(c, "kind", "변경"),
                                getattr(c, "summary", "") or pb.topic))
    except Exception:
        pass

    return sorted(out, key=lambda t: t[0])


def _recent_news(days: int = 1, levels=("high", "mid"), limit: int = 20) -> List:
    try:
        from data_layer.news import repo
        return repo.list_items(days=days, importance_in=list(levels), limit=limit)
    except Exception:
        return []


def build_digest(*, news_days: int = 1, reg_window: int = 30,
                 today: Optional[datetime] = None) -> str:
    """다이제스트 마크다운 생성."""
    today = today or datetime.now()
    stamp = today.strftime("%Y-%m-%d (%a)")
    lines = [f"# 📋 Pharma Watch 데일리 브리핑 — {stamp}", ""]

    # (1) 중요 뉴스
    news = _recent_news(days=news_days)
    high = [n for n in news if getattr(n, "importance", "") == "high"]
    mid = [n for n in news if getattr(n, "importance", "") == "mid"]
    lines.append(f"## 🔴 중요 뉴스 (최근 {news_days}일) — 높음 {len(high)} · 보통 {len(mid)}")
    if not news:
        lines.append("- 해당 기간 중요 뉴스 없음 (또는 수집 전)")
    else:
        for n in high + mid:
            badge = "🔴" if getattr(n, "importance", "") == "high" else "🟠"
            src = getattr(n, "source_label", "")
            when = (getattr(n, "published_at", "") or getattr(n, "fetched_at", ""))[:10]
            lines.append(f"- {badge} [{n.title}]({n.url})  _({src} · {when})_")
    lines.append("")

    # (2) 다가오는 규제 일정
    reg = _upcoming_regulatory(window_days=reg_window, today=today)
    lines.append(f"## 📅 다가오는 규제 일정 (향후 {reg_window}일) — {len(reg)}건")
    if not reg:
        lines.append("- 예정된 규제 일정 없음")
    else:
        for d, kind, title in reg:
            try:
                dleft = (datetime.strptime(d, "%Y-%m-%d").date() - today.date()).days
                dtxt = "오늘" if dleft == 0 else f"D-{dleft}"
            except ValueError:
                dtxt = ""
            lines.append(f"- **{d}** ({dtxt}) · {kind} — {title}")
    lines.append("")

    # (3) 개정 영향 알림 — 미확인 리포트가 있을 때만 섹션 추가
    try:
        from engines.impact_engine import digest_lines
        impact = digest_lines(limit=5)
        if impact:
            lines.extend(impact)
            lines.append("")
    except Exception:
        pass

    lines.append("---")
    lines.append("_결정론적 자동 생성 — Pharma Watch. 상세는 앱에서 확인하세요._")
    return "\n".join(lines)


def send_email(subject: str, body_md: str) -> tuple:
    """SMTP 발송. 성공 (True, msg) / 실패 (False, msg). .env 미설정이면 발송 생략."""
    host = os.getenv("PW_SMTP_HOST", "")
    if not host:
        return False, "PW_SMTP_HOST 미설정 — 이메일 발송 생략 (다이제스트는 생성됨)"
    port = int(os.getenv("PW_SMTP_PORT", "587"))
    user = os.getenv("PW_SMTP_USER", "")
    pw = os.getenv("PW_SMTP_PASS", "")
    sender = os.getenv("PW_SMTP_FROM", user)
    to = os.getenv("PW_SMTP_TO", "")
    if not to:
        return False, "PW_SMTP_TO 미설정 — 수신자 없음"

    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(body_md, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    try:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls()
            if user:
                s.login(user, pw)
            s.sendmail(sender, [x.strip() for x in to.split(",") if x.strip()], msg.as_string())
        return True, f"이메일 발송 완료 → {to}"
    except Exception as e:  # noqa: BLE001
        return False, f"이메일 발송 실패: {type(e).__name__}: {e}"
