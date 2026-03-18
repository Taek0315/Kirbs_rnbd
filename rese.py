# 실행 방법:
#   set ENABLE_DB_INSERT=false
#   streamlit run rses_5.py
#
# 운영/병합 환경:
#   ENABLE_DB_INSERT=true   -> DB insert 수행
#   ENABLE_DB_INSERT=false  -> DB insert 미수행 + debug payload 노출

# -*- coding: utf-8 -*-
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="자아존중감 자기평가 검사",
    page_icon="🧠",
    layout="centered",
)

KST = timezone(timedelta(hours=9))

EXAM_NAME = "RSES_5"
EXAM_TITLE = "자아존중감 자기평가 검사"
EXAM_SUBTITLE = "Rosenberg Self-Esteem Scale 기반"
EXAM_VERSION = "streamlit_1.0"

REGION_OPTIONS = [
    "서울",
    "인천",
    "광주",
    "대전",
    "부산",
    "울산",
    "경기도",
    "충청도",
    "경상도",
    "전라도",
    "강원도",
    "제주도",
    "기타",
]

GENDER_OPTIONS = [
    "남성",
    "여성",
    "기타",
    "응답하지 않음",
]

SCALE_LABELS = [
    "전혀 그렇지 않다 (1)",
    "그렇지 않은 편이다 (2)",
    "보통이다 (3)",
    "그런 편이다 (4)",
    "매우 그렇다 (5)",
]

SCALE_TEXT_LABELS = [
    "전혀 그렇지 않다",
    "그렇지 않은 편이다",
    "보통이다",
    "그런 편이다",
    "매우 그렇다",
]

SCALE_SCORES = [1, 2, 3, 4, 5]

QUESTIONS = [
    "나는 다른 사람들과 동등한 수준에서 가치 있는 사람이라고 느낀다.",
    "나는 여러 가지 긍정적인 장점을 가지고 있다고 느낀다.",
    "전반적으로 나는 스스로를 실패한 사람이라고 느끼는 편이다.",
    "나는 대부분의 사람들만큼 일을 잘 해낼 수 있다고 생각한다.",
    "나는 자랑스럽게 여길 만한 것이 별로 없다고 느낀다.",
    "나는 나 자신에 대해 긍정적인 태도를 가지고 있다.",
    "전반적으로 나는 나 자신에게 만족한다.",
    "나는 스스로를 더 존중할 수 있었으면 좋겠다고 느낀다.",
    "나는 때때로 내가 쓸모없는 사람이라고 느낀다.",
    "나는 가끔 내가 전혀 쓸모없는 사람이라고 생각한다.",
]

REVERSE_ITEMS = {3, 5, 8, 9, 10}


def rses_level(total: int):
    if total >= 40:
        return (
            "높은 자아존중감",
            "전반적으로 자신을 긍정적으로 인식하고 있으며, 자기 가치감과 자기 존중감이 비교적 안정적인 수준으로 해석될 수 있습니다.",
        )
    if total >= 30:
        return (
            "보통 수준의 자아존중감",
            "자아존중감이 전반적으로 평균적인 수준으로 보입니다. 상황에 따라 자신에 대한 평가가 다소 흔들릴 수 있으나 전반적 적응은 무난한 편으로 볼 수 있습니다.",
        )
    return (
        "낮은 자아존중감",
        "자신에 대한 부정적 평가나 낮은 자기 가치감이 상대적으로 높을 수 있습니다. 이러한 느낌이 지속되거나 일상생활에 영향을 준다면 보다 세심한 자기이해와 정서적 점검이 도움이 될 수 있습니다.",
    )


def score_from_label(label: str | None):
    if not label:
        return None
    for idx, full_label in enumerate(SCALE_LABELS, start=1):
        if label == full_label:
            return idx
    return None


def label_from_score(score: int | None):
    if score is None:
        return None
    if score in SCALE_SCORES:
        return SCALE_LABELS[score - 1]
    return None


def reverse_score(value: int) -> int:
    return 6 - value


def now_iso():
    return datetime.now(KST).isoformat()


def init_state():
    if "page" not in st.session_state:
        st.session_state.page = "intro"

    if "meta" not in st.session_state:
        st.session_state.meta = {
            "respondent_id": str(uuid.uuid4()),
            "consent": False,
            "consent_ts": "",
            "started_ts": "",
            "submitted_ts": "",
        }

    if "examinee" not in st.session_state:
        st.session_state.examinee = {
            "name": "",
            "gender": "",
            "age": "",
            "region": "",
            "phone": "",
            "email": "",
        }

    if "answers" not in st.session_state:
        st.session_state.answers = {}

    if "result_payload" not in st.session_state:
        st.session_state.result_payload = None

    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False

    if "close_attempted" not in st.session_state:
        st.session_state.close_attempted = False

    if "last_q" not in st.session_state:
        st.session_state.last_q = None


def reset_all():
    respondent_id = str(uuid.uuid4())
    st.session_state.page = "intro"
    st.session_state.meta = {
        "respondent_id": respondent_id,
        "consent": False,
        "consent_ts": "",
        "started_ts": "",
        "submitted_ts": "",
    }
    st.session_state.examinee = {
        "name": "",
        "gender": "",
        "age": "",
        "region": "",
        "phone": "",
        "email": "",
    }
    st.session_state.answers = {}
    st.session_state.result_payload = None
    st.session_state.db_insert_done = False
    st.session_state.close_attempted = False
    st.session_state.last_q = None


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"[^0-9]", "", phone or "")
    return digits


def validate_name(name: str) -> str | None:
    if not name.strip():
        return "이름을 입력해 주세요."
    return None


def validate_age(age: str) -> str | None:
    age = (age or "").strip()
    if not age:
        return "연령을 입력해 주세요."
    if not age.isdigit():
        return "연령은 숫자로 입력해 주세요."
    age_num = int(age)
    if age_num < 1 or age_num > 120:
        return "연령은 1세 이상 120세 이하로 입력해 주세요."
    return None


def validate_gender(gender: str) -> str | None:
    if not (gender or "").strip():
        return "성별을 선택해 주세요."
    return None


def validate_region(region: str) -> str | None:
    if not (region or "").strip():
        return "거주지역을 선택해 주세요."
    return None


def validate_phone(phone: str) -> str | None:
    if not phone:
        return None
    if len(phone) not in (10, 11):
        return "휴대폰번호는 숫자만 입력 시 10자리 또는 11자리여야 합니다."
    return None


def validate_email(email: str) -> str | None:
    email = (email or "").strip()
    if not email:
        return None
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    if not re.match(pattern, email):
        return "이메일 형식이 올바르지 않습니다."
    return None


def _sanitize_csv_value(v) -> str:
    if v is None:
        return ""
    s = str(v)
    s = s.replace("\n", " ").replace("\r", " ")
    s = s.replace(",", " ")
    return s.strip()


def dict_to_kv_csv(d: dict) -> str:
    if not isinstance(d, dict):
        return ""
    parts = []
    for k, v in d.items():
        parts.append(f"{_sanitize_csv_value(k)}={_sanitize_csv_value(v)}")
    return ",".join(parts)


def build_payload():
    total_score = 0
    missing = []
    item_scores_raw = {}
    item_scores_final = {}

    for i, _ in enumerate(QUESTIONS, start=1):
        key = f"q{i}"
        value = st.session_state.answers.get(key)

        if value is None:
            missing.append(key)
            item_scores_raw[key] = None
            item_scores_final[key] = None
            continue

        raw_value = int(value)
        item_scores_raw[key] = raw_value

        if i in REVERSE_ITEMS:
            final_value = reverse_score(raw_value)
        else:
            final_value = raw_value

        item_scores_final[key] = final_value
        total_score += final_value

    severity, interpretation = rses_level(total_score)

    payload = {
        "instrument": EXAM_NAME,
        "title": EXAM_TITLE,
        "version": EXAM_VERSION,
        "respondent_id": st.session_state.meta["respondent_id"],
        "consent": st.session_state.meta["consent"],
        "consent_ts": st.session_state.meta["consent_ts"],
        "started_ts": st.session_state.meta["started_ts"],
        "submitted_ts": st.session_state.meta["submitted_ts"],
        "examinee": st.session_state.examinee,
        "items": {
            "scale": {
                "1": "전혀 그렇지 않다",
                "2": "그렇지 않은 편이다",
                "3": "보통이다",
                "4": "그런 편이다",
                "5": "매우 그렇다",
            },
            "questions": {f"q{i}": q for i, q in enumerate(QUESTIONS, start=1)},
            "answers": {f"q{i}": st.session_state.answers.get(f"q{i}") for i in range(1, 11)},
            "scores_raw": item_scores_raw,
            "scores_final": item_scores_final,
            "reverse_items": [f"q{i}" for i in sorted(REVERSE_ITEMS)],
        },
        "result": {
            "total": total_score,
            "level": severity,
            "interpretation": interpretation,
            "score_range": {"min": 10, "max": 50},
        },
    }
    return payload, missing


def build_exam_data(payload: dict) -> dict:
    examinee = payload.get("examinee", {})
    answers = payload.get("items", {}).get("answers", {})
    result = payload.get("result", {})

    consent_col = {
        "consent": payload.get("consent", False),
        "consent_ts": payload.get("consent_ts", ""),
        "started_ts": payload.get("started_ts", ""),
        "submitted_ts": payload.get("submitted_ts", ""),
        "respondent_id": payload.get("respondent_id", ""),
    }

    examinee_col = {
        "name": examinee.get("name", ""),
        "gender": examinee.get("gender", ""),
        "age": examinee.get("age", ""),
        "region": examinee.get("region", ""),
        "phone": examinee.get("phone", ""),
        "email": examinee.get("email", ""),
    }

    answers_col = {
        f"q{i}": answers.get(f"q{i}", "")
        for i in range(1, 11)
    }

    result_col = {
        "total": result.get("total", ""),
        "level": result.get("level", ""),
        "interpretation": result.get("interpretation", ""),
        "reverse_items": "|".join(payload.get("items", {}).get("reverse_items", [])),
    }

    exam_data = {
        "exam_name": EXAM_NAME,
        "consent_col": dict_to_kv_csv(consent_col),
        "examinee_col": dict_to_kv_csv(examinee_col),
        "answers_col": dict_to_kv_csv(answers_col),
        "result_col": dict_to_kv_csv(result_col),
    }
    return exam_data


def render_stepper(current_page: str):
    steps = [
        ("intro", "동의"),
        ("info", "정보입력"),
        ("survey", "문항응답"),
        ("result", "결과"),
    ]
    idx_map = {key: i for i, (key, _) in enumerate(steps)}
    current_idx = idx_map.get(current_page, 0)

    html = ["<div class='stepper'>"]
    for i, (key, label) in enumerate(steps):
        state = "done" if i < current_idx else "active" if i == current_idx else "todo"
        html.append(f"""
            <div class='step-item {state}'>
                <div class='step-circle'>{i+1}</div>
                <div class='step-label'>{label}</div>
            </div>
        """)
        if i < len(steps) - 1:
            line_state = "done" if i < current_idx else "todo"
            html.append(f"<div class='step-line {line_state}'></div>")
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_answer_segments(q_key: str, selected_score: int | None):
    options_html = ["<div class='segmented'>"]
    for score, label in zip(SCALE_SCORES, SCALE_TEXT_LABELS):
        checked = "checked" if selected_score == score else ""
        options_html.append(
            f"""
            <label class="seg-option">
                <input type="radio" name="{q_key}" value="{score}" {checked}>
                <span>{label}</span>
            </label>
            """
        )
    options_html.append("</div>")

    components.html(
        f"""
        <html>
        <head>
        <style>
            body {{
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            .segmented {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 8px;
                margin-top: 12px;
            }}
            .seg-option {{
                display: block;
                cursor: pointer;
            }}
            .seg-option input {{
                display: none;
            }}
            .seg-option span {{
                display: block;
                border: 1px solid #d1d5db;
                border-radius: 12px;
                padding: 12px 14px;
                background: #fff;
                font-size: 14px;
                line-height: 1.4;
            }}
            .seg-option input:checked + span {{
                border-color: #1d4ed8;
                background: #eff6ff;
                font-weight: 600;
            }}
            .seg-option span:hover {{
                border-color: #93c5fd;
            }}
        </style>
        </head>
        <body>
            {''.join(options_html)}
            <script>
                const radios = document.querySelectorAll('input[type="radio"]');
                radios.forEach((radio) => {{
                    radio.addEventListener('change', function() {{
                        const value = this.value;
                        window.parent.postMessage({{
                            isStreamlitMessage: true,
                            type: "streamlit:setComponentValue",
                            value: value
                        }}, "*");
                    }});
                }});
            </script>
        </body>
        </html>
        """,
        height=260,
        scrolling=False,
    )


def inject_css():
    st.markdown(
        """
        <style>
        .page-wrap { max-width: 840px; margin: 0 auto; padding-bottom: 48px; }
        .card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 20px;
            padding: 22px 22px;
            box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
            margin-bottom: 16px;
        }
        .card.soft {
            background: #f8fafc;
        }
        .badge {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 999px;
            background: #eef2ff;
            color: #3730a3;
            font-size: 12px;
            font-weight: 700;
            margin-right: 8px;
            margin-bottom: 8px;
        }
        .title-lg {
            font-size: 28px;
            font-weight: 800;
            line-height: 1.3;
            margin: 6px 0 0;
            color: #111827;
        }
        .title-md {
            font-size: 20px;
            font-weight: 700;
            line-height: 1.35;
            margin: 0 0 8px;
            color: #111827;
        }
        .text {
            font-size: 15px;
            line-height: 1.7;
            color: #374151;
        }
        .muted {
            font-size: 13px;
            line-height: 1.6;
            color: #6b7280;
        }
        .note-box {
            background: #fff7ed;
            border: 1px solid #fed7aa;
            border-radius: 16px;
            padding: 14px 16px;
        }
        .stepper {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin: 10px 0 22px;
            flex-wrap: wrap;
        }
        .step-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 72px;
        }
        .step-circle {
            width: 34px;
            height: 34px;
            border-radius: 999px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 14px;
            border: 1px solid #cbd5e1;
            background: #fff;
            color: #64748b;
        }
        .step-item.active .step-circle {
            background: #2563eb;
            border-color: #2563eb;
            color: #fff;
        }
        .step-item.done .step-circle {
            background: #1e40af;
            border-color: #1e40af;
            color: #fff;
        }
        .step-label {
            margin-top: 6px;
            font-size: 12px;
            color: #64748b;
            font-weight: 600;
            text-align: center;
        }
        .step-item.active .step-label,
        .step-item.done .step-label {
            color: #1f2937;
        }
        .step-line {
            width: 42px;
            height: 2px;
            background: #cbd5e1;
            border-radius: 999px;
        }
        .step-line.done {
            background: #1e40af;
        }
        .question-title {
            font-size: 18px;
            font-weight: 700;
            line-height: 1.55;
            color: #111827;
        }
        .progress-row {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            margin-top: 12px;
            margin-bottom: 8px;
        }
        .progress-label {
            font-size: 13px;
            color: #475569;
            font-weight: 600;
        }
        .meter {
            width: 100%;
            height: 10px;
            background: #e5e7eb;
            border-radius: 999px;
            overflow: hidden;
        }
        .meter > span {
            display: block;
            height: 100%;
            background: #2563eb;
            border-radius: 999px;
        }
        .result-score {
            font-size: 38px;
            font-weight: 800;
            line-height: 1.1;
            color: #111827;
            margin: 0;
        }
        .result-level {
            font-size: 18px;
            font-weight: 700;
            color: #1d4ed8;
            margin: 6px 0 0;
        }
        .footer-note {
            font-size: 13px;
            color: #6b7280;
            line-height: 1.7;
        }
        div[data-testid="stRadio"] {
            margin-top: 12px;
        }
        div[data-testid="stRadio"] > label {
            margin-bottom: 0;
        }
        div[data-testid="stRadio"] div[role="radiogroup"] {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0;
            width: 100%;
            min-width: 0;
            border: 1px solid rgba(148, 163, 184, 0.55);
            border-radius: 10px;
            overflow: hidden;
            background: rgba(255, 255, 255, 0.04);
        }
        div[data-testid="stRadio"] div[role="radiogroup"] > label {
            margin: 0 !important;
            min-width: 0;
            width: 100%;
        }
        div[data-testid="stRadio"] div[role="radiogroup"] > label > div {
            width: 100%;
            min-height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 0;
            border-right: 1px solid rgba(148, 163, 184, 0.45);
            border-radius: 0;
            padding: 0;
            background: transparent;
            font-size: 15px;
            font-weight: 600;
            color: inherit;
            transition: background-color 0.15s ease, color 0.15s ease;
        }
        div[data-testid="stRadio"] div[role="radiogroup"] > label:last-child > div {
            border-right: 0;
        }
        div[data-testid="stRadio"] div[role="radiogroup"] > label:hover > div {
            background: rgba(59, 130, 246, 0.08);
        }
        div[data-testid="stRadio"] div[role="radiogroup"] > label[data-baseweb="radio"] input:checked + div {
            background: rgba(59, 130, 246, 0.18);
            color: #60a5fa;
            box-shadow: inset 0 0 0 1px rgba(96, 165, 250, 0.45);
        }
        .likert-edge-label {
            margin-top: 12px;
            min-height: 48px;
            display: flex;
            align-items: center;
            font-size: 13px;
            font-weight: 600;
            color: #6b7280;
            white-space: nowrap;
        }
        .likert-edge-label.right {
            justify-content: flex-end;
            text-align: right;
        }
        @media (max-width: 640px) {
            .likert-edge-label,
            .likert-edge-label.right {
                justify-content: center;
                text-align: center;
                min-height: auto;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_intro():
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    st.markdown(
        f"""
        <section class="card">
            <span class="badge">RSES 기반</span>
            <span class="badge">총 10문항</span>
            <h1 class="title-lg">{EXAM_TITLE}</h1>
            <p class="text" style="margin-top:8px;">
                본 검사는 자신에 대한 전반적인 인식과 태도를 살펴보기 위한 자기보고식 검사입니다.
                약 2~3분 내에 완료하실 수 있습니다.
            </p>
            <div class="note-box" style="margin-top:12px;">
                <p class="text" style="margin:0;">
                    <strong>안내:</strong> 본 결과는 참고용이며 임상적 진단을 대체하지 않습니다.
                    지속적인 불편감이 있거나 일상 기능에 어려움이 있다면 전문가 상담을 권장드립니다.
                </p>
                <p class="muted" style="margin:8px 0 0;">
                    입력하신 응답은 현재 세션에서 결과 산출에 사용되며, 저장 여부는 연동 환경 설정에 따라 달라질 수 있습니다.
                </p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <section class="card soft">
            <h2 class="title-md">검사 진행 동의</h2>
            <p class="text">
                검사 진행과 결과 산출을 위해 기본 인적사항을 수집합니다.
                아래 안내를 확인하신 후 동의해 주세요.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    consent = st.checkbox(
        "예, 위 안내를 확인하였고 검사 진행에 동의합니다.",
        value=st.session_state.meta["consent"],
    )
    st.session_state.meta["consent"] = consent

    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("검사 시작", type="primary", disabled=not consent, use_container_width=True):
            now = now_iso()
            st.session_state.meta["consent_ts"] = now
            st.session_state.meta["started_ts"] = now
            st.session_state.page = "info"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def page_info():
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    st.markdown(
        """
        <section class="card">
            <h1 class="title-lg">기본 정보 입력</h1>
            <p class="text" style="margin-top:8px;">
                아래 정보를 입력해 주세요. 이름, 성별, 연령, 거주지역은 필수 항목이며
                휴대폰번호와 이메일은 선택 입력 항목입니다.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    info_row_1_col_1, info_row_1_col_2 = st.columns(2)
    with info_row_1_col_1:
        name = st.text_input("이름", value=st.session_state.examinee.get("name", ""))
    with info_row_1_col_2:
        gender = st.selectbox(
            "성별",
            options=[""] + GENDER_OPTIONS,
            index=([""] + GENDER_OPTIONS).index(st.session_state.examinee.get("gender", "")) if st.session_state.examinee.get("gender", "") in ([""] + GENDER_OPTIONS) else 0,
        )

    info_row_2_col_1, info_row_2_col_2 = st.columns(2)
    with info_row_2_col_1:
        age = st.text_input("연령", value=st.session_state.examinee.get("age", ""))
    with info_row_2_col_2:
        region = st.selectbox(
            "거주지역",
            options=[""] + REGION_OPTIONS,
            index=([""] + REGION_OPTIONS).index(st.session_state.examinee.get("region", "")) if st.session_state.examinee.get("region", "") in ([""] + REGION_OPTIONS) else 0,
        )

    phone_input = st.text_input("휴대폰번호 (선택)", value=st.session_state.examinee.get("phone", ""))
    email = st.text_input("이메일 (선택)", value=st.session_state.examinee.get("email", ""))

    normalized_phone = normalize_phone(phone_input)

    st.session_state.examinee = {
        "name": name.strip(),
        "gender": gender.strip(),
        "age": age.strip(),
        "region": region.strip(),
        "phone": normalized_phone,
        "email": email.strip(),
    }

    name_error = validate_name(name)
    gender_error = validate_gender(gender)
    age_error = validate_age(age)
    region_error = validate_region(region)
    phone_error = validate_phone(normalized_phone)
    email_error = validate_email(email)

    # 필수 입력 누락만 모아서 표시
    missing_fields = []

    if name_error:
        missing_fields.append("이름")

    if gender_error:
        missing_fields.append("성별")

    if age_error:
        missing_fields.append("연령")

    if region_error:
        missing_fields.append("거주지역")

    if missing_fields:
        st.error(f"{', '.join(missing_fields)}을 입력해주세요.")

    # 선택항목은 따로 표시 (원하면 유지)
    if phone_error:
        st.warning(phone_error)

    if email_error:
        st.warning(email_error)

    # 버튼 활성화 기준
    all_valid = len(missing_fields) == 0

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("이전", use_container_width=True):
            st.session_state.page = "intro"
            st.rerun()
    with c2:
        if st.button("다음", type="primary", disabled=not all_valid, use_container_width=True):
            st.session_state.page = "survey"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def page_survey(dev_mode: bool = False):
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    payload, missing = build_payload()
    answered_count = 10 - len(missing)
    progress_pct = int((answered_count / 10) * 100)

    st.markdown(
        f"""
        <section class="card">
            <span class="badge">문항 10개</span>
            <h1 class="title-lg">문항 응답</h1>
            <p class="text">현재 자신의 모습에 가장 가까운 응답을 선택해 주세요.</p>
            <div class="progress-row">
                <span class="progress-label">진행률 {answered_count}/10</span>
                <span class="progress-label">{progress_pct}%</span>
            </div>
            <div class="meter"><span style="width:{progress_pct}%;"></span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    for i, q in enumerate(QUESTIONS, start=1):
        key = f"q{i}"
        current_value = st.session_state.answers.get(key)

        st.markdown(f"<div id='q-anchor-{key}'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <section class="card">
                <div class="question-title">{i}. {q}</div>
            """,
            unsafe_allow_html=True,
        )

        likert_left, likert_center, likert_right = st.columns([1.9, 4.2, 1.9], vertical_alignment="center")
        with likert_left:
            st.markdown("<div class='likert-edge-label'>전혀 그렇지 않다</div>", unsafe_allow_html=True)
        with likert_center:
            selected = st.radio(
                label=f"{i}번 문항 응답",
                options=SCALE_SCORES,
                format_func=lambda x: str(x),
                index=SCALE_SCORES.index(current_value) if current_value in SCALE_SCORES else None,
                key=f"radio_{key}",
                label_visibility="collapsed",
                horizontal=True,
            )
        with likert_right:
            st.markdown("<div class='likert-edge-label right'>매우 그렇다</div>", unsafe_allow_html=True)
        st.session_state.answers[key] = selected
        st.markdown("</section>", unsafe_allow_html=True)

    last_q = st.session_state.get("last_q")
    if last_q:
        components.html(
            f"""
            <script>
              const el = parent.document.getElementById("q-anchor-{last_q}");
              if (el) el.scrollIntoView({{behavior: "auto", block: "center"}});
            </script>
            """,
            height=0,
            scrolling=False,
        )

    payload, missing = build_payload()
    all_done = len(missing) == 0

    if not all_done:
        st.caption("모든 문항에 응답하면 결과 보기가 활성화됩니다.")

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("이전", use_container_width=True):
            st.session_state.page = "info"
            st.rerun()
    with c2:
        if st.button("결과 보기", type="primary", disabled=not all_done, use_container_width=True):
            st.session_state.meta["submitted_ts"] = now_iso()
            payload, missing = build_payload()
            st.session_state.result_payload = payload
            st.session_state.page = "result"
            st.rerun()

    if dev_mode:
        st.caption("개발 모드 payload")
        st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")

    st.markdown("</div>", unsafe_allow_html=True)


def page_result(dev_mode: bool = False):
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    internal_payload = st.session_state.result_payload
    if not internal_payload:
        st.warning("결과 데이터가 없습니다. 다시 진행해 주세요.")
        if st.button("처음으로", use_container_width=True):
            reset_all()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    exam_data = build_exam_data(internal_payload)
    auto_db_insert(exam_data)

    result = internal_payload["result"]
    total = result["total"]
    level = result["level"]
    interpretation = result["interpretation"]

    st.markdown(
        f"""
        <section class="card">
            <span class="badge">검사 완료</span>
            <h1 class="title-lg">검사 결과</h1>
            <p class="result-score" style="margin-top:16px;">{total}점</p>
            <p class="result-level">{level}</p>
            <p class="text" style="margin-top:14px;">{interpretation}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <section class="card soft">
            <h2 class="title-md">안내</h2>
            <p class="footer-note">
                본 결과는 참고용이며, 개인의 상태를 종합적으로 판단하는 전문적 평가를 대체하지 않습니다.
                자신에 대한 부정적 평가가 지속되거나 정서적 어려움이 반복된다면 전문가와 상담해 보시길 권장드립니다.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("검사 다시하기", type="primary", use_container_width=True):
            reset_all()
            st.rerun()
    with c2:
        if st.button("닫기", use_container_width=True):
            st.session_state.close_attempted = True
            components.html(
                """
                <script>
                    try { window.close(); } catch (e) {}
                </script>
                """,
                height=0,
            )
            st.rerun()

    if st.session_state.close_attempted:
        st.warning("탭이 자동으로 닫히지 않는 경우, 사용자가 직접 탭을 닫아주세요.")

    if dev_mode:
        st.caption("개발 모드 internal payload")
        st.code(json.dumps(internal_payload, ensure_ascii=False, indent=2), language="json")
        st.caption("개발 모드 DB exam_data")
        st.code(json.dumps(exam_data, ensure_ascii=False, indent=2), language="json")

    st.markdown("</div>", unsafe_allow_html=True)


def main():
    inject_css()
    init_state()

    params = st.query_params
    dev_mode = str(params.get("dev", "0")) == "1"

    st.caption("RSES 기반 자아존중감 자기평가 검사 · Streamlit 웹 인터페이스")

    if st.session_state.page == "intro":
        page_intro()
    elif st.session_state.page == "info":
        if not st.session_state.meta.get("consent"):
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            st.rerun()
        page_info()
    elif st.session_state.page == "survey":
        if not st.session_state.meta.get("consent"):
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            st.rerun()
        if not st.session_state.examinee.get("name", "").strip():
            st.session_state.page = "info"
            st.rerun()
        page_survey(dev_mode=dev_mode)
    elif st.session_state.page == "result":
        page_result(dev_mode=dev_mode)
    else:
        st.session_state.page = "intro"
        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# 데이터 저장 분기 + DB 연동 전용 블록
def _is_db_insert_enabled() -> bool:
    raw = os.getenv("ENABLE_DB_INSERT", "true")
    return str(raw).strip().lower() != "false"


ENABLE_DB_INSERT = _is_db_insert_enabled()

if ENABLE_DB_INSERT:
    from utils.database import Database


def safe_db_insert(exam_data: dict) -> bool:
    """
    dev PC: ENABLE_DB_INSERT=false → 저장 호출 안 함
    운영/병합: ENABLE_DB_INSERT가 false가 아니면 → Database().insert(exam_data) 수행
    """
    if not ENABLE_DB_INSERT:
        return False
    try:
        db = Database()
        db.insert(exam_data)
        return True
    except Exception as e:
        print(f"[DB INSERT ERROR] {e}")
        return False


def auto_db_insert(exam_data: dict) -> None:
    """
    결과 저장 자동 호출
    - 개발 환경(ENABLE_DB_INSERT=false): DB insert 미실행 + exam_data expander로 노출
    - 활성 환경: 이름 검증 후 DB 저장 1회 시도 (성공 시 중복 방지 플래그 ON)
    """
    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False
    if st.session_state.db_insert_done:
        return

    if not ENABLE_DB_INSERT:
        with st.expander("DB disabled debug payload", expanded=False):
            st.json(exam_data)
        st.caption("DB disabled (ENABLE_DB_INSERT=false)")
        return

    if not st.session_state.examinee.get("name"):
        st.error("이름을 입력해 주세요.")
        return

    ok = safe_db_insert(exam_data)
    if ok:
        st.session_state.db_insert_done = True
        st.success("검사 완료")
    else:
        st.warning("DB 저장이 수행되지 않았습니다. 환경/모듈 상태를 확인해 주세요.")


if __name__ == "__main__":
    main()