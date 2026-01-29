from datetime import datetime
from uuid import uuid4

import pandas as pd
import streamlit as st

from gcp_storage import append_one_row_to_sheet

st.set_page_config(page_title="사용성 평가 설문", layout="wide")

# -------------------------
# 1) 설문 문항 정의
# -------------------------
QUESTIONS = [
    # 기본탐색
    {"category": "기본탐색", "sub": "", "item": "메뉴 구조가 직관적으로 구성되어 있는가?"},
    {"category": "기본탐색", "sub": "", "item": "검색 기능이 키워드 기반으로 정확하게 작동하는가?"},
    {"category": "기본탐색", "sub": "", "item": "FAQ, 고객센터 등 사용자 지원 채널이 작동하고 있는가?"},
    # UI 및 반응형
    {"category": "사용자 인터페이스(UI) 및 반응형 디자인", "sub": "", "item": "디자인 컬러가 연구소의 신뢰성과 접근성을 반영하는가?"},
    {"category": "사용자 인터페이스(UI) 및 반응형 디자인", "sub": "", "item": "사용자가 현재 접속한 페이지를 명확히 인식할 수 있는가?"},
    # 기술적 성능
    {"category": "기술적 성능", "sub": "", "item": "로딩 속도, 이미지 출력 속도가 적절한가?"},
    {"category": "기술적 성능", "sub": "", "item": "링크 오류, 기능 오류 등 기술적 문제 없이 원활하게 작동하는가?"},
    # 회원 > 회원가입
    {"category": "회원", "sub": "회원 가입", "item": "회원가입/로그인 과정이 원활하게 진행되며 개인/기관 유형별로 구분 가능한가?"},
    {"category": "회원", "sub": "회원 가입", "item": "구매 자격 확인 기능이 명확히 작동하고, 승인 후 구매 가능 여부가 안내되어 있는가?"},
    {"category": "회원", "sub": "회원 가입", "item": "학위증, 자격증명서, 교육이수증 등 자료의 업로드가 가능한가? (임의 예시 이미지 파일 업로드 진행)"},
    # 회원 > 마이페이지 > 대시보드
    {"category": "회원", "sub": "마이페이지 > 대시보드", "item": "이름 및 회원 등급이 잘 표시되어 있는가?"},
    {"category": "회원", "sub": "마이페이지 > 대시보드", "item": "대시보드의 정보의 확인이 가능한가?"},
    # 회원 > 마이페이지 > 회원정보수정
    {"category": "회원", "sub": "마이페이지 > 회원 정보 수정", "item": "학위증, 자격증명서, 교육이수증 등이 회원정보 수정 창에서 삭제 및 재업로드가 가능한가? (예시 이미지로 삭제 후 재업로드 진행)"},
    # 구매 > 심리검사 > 상품정보
    {"category": "구매", "sub": "심리검사 > 상품 정보", "item": "검사, 교육 콘텐츠 등의 정보가 명확하게 표시되어 있는가?"},
    {"category": "구매", "sub": "심리검사 > 상품 정보", "item": "상세 정보에 있는 버튼의 기능은 작동하는가? (결과지 sample, 검사 목적, 특징 등)"},
    # 구매 > 구매
    {"category": "구매", "sub": "구매", "item": "상품 구매가 가능한가? (테스트를 위해 최소 2건의 검사를 구매)"},
    {"category": "구매", "sub": "구매", "item": "구매 후 마이페이지에서 주문 내역 확인이 가능한가?"},
    # 검사 관리
    {"category": "검사 관리", "sub": "마이페이지 검사관리", "item": "검사 관리 페이지에서 구매한 검사 내역 확인이 가능한가?"},
    {"category": "검사 관리", "sub": "코드 발송", "item": "검사 실시 버튼으로 바로 검사 진행이 가능한가?"},
    {"category": "검사 관리", "sub": "코드 발송", "item": "코드 발송을 통해 온라인 코드 발송이 가능한가? (코드 발송은 이메일 발송으로 진행)"},
    {"category": "검사 관리", "sub": "코드 발송", "item": "발송된 코드로 접속하여 검사 진행이 가능한가?"},
    {"category": "검사 관리", "sub": "검사 실시", "item": "검사 진행 과정이 단계별로 명확하게 안내되어 있는가?"},
    {"category": "검사 관리", "sub": "검사 실시", "item": "결과지 및 보고서 확인, 다운로드 기능이 문제 없이 제공되는가?"},
    {"category": "검사 관리", "sub": "결과 확인", "item": "완료된 검사의 결과를 마이페이지 - 검사 관리 - 검사 결과 탭에서 확인 가능한가?"},
    {"category": "검사 관리", "sub": "결과 확인", "item": "결과화면, 결과지 등이 시각적으로 이해하기 쉽게 구성되어 있는가?"},
    {"category": "검사 관리", "sub": "결과 확인", "item": "검사 결과의 다운로드(엑셀, pdf)가 가능하며 재확인이 되는가?"},
    # 테스타리움
    {"category": "테스타리움", "sub": "", "item": "테스타리움 무료 검사 진행이 가능한가?"},
]

CATEGORY_ORDER = [
    "기본탐색",
    "사용자 인터페이스(UI) 및 반응형 디자인",
    "기술적 성능",
    "회원",
    "구매",
    "검사 관리",
    "테스타리움",
]

# -------------------------
# 2) 세션 상태 초기화
# -------------------------

def qkey(i: int) -> str:
    return f"q_{i:03d}"


def init_question_defaults(i: int) -> None:
    base = qkey(i)
    sat_key = f"{base}_sat"
    func_key = f"{base}_func"
    imp_key = f"{base}_imp"
    cmt_key = f"{base}_cmt"
    responses = st.session_state.setdefault("responses", {})
    response = responses.setdefault(
        base,
        {
            "functionality": None,
            "satisfaction": None,
            "improvement": "",
            "comment": "",
        },
    )

    if func_key in st.session_state:
        func_val = st.session_state.get(func_key)
        response["functionality"] = func_val if func_val in ("Y", "N") else None
    if sat_key in st.session_state:
        sat = st.session_state.get(sat_key)
        response["satisfaction"] = int(sat) if sat is not None else None

    st.session_state[imp_key] = st.session_state.get(imp_key, "")
    st.session_state[cmt_key] = st.session_state.get(cmt_key, "")

    response["improvement"] = st.session_state.get(imp_key, "")
    response["comment"] = st.session_state.get(cmt_key, "")


def get_missing(question_indices: list[int]) -> list[int]:
    missing: list[int] = []
    responses = st.session_state.get("responses", {})
    for i in question_indices:
        base = qkey(i)
        response = responses.get(base, {})
        func_val = response.get("functionality")
        sat_val = response.get("satisfaction")
        if func_val is None or sat_val is None:
            missing.append(i + 1)
    return missing


if "step_idx" not in st.session_state:
    st.session_state["step_idx"] = 0

if "submission_complete" not in st.session_state:
    st.session_state["submission_complete"] = False

if "submitted" not in st.session_state:
    st.session_state["submitted"] = False

if "respondent_id" not in st.session_state:
    st.session_state["respondent_id"] = str(uuid4())

for i in range(len(QUESTIONS)):
    init_question_defaults(i)

# -------------------------
# 3) UI 헤더
# -------------------------
st.title("사용성 평가 설문지 (KIRBSPLUS)")
st.caption("각 문항에 대해 기능 여부(Y/N), 만족도(1~5), 개선요청/추가의견을 입력해주세요.")

if st.session_state.get("error_message"):
    st.error(st.session_state.pop("error_message"))

with st.sidebar:
    st.header("설문 페이지")
    st.caption(f"진행: {st.session_state['step_idx'] + 1}/{len(CATEGORY_ORDER)}")
    st.progress((st.session_state["step_idx"] + 1) / len(CATEGORY_ORDER))
    st.divider()
    reset_confirm = st.checkbox("응답 초기화 확인", value=False)
    if st.button("응답 초기화", type="secondary"):
        if reset_confirm:
            for i in range(len(QUESTIONS)):
                base = qkey(i)
                for suffix in ("func", "sat", "imp", "cmt"):
                    st.session_state.pop(f"{base}_{suffix}", None)
            st.session_state["responses"] = {}
            st.session_state["step_idx"] = 0
            st.session_state["submission_complete"] = False
            st.session_state["submitted"] = False
            st.session_state.pop("respondent_id", None)
            st.session_state.pop("last_submission_id", None)
            st.session_state.pop("last_submission_ts", None)
            st.session_state.pop("submission_csv", None)
            st.success("응답이 초기화되었습니다.")
            st.rerun()
        else:
            st.warning("체크박스를 선택한 뒤 초기화를 진행하세요.")

# -------------------------
# 4) 현재 분류 문항 필터
# -------------------------
current_category = CATEGORY_ORDER[st.session_state["step_idx"]]
filtered = [(idx, q) for idx, q in enumerate(QUESTIONS) if q["category"] == current_category]

# -------------------------
# 5) 문항 렌더링
# -------------------------
previous_sub = None
for idx, q in filtered:
    base = qkey(idx)
    sub = q["sub"].strip() if q["sub"] else ""
    if sub != previous_sub:
        st.subheader(sub if sub else current_category)
        previous_sub = sub

    responses = st.session_state["responses"][base]

    with st.container(border=True):
        st.markdown(f"**문항 {idx + 1}. {q['item']}**")

        col1, col2 = st.columns([1, 1])
        with col1:
            st.radio(
                "기능 여부",
                options=["Y", "N"],
                horizontal=True,
                index=None,
                key=f"{base}_func",
            )
        with col2:
            st.radio(
                "만족도 (1~5)",
                options=[1, 2, 3, 4, 5],
                horizontal=True,
                index=None,
                key=f"{base}_sat",
            )

        st.text_area("개선요청(주관식)", key=f"{base}_imp")
        st.text_area("추가 의견(주관식)", key=f"{base}_cmt")

    func_val = st.session_state.get(f"{base}_func")
    responses["functionality"] = func_val if func_val in ("Y", "N") else None
    sat = st.session_state.get(f"{base}_sat")
    responses["satisfaction"] = int(sat) if sat is not None else None
    responses["improvement"] = (st.session_state.get(f"{base}_imp") or "").strip()
    responses["comment"] = (st.session_state.get(f"{base}_cmt") or "").strip()

# -------------------------
# 6) 검증 및 제출
# -------------------------

def handle_submit() -> None:
    if st.session_state.get("submitted"):
        st.info("이미 제출되었습니다. 새 제출을 위해 응답을 초기화하세요.")
        return

    all_missing = get_missing(list(range(len(QUESTIONS))))
    if all_missing:
        missing_list = ", ".join(map(str, all_missing))
        first_missing_idx = all_missing[0] - 1
        missing_category = QUESTIONS[first_missing_idx]["category"]

        st.session_state["step_idx"] = CATEGORY_ORDER.index(missing_category)
        st.session_state["error_message"] = f"필수 응답이 누락되었습니다: 문항 {missing_list}"
        st.rerun()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_compact = datetime.now().strftime("%Y%m%d_%H%M%S")
    respondent_id = st.session_state.get("respondent_id") or str(uuid4())
    st.session_state["respondent_id"] = respondent_id
    submission_id = f"{respondent_id}_{timestamp_compact}"

    if st.session_state.get("last_submission_id") == submission_id:
        st.info("이미 제출 처리되었습니다.")
        return

    wide_row: dict[str, str] = {
        "submission_ts": timestamp,
        "respondent_id": respondent_id,
    }

    rows = []
    responses = st.session_state.get("responses", {})
    for i, q in enumerate(QUESTIONS):
        base = qkey(i)
        response = responses.get(base, {})
        wide_row[f"Q{i + 1}_func"] = response.get("functionality") or ""
        wide_row[f"Q{i + 1}_sat"] = response.get("satisfaction") or ""
        wide_row[f"Q{i + 1}_imp"] = (response.get("improvement") or "").strip()
        wide_row[f"Q{i + 1}_cmt"] = (response.get("comment") or "").strip()
        rows.append(
            {
                "submission_ts": timestamp,
                "분류": q["category"],
                "세부": q.get("sub", ""),
                "문항번호": i + 1,
                "문항": q["item"],
                "기능여부": response.get("functionality"),
                "만족도": int(response.get("satisfaction")),
                "개선요청": (response.get("improvement") or "").strip(),
                "추가의견": (response.get("comment") or "").strip(),
            }
        )

    df = pd.DataFrame(rows)

    st.session_state["submission_complete"] = True
    st.session_state["submission_csv"] = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

    try:
        append_one_row_to_sheet(wide_row)
        st.session_state["submitted"] = True
        st.session_state["last_submission_ts"] = timestamp
        st.session_state["last_submission_id"] = submission_id
        st.success("저장 완료")
    except Exception as exc:
        st.warning(f"저장 실패, 연구사업부로 알려주세요: {exc}")


st.divider()

col_left, col_spacer, col_right = st.columns([1, 6, 1])

with col_left:
    if st.button("이전", disabled=st.session_state["step_idx"] == 0):
        st.session_state["step_idx"] -= 1
        st.rerun()

with col_right:
    is_last_step = st.session_state["step_idx"] == len(CATEGORY_ORDER) - 1
    if is_last_step:
        if st.button("제출", type="primary"):
            handle_submit()
    else:
        if st.button("다음", type="primary"):
            current_indices = [idx for idx, _ in filtered]
            missing = get_missing(current_indices)
            if missing:
                missing_list = ", ".join(map(str, missing))
                st.error(f"필수 응답이 누락되었습니다: 문항 {missing_list}")
            else:
                st.session_state["step_idx"] += 1
                st.rerun()


