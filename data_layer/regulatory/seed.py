"""규제 데이터 시드 — KGSP/GDP/GMP 대표 샘플.

임시 시드. law.go.kr/MFDS 실연동으로 대체 예정.
시드 항목은 *예시 목적*이며 실제 시행 조문 그대로가 아닐 수 있다 — 사람 검토 필수.
"""
from data_layer.connectors.base import SourceTier
from data_layer.regulatory.models import LawEntry


SEED_ENTRIES = [
    LawEntry(
        id="kgsp_storage",
        title="의약품 등의 안전 및 품질관리에 관한 규정 — 보관 관리",
        grade=SourceTier.LAW,
        article="제○조 보관 관리",
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
        title="의약품 출하 — 출하증명서 발행",
        grade=SourceTier.LAW,
        article="제○조 출하 관리",
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
        title="의약품 안전운송 관리 기준",
        grade=SourceTier.NOTICE,
        article="식약처 고시 제2024-○호",
        effective_date="2024-06-01",
        source="MFDS 법령정보",
        content=(
            "의약품 운송업자는 다음을 갖추어야 한다.\n"
            "1. 운송 중 온도 기록 장치(데이터 로거)\n"
            "2. 일탈 발생 시 알림 시스템\n"
            "3. 운송 SOP 및 운전자 교육 기록"
        ),
        practical_interpretation=(
            "냉장·냉동 운송 차량은 데이터 로거 의무 부착. "
            "로거 단가·유심비·검교정비 등 운송 비용 항목을 사전에 확인할 것."
        ),
        tags=["운송", "콜드체인", "로거", "고시", "MFDS"],
    ),
    LawEntry(
        id="gdp_cold_chain",
        title="WHO Good Distribution Practices — 콜드체인 가이드",
        grade=SourceTier.GUIDE,
        article="GDP §5 (Cold Chain)",
        effective_date="2020-03-15",
        source="MFDS 안내서 / WHO TRS",
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
]
