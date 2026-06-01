"""주제 플레이북 시드 — 검증 콘텐츠 우선, 주제는 깊게 적게.

  - 온도 이탈     : 완전 작성 ← 1순위 증명 대상
  - 출하증명       : 골격
  - 백신·BRC      : 골격

주의: url 은 예시. 실제 상세링크는 LawGoKrConnector 가 돌려주는 rec.url 사용 권장.
체크리스트·감사질문은 사람(QA) 검증 전까지 last_reviewed_* 가 비어 있음.
"""
from __future__ import annotations

from data_layer.connectors.base import SourceTier
from data_layer.regulatory.playbook import (
    AuditQuestion,
    ChecklistItem,
    KnownIssue,
    Provenance,
    RecentChange,
    ReferenceLink,
    RegRef,
    TopicPlaybook,
)


_LAW = "https://www.law.go.kr/LSW/lsSc.do?menuId=1&query="
_ADM = "https://www.law.go.kr/LSW/admRulSc.do?menuId=5&query="


TEMP_EXCURSION = TopicPlaybook(
    id="temp_excursion",
    topic="온도 이탈",
    summary=(
        "보관·운송 중 허용 온도 범위를 벗어난 상황. 콜드체인 3PL 에서 가장 빈번하고, "
        "위탁자 통보 기한·격리·CAPA 가 한 묶음으로 걸린다."
    ),
    overview=(
        "콜드체인은 의약품을 제조부터 환자 전달까지 규정 온도(2~8℃ 냉장, −20℃ 이하 냉동 등)로 "
        "유지·운송하는 체계다. 「약사법」과 그 하위 「의약품 등의 안전 및 품질관리에 관한 규정」(KGSP)이 "
        "보관·운송 품질의 법적 근거이며, 생물학적제제는 별도 관리 규칙이 추가 적용된다."
    ),
    aliases=["온도이탈", "온도 일탈", "일탈", "excursion", "콜드체인", "보관 온도", "온도"],
    reg_refs=[
        RegRef(
            title="약사법",
            tier=SourceTier.LAW,
            article="의약품 유통·품질관리의 모법(母法)",
            url=_LAW + "약사법",
            provenance=Provenance.AUTO,
        ),
        RegRef(
            title="의약품 등의 안전 및 품질관리에 관한 규정 — 보관 관리",
            tier=SourceTier.LAW,
            article="제○조(보관 관리)",
            url=_LAW + "의약품 등의 안전 및 품질관리에 관한 규정",
            effective_date="2024-01-01",
            law_entry_id="kgsp_storage",
            provenance=Provenance.AUTO,
        ),
        RegRef(
            title="의약품 안전운송 관리 기준 (식약처 고시)",
            tier=SourceTier.NOTICE,
            article="식약처 고시 제2024-○호",
            url=_ADM + "의약품 안전운송 관리 기준",
            effective_date="2024-06-01",
            law_entry_id="mfds_transport",
            provenance=Provenance.AUTO,
        ),
        RegRef(
            title="WHO GDP — 콜드체인 가이드",
            tier=SourceTier.GUIDE,
            article="GDP §5 (Cold Chain)",
            url="https://www.who.int/publications/i/item/WHO-TRS-961",
            effective_date="2020-03-15",
            law_entry_id="gdp_cold_chain",
            key_points=[
                "온도 유지·검증(Qualification/Validation): 보관소·냉장/냉동 차량·수송용기는 IQ/OQ/PQ 로 사전 검증. 2~8℃ 또는 −25~−15℃ 등 제품별 온도 범위 이탈 금지.",
                "온도 매핑(Temperature Mapping): 보관 창고 위치별 온도 편차 파악을 위해 최소 연 1회 매핑 → 안전 보관 구역 설정.",
                "실시간 모니터링: 보관·운송 전 과정 온도 기록계 부착, 환경 지속 모니터링 + 기록 보관.",
                "운송 포장 검증(Packaging Validation): 단열 수송 용기 사용, 계절별 외부 온도 변화를 견디는지 테스트.",
            ],
            provenance=Provenance.AUTO,
        ),
    ],
    reference_links=[
        ReferenceLink(
            title="WHO TRS — Good Distribution Practices for pharmaceutical products",
            url="https://www.who.int/publications/i/item/WHO-TRS-961",
            source="WHO",
            note="콜드체인 보관·운송·검증의 국제 기준 원문(PDF).",
        ),
        ReferenceLink(
            title="식약처 의약품 우수유통관리기준(KGSP) 안내서",
            url="https://www.mfds.go.kr",
            source="MFDS",
            note="국내 유통품질관리기준 해설 — 냉장·냉동 보관, 출하 온도 검수 의무.",
        ),
        ReferenceLink(
            title="PIC/S GDP Guide (PE 011)",
            url="https://picscheme.org/en/publications",
            source="PIC/S",
            note="실사 대응 시 자주 참조되는 국제 GDP 가이드.",
        ),
    ],
    web_query="콜드체인 의약품 온도",
    recent_changes=[
        RecentChange(
            date="2026-06-06",
            kind="개정 예고",
            summary="콜드체인 보관·운송 가이드라인 개정 — 2~8℃ 온도 일탈 보고 절차 강화, 운송 중 모니터링 데이터 보관기간 명시.",
            url=_ADM + "콜드체인 보관 운송 가이드라인",
            provenance=Provenance.AUTO,
        ),
    ],
    common_issues=[
        KnownIssue(name="냉장차량 온도 일탈", keyword="운송 온도"),
        KnownIssue(name="데이터 로거 기록 누락", keyword="데이터 로거"),
        KnownIssue(name="격리 지연 / 격리 라벨 누락", keyword="격리"),
    ],
    audit_questions=[
        AuditQuestion(
            question="온도 일탈 발생 시 격리·통보·CAPA 까지의 타임라인을 증빙할 수 있습니까?",
            hint="일탈 로그 + 격리 사진/라벨 + 위탁자 통보 이메일 타임스탬프 + CAPA 번호를 한 세트로 준비.",
        ),
        AuditQuestion(
            question="운송 온도 모니터링(데이터 로거) 검교정 기록이 있습니까?",
            hint="로거 검교정 성적서 + 주기 + 검교정 기관.",
        ),
        AuditQuestion(
            question="온도 Mapping(매핑)을 연 1회 이상 수행했습니까?",
            hint="보관소·차량별 매핑 보고서 + 최근 수행일.",
        ),
    ],
    checklist=[
        ChecklistItem(
            action="해당 의약품 즉시 격리 (노란색 라벨)",
            detail="물리적 격리 + 시스템 상태 변경. 출하 차단.",
            related_sop_id="SOP-QA-001",
        ),
        ChecklistItem(
            action="데이터 로거 기록 다운로드·보존",
            detail="원본 로그 보존(가공 금지) + 일탈 구간 캡처.",
            related_sop_id="SOP-QA-001",
        ),
        ChecklistItem(
            action="품질팀 즉시 통지 (전화 + 이메일)",
            detail="감지 시점 기준 지체 없이.",
            related_sop_id="SOP-QA-001",
        ),
        ChecklistItem(
            action="위탁자(제약사)에 24시간 내 서면 통보",
            detail="SLA 에 더 짧은 기한이 있으면 SLA 우선.",
        ),
        ChecklistItem(
            action="CAPA 작성 → 7일 내 초안, 5년 보관",
            detail="QA·GDP Director 검토 후 종결.",
        ),
    ],
    related_sop_ids=["SOP-QA-001"],
    report_deadline="감지 즉시 격리·품질팀 통지 → 24h 내 위탁자 서면 통보 → 7일 내 CAPA 초안 (SLA 우선)",
    audit_impact="높음",
    requires_human_review=True,
    last_reviewed_by="",
    last_reviewed_at="",
)


RELEASE_CERT = TopicPlaybook(
    id="release_cert",
    topic="출하증명",
    summary="의약품 출하 시 출하증명서 발행·보관. 위탁 3PL 의 책임 구조가 SLA 와 얽힌다.",
    overview=(
        "출하증명서는 의약품 출하 시 제품명·제조번호·유효기간·보관/운송조건·책임자를 기재해 발행하는 "
        "품질 증빙 문서다. 「약사법」과 KGSP 가 근거이며, 위탁 3PL 은 위탁자(제약사) 명의로 발행하되 "
        "책임 구조를 SLA 에 명시한다."
    ),
    aliases=["출하증명", "출하증명서", "release certificate"],
    web_query="의약품 출하증명서",
    reg_refs=[
        RegRef(
            title="의약품 출하 — 출하증명서 발행",
            tier=SourceTier.LAW,
            article="제○조(출하 관리)",
            url=_LAW + "의약품 출하증명",
            effective_date="2024-01-01",
            law_entry_id="kgsp_release",
            provenance=Provenance.AUTO,
        ),
    ],
    reference_links=[
        ReferenceLink(
            title="식약처 의약품 우수유통관리기준(KGSP) 안내서",
            url="https://www.mfds.go.kr",
            source="MFDS",
            note="출하증명서 기재사항·보관기간 관련 해설.",
        ),
    ],
    common_issues=[KnownIssue(name="출하증명서 보관기간", keyword="출하증명")],
    audit_questions=[
        AuditQuestion(question="위탁자 명의 출하증명서 발행 권한·책임이 SLA 에 명시돼 있습니까?"),
    ],
    checklist=[
        ChecklistItem(action="제품명·제조번호·유효기간 기재 확인"),
        ChecklistItem(action="온도 로거 기록 첨부"),
        ChecklistItem(action="책임자 서명 + 보관기간 확인"),
    ],
    report_deadline="",
    audit_impact="중간",
    requires_human_review=True,
)


VACCINE_BRC = TopicPlaybook(
    id="vaccine_brc",
    topic="백신·생물학적제제",
    summary="생물학적제제의 출하·회수·온도관리. BRC(배치기록) 관리와 출하증명서 보관이 핵심.",
    overview=(
        "생물학적제제(백신 등)는 콜드체인 보관·운송에 더해 배치기록(BRC) 관리·회수·출하증명 보관이 "
        "핵심이다. 「약사법」과 「생물학적 제제 등의 제조ㆍ판매관리 규칙」(총리령) 등이 적용된다."
    ),
    aliases=["백신", "생물학적제제", "BRC", "회수", "생물학적"],
    web_query="백신 생물학적제제 콜드체인",
    reg_refs=[
        RegRef(
            title="약사법",
            tier=SourceTier.LAW,
            article="의약품 유통·품질관리의 모법(母法)",
            url=_LAW + "약사법",
            provenance=Provenance.AUTO,
        ),
        RegRef(
            title="생물학적 제제 등의 제조ㆍ판매관리 규칙",
            tier=SourceTier.LAW,
            article="총리령 · 시행 2023-02-20",
            url=_LAW + "생물학적 제제 등의 제조ㆍ판매관리 규칙",
            effective_date="2023-02-20",
            provenance=Provenance.AUTO,
        ),
        RegRef(
            title="의약품 등의 안전 및 품질관리에 관한 규정 — 보관 관리",
            tier=SourceTier.LAW,
            article="제○조(보관 관리)",
            url=_LAW + "의약품 등의 안전 및 품질관리에 관한 규정",
            effective_date="2024-01-01",
            law_entry_id="kgsp_storage",
            provenance=Provenance.AUTO,
        ),
    ],
    reference_links=[
        ReferenceLink(
            title="WHO TRS — GDP for pharmaceutical products",
            url="https://www.who.int/publications/i/item/WHO-TRS-961",
            source="WHO",
            note="생물학적제제 콜드체인 검증의 국제 기준.",
        ),
    ],
    recent_changes=[
        RecentChange(
            date="2026-06-20",
            kind="행정 예고",
            summary="바이오의약품 콜드체인 모니터링 의무화 행정예고 — 의견수렴 중.",
            url=_ADM + "바이오의약품 콜드체인 모니터링",
            provenance=Provenance.AUTO,
        ),
    ],
    common_issues=[
        KnownIssue(name="BRC 회수 확인", keyword="회수"),
        KnownIssue(name="출하증명서 보관", keyword="출하증명"),
    ],
    audit_questions=[
        AuditQuestion(question="배치별 BRC 회수·보관이 추적 가능합니까?"),
    ],
    checklist=[
        ChecklistItem(action="BRC 회수 확인"),
        ChecklistItem(action="보관기간 확인"),
        ChecklistItem(action="반품 처리 확인"),
    ],
    report_deadline="",
    audit_impact="높음",
    requires_human_review=True,
)


PLAYBOOKS = [TEMP_EXCURSION, RELEASE_CERT, VACCINE_BRC]


def get_playbook(topic_or_alias: str) -> TopicPlaybook | None:
    """주제명 또는 alias 로 플레이북 조회 (대소문자·공백 무시 매칭)."""
    q = (topic_or_alias or "").strip().lower().replace(" ", "")
    if not q:
        return None
    for pb in PLAYBOOKS:
        keys = [pb.id, pb.topic] + pb.aliases
        if any(q == k.strip().lower().replace(" ", "") for k in keys):
            return pb
    for pb in PLAYBOOKS:
        keys = [pb.topic] + pb.aliases
        if any(q in k.strip().lower().replace(" ", "") for k in keys):
            return pb
    return None
