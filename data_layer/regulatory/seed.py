"""규제 데이터 시드 — KGSP/GDP/GMP 대표 샘플.

임시 시드. law.go.kr/MFDS 실연동으로 대체 예정.
시드 항목은 *예시 목적*이며 실제 시행 조문 그대로가 아닐 수 있다 — 사람 검토 필수.
"""
from data_layer.connectors.base import SourceTier
from data_layer.regulatory.models import LawEntry


SEED_ENTRIES = [
    LawEntry(
        id="kgsp_storage",
        title="의약품 유통품질 관리기준(KGSP) — 보관 관리",
        grade=SourceTier.LAW,
        article="약사법 시행규칙 별표6 (제62조제7호 관련)",
        effective_date="2024-01-01",
        source="law.go.kr / MFDS",
        content=(
            "의약품을 보관하는 자는 다음 사항을 준수하여야 한다.\n"
            "1. 의약품의 품질이 손상되지 않도록 적절한 온도·습도 조건 유지\n"
            "2. 보관조건 일탈 시 즉시 격리하고 품질평가 실시\n"
            "3. 보관시설은 의약품 특성에 따라 구분 운영"
        ),
        practical_interpretation=(
            "콜드체인 운영 시 -20°C 냉동 / 2~8°C 냉장 구역 명확히 구분, "
            "온도 모니터링 시스템 의무. 온도이탈(±2°C 초과) 발생 시 즉시 격리 + 24시간 내 품질팀 보고."
        ),
        tags=["KGSP", "보관", "온도", "콜드체인", "품질관리"],
    ),
    LawEntry(
        id="kgsp_release",
        title="의약품 출하 — 출하증명서 발행 (KGSP)",
        grade=SourceTier.LAW,
        article="약사법 시행규칙 별표6 (의약품 유통품질 관리기준)",
        effective_date="2024-01-01",
        source="law.go.kr / MFDS",
        content=(
            "의약품 출하 시 다음 사항을 기재한 출하증명서를 발행하여야 한다.\n"
            "1. 제품명·제조번호·유효기간\n"
            "2. 보관조건 및 운송조건\n"
            "3. 출하일자 및 수령자\n"
            "4. 책임자 서명"
        ),
        practical_interpretation=(
            "위탁 3PL은 위탁자(제약사) 명의 출하증명서를 발행하되, 책임 구조는 SLA 에 명시. "
            "온도 로거 기록을 출하증명서에 첨부하는 것이 관행."
        ),
        tags=["KGSP", "출하", "출하증명서", "책임", "위탁"],
    ),
    LawEntry(
        id="mfds_transport",
        title="생물학적 제제 등 보관 및 수송 관리 가이드라인",
        grade=SourceTier.GUIDE,
        article="식약처 민원인 안내서 · 2023-12-28 개정 (법적 근거: 생물학적 제제 등의 제조ㆍ판매관리 규칙)",
        effective_date="2023-12-28",
        source="MFDS 민원인 안내서",
        content=(
            "생물학적 제제 등의 보관·수송 시 다음을 갖추어야 한다.\n"
            "1. 보관시설·수송차량·수송용기 내부에 자동온도기록장치 설치\n"
            "2. 수송용기 외부 온도계 부착, 적정 온도 유지 구조·장치 사전 검증\n"
            "3. 자동온도기록장치 검정·교정 후 기록 2년 보관\n"
            "4. 제품을 바닥에 직접 닿지 않게 보관"
        ),
        practical_interpretation=(
            "냉장·냉동 수송 차량·용기는 자동온도기록장치 의무. "
            "로거 단가·유심비·검교정비 등 수송 비용 항목을 사전 확인. "
            "일시적 온도 일탈 시 과학적 입증(안정성 데이터) 자료를 함께 보관."
        ),
        tags=["수송", "콜드체인", "로거", "생물학적제제", "MFDS", "가이드라인"],
    ),
    LawEntry(
        id="gdp_cold_chain",
        title="WHO TRS 961 Annex 9 — 온도민감 의약품 보관·수송 가이드",
        grade=SourceTier.GUIDE,
        article="WHO TRS 961, Annex 9 (2011)",
        effective_date="2011-01-01",
        source="WHO TRS 961, Annex 9",
        content=(
            "콜드체인 의약품 유통자는:\n"
            "1. 검증된 보관·운송 조건 유지\n"
            "2. 온도 매핑(temperature mapping) 연 1회 실시\n"
            "3. 백업 전원 / 비상 대응 계획\n"
            "4. 운송 검증 (transport validation) 문서화"
        ),
        practical_interpretation=(
            "가이드는 법적 의무는 아니지만 인증·실사 시 적용. "
            "GDP 인증 신청 시 transport validation 보고서가 핵심 자료."
        ),
        tags=["GDP", "콜드체인", "validation", "WHO", "가이드"],
    ),
    LawEntry(
        id="gmp_deviation",
        title="GMP 일탈 관리 (Deviation Management)",
        grade=SourceTier.GUIDE,
        article="GMP Annex - Deviation",
        effective_date="2023-01-01",
        source="MFDS 안내서",
        content=(
            "일탈 발생 시:\n"
            "1. 즉시 격리 및 기록\n"
            "2. 영향 평가 (Impact Assessment)\n"
            "3. CAPA (Corrective and Preventive Action) 수립\n"
            "4. 품질팀 승인 후 처리"
        ),
        practical_interpretation=(
            "3PL 운영 중 일탈(온도이탈/포장 손상 등)은 24시간 내 위탁자 통보 + 7일 내 CAPA 초안. "
            "품질 책임자(QA) 검토 후 종결."
        ),
        tags=["GMP", "일탈", "CAPA", "품질"],
    ),
    LawEntry(
        id="sop_temp_excursion",
        title="SOP 예시 — 온도 이탈 대응 절차",
        grade=SourceTier.INTERNAL,
        article="SOP-QA-001 (예시)",
        effective_date="2025-03-01",
        source="품질 SOP 예시",
        content=(
            "온도 이탈 감지 시:\n"
            "1. 즉시 해당 의약품 격리 (노란색 라벨)\n"
            "2. 데이터 로거 기록 다운로드 및 보존\n"
            "3. 품질팀 즉시 통지 (전화 + 이메일)\n"
            "4. 위탁자(제약사)에 24시간 내 서면 통보\n"
            "5. CAPA 작성 → 5년 보관"
        ),
        practical_interpretation=(
            "SOP 예시이므로 위탁자 SLA 와 충돌 시 SLA 우선 적용. "
            "감사 시 본 SOP가 KGSP/GDP 요구사항 충족 증빙으로 사용됨."
        ),
        tags=["SOP", "온도이탈", "CAPA", "예시"],
    ),
    LawEntry(
        id="ai_estimate_sample",
        title="(AI 추정) 신규 바이오의약품 보관 기준 — 데이터 부재 추정",
        grade=SourceTier.AI,
        article="—",
        effective_date="—",
        source="AI 추정 (공식 출처 없음)",
        content=(
            "AI 분석: 유사 분자량/안정성 제품군 기준 추정. "
            "공식 가이드라인 공개 전이므로 본 내용은 *추정*이며 실무 적용 불가."
        ),
        practical_interpretation=(
            "⚠️ 데이터 부재 — 반드시 위탁자에게 보관 기준 명문 요청 + 추가 검증 필요. "
            "본 항목을 의사결정 근거로 사용 금지."
        ),
        tags=["AI", "추정", "확인필요"],
    ),
    # ── 확장 시드 (2026-06): 검색 0건 키워드 보강 ──────────────────────────
    LawEntry(
        id="narcotics_storage",
        title="마약류 보관·관리 기준 (마약류관리법)",
        grade=SourceTier.LAW,
        article="마약류 관리에 관한 법률 제15조·시행규칙 제26조",
        effective_date="2024-06-01",
        source="law.go.kr / 식약처",
        content=(
            "마약류취급자는 다음을 준수하여야 한다.\n"
            "1. 마약·향정신성의약품은 이중 잠금장치가 있는 견고한 장소(철제금고 등)에 저장\n"
            "2. 저장시설은 일반 의약품과 구분, 출입 통제 및 CCTV 권장\n"
            "3. 입·출고 및 재고를 마약류통합관리시스템(NIMS)에 보고\n"
            "4. 사고(분실·도난·변질) 발생 시 즉시 관할 기관 보고"
        ),
        practical_interpretation=(
            "3PL 창고에서 마약류 취급 시 별도 이중잠금 보관소 + NIMS 보고 체계 필수. "
            "재고 실사 불일치는 사고마약류로 간주될 수 있어 일·월 단위 재고대사 SOP 필요."
        ),
        tags=["마약류", "NIMS", "보관", "재고", "보안", "법령"],
    ),
    LawEntry(
        id="inventory_expiry",
        title="재고·유효기간 관리 (선입선출/사용기한)",
        grade=SourceTier.GUIDE,
        article="KGSP 별표6 · GDP 재고관리 원칙",
        effective_date="2024-01-01",
        source="MFDS / WHO GDP",
        content=(
            "의약품 재고 관리 시:\n"
            "1. 선입선출(FEFO, 유효기간 우선) 원칙 적용\n"
            "2. 유효기간 임박품(통상 잔여 6개월 이내) 별도 식별·관리\n"
            "3. 사용기한 경과품은 즉시 격리 후 판매 가능 재고와 분리\n"
            "4. 정기 재고실사 및 전산-실물 일치 관리"
        ),
        practical_interpretation=(
            "WMS 에 유효기간(로트) 단위 관리 + FEFO 피킹 로직 필수. "
            "유효기간 임박 알림 자동화로 반품·폐기 손실 최소화. 실사 불일치 원인분석 기록 보관."
        ),
        tags=["재고", "유효기간", "FEFO", "선입선출", "실사", "WMS"],
    ),
    LawEntry(
        id="returns_management",
        title="반품 의약품 처리 기준",
        grade=SourceTier.GUIDE,
        article="KGSP 유통품질 관리기준 — 반품",
        effective_date="2024-01-01",
        source="law.go.kr / MFDS",
        content=(
            "반품된 의약품은 다음에 따라 처리한다.\n"
            "1. 반품품은 즉시 별도 구역에 격리(판매 가능 재고와 물리적 분리)\n"
            "2. 보관조건 이탈 여부·포장 상태·유효기간을 품질책임자가 평가\n"
            "3. 재판매(재입고) 가능 여부는 품질책임자 판정 후에만 결정\n"
            "4. 부적합 반품품은 폐기 절차에 따라 처리·기록"
        ),
        practical_interpretation=(
            "콜드체인 제품 반품은 온도이력 입증이 안 되면 원칙적으로 재판매 불가. "
            "반품 격리구역과 재판매 판정 SOP, 폐기 증빙(폐기물 처리 위탁계약) 구비 필요."
        ),
        tags=["반품", "재판매", "격리", "폐기", "품질책임자"],
    ),
    LawEntry(
        id="recall_procedure",
        title="의약품 회수·폐기 절차 (위해성 등급 회수)",
        grade=SourceTier.LAW,
        article="약사법 제39조 · 의약품 회수·폐기 등에 관한 규정",
        effective_date="2024-03-01",
        source="law.go.kr / 식약처 고시",
        content=(
            "회수 대상 의약품 발생 시:\n"
            "1. 위해성 등급(1~3등급)에 따라 회수계획서 보고\n"
            "2. 1등급은 24시간 내, 2등급 48시간, 3등급 72시간 내 회수 착수\n"
            "3. 유통·판매처에 회수 사실 통보 및 반송 회수\n"
            "4. 회수 종료 후 결과보고서 제출, 회수품 폐기 기록 보관"
        ),
        practical_interpretation=(
            "3PL 은 위탁자 회수 발생 시 즉시 출고 중지 + 해당 로트 재고 동결 + 추적(traceability) 자료 제공. "
            "로트별 입출고 이력 추적이 안 되면 회수 대응이 지연되므로 로트 추적 체계 필수."
        ),
        tags=["회수", "리콜", "폐기", "위해성등급", "추적", "법령"],
    ),
    LawEntry(
        id="change_control",
        title="변경관리 (Change Control)",
        grade=SourceTier.GUIDE,
        article="GMP/GDP 품질시스템 — 변경관리",
        effective_date="2023-01-01",
        source="MFDS 안내서",
        content=(
            "보관·운송·설비·공급망 등 변경 시:\n"
            "1. 변경 요청서 작성 및 영향평가\n"
            "2. 품질에 미치는 영향 검토 후 승인\n"
            "3. 필요 시 재검증(re-validation) 수행\n"
            "4. 변경 이력 문서화 및 관련자 교육"
        ),
        practical_interpretation=(
            "창고 이전·운송사 변경·온도설비 교체는 변경관리 대상. "
            "위탁자 사전 승인 없이 변경 시 SLA 위반·인증 리스크. 변경 전 영향평가서 위탁자 공유 권장."
        ),
        tags=["변경관리", "change control", "재검증", "위탁", "품질시스템"],
    ),
    LawEntry(
        id="contract_outsourcing",
        title="위·수탁 관리 기준 (품질 위·수탁)",
        grade=SourceTier.LAW,
        article="약사법 시행규칙 · 의약품 제조·품질관리 위수탁 기준",
        effective_date="2024-01-01",
        source="law.go.kr / MFDS",
        content=(
            "품질 업무를 위·수탁하는 경우:\n"
            "1. 위·수탁 범위·책임을 명시한 품질계약서(Quality Agreement) 체결\n"
            "2. 수탁자의 적격성 평가(실사 등) 및 주기적 점검\n"
            "3. 위탁자는 수탁자 업무에 대한 최종 품질책임 보유\n"
            "4. 변경·일탈 발생 시 상호 통보 절차 명문화"
        ),
        practical_interpretation=(
            "3PL 보관·운송 수탁 시 Quality Agreement + SLA 동시 관리. "
            "위탁자 정기 실사(audit) 대응 체크리스트, 일탈 통보 SLA(예: 24시간) 사전 합의 필요."
        ),
        tags=["위탁", "수탁", "품질계약", "Quality Agreement", "실사", "SLA"],
    ),
    LawEntry(
        id="self_inspection",
        title="자체점검·실태조사 대응 (Self-inspection/Audit)",
        grade=SourceTier.GUIDE,
        article="KGSP/GDP — 자체점검",
        effective_date="2024-01-01",
        source="MFDS 안내서 / WHO GDP",
        content=(
            "유통품질 시스템 유지를 위해:\n"
            "1. 연 1회 이상 자체점검(self-inspection) 실시\n"
            "2. 점검 결과 부적합 사항에 대한 CAPA 수립·이행\n"
            "3. 식약처 실태조사(정기/수시) 대비 문서·기록 상시 구비\n"
            "4. 점검·시정 이력 문서 보관"
        ),
        practical_interpretation=(
            "실태조사 단골 지적: 온도기록 누락, 교육이수 미비, SOP 최신화 미흡, 일탈 종결 지연. "
            "연 1회 자체점검 체크리스트 + CAPA 추적표로 상시 대비. 제출자료 마감 관리 필요."
        ),
        tags=["실태조사", "자체점검", "audit", "CAPA", "자료제출", "점검"],
    ),
    # ── 공식 법령 보강 (2026-06): 법령명 검색 정확도 — 정식명칭·법제처 permalink ──
    LawEntry(
        id="law_pharm_act", title="약사법", grade=SourceTier.LAW,
        canonical_title="약사법",
        aliases=["약사법", "의약품 도매상", "의약품 유통", "약사법 도매상"],
        document_type="법률", issuing_authority="식품의약품안전처",
        official_source_url="https://www.law.go.kr/법령/약사법",
        current_status="현행", origin="domestic", article="약사법",
        effective_date="2024-01-01", source="국가법령정보센터",
        content="의약품의 제조·수입·유통·판매 및 약사(藥事)에 관한 사항을 규율하는 기본 법률. 의약품 도매상 허가·관리, 회수·폐기 등의 근거 조항을 포함한다.",
        practical_interpretation="유통·도매 업무의 상위 근거 법률. 구체 기준은 시행령·시행규칙·고시로 위임된다.",
        scope_tags=["유통", "도매", "허가", "회수", "관리약사"],
        tags=["약사법", "유통", "도매상", "허가", "법령"],
        related_ids=["law_pharm_rule"],
    ),
    LawEntry(
        id="law_pharm_rule", title="약사법 시행규칙", grade=SourceTier.LAW,
        canonical_title="약사법 시행규칙",
        aliases=["KGSP", "의약품 유통품질 관리기준", "유통품질관리기준", "약사법 시행규칙 별표6"],
        document_type="시행규칙", issuing_authority="식품의약품안전처",
        official_source_url="https://www.law.go.kr/법령/약사법 시행규칙",
        current_status="현행", origin="domestic",
        article="약사법 시행규칙 (별표6 의약품 유통품질 관리기준 등)",
        effective_date="2024-01-01", source="국가법령정보센터",
        content="약사법의 위임에 따른 세부 기준. 별표6 「의약품 유통품질 관리기준(KGSP)」으로 보관·운송·출하·반품 등 유통품질 요건을 규정한다.",
        practical_interpretation="KGSP(유통품질 관리기준)의 법적 근거. 보관·운송·반품·출하증명 실무 기준의 출발점.",
        scope_tags=["KGSP", "유통품질", "보관", "운송", "반품", "출하"],
        tags=["약사법 시행규칙", "KGSP", "유통품질", "별표6", "법령"],
        related_ids=["law_pharm_act", "kgsp_storage", "returns_management"],
    ),
    LawEntry(
        id="law_safety_rule", title="의약품 등의 안전에 관한 규칙", grade=SourceTier.LAW,
        canonical_title="의약품 등의 안전에 관한 규칙",
        aliases=["안전규칙", "의약품 안전 규칙", "의약품등의 안전에 관한 규칙"],
        document_type="시행규칙", issuing_authority="식품의약품안전처",
        official_source_url="https://www.law.go.kr/법령/의약품 등의 안전에 관한 규칙",
        current_status="현행", origin="domestic",
        article="의약품 등의 안전에 관한 규칙",
        effective_date="2024-01-01", source="국가법령정보센터",
        content="의약품 등의 제조·품질관리·안전관리에 관한 세부 사항을 정한 총리령. 품질관리·기록유지·안전성 관련 요건을 포함한다.",
        practical_interpretation="제조·품질·안전관리의 핵심 시행규칙. 보관·운송 품질관리·기록 유지 근거로 자주 인용된다.",
        scope_tags=["안전관리", "품질관리", "기록", "보관", "운송"],
        tags=["의약품 등의 안전에 관한 규칙", "품질관리", "안전", "법령"],
        related_ids=["law_pharm_rule"],
    ),
    LawEntry(
        id="law_bio_rule", title="생물학적제제 등의 제조ㆍ판매관리 규칙", grade=SourceTier.LAW,
        canonical_title="생물학적제제 등의 제조ㆍ판매관리 규칙",
        aliases=["생물학적제제 제조 및 판매 관리 규칙", "생물학적제제 판매관리", "생물학적제제 규칙", "생물학적제제 제조판매관리"],
        document_type="규칙", issuing_authority="식품의약품안전처",
        official_source_url="https://www.law.go.kr/법령/생물학적제제 등의 제조ㆍ판매관리 규칙",
        current_status="현행", origin="domestic",
        article="생물학적제제 등의 제조ㆍ판매관리 규칙",
        effective_date="2023-12-28", source="국가법령정보센터",
        content="백신·혈액제제 등 생물학적제제의 제조·판매·보관·수송 관리 기준을 정한 규칙. 자동온도기록장치·콜드체인 요건의 법적 근거.",
        practical_interpretation="생물학적제제 보관·수송(콜드체인)의 법적 근거. 식약처 민원인 안내서가 이를 해설한다.",
        scope_tags=["생물학적제제", "백신", "콜드체인", "보관", "수송"],
        tags=["생물학적제제", "제조판매관리규칙", "콜드체인", "백신", "법령"],
        related_ids=["mfds_transport"],
    ),
]
