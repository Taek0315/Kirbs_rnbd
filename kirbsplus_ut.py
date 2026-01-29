# app.py
# streamlit run app.py

import streamlit as st
import pandas as pd
from datetime import datetime

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

CATEGORIES = sorted(list({q["category"] for q in QUESTIONS}))

# -------------------------
# 2) 세션 상태 초기화
# -------------------------
if "responses" not in st.session_state:
    st.session_state["responses"] = {}  # key -> dict

def qkey(i: int) -> str:
    return f"q_{i:03d}"

def init_default(i: int):
    k = qkey(i)
    if k not in st.session_state["responses"]:
        st.session_state["responses"][k] = {
            "functionality": None,   # "Y" / "N"
            "satisfaction": None,    # 1~5
            "improvement": "",
            "comment": "",
        }

# -------------------------
# 3) UI 헤더
# -------------------------
st.title("사용성 평가 설문지 (Streamlit)")
st.caption("각 문항에 대해 기능 여부(Y/N), 만족도(1~5), 개선요청/추가의견을 입력해주세요.")

with st.sidebar:
    st.header("설문 페이지")
    category = st.selectbox("분류 선택", CATEGORIES, index=0)
    st.divider()
    st.write("진행 팁")
    st.write("- 페이지를 바꿔도 입력값은 유지됩니다.\n- 마지막에 '결과/제출'에서 다운로드 가능합니다.")

# -------------------------
# 4) 현재 분류 문항 필터
# -------------------------
filtered = [(idx, q) for idx, q in enumerate(QUESTIONS) if q["category"] == category]

# 서브섹션별로 묶기
subgroups = {}
for idx, q in filtered:
    sub = q["sub"].strip() if q["sub"] else ""
    subgroups.setdefault(sub, []).append((idx, q))

# -------------------------
# 5) 문항 렌더링
# -------------------------
for sub, items in subgroups.items():
    if sub:
        st.subheader(sub)
    else:
        st.subheader(category)

    for idx, q in items:
        init_default(idx)
        k = qkey(idx)
        resp = st.session_state["responses"][k]

        with st.container(border=True):
            st.markdown(f"**문항 {idx+1}. {q['item']}**")

            col1, col2 = st.columns([1, 1])
            func_options = ["미선택", "Y", "N"]
            sat_options = ["미선택", 1, 2, 3, 4, 5]
            with col1:
                func_index = func_options.index(resp["functionality"]) if resp["functionality"] in func_options else 0
                func = st.radio(
                    "기능 여부",
                    options=func_options,
                    index=func_index,
                    horizontal=True,
                    key=f"{k}_func",
                )
            with col2:
                sat_index = sat_options.index(resp["satisfaction"]) if resp["satisfaction"] in sat_options else 0
                sat = st.radio(
                    "만족도 (1~5)",
                    options=sat_options,
                    index=sat_index,
                    horizontal=True,
                    key=f"{k}_sat",
                )

            imp = st.text_area("개선요청(주관식)", value=resp["improvement"], key=f"{k}_imp")
            cmt = st.text_area("추가 의견(주관식)", value=resp["comment"], key=f"{k}_cmt")

            # 세션에 즉시 반영
            func_val = None if func in (None, "미선택") else func
            sat_val = None if sat in (None, "미선택") else int(sat)
            st.session_state["responses"][k] = {
                "functionality": func_val,
                "satisfaction": sat_val,
                "improvement": imp.strip(),
                "comment": cmt.strip(),
            }

# -------------------------
# 6) 결과/제출 페이지(하단 고정 느낌)
# -------------------------
st.divider()
st.header("결과 / 제출")

# 응답을 DF로 변환
rows = []
for i, q in enumerate(QUESTIONS):
    init_default(i)
    k = qkey(i)
    r = st.session_state["responses"][k]
    rows.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "분류": q["category"],
        "세부": q["sub"],
        "문항": q["item"],
        "기능여부": r["functionality"],
        "만족도": r["satisfaction"],
        "개선요청": r["improvement"],
        "추가의견": r["comment"],
    })

df = pd.DataFrame(rows)
df["만족도"] = pd.to_numeric(df["만족도"], errors="coerce")

# 간단한 요약(분류별 평균 만족도)
summary = df.groupby("분류", dropna=False)["만족도"].mean().reset_index().rename(columns={"만족도": "평균만족도"})

c1, c2 = st.columns([2, 1])
with c1:
    st.write("응답 미리보기")
    st.dataframe(df[["분류", "세부", "문항", "기능여부", "만족도", "개선요청", "추가의견"]], use_container_width=True, height=320)
with c2:
    st.write("분류별 평균 만족도")
    st.dataframe(summary, use_container_width=True, height=320)

# 다운로드
csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    label="응답 CSV 다운로드",
    data=csv,
    file_name="usability_survey_responses.csv",
    mime="text/csv",
)

# 초기화 버튼
if st.button("모든 응답 초기화", type="secondary"):
    st.session_state["responses"] = {}
    st.rerun()
