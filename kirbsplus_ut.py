import os
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
import streamlit as st

from gcp_storage import save_to_gcp

from gcp_storage import save_to_gcp

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

DEFAULT_FUNCTIONALITY = "Y"
DEFAULT_SATISFACTION = 3

# -------------------------
# 2) 세션 상태 초기화
# -------------------------

def qkey(i: int) -> str:
    return f"q_{i:03d}"


def init_question(i: int) -> None:
    key_prefix = qkey(i)
    responses = st.session_state.setdefault("responses", {})
    if key_prefix not in responses:
        responses[key_prefix] = {
            "functionality": DEFAULT_FUNCTIONALITY,
            "satisfaction": DEFAULT_SATISFACTION,
            "improvement": "",
            "comment": "",
        }

    st.session_state.setdefault(f"{key_prefix}_func", responses[key_prefix]["functionality"])
    st.session_state.setdefault(f"{key_prefix}_sat", responses[key_prefix]["satisfaction"])
    st.session_state.setdefault(f"{key_prefix}_imp", responses[key_prefix]["improvement"])
    st.session_state.setdefault(f"{key_prefix}_cmt", responses[key_prefix]["comment"])
def init_defaults(i: int) -> None:
    base = qkey(i)
    st.session_state.setdefault(f"{base}_func", None)
    st.session_state.setdefault(f"{base}_sat", None)
    st.session_state.setdefault(f"{base}_imp", "")
    st.session_state.setdefault(f"{base}_cmt", "")


if "step_idx" not in st.session_state:
    st.session_state["step_idx"] = 0

if "submission_complete" not in st.session_state:
    st.session_state["submission_complete"] = False

for i in range(len(QUESTIONS)):
    init_question(i)

# -------------------------
# 3) UI 헤더
# -------------------------
st.title("사용성 평가 설문지 (Streamlit)")
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
                key_prefix = qkey(i)
                for suffix in ("func", "sat", "imp", "cmt"):
                    st.session_state.pop(f"{key_prefix}_{suffix}", None)
            st.session_state["responses"] = {}
            st.session_state["step_idx"] = 0
            st.session_state["submission_complete"] = False
            st.session_state.pop("submission_csv", None)
            st.session_state.pop("saved_filepath", None)
            st.session_state.pop(f"{base}_{suffix}", None)
            st.session_state["step_idx"] = 0
            st.session_state["submission_complete"] = False
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
    init_question(idx)
    sub = q["sub"].strip() if q["sub"] else ""
    if sub != previous_sub:
        st.subheader(sub if sub else current_category)
        previous_sub = sub

    key_prefix = qkey(idx)
    responses = st.session_state["responses"][key_prefix]

    with st.container(border=True):
        st.markdown(f"**문항 {idx + 1}. {q['item']}**")

        col1, col2 = st.columns([1, 1])
        func_options = ["Y", "N"]
        sat_options = [1, 2, 3, 4, 5]
        with col1:
            func_value = responses["functionality"]
            func_index = func_options.index(func_value) if func_value in func_options else 0
            func_value = st.session_state.get(f"{base}_func")
            func_index = func_options.index(func_value) if func_value in func_options else None
            st.radio(
                "기능 여부",
                options=func_options,
                index=func_index,
                horizontal=True,
                key=f"{key_prefix}_func",
            )
        with col2:
            sat_value = responses["satisfaction"]
            sat_index = sat_options.index(sat_value) if sat_value in sat_options else 2
            sat_value = st.session_state.get(f"{base}_sat")
            sat_index = sat_options.index(sat_value) if sat_value in sat_options else None
            st.radio(
                "만족도 (1~5)",
                options=sat_options,
                index=sat_index,
                horizontal=True,
                key=f"{key_prefix}_sat",
            )

        st.text_area("개선요청(주관식)", key=f"{key_prefix}_imp")
        st.text_area("추가 의견(주관식)", key=f"{key_prefix}_cmt")

    responses["functionality"] = st.session_state[f"{key_prefix}_func"]
    responses["satisfaction"] = st.session_state[f"{key_prefix}_sat"]
    responses["improvement"] = st.session_state[f"{key_prefix}_imp"].strip()
    responses["comment"] = st.session_state[f"{key_prefix}_cmt"].strip()

# -------------------------
# 6) 검증 및 제출
# -------------------------

def missing_for_indices(indices: list[tuple[int, dict]]) -> list[int]:
    missing = []
    responses = st.session_state.get("responses", {})
    for i, _ in indices:
        key_prefix = qkey(i)
        response = responses.get(key_prefix, {})
        func_val = response.get("functionality")
        sat_val = response.get("satisfaction")
    for i, _ in indices:
        base = qkey(i)
        func_val = st.session_state.get(f"{base}_func")
        sat_val = st.session_state.get(f"{base}_sat")
        if func_val not in {"Y", "N"} or sat_val not in {1, 2, 3, 4, 5}:
            missing.append(i + 1)
    return missing


st.divider()

left_col, spacer, right_col = st.columns([1, 6, 1])
with left_col:
col_prev, col_next = st.columns([1, 1])
with col_prev:
    if st.button("이전", disabled=st.session_state["step_idx"] == 0):
        st.session_state["step_idx"] -= 1
        st.rerun()

with right_col:
with col_next:
    is_last_step = st.session_state["step_idx"] == len(CATEGORY_ORDER) - 1
    next_label = "제출" if is_last_step else "다음"
    if st.button(next_label, type="primary"):
        if is_last_step:
            all_missing = missing_for_indices(list(enumerate(QUESTIONS)))
            if all_missing:
                missing_list = ", ".join(map(str, all_missing))
                first_missing_idx = all_missing[0] - 1
                missing_category = QUESTIONS[first_missing_idx]["category"]
                st.session_state["step_idx"] = CATEGORY_ORDER.index(missing_category)
                st.session_state["error_message"] = f"필수 응답이 누락되었습니다: 문항 {missing_list}"
                st.rerun()
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                timestamp_compact = datetime.now().strftime("%Y%m%d_%H%M%S")
                rows = []
                for i, q in enumerate(QUESTIONS):
                    key_prefix = qkey(i)
                    response = st.session_state["responses"][key_prefix]
                rows = []
                for i, q in enumerate(QUESTIONS):
                    base = qkey(i)
                    rows.append({
                        "submission_ts": timestamp,
                        "분류": q["category"],
                        "세부": q["sub"],
                        "문항번호": i + 1,
                        "문항": q["item"],
                        "기능여부": response["functionality"],
                        "만족도": int(response["satisfaction"]),
                        "개선요청": response["improvement"],
                        "추가의견": response["comment"],
                    })

                df = pd.DataFrame(rows)
                submissions_dir = Path("submissions")
                os.makedirs(submissions_dir, exist_ok=True)
                filepath = submissions_dir / f"submission_{timestamp_compact}.csv"
                df.to_csv(filepath, index=False, encoding="utf-8-sig")
                st.session_state["saved_filepath"] = str(filepath)

                        "기능여부": st.session_state.get(f"{base}_func"),
                        "만족도": int(st.session_state.get(f"{base}_sat")),
                        "개선요청": st.session_state.get(f"{base}_imp", "").strip(),
                        "추가의견": st.session_state.get(f"{base}_cmt", "").strip(),
                    })

                df = pd.DataFrame(rows)
                try:
                    save_to_gcp(df)
                except Exception as exc:  # noqa: BLE001
                    st.warning(f"저장 실패: {exc}")

                st.session_state["submission_complete"] = True
                st.session_state["submission_csv"] = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.success(f"제출 완료: {filepath}")
                st.success("제출 완료")
        else:
            missing = missing_for_indices(filtered)
            if missing:
                missing_list = ", ".join(map(str, missing))
                st.error(f"필수 응답이 누락되었습니다: 문항 {missing_list}")
            else:
                st.session_state["step_idx"] += 1
                st.rerun()

if st.session_state.get("submission_complete"):
    st.download_button(
        label="응답 CSV 다운로드",
        data=st.session_state.get("submission_csv"),
        file_name="usability_survey_responses.csv",
        mime="text/csv",
    )
