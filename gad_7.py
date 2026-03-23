# 실행 방법:
#   streamlit run gad_7.py

# -*- coding: utf-8 -*-
import html
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="GAD-7 불안검사",
    page_icon="🧠",
    layout="centered",
)

KST = timezone(timedelta(hours=9))

SCALE_LABELS = [
    "전혀 없음 (0)",
    "몇 일 동안 (1)",
    "일주일 이상 (2)",
    "거의 매일 (3)",
]

SCALE_SHORT = {
    "전혀 없음 (0)": "전혀 없음",
    "몇 일 동안 (1)": "몇 일 동안",
    "일주일 이상 (2)": "일주일 이상",
    "거의 매일 (3)": "거의 매일",
}

SCALE_TEXT_LABELS = [
    "전혀 없음",
    "몇 일 동안",
    "일주일 이상",
    "거의 매일",
]

SCALE_SCORES = [0, 1, 2, 3]

REGION_OPTIONS = [
    "수도권",
    "충청권",
    "강원권",
    "전라권",
    "경상권",
    "제주도",
]

GENDER_OPTIONS = [
    "남성",
    "여성",
    "기타",
    "응답하지 않음",
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

INTRO_CARD_TITLE = "불안검사 (Generalized Anxiety Disorder-7)"
INTRO_BADGES = ["GAD-7", "최근 2주"]
INTRO_DESC_BULLETS = [
    "이 검사는 최근 2주 동안 경험한 불안 관련 증상의 빈도를 살펴보기 위한 자기보고식 검사입니다.",
    "검사 목적은 현재의 불안 정도를 참고용으로 확인하고, 필요한 경우 추가적인 도움을 고려할 수 있도록 돕는 데 있습니다.",
    "총 7개 문항으로 구성되어 있으며, 보통 2~3분 정도면 완료할 수 있습니다.",
]
INTRO_NOTICE_TITLE = "참고용 안내"
INTRO_NOTICE_BULLETS = [
    "응답은 최근 2주를 기준으로, 자신에게 가장 가까운 빈도를 선택해 주세요.",
    "결과는 참고용 안내이며 의료적 진단이나 치료 판단을 대체하지 않습니다.",
    "불안으로 인한 불편감이 지속되거나 일상 기능 저하가 느껴진다면 전문가 상담을 권장합니다.",
]
PRIVACY_CARD_TITLE = "개인정보 수집 및 검사 진행 동의"
PRIVACY_BULLETS = [
    "검사 진행을 위해 이름, 성별, 연령, 거주지역 등 기본 정보를 입력받습니다. 휴대폰 번호와 이메일은 선택 입력 항목입니다.",
    "입력된 개인정보는 KIRBS+의 개인정보 관련 약관에 적용되며 약관에 따라 저장 및 활용될 수 있습니다.",
    "동의 후 검사 시작 시점과 동의 시점 정보가 기록되며, 이후 응답 내용은 결과 산출에 사용됩니다.",
]
CONSENT_CHECKBOX_LABEL = "예, 개인정보 수집·이용 및 검사 진행 안내를 확인하였으며 이에 동의합니다."


def gad7_level(total: int):
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


def score_from_label(label: str):
    if isinstance(label, int) and label in SCALE_SCORES:
        return label
    if label is None:
        return None
    try:
        return int(label.split("(")[-1].split(")")[0])
    except Exception:
        return None


def format_select_option(value: str) -> str:
    return "선택해 주세요" if value == "" else value


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
        st.session_state.answers = {f"q{i}": None for i in range(1, 8)}

    if "examinee" not in st.session_state:
        st.session_state.examinee = {
            "name": "",
            "gender": "",
            "age": "",
            "region": "",
            "phone": "",
            "email": "",
        }

    if "close_attempted" not in st.session_state:
        st.session_state.close_attempted = False

    if "last_q" not in st.session_state:
        st.session_state.last_q = None

    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False


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
    st.session_state.examinee = {
        "name": "",
        "gender": "",
        "age": "",
        "region": "",
        "phone": "",
        "email": "",
    }
    st.session_state.close_attempted = False
    st.session_state.last_q = None
    st.session_state.db_insert_done = False


def select_answer(q_key: str, score: int):
    st.session_state.answers[q_key] = score
    st.session_state.last_q = q_key


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


def build_exam_data_gad7(payload: dict) -> dict:
    exam_name = payload.get("instrument", "GAD_7")

    consent_meta = {
        "consent": payload.get("consent"),
        "consent_ts": payload.get("consent_ts"),
        "started_ts": payload.get("started_ts"),
        "submitted_ts": payload.get("submitted_ts"),
        "version": payload.get("version"),
        "respondent_id": payload.get("respondent_id"),
    }

    examinee = payload.get("examinee", {}) or {}

    items = payload.get("items", {}) or {}
    scores = items.get("scores", {}) or {}
    answers = dict(scores)

    result_raw = payload.get("result", {}) or {}
    result_flat = {
        "total": result_raw.get("total"),
        "severity": result_raw.get("level"),
        "interpretation": result_raw.get("interpretation"),
        "rule_of_thumb_ge10": ((result_raw.get("rule_of_thumb", {}) or {}).get(">=10")),
        "rule_of_thumb_ge15": ((result_raw.get("rule_of_thumb", {}) or {}).get(">=15")),
        "flag_recommend_counseling": ((result_raw.get("flags", {}) or {}).get("recommend_counseling")),
        "flag_recommend_clinic": ((result_raw.get("flags", {}) or {}).get("recommend_clinic")),
    }

    return {
        "exam_name": _sanitize_csv_value(exam_name),
        "consent_col": dict_to_kv_csv(consent_meta),
        "examinee_col": dict_to_kv_csv(examinee),
        "answers_col": dict_to_kv_csv(answers),
        "result_col": dict_to_kv_csv(result_flat),
    }


def build_payload():
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
        "instrument": "GAD_7",
        "version": "streamlit_1.0",
        "respondent_id": st.session_state.meta["respondent_id"],
        "consent": st.session_state.meta["consent"],
        "consent_ts": st.session_state.meta["consent_ts"],
        "started_ts": st.session_state.meta["started_ts"],
        "submitted_ts": st.session_state.meta["submitted_ts"],
        "examinee": st.session_state.examinee,
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


def get_level_key(level_text: str) -> str:
    if "최소/거의 없음" in level_text:
        return "minimal"
    if "경도" in level_text:
        return "mild"
    if "중등도" in level_text:
        return "moderate"
    return "severe"


def render_stepper(current_page: str):
    status_by_page = {
        "intro": ["active", "todo", "todo", "todo"],
        "info": ["completed", "active", "todo", "todo"],
        "survey": ["completed", "completed", "active", "todo"],
        "result": ["completed", "completed", "completed", "active"],
    }
    step_statuses = status_by_page.get(current_page, status_by_page["intro"])
    steps = [
        ("1", "안내/동의"),
        ("2", "개인정보 입력"),
        ("3", "문항 응답"),
        ("4", "결과 확인"),
    ]

    step_items_html = []
    for idx, (num, label) in enumerate(steps):
        state = step_statuses[idx]
        aria_current = ' aria-current="step"' if state == "active" else ""
        dot_content = "✓" if state == "completed" else num
        connector = ""
        if idx < len(steps) - 1:
            connector_state = "filled" if step_statuses[idx] == "completed" else "todo"
            connector = (
                '<div class="step-connector" aria-hidden="true">'
                f'<span class="connector-fill {connector_state}"></span>'
                "</div>"
            )

        step_items_html.append(
            f"""
            <div class="step-item {state}"{aria_current}>
                <div class="step-main">
                    <div class="step-dot">{dot_content}</div>
                    <div class="step-label">{label}</div>
                </div>
                {connector}
            </div>
            """
        )

    component_html = f"""
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          .app-stepper,
          .app-stepper * {{ box-sizing: border-box; }}

          .app-stepper {{
            width: 100%;
            margin: 0;
            padding: 0;
            background: transparent;
            display: flex;
            justify-content: center;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
            color: #f8fbff;
          }}

          .app-stepper .stepper-inner {{
            width: 100%;
            max-width: 860px;
            margin: 0 auto;
            padding: 0;
          }}

          .app-stepper {{
            --card: #0d2140;
            --border: rgba(148, 163, 184, 0.26);
            --text: #f8fbff;
            --muted: #c7d3e3;
            --primary: #4f9cff;
            --success: #56e39a;
          }}

          .app-stepper .step-track {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            overflow: hidden;
          }}

          .app-stepper .step-item {{
            flex: 0 0 auto;
            min-width: 0;
            display: flex;
            align-items: center;
            gap: 12px;
          }}

          .app-stepper .step-main {{
            flex: 0 1 auto;
            min-width: 100px;
            border: 1px solid var(--border);
            border-radius: 14px;
            background: var(--card);
            padding: 9px 8px 8px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 5px;
            position: relative;
            overflow: hidden;
            transition: border-color .24s ease, background-color .24s ease, box-shadow .24s ease;
          }}

          .app-stepper .step-main::after {{
            content: "";
            position: absolute;
            left: 12px;
            right: 12px;
            bottom: 6px;
            height: 2px;
            background: var(--primary);
            transform: scaleX(0);
            transform-origin: left center;
            opacity: 0;
            transition: transform .3s ease, opacity .3s ease;
          }}

          .app-stepper .step-dot {{
            width: 28px;
            height: 28px;
            border-radius: 999px;
            border: 1px solid var(--border);
            display: grid;
            place-items: center;
            font-size: .84rem;
            font-weight: 800;
            line-height: 1;
            color: var(--muted);
            background: rgba(255,255,255,0.08);
            transition: transform .24s ease, background-color .24s ease, border-color .24s ease, color .24s ease, box-shadow .24s ease;
          }}

          .app-stepper .step-label {{
            font-size: .79rem;
            line-height: 1.25;
            font-weight: 700;
            text-align: center;
            color: var(--muted);
            transform: translateY(2px);
            opacity: .9;
            transition: color .24s ease, opacity .24s ease, transform .24s ease;
            word-break: keep-all;
          }}

          .app-stepper .step-connector {{
            flex: 1 1 auto;
            min-width: 70px;
            height: 2px;
            border-radius: 999px;
            background: rgba(148,163,184,0.20);
            overflow: hidden;
            align-self: center;
          }}

          .app-stepper .connector-fill {{
            display: block;
            width: 100%;
            height: 100%;
            border-radius: inherit;
            transform-origin: left center;
            transition: transform .35s ease, opacity .3s ease;
          }}

          .app-stepper .connector-fill.filled {{
            background: linear-gradient(90deg, var(--success), #79ecb4);
            transform: scaleX(1);
            opacity: .95;
          }}

          .app-stepper .connector-fill.todo {{
            background: linear-gradient(90deg, rgba(79,156,255,.45), rgba(79,156,255,.30));
            transform: scaleX(.18);
            opacity: .35;
          }}

          .app-stepper .step-item.active .step-main {{
            border-color: rgba(120, 173, 255, 0.9);
            box-shadow: 0 0 0 1px rgba(79,156,255,0.38);
          }}

          .app-stepper .step-item.active .step-main::after {{
            transform: scaleX(1);
            opacity: .92;
          }}

          .app-stepper .step-item.active .step-dot {{
            background: var(--primary);
            border-color: var(--primary);
            color: #fff;
          }}

          .app-stepper .step-item.active .step-label {{
            color: var(--text);
            opacity: 1;
            transform: translateY(0);
          }}

          .app-stepper .step-item.completed .step-main {{
            border-color: rgba(86,227,154,.75);
          }}

          .app-stepper .step-item.completed .step-dot {{
            background: var(--success);
            border-color: var(--success);
            color: #fff;
          }}

          .app-stepper .step-item.completed .step-label {{
            color: var(--text);
            opacity: .95;
            transform: translateY(0);
          }}

          @media (max-width: 640px) {{
            .app-stepper .step-track {{
              flex-wrap: nowrap;
              gap: 6px;
            }}

            .app-stepper .step-item {{
              flex: 1 1 0;
              gap: 6px;
            }}

            .app-stepper .step-main {{
              width: 100%;
              min-width: 0;
              gap: 7px;
              padding: 7px 5px;
            }}

            .app-stepper .step-dot {{
              width: 24px;
              height: 24px;
              font-size: .76rem;
            }}

            .app-stepper .step-label {{
              font-size: .72rem;
              text-align: center;
              white-space: normal;
            }}
          }}
        </style>
      </head>
      <body>
        <div class="app-stepper" data-step="{current_page}" role="group" aria-label="GAD-7 단계 진행">
          <div class="stepper-inner">
            <div class="step-track">
              {''.join(step_items_html)}
            </div>
          </div>
        </div>
      </body>
    </html>
    """

    st.markdown('<div class="stepper-wrap">', unsafe_allow_html=True)
    components.html(component_html, height=80, scrolling=False)
    st.markdown("</div>", unsafe_allow_html=True)


def render_bullet_list(items: list[str], css_class: str = "intro-bullets") -> str:
    list_items = "".join(f"<li>{html.escape(item)}</li>" for item in items)
    return f'<ul class="{html.escape(css_class, quote=True)}">{list_items}</ul>'


def render_answer_segments(q_key: str, selected_score: int | None):
    st.markdown(f"<div id='seg-{q_key}' class='answer-segments'>", unsafe_allow_html=True)
    cols = st.columns(4, gap="small")

    for idx, (label, score) in enumerate(zip(SCALE_TEXT_LABELS, SCALE_SCORES)):
        with cols[idx]:
            st.button(
                label,
                key=f"{q_key}_opt_{score}",
                type="primary" if selected_score == score else "secondary",
                use_container_width=True,
                on_click=select_answer,
                args=(q_key, score),
            )

    st.markdown("</div>", unsafe_allow_html=True)


def inject_css():
    st.markdown(
        """
        <style>
        :root {
            --content-max-width: 860px;

            --bg: #071225;
            --surface: #0b1a33;
            --surface-2: #0d2140;
            --surface-3: #10284c;

            --text: #f8fbff;
            --muted: #c7d3e3;

            --line: rgba(148, 163, 184, 0.28);
            --primary: #4f9cff;
            --primary-soft: rgba(79, 156, 255, 0.16);

            --success: #56e39a;
            --warning: #ffb454;
            --danger: #ff7373;

            --field-bg: #10284c;
            --field-bg-hover: #13315d;
            --field-border: rgba(96, 165, 250, 0.52);
            --field-border-strong: rgba(120, 173, 255, 0.9);
            --field-shadow: 0 0 0 3px rgba(79, 156, 255, 0.16);

            --radius-xl: 20px;
            --shadow-sm: 0 8px 24px rgba(2, 8, 23, 0.28);
            --shadow-md: 0 18px 40px rgba(2, 8, 23, 0.38);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(79,156,255,.08), transparent 30%),
                linear-gradient(180deg, #06101f 0%, #071225 100%);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
            letter-spacing: -0.01em;
        }

        .block-container {
            max-width: var(--content-max-width);
            padding-top: 0.75rem !important;
            padding-bottom: 3.2rem;
        }

        header[data-testid="stHeader"] {
            display: none !important;
            height: 0 !important;
        }

        [data-testid="stToolbar"] {
            display: none !important;
        }

        #MainMenu,
        footer {
            visibility: hidden !important;
            display: none !important;
        }

        div[data-testid="stDecoration"] {
            display: none !important;
        }

        .stepper-wrap {
            width: min(100%, var(--content-max-width));
            margin: 0 auto 8px;
            padding: 0 1.25rem;
        }

        .stepper-wrap > div[data-testid="stHtml"] {
            width: 100%;
        }

        .stepper-wrap > div[data-testid="stHtml"] > iframe,
        .stepper-wrap > div[data-testid="stHtml"] iframe,
        div[data-testid="stHtml"],
        div[data-testid="stHtml"] > div,
        div[data-testid="stHtml"] > div > iframe,
        div[data-testid="stHtml"] iframe {
            width: 100% !important;
            max-width: var(--content-max-width) !important;
            margin-left: auto !important;
            margin-right: auto !important;
            display: block !important;
            padding: 0 !important;
            border: 0 !important;
            left: auto !important;
            right: auto !important;
            transform: none !important;
        }

        .page-wrap {
            animation: fadeIn .25s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .card {
            background: linear-gradient(180deg, rgba(255,255,255,.015), rgba(255,255,255,.005)), var(--surface);
            border: 1px solid var(--line);
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow-sm);
            padding: 20px;
            margin-bottom: 12px;
        }

        .card.soft {
            background: linear-gradient(180deg, rgba(255,255,255,.012), rgba(255,255,255,.004)), var(--surface-2);
        }

        .title-lg {
            font-size: clamp(22px, 2.8vw, 29px) !important;
            font-weight: 800;
            line-height: 1.3;
            color: var(--text);
        }

        .title-md {
            font-size: clamp(17px, 2.2vw, 19px) !important;
            font-weight: 750;
            line-height: 1.35;
            color: var(--text);
        }

        .text {
            font-size: clamp(15px, 1.9vw, 16px) !important;
            line-height: 1.72;
            color: var(--muted);
        }

        .muted {
            font-size: 14px !important;
            line-height: 1.6;
            color: var(--muted);
        }

        .badge {
            display: inline-block;
            background: var(--primary-soft);
            color: #89beff;
            font-weight: 700;
            font-size: .8rem;
            border-radius: 999px;
            padding: 6px 10px;
            margin: 0 6px 8px 0;
            border: 1px solid rgba(79, 156, 255, 0.22);
        }

        .progress-row {
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:12px;
            margin-bottom: 10px;
        }

        .progress-label {
            font-size:.88rem;
            font-weight:700;
            color: var(--muted);
        }

        .survey-shell {
            width: min(100%, var(--content-max-width));
            margin: 0 auto;
        }

        .meter {
            width: 100%;
            height: 10px;
            border-radius: 999px;
            background: rgba(255,255,255,0.04);
            overflow: hidden;
            border: 1px solid var(--line);
        }

        .meter > span {
            display:block;
            height:100%;
            background: linear-gradient(90deg, #3b82f6, #60a5fa);
            transition: width .25s ease;
        }

        .question-title {
            font-size: 1rem;
            font-weight: 750;
            color: var(--text);
            margin-bottom: .45rem;
        }

        .answer-segments {
            margin-top: .45rem;
        }

        .answer-segments div[data-testid="stHorizontalBlock"] {
            gap: .5rem;
            flex-wrap: nowrap;
        }

        .answer-segments div[data-testid="column"] {
            min-width: 0;
        }

        div[data-testid="stButton"] > button {
            border-radius: 12px !important;
            min-height: 46px;
            border: 1px solid var(--line) !important;
            background: var(--surface-3) !important;
            color: var(--text) !important;
            font-weight: 700 !important;
            letter-spacing: -0.01em;
            transition: all .18s ease;
            box-shadow: none !important;
        }

        div[data-testid="stButton"] > button:hover {
            border-color: var(--field-border-strong) !important;
            background: #163864 !important;
            box-shadow: 0 0 0 2px rgba(79, 156, 255, 0.10) !important;
        }

        div[data-testid="stButton"] > button:focus-visible {
            outline: none !important;
            border-color: var(--field-border-strong) !important;
            box-shadow: var(--field-shadow) !important;
        }

        div[data-testid="stButton"] > button[kind="primary"] {
            border-color: var(--field-border-strong) !important;
            background: linear-gradient(180deg, #1d4f8d, #163f73) !important;
            color: #ffffff !important;
            box-shadow: 0 0 0 1px rgba(79, 156, 255, 0.28), 0 8px 18px rgba(79, 156, 255, 0.18) !important;
        }

        .answer-segments div[data-testid="stButton"] > button {
            min-height: 48px !important;
            white-space: normal;
            line-height: 1.35;
        }

        .status-chip {
            display:inline-flex;
            align-items:center;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: .8rem;
            font-weight: 700;
            margin-right: 6px;
            margin-bottom: 6px;
        }

        .chip-danger { color: #ffd1d1; background: rgba(255,115,115,.15); }
        .chip-warning { color: #ffe3b4; background: rgba(255,180,84,.14); }
        .chip-success { color: #c8ffe5; background: rgba(86,227,154,.14); }

        .result-score {
            font-size: clamp(2.4rem, 7vw, 3.3rem);
            font-weight: 900;
            line-height: 1.05;
            color: var(--text);
        }

        .result-sub { color: var(--muted); font-size: .95rem; }

        .level-badge {
            display:inline-block;
            margin-top: 8px;
            border-radius: 999px;
            padding: 7px 12px;
            font-size: .86rem;
            font-weight: 750;
        }

        .level-minimal { color: #bfffe0; background: rgba(86,227,154,.14); }
        .level-mild { color: #ffe0a8; background: rgba(255,180,84,.14); }
        .level-moderate { color: #cfe3ff; background: rgba(79,156,255,.16); }
        .level-severe { color: #ffd1d1; background: rgba(255,115,115,.15); }

        .score-track {
            position: relative;
            width: 100%;
            height: 14px;
            border-radius: 999px;
            border: 1px solid var(--line);
            overflow: hidden;
            background: linear-gradient(90deg, #22c55e 0%, #eab308 45%, #f59e0b 70%, #ef4444 100%);
            margin: 12px 0 6px;
        }

        .score-cover { height:100%; background: rgba(255,255,255,.78); }
        .score-marks { display:flex; justify-content:space-between; font-size:.78rem; color: var(--muted); }

        .note-box {
            border-radius: 12px;
            border: 1px dashed var(--line);
            background: var(--surface-2);
            padding: 12px;
        }

        .intro-section {
            display: grid;
            gap: 1rem;
        }

        .intro-bullets {
            margin: 0;
            padding-left: 1.15rem;
            display: grid;
            gap: .7rem;
            color: var(--muted);
        }

        .intro-bullets li {
            padding-left: .1rem;
            line-height: 1.72;
            word-break: keep-all;
        }

        .intro-note {
            margin-top: .25rem;
            padding: 14px 16px;
            border-radius: 14px;
            border: 1px dashed rgba(96,165,250,.22);
            background: linear-gradient(180deg, rgba(79,156,255,.04), rgba(79,156,255,.02)), var(--surface-2);
            display: grid;
            gap: .7rem;
        }

        .privacy-card {
            background: linear-gradient(180deg, rgba(255,255,255,.012), rgba(255,255,255,.004)), var(--surface-2);
        }

        .intro-action {
            margin-top: .9rem;
        }

        .intro-action div[data-testid="column"]:last-child {
            display: flex;
            align-items: end;
        }

        [data-testid="stTextInput"] label,
        [data-testid="stSelectbox"] label {
            color: var(--text) !important;
            font-weight: 700 !important;
            opacity: 1 !important;
        }

        [data-testid="stTextInput"] input {
            background: var(--field-bg) !important;
            color: var(--text) !important;
            border: 1px solid var(--field-border) !important;
            border-radius: 12px !important;
            min-height: 46px !important;
            box-shadow: none !important;
            padding: 12px 14px !important;
        }

        [data-testid="stTextInput"] input:hover {
            background: var(--field-bg-hover) !important;
            border-color: var(--field-border-strong) !important;
        }

        [data-testid="stTextInput"] input::placeholder {
            color: var(--muted) !important;
            opacity: 1 !important;
        }

        [data-testid="stTextInput"] input:focus {
            border-color: var(--field-border-strong) !important;
            box-shadow: var(--field-shadow) !important;
            background: var(--field-bg) !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] {
            width: 100% !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background: var(--field-bg) !important;
            color: var(--text) !important;
            border: 1px solid var(--field-border) !important;
            border-radius: 12px !important;
            min-height: 46px !important;
            box-shadow: none !important;
            transition: border-color .18s ease, box-shadow .18s ease, background-color .18s ease !important;
            padding: 2px 10px !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div:hover {
            background: var(--field-bg-hover) !important;
            border-color: var(--field-border-strong) !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
            background: var(--field-bg) !important;
            border-color: var(--field-border-strong) !important;
            box-shadow: var(--field-shadow) !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] > div *,
        [data-testid="stSelectbox"] [data-baseweb="select"] span,
        [data-testid="stSelectbox"] [data-baseweb="select"] input,
        [data-testid="stSelectbox"] [data-baseweb="select"] div {
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            opacity: 1 !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] input::placeholder {
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
            opacity: 1 !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] svg,
        [data-testid="stSelectbox"] [data-baseweb="select"] path {
            fill: var(--text) !important;
            color: var(--text) !important;
            opacity: 1 !important;
        }

        div[data-baseweb="popover"] {
            z-index: 99999 !important;
        }

        div[data-baseweb="popover"] [data-baseweb="menu"],
        div[data-baseweb="popover"] [role="listbox"],
        div[data-baseweb="popover"] ul {
            background: var(--surface-2) !important;
            border: 1px solid var(--field-border) !important;
            border-radius: 12px !important;
            box-shadow: var(--shadow-md) !important;
            overflow: hidden !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
        }

        div[data-baseweb="popover"] [role="option"],
        div[data-baseweb="popover"] li,
        div[data-baseweb="popover"] [data-baseweb="menu"] > div,
        div[data-baseweb="popover"] [data-baseweb="menu"] li {
            background: transparent !important;
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            opacity: 1 !important;
            min-height: 42px !important;
        }

        div[data-baseweb="popover"] [role="option"] *,
        div[data-baseweb="popover"] li *,
        div[data-baseweb="popover"] [data-baseweb="menu"] > div *,
        div[data-baseweb="popover"] [data-baseweb="menu"] li * {
            color: var(--text) !important;
            -webkit-text-fill-color: var(--text) !important;
            opacity: 1 !important;
        }

        div[data-baseweb="popover"] [role="option"]:hover,
        div[data-baseweb="popover"] li:hover,
        div[data-baseweb="popover"] [data-baseweb="menu"] > div:hover,
        div[data-baseweb="popover"] [data-baseweb="menu"] li:hover {
            background: rgba(79,156,255,.12) !important;
        }

        div[data-baseweb="popover"] [aria-selected="true"],
        div[data-baseweb="popover"] [data-highlighted="true"] {
            background: rgba(79,156,255,.18) !important;
            color: var(--text) !important;
        }

        div[data-testid="stAlert"] {
            background: rgba(255,115,115,.14) !important;
            border: 1px solid rgba(255,115,115,.24) !important;
            border-radius: 14px !important;
            color: #ffd6d6 !important;
        }

        div[data-testid="stAlert"] * {
            color: #ffd6d6 !important;
        }

        [data-testid="stCaptionContainer"] {
            color: var(--muted) !important;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: .8rem;
                padding-right: .8rem;
            }

            .card {
                padding: 16px;
                border-radius: 16px;
            }

            .intro-section { gap: .85rem; }
            .intro-bullets { gap: .58rem; padding-left: 1rem; }
            .intro-bullets li { line-height: 1.65; word-break: break-word; }
            .intro-note { padding: 13px 14px; }
            .intro-action { margin-top: .7rem; }

            .answer-segments div[data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }

            .answer-segments div[data-testid="column"] {
                flex: 1 1 calc(50% - .3rem);
            }

            .answer-segments div[data-testid="stButton"] > button {
                min-height: 44px !important;
                font-size: .93rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_intro():
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    intro_desc_html = render_bullet_list(INTRO_DESC_BULLETS)
    intro_notice_html = render_bullet_list(INTRO_NOTICE_BULLETS)
    privacy_html = render_bullet_list(PRIVACY_BULLETS)
    intro_badges_html = "".join(f'<span class="badge">{html.escape(badge)}</span>' for badge in INTRO_BADGES)

    st.markdown(
        f"""
        <section class="card intro-section">
            <div>
                {intro_badges_html}
                <h1 class="title-lg">{html.escape(INTRO_CARD_TITLE)}</h1>
            </div>
            <div>
                <h2 class="title-md">검사 설명</h2>
                {intro_desc_html}
            </div>
            <div class="note-box intro-note">
                <h3 class="title-md" style="font-size:1rem !important; margin:0;">{html.escape(INTRO_NOTICE_TITLE)}</h3>
                {intro_notice_html}
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <section class="card soft intro-section privacy-card">
            <div>
                <h2 class="title-md">{html.escape(PRIVACY_CARD_TITLE)}</h2>
                <p class="muted" style="margin:6px 0 0;">안내 내용을 확인하신 뒤 동의 체크 후 검사를 진행해 주세요.</p>
            </div>
            <div>
                {privacy_html}
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    consent = st.checkbox(CONSENT_CHECKBOX_LABEL, value=st.session_state.meta["consent"])
    st.session_state.meta["consent"] = consent

    st.markdown("<div class='intro-action'>", unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("검사 시작", type="primary", disabled=not consent, use_container_width=True):
            now = datetime.now(KST).isoformat()
            st.session_state.meta["consent_ts"] = now
            st.session_state.meta["started_ts"] = now
            st.session_state.page = "info"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def validate_name(name: str) -> str | None:
    if not name.strip():
        return "이름을 입력해 주세요."
    return None


def validate_gender(gender: str) -> str | None:
    if not gender.strip():
        return "성별을 선택해 주세요."
    if gender not in GENDER_OPTIONS:
        return "성별을 다시 선택해 주세요."
    return None


def validate_age(age: str) -> str | None:
    value = age.strip()
    if not value:
        return "연령을 입력해 주세요."
    if not value.isdigit():
        return "연령은 숫자만 입력해 주세요."
    age_num = int(value)
    if not 1 <= age_num <= 120:
        return "연령은 1세부터 120세 사이로 입력해 주세요."
    return None


def validate_region(region: str) -> str | None:
    if not region.strip():
        return "거주지역을 선택해 주세요."
    if region not in REGION_OPTIONS:
        return "거주지역을 다시 선택해 주세요."
    return None


def validate_phone(phone: str) -> str | None:
    value = phone.strip()
    if not value:
        return None
    if not re.fullmatch(r"[0-9-]+", value):
        return "휴대폰번호는 숫자와 하이픈(-)만 입력해 주세요."
    return None


def validate_email(email: str) -> str | None:
    value = email.strip()
    if not value:
        return None
    if "@" not in value or "." not in value:
        return "이메일 형식이 올바르지 않습니다. (@와 . 포함)"
    return None


def normalize_phone(phone: str) -> str:
    value = phone.strip().replace(" ", "")
    value = re.sub(r"[^0-9-]", "", value)
    value = re.sub(r"-{2,}", "-", value)
    return value


def page_info():
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    st.markdown(
        """
        <section class="card">
            <span class="badge">개인정보 입력</span>
            <h1 class="title-lg">검사 대상자 정보</h1>
            <p class="text">이름, 성별, 연령, 거주지역은 필수이며, 휴대폰번호와 이메일은 선택 입력입니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    row1_col1, row1_col2 = st.columns(2, gap="medium")
    with row1_col1:
        name = st.text_input("이름", value=st.session_state.examinee.get("name", ""))
    with row1_col2:
        gender_options = [""] + GENDER_OPTIONS
        current_gender = st.session_state.examinee.get("gender", "")
        gender = st.selectbox(
            "성별",
            options=gender_options,
            index=gender_options.index(current_gender) if current_gender in gender_options else 0,
            format_func=format_select_option,
        )

    row2_col1, row2_col2 = st.columns(2, gap="medium")
    with row2_col1:
        age = st.text_input("연령", value=st.session_state.examinee.get("age", ""))
    with row2_col2:
        region_options = [""] + REGION_OPTIONS
        current_region = st.session_state.examinee.get("region", "")
        region = st.selectbox(
            "거주지역",
            options=region_options,
            index=region_options.index(current_region) if current_region in region_options else 0,
            format_func=format_select_option,
        )

    phone_input = st.text_input("휴대폰번호 (선택)", value=st.session_state.examinee.get("phone", ""))
    email = st.text_input("이메일 (선택)", value=st.session_state.examinee.get("email", ""))

    normalized_phone = normalize_phone(phone_input)

    st.session_state.examinee = {
        "name": name.strip(),
        "gender": gender,
        "age": age.strip(),
        "region": region,
        "phone": normalized_phone,
        "email": email.strip(),
    }

    name_error = validate_name(name)
    gender_error = validate_gender(gender)
    age_error = validate_age(age)
    region_error = validate_region(region)
    phone_error = validate_phone(normalized_phone)
    email_error = validate_email(email)

    missing_fields = []
    if not name.strip():
        missing_fields.append("이름")
    if not gender.strip():
        missing_fields.append("성별")
    if not age.strip():
        missing_fields.append("연령")
    if not region.strip():
        missing_fields.append("거주지역")

    required_errors = []
    if name_error and name.strip():
        required_errors.append(name_error)
    if gender_error and gender.strip():
        required_errors.append(gender_error)
    if age_error and age.strip():
        required_errors.append(age_error)
    if region_error and region.strip():
        required_errors.append(region_error)

    if missing_fields:
        st.error(f"{', '.join(missing_fields)}을 입력해주세요.")
    for error in required_errors:
        st.error(error)
    if phone_error:
        st.error(phone_error)
    if email_error:
        st.error(email_error)

    all_valid = not any([name_error, gender_error, age_error, region_error, phone_error, email_error])

    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("다음", type="primary", disabled=not all_valid, use_container_width=True):
            st.session_state.page = "survey"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def page_survey(dev_mode: bool = False):
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    payload, missing = build_payload()
    answered_count = 7 - len(missing)
    progress_pct = int((answered_count / 7) * 100)

    st.markdown("<div class='survey-shell'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <section class="card">
            <span class="badge">문항 7개</span>
            <h1 class="title-lg">문항 응답</h1>
            <p class="text">최근 2주 동안의 경험에 가장 가까운 응답을 선택해 주세요.</p>
            <div class="progress-row">
                <span class="progress-label">진행률 {answered_count}/7</span>
                <span class="progress-label">{progress_pct}%</span>
            </div>
            <div class="meter"><span style="width:{progress_pct}%;"></span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    for i, q in enumerate(QUESTIONS, start=1):
        key = f"q{i}"
        current_answer = st.session_state.answers.get(key)
        current_value = current_answer if isinstance(current_answer, int) else score_from_label(current_answer)

        st.markdown(f"<div id='q-anchor-{key}'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <section class="card">
                <div class="question-title">{i}. {q}</div>
            """,
            unsafe_allow_html=True,
        )

        render_answer_segments(q_key=key, selected_score=current_value)
        st.markdown("</section>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

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

    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("결과 보기", type="primary", disabled=not all_done, use_container_width=True):
            st.session_state.meta["submitted_ts"] = datetime.now(KST).isoformat()
            st.session_state.page = "result"
            st.rerun()

    if dev_mode:
        st.caption("개발 모드 payload")
        st.json(payload, expanded=False)

    st.markdown("</div>", unsafe_allow_html=True)


def page_result(dev_mode: bool = False):
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    internal_payload, _ = build_payload()
    exam_data = build_exam_data_gad7(internal_payload)
    total = internal_payload["result"]["total"]
    level = internal_payload["result"]["level"]
    interp = internal_payload["result"]["interpretation"]
    flags = internal_payload["result"]["flags"]

    auto_db_insert(exam_data)

    if dev_mode:
        required_keys = ["exam_name", "consent_col", "examinee_col", "answers_col", "result_col"]
        st.caption("dev=1 sanity check · standardized exam_data")
        st.json(exam_data, expanded=False)
        st.code(
            f"exam_data_has_exact_5_keys={list(exam_data.keys()) == required_keys} keys={list(exam_data.keys())}",
            language="text",
        )

    ratio = max(0, min(total / 21, 1))
    level_key = get_level_key(level)

    summary_line = {
        "minimal": "현재 불안 관련 반응이 비교적 낮은 범위로 나타났습니다.",
        "mild": "경도의 불안 신호가 관찰되어 스트레스 관리가 도움이 될 수 있습니다.",
        "moderate": "중등도의 불안 반응이 나타나 정서 상태 점검을 권장드립니다.",
        "severe": "높은 수준의 불안 반응이 관찰되어 전문가 도움을 적극 권장드립니다.",
    }[level_key]

    st.markdown(
        f"""
        <section class="card" style="box-shadow: var(--shadow-md);">
            <span class="badge">결과</span>
            <h1 class="title-lg">GAD-7 검사 결과</h1>
            <div class="result-score">{total}<span style="font-size:.45em; font-weight:700; margin-left:6px;">/ 21점</span></div>
            <div class="result-sub">응답 기준: 최근 2주 · 총점 범위: 0~21</div>
            <div class="level-badge level-{level_key}">{level}</div>
            <p class="text" style="margin-top:10px;"><strong>요약:</strong> {summary_line}</p>
            <p class="text" style="margin-top:4px;"><strong>상세 해석:</strong> {interp}</p>
            <div class="score-track"><div class="score-cover" style="width:{(1-ratio)*100:.1f}%;"></div></div>
            <div class="score-marks"><span>0</span><span>4</span><span>9</span><span>14</span><span>21</span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    chips = []
    if flags.get("recommend_counseling"):
        chips.append('<span class="status-chip chip-warning">10점 이상 · 상담 권장</span>')
    else:
        chips.append('<span class="status-chip chip-success">10점 미만 · 경과 관찰</span>')

    if flags.get("recommend_clinic"):
        chips.append('<span class="status-chip chip-danger">15점 이상 · 진료 권장</span>')
    else:
        chips.append('<span class="status-chip chip-success">15점 미만 · 단계적 점검</span>')

    st.markdown(
        f"""
        <section class="card soft">
            <h2 class="title-md">운영 기준 안내</h2>
            <p class="text">아래 기준은 결과 해석 시 참고를 위한 운영 규칙입니다.</p>
            <div>{''.join(chips)}</div>
            <div class="note-box" style="margin-top:10px;">
                <p class="text" style="margin:0;">· 10점 이상: 중등도 임상적 가능성 → 상담 권장</p>
                <p class="text" style="margin:8px 0 0;">· 15점 이상: 불안장애 가능성 → 정신과 진료 필요</p>
            </div>
            <p class="muted" style="margin-top:10px;">
                본 결과는 참고용이며 의학적 진단을 대체하지 않습니다. 필요 시 전문 의료진과 상담해 주세요.
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
        st.caption("개발 모드 payload")
        st.code(json.dumps(internal_payload, ensure_ascii=False, indent=2), language="json")

    st.markdown("</div>", unsafe_allow_html=True)


def main():
    inject_css()
    init_state()

    params = st.query_params
    dev_mode = str(params.get("dev", "0")) == "1"

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
    운영/병합: ENABLE_DB_INSERT=true → Database().insert(exam_data) 수행
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