# gad7_app.py
# -*- coding: utf-8 -*-

import json
import uuid
from datetime import datetime, timezone, timedelta

import streamlit as st

# =========================
# 0) Page config
# =========================
st.set_page_config(
    page_title="GAD-7 불안검사",
    page_icon="🧠",
    layout="centered",
)

KST = timezone(timedelta(hours=9))


# =========================
# 1) Style
# =========================
def inject_css():
    st.markdown(
        """
        <style>
        .app-wrap { max-width: 820px; margin: 0 auto; }
        .title-lg { font-size: 28px; font-weight: 800; letter-spacing: -0.5px; }
        .title-md { font-size: 18px; font-weight: 800; letter-spacing: -0.2px; margin-top: 8px; }
        .text { font-size: 14px; color: rgba(0,0,0,0.72); line-height: 1.65; }
        .muted { font-size: 12px; color: rgba(0,0,0,0.55); line-height: 1.55; }

        .card {
            border: 1px solid rgba(0,0,0,0.08);
            border-radius: 16px;
            padding: 18px 18px 14px 18px;
            background: #fff;
            box-shadow: 0 6px 20px rgba(0,0,0,0.04);
            margin-bottom: 12px;
        }
        .card-header { margin-bottom: 10px; }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            background: rgba(2,132,199,0.10);
            color: rgba(2,132,199,1);
            margin-right: 8px;
        }
        .hr { height: 1px; background: rgba(0,0,0,0.06); border: 0; margin: 12px 0; }

        .qno { font-weight: 800; margin-right: 6px; }
        .qtext { font-weight: 650; }

        .result-score {
            font-size: 40px;
            font-weight: 900;
            letter-spacing: -1px;
            margin: 4px 0 4px 0;
        }
        .result-level {
            font-size: 16px;
            font-weight: 800;
            padding: 6px 12px;
            border-radius: 999px;
            display: inline-block;
            background: rgba(0,0,0,0.06);
            margin-bottom: 8px;
        }
        .btn-row { display:flex; gap:10px; flex-wrap:wrap; }

        /* Streamlit radio spacing */
        div[role="radiogroup"] > label { margin: 0.25rem 0; }

        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# 2) GAD-7 content
# =========================
SCALE_LABELS = [
    "전혀 없음 (0)",
    "몇 일 동안 (1)",
    "일주일 이상 (2)",
    "거의 매일 (3)",
]

QUESTIONS = [
    "초조하거나 불안하거나 조마조마함을 느낌",
    "걱정하는 것을 멈추거나 조절하기 어려움",
    "여러 가지에 대해 지나치게 걱정함",
    "편안하게 있는 것이 어려움",
    "너무 안절부절해서 가만히 있기 힘듦",
    "쉽게 짜증이 나거나 성가심을 느낌",
    "끔찍한 일이 생길 것처럼 두려움",
]


def gad7_level(total: int):
    # 기준: 0–4 Minimal, 5–9 Mild, 10–14 Moderate, 15–21 Severe
    if total <= 4:
        return (
            "최소/거의 없음 (Minimal)",
            "현재로서는 불안 관련 불편감이 거의 보고되지 않았습니다. "
            "일상적인 긴장이나 걱정 수준으로 해석할 수 있습니다.",
        )
    if total <= 9:
        return (
            "경도 (Mild)",
            "최근 일상에서 불안이나 걱정을 느끼는 상황이 일부 보고되었습니다. "
            "스트레스 상황에서 흔히 나타날 수 있는 반응 범위로 볼 수 있습니다.",
        )
    if total <= 14:
        return (
            "중등도 (Moderate)",
            "불안이나 걱정으로 인한 불편감이 비교적 자주 보고되었습니다. "
            "일상생활에서 부담을 느끼는 순간이 있었을 가능성이 있어, "
            "자신의 정서 상태를 한 번 더 살펴보는 것이 도움이 될 수 있습니다.",
        )
    return (
        "중증 (Severe)",
        "불안과 관련된 불편감이 상당히 자주 보고되었습니다. "
        "최근 정서적 부담이 컸을 가능성이 있으며, 필요하다면 전문가와의 상담을 통해 "
        "현재 상태를 점검해 보는 것도 한 방법이 될 수 있습니다.",
    )


def score_from_label(label: str) -> int:
    # "… (n)" 형태에서 n만 추출
    if label is None:
        return None
    try:
        return int(label.split("(")[-1].split(")")[0])
    except Exception:
        return None


# =========================
# 3) State
# =========================
def init_state():
    if "page" not in st.session_state:
        st.session_state.page = "intro"

    if "meta" not in st.session_state:
        st.session_state.meta = {
            "respondent_id": str(uuid.uuid4()),
            "consent": False,
            "consent_ts": None,
            "started_ts": None,
            "submitted_ts": None,
        }

    if "answers" not in st.session_state:
        # q1~q7: None or one of SCALE_LABELS
        st.session_state.answers = {f"q{i}": None for i in range(1, 8)}


def reset_all():
    st.session_state.page = "intro"
    st.session_state.meta = {
        "respondent_id": str(uuid.uuid4()),
        "consent": False,
        "consent_ts": None,
        "started_ts": None,
        "submitted_ts": None,
    }
    st.session_state.answers = {f"q{i}": None for i in range(1, 8)}


# =========================
# 4) Payload / Save hook
# =========================
def build_payload():
    # 점수 계산
    item_scores = {}
    total = 0
    missing = []

    for i in range(1, 8):
        key = f"q{i}"
        label = st.session_state.answers.get(key)
        s = score_from_label(label)
        if s is None:
            missing.append(key)
            item_scores[key] = None
        else:
            item_scores[key] = s
            total += s

    level, interp = gad7_level(total)

    payload = {
        "instrument": "GAD-7",
        "version": "streamlit_1.0",
        "respondent_id": st.session_state.meta["respondent_id"],
        "consent": st.session_state.meta["consent"],
        "consent_ts": st.session_state.meta["consent_ts"],
        "started_ts": st.session_state.meta["started_ts"],
        "submitted_ts": st.session_state.meta["submitted_ts"],
        "items": {
            "scale": {
                "0": "전혀 없음",
                "1": "몇 일 동안",
                "2": "일주일 이상",
                "3": "거의 매일",
            },
            "questions": {f"q{i}": QUESTIONS[i - 1] for i in range(1, 8)},
            "answers": st.session_state.answers,
            "scores": item_scores,
        },
        "result": {
            "total": total,
            "level": level,
            "interpretation": interp,
            # 운영 규칙(원하신 활용 방식)
            "rule_of_thumb": {
                ">=10": "중등도 임상적 가능성 → 상담 권장",
                ">=15": "불안장애 가능성 → 정신과 진료 필요",
            },
            "flags": {
                "recommend_counseling": bool(total >= 10),
                "recommend_clinic": bool(total >= 15),
            },
        },
        "developer_reference": {
            "developers": "Spitzer, Kroenke, Williams, & Löwe (2006)",
            "paper": "A brief measure for assessing generalized anxiety disorder: The GAD-7. Archives of Internal Medicine, 166(10), 1092–1097.",
            "doi": "10.1001/archinte.166.10.1092",
        },
    }
    return payload, missing


def auto_db_insert(payload: dict):
    """
    ✅ 여기에 DB 저장 로직을 붙이면 됩니다.
    - 예: Postgres/SQLite/Sheets API 등
    - 중복 저장 방지 로직은 meta['submitted_ts'] 또는 별도 키로 관리 권장

    현재는 안전하게 '비활성(아무것도 안 함)' 처리.
    """
    return


# =========================
# 5) UI pages
# =========================
def page_intro():
    st.markdown('<div class="app-wrap">', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="card">
          <div class="card-header">
            <span class="badge">GAD-7</span>
            <span class="badge">최근 2주</span>
            <div class="title-lg">불안검사 (Generalized Anxiety Disorder-7)</div>
            <div class="text" style="margin-top:6px;">
              본 검사는 최근 2주 동안 경험한 불안 관련 증상의 빈도·심각도를 확인하기 위한 자기보고식 척도입니다.
            </div>
            <div class="muted" style="margin-top:10px;">
              ※ 본 결과는 진단이 아니며, 참고용입니다. 불편감이 크거나 일상 기능이 저하된다면 전문가 상담을 권장합니다.
            </div>
          </div>
          <hr class="hr"/>
          <div class="title-md">지시문</div>
          <div class="text">
            다음은 최근 2주 동안 경험한 불안 관련 증상에 대한 질문입니다.<br/>
            가장 가까운 경험 정도를 선택해 주세요.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 동의
    st.markdown(
        """
        <div class="card">
          <div class="title-md">동의</div>
          <div class="text">검사 진행 및 결과 산출에 동의하십니까?</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    consent = st.checkbox("예, 동의합니다.", value=st.session_state.meta["consent"])
    st.session_state.meta["consent"] = consent

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("검사 시작", type="primary", disabled=not consent, use_container_width=True):
            now = datetime.now(KST).isoformat()
            st.session_state.meta["consent_ts"] = now
            st.session_state.meta["started_ts"] = now
            st.session_state.page = "survey"
            st.rerun()

    with col2:
        if st.button("초기화", use_container_width=True):
            reset_all()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def page_survey():
    st.markdown('<div class="app-wrap">', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="card">
          <div class="card-header">
            <span class="badge">문항 7개</span>
            <div class="title-lg">문항 응답</div>
            <div class="text">각 문항에 대해 최근 2주 동안의 경험에 가장 가까운 수준을 선택해 주세요.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 문항 렌더
    for i, q in enumerate(QUESTIONS, start=1):
        key = f"q{i}"
        st.markdown(
            f"""
            <div class="card">
              <div class="card-header">
                <div><span class="qno">{i}.</span><span class="qtext">{q}</span></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # 카드 아래에 라디오 (Streamlit 컴포넌트 제한 때문에 분리)
        st.session_state.answers[key] = st.radio(
            label=f"문항 {i} 응답",
            options=SCALE_LABELS,
            index=SCALE_LABELS.index(st.session_state.answers[key]) if st.session_state.answers[key] in SCALE_LABELS else 0,
            key=f"radio_{key}",
            horizontal=True,
            label_visibility="collapsed",
        )

    payload, missing = build_payload()
    all_done = (len(missing) == 0)

    st.markdown(
        """
        <div class="card">
          <div class="title-md">제출</div>
          <div class="text">모든 문항에 응답하신 뒤 결과를 확인해 주세요.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("결과 보기", type="primary", disabled=not all_done, use_container_width=True):
            st.session_state.meta["submitted_ts"] = datetime.now(KST).isoformat()
            st.session_state.page = "result"
            st.rerun()
    with col2:
        if st.button("뒤로", use_container_width=True):
            st.session_state.page = "intro"
            st.rerun()
    with col3:
        if st.button("초기화", use_container_width=True):
            reset_all()
            st.rerun()

    # 개발용: 현재 점수 미리보기(원치 않으면 주석)
    with st.expander("개발용: 현재 점수 미리보기", expanded=False):
        st.write(payload["result"])

    st.markdown("</div>", unsafe_allow_html=True)


def page_result():
    st.markdown('<div class="app-wrap">', unsafe_allow_html=True)

    payload, missing = build_payload()
    total = payload["result"]["total"]
    level = payload["result"]["level"]
    interp = payload["result"]["interpretation"]

    # ✅ 결과 저장(원하시면 여기서 실행)
    auto_db_insert(payload)

    st.markdown(
        f"""
        <div class="card result-card">
          <div class="card-header">
            <span class="badge">결과</span>
            <div class="title-lg">GAD-7 검사 결과</div>
            <div class="muted">응답 기준: 최근 2주 / 총점 범위: 0–21</div>
          </div>
          <hr class="hr"/>
          <div class="result-score">{total}</div>
          <div class="result-level">{level}</div>
          <div class="text" style="margin-top:10px;">{interp}</div>
          <hr class="hr"/>
          <div class="text">
            <b>활용 기준(운영 규칙)</b><br/>
            · 10점 이상: 중등도 임상적 가능성 → 상담 권장<br/>
            · 15점 이상: 불안장애 가능성 → 정신과 진료 필요
          </div>
          <div class="muted" style="margin-top:10px;">
            ※ 본 결과는 참고용이며 의학적 진단을 대체하지 않습니다.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="card">
          <div class="title-md">개발/연동용 Payload</div>
          <div class="text">DB 저장, API 전송, 로그 기록 등에 사용할 수 있습니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("다시 검사", type="primary", use_container_width=True):
            reset_all()
            st.rerun()
    with col2:
        if st.button("문항으로 돌아가기", use_container_width=True):
            st.session_state.page = "survey"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# 6) Main
# =========================
def main():
    inject_css()
    init_state()

    # 상단 작은 정보
    st.caption("GAD-7 (Spitzer et al., 2006) · Streamlit 구현")

    if st.session_state.page == "intro":
        page_intro()
    elif st.session_state.page == "survey":
        # 동의 없이 직접 접근 방지
        if not st.session_state.meta.get("consent"):
            st.warning("동의 후 검사를 시작할 수 있습니다.")
            st.session_state.page = "intro"
            st.rerun()
        page_survey()
    elif st.session_state.page == "result":
        page_result()
    else:
        st.session_state.page = "intro"
        st.rerun()


if __name__ == "__main__":
    main()
