"""SOP 생성기 — 회사 정보만 입력하면 KGSP 충족 SOP 초안을 워드로.

회사 양식(docx)을 올리면 머리글·바닥글·페이지 설정을 그대로 유지한 채
본문만 새 내용으로 채운다. 양식이 없으면 표준 양식으로 생성.

산출물은 '초안' — 시행 전 품질책임자(관리약사) 검토·승인 필수.
"""
import streamlit as st

import branding
from engines import exam_engine as ee  # 주제 목록 재사용 (collect_topics)
from engines import sop_gen as sg


def _user() -> str:
    try:
        from ui.auth import current_user
        return current_user() or "(local)"
    except Exception:
        return "(local)"


def render():
    st.title("SOP 생성기")
    st.caption(
        "회사 정보와 주제를 고르면 KGSP 요구사항을 충족하는 SOP 초안을 만듭니다. "
        "회사 양식(docx)을 올리면 그 서식을 유지합니다. (초안 — 시행 전 QA 검토·승인 필수)"
    )

    topics = ee.collect_topics()
    topic_labels = [t[1] for t in topics]

    template = st.file_uploader(
        "회사 양식 업로드 (선택, docx) — 머리글·바닥글·페이지 설정이 유지됩니다",
        type=["docx"], key="sopgen_template",
    )

    with st.form("sopgen_form"):
        c1, c2 = st.columns(2)
        with c1:
            company = st.text_input("회사명", placeholder="예: ○○약품(주)")
            doc_no = st.text_input("문서번호 (선택)", placeholder="예: SOP-WH-001")
            version = st.text_input("개정번호", value="1.0")
        with c2:
            handles = st.multiselect(
                "취급 유형",
                ["상온 의약품", "냉장(2~8℃)", "냉동(-20℃)", "생물학적제제", "마약류·향정"],
                default=["상온 의약품"],
            )
            sop_title = st.text_input("SOP 제목", value="의약품 보관관리 표준작업절차서")

        sel = st.multiselect(
            "포함할 규제 주제 (비우면 보관·출하·일탈 기본 3종)",
            options=list(range(len(topics))),
            format_func=lambda i: topic_labels[i],
        )
        topic_ids = [topics[i][0] for i in sel] if sel else None

        extra = st.text_input("추가 요청 (선택)",
                              placeholder="예: 3PL 위탁 출고 절차 포함, 야간 입고 상황 반영")
        use_claude = st.checkbox(
            "Claude 로 구체적 절차 문장 생성 (키 필요 — 실패 시 기본 골격으로 자동 대체)",
            value=True,
        )
        submitted = st.form_submit_button("📄 SOP 초안 생성", type="primary")

    if submitted:
        with st.spinner("SOP 초안 작성 중…"):
            if use_claude:
                sections, mode = sg.build_with_claude(
                    company=company, topic_ids=topic_ids,
                    handles=handles, extra_request=extra)
            else:
                sections, mode = sg.build_skeleton(
                    company=company, topic_ids=topic_ids, handles=handles), "skeleton"
        st.session_state["sopgen_sections"] = sections
        st.session_state["sopgen_meta"] = dict(
            company=company, doc_no=doc_no, version=version,
            sop_title=sop_title, mode=mode,
            template=template.getvalue() if template else None,
        )
        try:
            from data_layer import usage as _usage
            _usage.log_action(_user(), "sop_generator", "초안 생성",
                              f"{sop_title[:30]} · {mode}")
        except Exception:
            pass

    sections = st.session_state.get("sopgen_sections")
    meta = st.session_state.get("sopgen_meta", {})
    if not sections:
        return

    st.markdown("---")
    mode_label = {"claude": "🤖 Claude 생성", "fallback": "⚙️ 기본 골격(폴백)",
                  "skeleton": "⚙️ 기본 골격"}.get(meta.get("mode"), "")
    tpl_label = " · 회사 양식 적용" if meta.get("template") else ""
    st.markdown(f"### 미리보기 — {len(sections)}개 조항  {mode_label}{tpl_label}")

    for heading, body in sections:
        with st.container(border=True):
            st.markdown(f"**{heading}**")
            st.markdown(body.replace("\n", "  \n"))

    try:
        from utils.docx_builder import build_sop_docx
        data = build_sop_docx(
            sections,
            sop_title=meta.get("sop_title", "표준작업절차서(SOP)"),
            company=meta.get("company", ""),
            doc_no=meta.get("doc_no", ""),
            version=meta.get("version", "1.0"),
            template_bytes=meta.get("template"),
        )
        fname = f"{meta.get('sop_title','SOP')}_초안.docx"
        st.download_button(
            "⬇️ 워드 파일 다운로드 (SOP 초안)",
            data=data, file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
        st.caption("💡 생성된 초안은 'SOP 자동비교'에서 규제 충족도를 바로 점검해보세요.")
    except ImportError:
        st.error("서버에 python-docx 가 없습니다 — "
                 "`pip install python-docx` 후 서비스를 재시작하세요.")

    st.markdown("---")
    st.caption(branding.FOOTER_NOTE)
