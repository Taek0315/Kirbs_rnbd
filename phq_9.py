# -*- coding: utf-8 -*-
import os
import platform
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from textwrap import dedent
from typing import Dict, List

import io
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont


st.set_page_config(page_title="PHQ-9 자기보고 검사", page_icon="📝", layout="centered")


# ──────────────────────────────────────────────────────────────────────────────
# 상태 초기화

def _reset_to_survey():
    """앱 상태 초기화 후 인트로로 이동"""
    st.session_state.page = "intro"
    st.session_state.consent = False
    st.session_state.consent_ts = None
    st.session_state.answers = {}
    st.session_state.functional = None
    st.session_state.summary = None
    st.session_state.db_insert_done = False
    st.session_state.examinee = {
        "user_id": str(uuid.uuid4()),
        "name": "",
        "gender": "",
        "age": "",
        "region": "",
        "email": "",
        "phone": "",
    }
    for i in range(1, 10):
        st.session_state.pop(f"q{i}", None)
    st.session_state.pop("functional-impact", None)
    st.session_state.pop("consent_checkbox", None)


# ──────────────────────────────────────────────────────────────────────────────
# ORCA 초기화

def _init_orca():
    orca_path = os.environ.get("PLOTLY_ORCA", "").strip() or shutil.which("orca")
    if orca_path:
        pio.orca.config.executable = orca_path
    if platform.system() != "Windows":
        try:
            pio.orca.config.use_xvfb = True
        except Exception:
            pass
    return orca_path


_ORCA_PATH = _init_orca()

INK = "#0F172A"
SUBTLE = "#475569"
CARD_BG = "#FFFFFF"
APP_BG = "#F6F8FB"
BORDER = "#E2E8F0"
BRAND = "#2563EB"
ACCENT = "#DC2626"


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

        :root {
          --bg: #f3f7fd;
          --surface: #ffffff;
          --surface-soft: #f7faff;
          --surface-blue: #eef5ff;
          --surface-blue-strong: #e0eeff;
          --ink: #10233f;
          --muted: #5b6b82;
          --muted-2: #789;
          --line: #d8e5f5;
          --line-strong: #bfd4ed;
          --brand: #2563eb;
          --brand-dark: #1d4ed8;
          --brand-soft: rgba(37, 99, 235, 0.1);
          --success-soft: #eefbf3;
          --warn-soft: #fff9eb;
          --danger-soft: #fff3f2;
          --danger-line: #f0c9c4;
          --shadow-lg: 0 24px 54px rgba(15, 23, 42, 0.1);
          --shadow-md: 0 16px 36px rgba(15, 23, 42, 0.08);
          --shadow-sm: 0 8px 24px rgba(15, 23, 42, 0.05);
          --radius-2xl: 28px;
          --radius-xl: 24px;
          --radius-lg: 18px;
          --radius-md: 14px;
          --control-height: 50px;
        }
        * { box-sizing: border-box; }
        html, body, [class*="css"] {
          font-family: "Inter", "Noto Sans KR", system-ui, -apple-system, sans-serif;
        }
        [data-testid="stAppViewContainer"] {
          background:
            radial-gradient(circle at top left, rgba(96, 165, 250, 0.18), transparent 28%),
            linear-gradient(180deg, #f9fbff 0%, var(--bg) 25%, var(--bg) 100%) !important;
        }
        [data-testid="block-container"] {
          max-width: 1080px;
          padding-top: 20px;
          padding-bottom: 56px;
        }
        [data-testid="stToolbar"], #MainMenu, header, footer { display: none !important; }

        .app-shell { max-width: 980px; margin: 0 auto; }
        .section-stack { display: flex; flex-direction: column; gap: 20px; }
        .card {
          background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, #ffffff 100%);
          border: 1px solid var(--line);
          border-radius: var(--radius-2xl);
          box-shadow: var(--shadow-md);
          padding: 28px;
        }
        .card-soft {
          background: linear-gradient(180deg, #f9fbff 0%, #ffffff 100%);
        }
        .hero-card {
          position: relative;
          overflow: hidden;
          padding: 34px;
          background:
            radial-gradient(circle at top right, rgba(96, 165, 250, 0.18), transparent 30%),
            linear-gradient(180deg, rgba(255,255,255,0.98) 0%, #ffffff 100%);
          border: 1px solid var(--line);
          border-radius: 30px;
          box-shadow: var(--shadow-lg);
        }
        .hero-grid, .two-col-grid, .result-grid, .progress-grid {
          display: grid;
          gap: 20px;
        }
        .hero-grid { grid-template-columns: minmax(0, 1.7fr) minmax(250px, 0.9fr); align-items: stretch; }
        .two-col-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .result-grid { grid-template-columns: minmax(260px, 0.95fr) minmax(0, 1.05fr); }
        .progress-grid { grid-template-columns: minmax(0, 1.2fr) minmax(250px, 0.8fr); }
        .eyebrow {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          width: fit-content;
          padding: 8px 14px;
          border-radius: 999px;
          background: var(--brand-soft);
          color: var(--brand);
          border: 1px solid rgba(37, 99, 235, 0.18);
          font-size: 0.82rem;
          font-weight: 800;
        }
        .hero-title, .section-title, .result-title {
          color: var(--ink);
          letter-spacing: -0.03em;
          margin: 0;
        }
        .hero-title { font-size: clamp(1.9rem, 3.2vw, 2.65rem); line-height: 1.16; font-weight: 900; margin-top: 14px; }
        .hero-copy, .body-copy, .muted-copy { color: var(--muted); line-height: 1.75; }
        .hero-copy { font-size: 1rem; margin-top: 14px; max-width: 660px; }
        .section-title { font-size: 1.18rem; font-weight: 800; }
        .result-title { font-size: 1.05rem; font-weight: 800; }
        .muted-copy { font-size: 0.92rem; }
        .stat-panel, .mini-panel, .notice-panel, .nav-panel, .question-card, .metric-card, .support-card {
          border: 1px solid var(--line);
          border-radius: 22px;
          background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
        }
        .stat-panel, .mini-panel, .notice-panel, .nav-panel, .support-card { padding: 20px; }
        .stat-panel { background: linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%); }
        .stat-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 10px 0; border-bottom: 1px solid rgba(191, 212, 237, 0.6); }
        .stat-row:last-child { border-bottom: 0; padding-bottom: 0; }
        .stat-row strong { color: var(--ink); font-size: 0.95rem; }
        .stat-row span { color: var(--muted); font-size: 0.92rem; text-align: right; }
        .bullet-list { margin: 0; padding-left: 18px; color: var(--ink); line-height: 1.8; }
        .bullet-list li { margin-bottom: 8px; }
        .chip-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
        .chip {
          padding: 10px 14px;
          border-radius: 999px;
          border: 1px solid var(--line);
          background: var(--surface-soft);
          color: var(--muted);
          font-size: 0.9rem;
        }
        .step-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
        .step-card {
          border: 1px solid var(--line);
          border-radius: 22px;
          background: rgba(255,255,255,0.78);
          box-shadow: var(--shadow-sm);
          padding: 18px;
          display: flex;
          gap: 14px;
          align-items: flex-start;
        }
        .step-card.active { background: linear-gradient(180deg, #ffffff 0%, #eef5ff 100%); border-color: rgba(37, 99, 235, 0.35); }
        .step-index {
          width: 38px; height: 38px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
          background: var(--surface-blue); color: var(--brand); font-weight: 900; flex-shrink: 0;
        }
        .step-card.active .step-index { background: var(--brand); color: #fff; }
        .step-label { color: var(--brand); font-size: 0.76rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; }
        .step-title { color: var(--ink); font-size: 1rem; font-weight: 800; margin-top: 4px; }
        .step-copy { color: var(--muted); font-size: 0.88rem; line-height: 1.6; margin-top: 5px; }
        .card-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
        .helper-box {
          padding: 13px 15px;
          border: 1px solid var(--line);
          border-radius: 16px;
          background: var(--surface-soft);
          color: var(--muted);
          font-size: 0.88rem;
          line-height: 1.6;
          min-width: 220px;
        }
        .question-card {
          padding: 22px 24px;
          background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
          box-shadow: var(--shadow-sm);
        }
        .question-head {
          display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; margin-bottom: 14px;
        }
        .question-number {
          padding: 10px 14px;
          border-radius: 16px;
          background: var(--surface-blue);
          border: 1px solid var(--line);
          color: var(--brand);
          font-size: 0.9rem;
          font-weight: 900;
          white-space: nowrap;
        }
        .question-title { color: var(--ink); font-size: 1rem; line-height: 1.7; font-weight: 700; }
        .question-meta { color: var(--muted); font-size: 0.87rem; margin-top: 6px; }
        .progress-card {
          padding: 20px;
          border-radius: 22px;
          border: 1px solid var(--line);
          background: linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
          box-shadow: var(--shadow-sm);
        }
        .progress-track { width: 100%; height: 10px; border-radius: 999px; background: rgba(191, 219, 254, 0.55); overflow: hidden; margin: 14px 0 10px; }
        .progress-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #60a5fa 0%, var(--brand) 100%); }
        .progress-meta { display: flex; justify-content: space-between; gap: 10px; color: var(--muted); font-size: 0.88rem; }
        .metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
        .metric-card { padding: 15px 16px; background: var(--surface-soft); }
        .metric-label { display: block; color: var(--muted); font-size: 0.8rem; margin-bottom: 6px; }
        .metric-value { color: var(--ink); font-size: 0.96rem; font-weight: 800; }
        .severity-pill { display: inline-flex; padding: 8px 18px; border-radius: 999px; font-weight: 800; border: 1.5px solid currentColor; }
        .notice-banner {
          border: 1px solid var(--danger-line);
          border-radius: 18px;
          background: var(--danger-soft);
          color: #8c3232;
          padding: 14px 18px;
          font-weight: 700;
        }
        .footer-card { text-align: center; font-size: 0.83rem; color: var(--muted); line-height: 1.7; }
        .action-note { color: var(--muted); font-size: 0.9rem; line-height: 1.65; margin-bottom: 14px; }

        [data-testid="stAlert"] {
          border-radius: 18px !important;
          border: 1px solid var(--danger-line) !important;
          background: var(--danger-soft) !important;
          box-shadow: var(--shadow-sm) !important;
        }
        [data-testid="stAlert"] * { color: var(--ink) !important; }
        [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] *, [data-testid="stCheckbox"] label, [data-testid="stCheckbox"] p,
        [data-testid="stRadio"] label, [data-testid="stRadio"] label span { color: var(--ink) !important; opacity: 1 !important; }
        [data-testid="stWidgetLabel"] p { font-weight: 700 !important; font-size: 0.95rem !important; }
        input, textarea, [data-baseweb="input"] > div, [data-baseweb="select"] > div {
          min-height: var(--control-height) !important;
          border-radius: var(--radius-md) !important;
          background: #fff !important;
          color: var(--ink) !important;
          border: 1px solid var(--line-strong) !important;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
        }
        input, textarea { -webkit-text-fill-color: var(--ink) !important; caret-color: var(--ink) !important; }
        input::placeholder, textarea::placeholder { color: #8fa0b7 !important; -webkit-text-fill-color: #8fa0b7 !important; }
        input:focus, input:focus-visible, textarea:focus, textarea:focus-visible,
        [data-baseweb="input"] > div:focus-within, [data-baseweb="select"] > div:focus-within {
          border-color: var(--brand) !important;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
        }
        [data-baseweb="select"] span, [data-baseweb="select"] input, [data-baseweb="select"] svg,
        [data-baseweb="input"] span, [data-baseweb="input"] input {
          color: var(--ink) !important; fill: var(--ink) !important; stroke: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
        }
        .stButton { width: 100%; }
        .stButton > button {
          width: 100% !important;
          min-height: 50px !important;
          border-radius: 15px !important;
          font-size: 0.96rem !important;
          font-weight: 800 !important;
          border: 1px solid transparent !important;
          transition: transform 0.18s ease, box-shadow 0.18s ease !important;
        }
        .stButton > button[kind="primary"] {
          background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
          color: #fff !important;
          box-shadow: 0 12px 24px rgba(37, 99, 235, 0.22) !important;
        }
        .stButton > button[kind="primary"] * { color: #fff !important; -webkit-text-fill-color: #fff !important; }
        .stButton > button:not([kind="primary"]) {
          background: #fff !important;
          border-color: var(--line-strong) !important;
          color: var(--brand) !important;
        }
        .stButton > button:not([kind="primary"]) * { color: var(--brand) !important; -webkit-text-fill-color: var(--brand) !important; }
        .stButton > button:hover { transform: translateY(-1px); }
        [data-testid="stRadio"] > div[role="radiogroup"] {
          display: grid !important;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px !important;
        }
        [data-testid="stRadio"] [role="radio"] {
          border-radius: 16px !important;
          border: 1px solid var(--line) !important;
          background: var(--surface-soft) !important;
          padding: 12px 14px !important;
          min-height: 56px !important;
          align-items: center !important;
        }
        [data-testid="stRadio"] [role="radio"][aria-checked="true"] {
          background: var(--surface-blue) !important;
          border-color: rgba(37, 99, 235, 0.34) !important;
          box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.10) !important;
        }
        [data-testid="stCheckbox"] svg { color: var(--brand) !important; }
        .form-divider { border-top: 1px solid var(--line); margin: 18px 0 0; padding-top: 18px; }

        @media (max-width: 900px) {
          .hero-grid, .two-col-grid, .result-grid, .progress-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 720px) {
          .card, .hero-card, .question-card { padding: 22px; border-radius: 22px; }
          .step-grid, .metric-grid, [data-testid="stRadio"] > div[role="radiogroup"] { grid-template-columns: 1fr !important; }
          .question-head, .card-header { flex-direction: column; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 상태 관리

def init_state() -> None:
    if "page" not in st.session_state:
        st.session_state.page = "intro"
    if "consent" not in st.session_state:
        st.session_state.consent = False
    if "consent_ts" not in st.session_state:
        st.session_state.consent_ts = None
    if "answers" not in st.session_state:
        st.session_state.answers: Dict[int, str] = {}
    if "functional" not in st.session_state:
        st.session_state.functional = None
    if "summary" not in st.session_state:
        st.session_state.summary = None
    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False
    if "examinee" not in st.session_state:
        st.session_state.examinee = {
            "user_id": str(uuid.uuid4()),
            "name": "",
            "gender": "",
            "age": "",
            "region": "",
            "email": "",
            "phone": "",
        }


REGION_OPTIONS = ["수도권", "충청권", "강원권", "전라권", "경상권", "제주도"]
GENDER_OPTIONS = ["남성", "여성", "기타", "응답하지 않음"]

QUESTIONS = [
    {"no": 1, "ko": "일상적인 활동(예: 취미나 일상 일과 등)에 흥미나 즐거움을 거의 느끼지 못한다.", "domain": "흥미/즐거움 상실"},
    {"no": 2, "ko": "기분이 가라앉거나, 우울하거나, 희망이 없다고 느낀다.", "domain": "우울한 기분"},
    {"no": 3, "ko": "잠들기 어렵거나 자주 깨는 등 수면에 문제가 있었거나, 반대로 너무 많이 잠을 잔다.", "domain": "수면 문제"},
    {"no": 4, "ko": "평소보다 피곤함을 더 자주 느꼈거나, 기운이 거의 없다.", "domain": "피로/에너지 부족"},
    {"no": 5, "ko": "식욕이 줄었거나 반대로 평소보다 더 많이 먹는다.", "domain": "식욕 변화"},
    {"no": 6, "ko": "자신을 부정적으로 느끼거나, 스스로 실패자라고 생각한다.", "domain": "죄책감/무가치감"},
    {"no": 7, "ko": "일상생활 및 같은 일에 집중하는 것이 어렵다.", "domain": "집중력 저하"},
    {"no": 8, "ko": "다른 사람들이 눈치챌 정도로 매우 느리게 말하고 움직이거나, 반대로 평소보다 초조하고 안절부절 못한다.", "domain": "느려짐/초조함"},
    {"no": 9, "ko": "죽는 게 낫겠다는 생각하거나, 어떤 식으로든 자신을 해치고 싶은 생각이 든다.", "domain": "자살/자해 생각"},
]
LABELS = ["전혀 아님 (0)", "며칠 동안 (1)", "절반 이상 (2)", "거의 매일 (3)"]
LABEL2SCORE = {LABELS[0]: 0, LABELS[1]: 1, LABELS[2]: 2, LABELS[3]: 3}


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
    if not all(ch.isdigit() or ch == "-" for ch in value):
        return "연락처는 숫자와 하이픈(-)만 입력해 주세요."
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
    cleaned = []
    last_dash = False
    for ch in value:
        if ch.isdigit():
            cleaned.append(ch)
            last_dash = False
        elif ch == "-" and not last_dash:
            cleaned.append(ch)
            last_dash = True
    return "".join(cleaned).strip("-")


def build_exam_data_phq9(payload: dict) -> dict:
    exam_name = (payload.get("exam", {}) or {}).get("title", "PHQ_9")

    meta = payload.get("meta", {}) or {}
    examinee = payload.get("examinee", {}) or {}
    consent_meta = {
        "consent": meta.get("consent"),
        "consent_ts": meta.get("consent_ts"),
        "started_ts": meta.get("started_ts") or meta.get("consent_ts") or "",
        "submitted_ts": meta.get("submitted_ts"),
        "version": (payload.get("exam", {}) or {}).get("version"),
        "respondent_id": examinee.get("user_id"),
    }

    answers = payload.get("answers", {}) or {}
    result = payload.get("result", {}) or {}

    domain_scores = result.get("domain_scores", {}) or {}
    result_flat = dict(result)
    if isinstance(domain_scores, dict):
        ds = "|".join([f"{_sanitize_csv_value(k)}:{_sanitize_csv_value(v)}" for k, v in domain_scores.items()])
        result_flat["domain_scores"] = ds

    return {
        "exam_name": _sanitize_csv_value(exam_name),
        "consent_col": dict_to_kv_csv(consent_meta),
        "examinee_col": dict_to_kv_csv(examinee),
        "answers_col": dict_to_kv_csv(answers),
        "result_col": dict_to_kv_csv(result_flat),
    }


def phq_severity(total: int) -> str:
    return ("정상" if total <= 4 else "경미" if total <= 9 else "중등도" if total <= 14 else "중증" if total <= 19 else "심각")


COG_AFF = [1, 2, 6, 7, 9]
SOMATIC = [3, 4, 5, 8]

SEVERITY_SEGMENTS = [
    {"label": "정상", "display": "0–4", "start": 0, "end": 5, "color": "#CDEED6"},
    {"label": "경미", "display": "5–9", "start": 5, "end": 10, "color": "#F8F1C7"},
    {"label": "중등도", "display": "10–14", "start": 10, "end": 15, "color": "#FFE0B2"},
    {"label": "중증", "display": "15–19", "start": 15, "end": 20, "color": "#FBC0A8"},
    {"label": "심각", "display": "20–27", "start": 20, "end": 27, "color": "#F6A6A6"},
]
SEVERITY_PILL = {
    "정상": ("#DBEAFE", "#1E3A8A"),
    "경미": ("#FEF3C7", "#92400E"),
    "중등도": ("#FFE4E6", "#9F1239"),
    "중증": ("#FED7AA", "#9A3412"),
    "심각": ("#FECACA", "#7F1D1D"),
}
SEVERITY_ARC_COLOR = {"정상": "#16a34a", "경미": "#f59e0b", "중등도": "#f97316", "중증": "#f43f5e", "심각": "#b91c1c"}
SEVERITY_GUIDANCE = {
    "정상": "현재 보고된 주관적 우울 증상은 정상 범위에 해당하며, 기본적인 자기 관리와 모니터링을 이어가시면 됩니다.",
    "경미": "경미 수준의 우울감이 보고되었습니다. 생활리듬 조정과 상담 자원 안내 등 예방적 개입을 고려할 수 있습니다.",
    "중등도": "임상적으로 의미 있는 중등도 수준으로, 정신건강 전문인의 평가와 치료적 개입을 권장합니다.",
    "중증": "중증 수준의 우울 증상이 보고되어, 신속한 전문 평가와 적극적인 치료 계획 수립이 필요합니다.",
    "심각": "심각 수준의 우울 증상이 보고되었습니다. 안전 평가를 포함한 즉각적인 전문 개입이 권고됩니다.",
}
DOMAIN_META = [
    {"name": "신체/생리 증상", "desc": "(수면, 피곤함, 식욕, 정신운동 문제)", "items": SOMATIC, "max": 12},
    {"name": "인지/정서 증상", "desc": "(흥미저하, 우울감, 죄책감, 집중력, 자살사고)", "items": COG_AFF, "max": 15},
]


def build_total_severity_bar(total: int) -> go.Figure:
    total = max(0, min(total, 27))
    fig = go.Figure()
    annotations = []

    for seg in SEVERITY_SEGMENTS:
        width = seg["end"] - seg["start"]
        fig.add_trace(
            go.Bar(
                x=[width],
                y=["총점"],
                base=seg["start"],
                orientation="h",
                marker=dict(color=seg["color"], line=dict(width=0)),
                hovertemplate=f"{seg['label']} · {seg['display']}점<extra></extra>",
                showlegend=False,
            )
        )
        midpoint = seg["start"] + width / 2
        annotations.append(
            dict(
                x=midpoint,
                y=-0.12,
                xref="x",
                yref="paper",
                text=f"<b>{seg['label']}</b><br><span style='font-size:11px;'>{seg['display']}점</span>",
                showarrow=False,
                align="center",
                font=dict(size=12, color=INK),
            )
        )

    fig.add_shape(
        type="line",
        x0=total,
        x1=total,
        y0=-0.05,
        y1=1.05,
        xref="x",
        yref="paper",
        line=dict(color=BRAND, width=3),
    )
    annotations.append(
        dict(
            x=total,
            y=1.08,
            xref="x",
            yref="paper",
            text=f"{total}점",
            showarrow=False,
            font=dict(size=14, color=BRAND, family="Inter, 'Noto Sans KR', sans-serif"),
            bgcolor="#e0ecff",
            bordercolor=BRAND,
            borderwidth=1,
            borderpad=6,
        )
    )

    fig.update_layout(
        barmode="stack",
        xaxis=dict(range=[0, 27], showgrid=False, zeroline=False, tickvals=[0, 5, 10, 15, 20, 27], ticks="outside", tickfont=dict(size=11)),
        yaxis=dict(showticklabels=False),
        margin=dict(l=30, r=30, t=50, b=60),
        height=260,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color=INK, family="Inter, 'Noto Sans KR', Arial, sans-serif"),
        annotations=annotations,
    )
    return fig


def build_domain_profile_html(scores: List[int]) -> str:
    if len(scores) < 9:
        scores = (scores + [0] * 9)[:9]

    rows: List[str] = []
    for meta in DOMAIN_META:
        score = sum(scores[i - 1] for i in meta["items"])
        ratio = (score / meta["max"]) if meta["max"] else 0
        rows.append(
            dedent(
                f"""
                <div style="display:grid;grid-template-columns:1.2fr 2fr 0.55fr;gap:14px;align-items:center;">
                  <div>
                    <div style="font-weight:800;color:{INK};">{meta['name']}</div>
                    <div style="color:{SUBTLE};font-size:0.85rem;margin-top:4px;">{meta['desc']}</div>
                  </div>
                  <div style="position:relative;height:14px;border-radius:999px;background:#dbeafe;overflow:hidden;border:1px solid #bfdbfe;">
                    <div style="position:absolute;inset:0;width:{ratio*100:.1f}%;background:linear-gradient(90deg,#60a5fa 0%,{BRAND} 100%);border-radius:999px;"></div>
                  </div>
                  <div style="justify-self:end;font-weight:800;color:{INK};">{score} / {meta['max']}</div>
                </div>
                """
            ).strip()
        )

    return "\n".join(rows)


def compose_narrative(total: int, severity: str, functional: str | None, item9: int) -> str:
    base = f"총점 {total}점(27점 만점)으로, [{severity}] 수준의 우울 증상이 보고되었습니다. {SEVERITY_GUIDANCE[severity]}"
    functional_text = f" 응답자 보고에 따르면, 이러한 증상으로 인한 일·집안일·대인관계의 어려움은 ‘{functional}’ 수준입니다." if functional else ""
    safety_text = " 특히, 자해/자살 관련 사고(9번 문항)가 보고되어 이에 대한 즉각적인 관심과 평가가 매우 중요합니다." if item9 > 0 else ""
    return base + functional_text + safety_text


def kst_iso_now() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).isoformat(timespec="seconds")


# ──────────────────────────────────────────────────────────────────────────────
# UI helper
STEP_ITEMS = [
    ("01", "검사 안내", "목적과 개인정보 동의를 확인합니다."),
    ("02", "응답자 정보", "기본 정보를 입력하고 유효성을 확인합니다."),
    ("03", "문항 응답", "지난 2주 기준으로 각 문항에 응답합니다."),
]


def render_app_shell_start() -> None:
    st.markdown('<div class="app-shell"><div class="section-stack">', unsafe_allow_html=True)


def render_app_shell_end() -> None:
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_step_strip(current_page: str) -> None:
    active_index = {"intro": 0, "examinee": 1, "survey": 2, "result": 2}.get(current_page, 0)
    cards = []
    for idx, (label, title, caption) in enumerate(STEP_ITEMS):
        active_class = " active" if idx == active_index else ""
        cards.append(
            f"""
            <div class="step-card{active_class}">
              <div class="step-index">{label}</div>
              <div>
                <div class="step-label">Step {idx + 1}</div>
                <div class="step-title">{title}</div>
                <div class="step-copy">{caption}</div>
              </div>
            </div>
            """
        )
    st.markdown(f'<div class="step-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_intro_section() -> None:
    st.markdown(
        dedent(
            """
            <section class="hero-card">
              <div class="hero-grid">
                <div>
                  <div class="eyebrow">PHQ-9 Assessment</div>
                  <h1 class="hero-title">우울 증상 자기보고 검사를<br>차분하고 명확한 흐름으로 진행합니다.</h1>
                  <p class="hero-copy">지난 2주 동안의 경험을 기준으로 각 증상의 빈도를 응답하면, 총점과 증상 수준, 주요 영역별 프로파일을 바로 확인할 수 있습니다.</p>
                  <div class="chip-row">
                    <div class="chip">총 9개 문항 + 기능 손상 1개 문항</div>
                    <div class="chip">표준 0–3점 척도 사용</div>
                    <div class="chip">결과는 참고용이며 진단을 대체하지 않음</div>
                  </div>
                </div>
                <aside class="stat-panel">
                  <div class="stat-row"><strong>응답 기준</strong><span>지난 2주</span></div>
                  <div class="stat-row"><strong>소요 시간</strong><span>약 2–3분</span></div>
                  <div class="stat-row"><strong>결과 제공</strong><span>즉시 총점 / 중증도 / 영역별 요약</span></div>
                </aside>
              </div>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )


def render_notice_cards() -> None:
    st.markdown(
        dedent(
            """
            <section class="two-col-grid">
              <article class="card card-soft">
                <h2 class="section-title">검사 안내</h2>
                <ul class="bullet-list" style="margin-top:12px;">
                  <li>목적: 최근 2주간 우울 관련 증상의 빈도를 자가 보고하여 현재 상태를 점검합니다.</li>
                  <li>대상: 만 12세 이상 누구나 스스로 응답할 수 있습니다.</li>
                  <li>응답 방식: 각 문항은 <b>전혀 아님(0)</b>부터 <b>거의 매일(3)</b>까지의 0~3점 척도로 응답합니다.</li>
                </ul>
                <p class="muted-copy" style="margin-top:10px;">※ 결과 해석은 참고용이며, 의학적 진단을 대신하지 않습니다.</p>
              </article>
              <article class="card card-soft">
                <h2 class="section-title">개인정보 수집·이용 동의</h2>
                <ul class="bullet-list" style="margin-top:12px;">
                  <li>수집 항목: 이름, 성별, 연령, 거주지역, 이메일, 연락처, 응답 내용, 결과, 제출 시각</li>
                  <li>이용 목적: 검사 수행 및 결과 제공, 통계 및 품질 개선, DB 저장</li>
                  <li>보관 기간: 내부 정책에 따름</li>
                  <li>제3자 제공: 없음</li>
                  <li>동의 거부 권리 및 불이익: 동의하지 않으실 경우 검사를 진행할 수 없습니다.</li>
                </ul>
              </article>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )


def render_navigation_row(prev_label: str, next_label: str, next_disabled: bool = False, helper_text: str | None = None):
    with st.container():
        st.markdown('<section class="nav-panel">', unsafe_allow_html=True)
        if helper_text:
            st.markdown(f'<div class="action-note">{helper_text}</div>', unsafe_allow_html=True)
        prev_col, next_col = st.columns(2, gap="medium")
        with prev_col:
            prev_clicked = st.button(prev_label, use_container_width=True)
        with next_col:
            next_clicked = st.button(next_label, type="primary", use_container_width=True, disabled=next_disabled)
        st.markdown("</section>", unsafe_allow_html=True)
    return prev_clicked, next_clicked


def render_respondent_form() -> tuple[bool, bool]:
    st.markdown(
        dedent(
            """
            <section class="hero-card">
              <div class="hero-grid">
                <div>
                  <div class="eyebrow">Respondent Information</div>
                  <h1 class="hero-title">응답자 정보를 확인하고<br>안정적인 검사 환경을 준비합니다.</h1>
                  <p class="hero-copy">필수 항목은 정확하게 입력해 주세요. 선택 항목은 결과 전달 및 후속 안내에 필요한 경우에만 입력하시면 됩니다.</p>
                </div>
                <aside class="stat-panel">
                  <div class="stat-row"><strong>필수 항목</strong><span>이름 · 성별 · 연령 · 거주지역</span></div>
                  <div class="stat-row"><strong>선택 항목</strong><span>휴대폰번호 · 이메일</span></div>
                  <div class="stat-row"><strong>검증 방식</strong><span>기존 유효성 검사 규칙 동일 적용</span></div>
                </aside>
              </div>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        dedent(
            """
            <section class="card">
              <div class="card-header">
                <div>
                  <h2 class="section-title">응답자 정보</h2>
                  <p class="body-copy" style="margin-top:8px;">검사 진행과 결과 확인을 위해 필요한 정보를 입력해 주세요. 이름, 성별, 연령, 거주지역은 필수이며 휴대폰번호와 이메일은 선택 입력입니다.</p>
                </div>
                <div class="helper-box">필수 항목을 모두 입력하고 형식이 맞아야 다음 단계로 이동할 수 있습니다.</div>
              </div>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )

    st.markdown('<section class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">필수 입력 정보</div>', unsafe_allow_html=True)
    st.markdown('<div class="muted-copy" style="margin:8px 0 16px;">결과 해석과 기록을 위해 필수 항목을 정확하게 입력해 주세요.</div>', unsafe_allow_html=True)

    identity_col, gender_col = st.columns(2, gap="medium")
    with identity_col:
        name = st.text_input("이름", value=st.session_state.examinee.get("name", ""))
    with gender_col:
        gender_options = [""] + GENDER_OPTIONS
        current_gender = st.session_state.examinee.get("gender", "")
        gender = st.selectbox("성별", options=gender_options, index=gender_options.index(current_gender) if current_gender in gender_options else 0)

    age_col, region_col = st.columns(2, gap="medium")
    with age_col:
        age = st.text_input("연령", value=st.session_state.examinee.get("age", ""))
    with region_col:
        region_options = [""] + REGION_OPTIONS
        current_region = st.session_state.examinee.get("region", "")
        region = st.selectbox("거주지역", options=region_options, index=region_options.index(current_region) if current_region in region_options else 0)

    st.markdown('<div class="form-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title" style="font-size:1rem;">선택 입력 정보</div>', unsafe_allow_html=True)
    st.markdown('<div class="muted-copy" style="margin:8px 0 16px;">선택 정보는 결과 전달이나 후속 안내가 필요한 경우에만 입력하시면 됩니다.</div>', unsafe_allow_html=True)

    phone_col, email_col = st.columns(2, gap="medium")
    with phone_col:
        phone = st.text_input("휴대폰번호 (선택)", value=st.session_state.examinee.get("phone", ""))
        st.caption("숫자만 입력해도 기존 규칙에 맞게 정규화됩니다.")
    with email_col:
        email = st.text_input("이메일 (선택)", value=st.session_state.examinee.get("email", ""))
        st.caption("선택 입력이며, 형식이 올바를 때만 다음 단계가 활성화됩니다.")
    st.markdown("</section>", unsafe_allow_html=True)

    normalized_phone = normalize_phone(phone)
    st.session_state.examinee.update({
        "name": name.strip(),
        "gender": gender,
        "age": age.strip(),
        "region": region,
        "phone": normalized_phone,
        "email": email.strip(),
    })

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
        st.warning(f"{', '.join(missing_fields)}을 입력해주세요.", icon="⚠️")
    for error in required_errors:
        st.warning(error, icon="⚠️")
    if phone_error:
        st.warning(phone_error, icon="⚠️")
    if email_error:
        st.warning(email_error, icon="⚠️")

    all_valid = not any([name_error, gender_error, age_error, region_error, phone_error, email_error])
    return render_navigation_row(
        "이전",
        "다음",
        next_disabled=not all_valid,
        helper_text="필수 항목이 모두 채워지고 입력 형식이 유효할 때 다음 단계가 활성화됩니다.",
    )


def render_questionnaire_progress() -> None:
    answered = sum(1 for i in range(1, 10) if st.session_state.answers.get(i) is not None)
    functional_done = 1 if st.session_state.functional is not None else 0
    completed = answered + functional_done
    total = 10
    progress = (completed / total) * 100

    st.markdown(
        dedent(
            f"""
            <section class="progress-grid">
              <div class="card">
                <div class="eyebrow">Questionnaire</div>
                <h2 class="section-title" style="margin-top:14px;">질문지 (지난 2주)</h2>
                <p class="body-copy" style="margin-top:10px;">각 문항에 대해 지난 2주 동안의 빈도를 <b>전혀 아님(0)</b> · <b>며칠 동안(1)</b> · <b>절반 이상(2)</b> · <b>거의 매일(3)</b> 가운데 가장 가까운 값으로 선택합니다.</p>
                <div class="chip-row">
                  <div class="chip">총 9개 문항</div>
                  <div class="chip">동일한 0–3점 척도</div>
                  <div class="chip">기능 손상 문항 포함</div>
                </div>
              </div>
              <aside class="progress-card">
                <div class="eyebrow">응답 진행 현황</div>
                <div class="section-title" style="margin-top:12px;">{completed} / {total} 항목 완료</div>
                <div class="muted-copy" style="margin-top:8px;">모든 문항과 기능 손상 문항까지 완료하면 즉시 결과를 확인할 수 있습니다.</div>
                <div class="progress-track"><div class="progress-fill" style="width:{progress:.2f}%"></div></div>
                <div class="progress-meta"><span>문항 1–9 + 기능 손상</span><span>{progress:.0f}%</span></div>
              </aside>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )


def render_questionnaire_section() -> None:
    st.markdown(
        dedent(
            """
            <section class="notice-panel">
              <h3 class="section-title" style="font-size:1rem;">응답 안내</h3>
              <ul class="bullet-list" style="margin-top:10px;">
                <li>각 문항은 지난 2주를 기준으로 가장 가까운 빈도를 선택합니다.</li>
                <li>모든 문항과 기능 손상 질문을 완료한 뒤 ‘결과 보기’를 누르면 총점, 중증도, 영역별 분석을 바로 확인할 수 있습니다.</li>
              </ul>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )

    for q in QUESTIONS:
        render_question_item(q)
    render_functional_block()


def render_question_item(question: Dict[str, str | int]) -> None:
    st.markdown(
        dedent(
            f"""
            <section class="question-card">
              <div class="question-head">
                <div>
                  <div class="question-title">{question['ko']}</div>
                  <div class="question-meta">증상 영역: {question['domain']}</div>
                </div>
                <div class="question-number">문항 {question['no']}</div>
              </div>
            """
        ),
        unsafe_allow_html=True,
    )
    st.session_state.answers[question["no"]] = st.radio(
        label=f"문항 {question['no']}",
        options=LABELS,
        index=None,
        horizontal=True,
        label_visibility="collapsed",
        key=f"q{question['no']}",
    )
    st.markdown("</section>", unsafe_allow_html=True)


def render_functional_block() -> None:
    st.markdown(
        dedent(
            """
            <section class="question-card">
              <div class="question-head">
                <div>
                  <div class="question-title">이 문제들 때문에 일·집안일·대인관계에 얼마나 어려움이 있었습니까?</div>
                  <div class="question-meta">기능 손상 문항 · 가장 가까운 수준을 선택해 주세요.</div>
                </div>
                <div class="question-number">기능 손상</div>
              </div>
            """
        ),
        unsafe_allow_html=True,
    )
    st.session_state.functional = st.radio(
        "기능 손상",
        options=["전혀 어렵지 않음", "어렵지 않음", "어려움", "매우 어려움"],
        index=None,
        horizontal=True,
        label_visibility="collapsed",
        key="functional-impact",
    )
    st.markdown("</section>", unsafe_allow_html=True)


def render_result_section(dev_mode: bool = False) -> None:
    if not st.session_state.summary:
        st.warning("먼저 설문을 완료해 주세요.")
        st.stop()

    total, sev, functional, scores, ts, unanswered = st.session_state.summary
    item9_score = scores[8] if len(scores) >= 9 else 0
    narrative = compose_narrative(total, sev, functional, item9_score)
    arc_color = SEVERITY_ARC_COLOR.get(sev, BRAND)
    gauge_percent = (max(0, min(total, 27)) / 27) * 100
    functional_value = functional if functional else "미응답"
    name_value = st.session_state.examinee.get("name", "").strip()
    name_text = name_value if name_value else "(미입력)"
    pill_bg, pill_fg = SEVERITY_PILL.get(sev, ("#DBEAFE", "#1E3A8A"))

    st.markdown(
        dedent(
            f"""
            <section class="hero-card">
              <div class="hero-grid">
                <div>
                  <div class="eyebrow">Assessment Result</div>
                  <h1 class="hero-title">검사 결과를 한눈에 확인하고<br>핵심 신호를 정리합니다.</h1>
                  <p class="hero-copy">총점, 중증도, 기능 손상 응답과 영역별 프로파일을 함께 검토해 현재 상태를 보다 구조적으로 이해할 수 있습니다.</p>
                  <div class="chip-row">
                    <div class="chip">검사 일시: {ts}</div>
                    <div class="chip">응답자: {name_text}</div>
                  </div>
                </div>
                <aside class="stat-panel">
                  <div class="stat-row"><strong>총점</strong><span>{total} / 27</span></div>
                  <div class="stat-row"><strong>중증도</strong><span>{sev}</span></div>
                  <div class="stat-row"><strong>기능 손상</strong><span>{functional_value}</span></div>
                </aside>
              </div>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )

    st.markdown('<section class="card"><div class="result-grid">', unsafe_allow_html=True)
    st.markdown(
        dedent(
            f"""
            <div class="mini-panel" style="padding:24px;text-align:center;background:linear-gradient(180deg,#f9fbff 0%,#ffffff 100%);">
              <div class="eyebrow" style="margin:0 auto;">총점 요약</div>
              <div style="width:220px;height:220px;border-radius:50%;margin:18px auto 14px;position:relative;display:flex;align-items:center;justify-content:center;background:conic-gradient({arc_color} {gauge_percent:.2f}%, rgba(219,234,254,0.95) {gauge_percent:.2f}%, rgba(219,234,254,0.95) 100%);">
                <div style="position:absolute;inset:22px;border-radius:50%;background:#fff;box-shadow:inset 0 1px 2px rgba(15,23,42,0.06);"></div>
                <div style="position:relative;z-index:1;">
                  <div style="font-size:3.1rem;line-height:1;color:{INK};font-weight:900;">{total}</div>
                  <div style="color:{SUBTLE};font-weight:700;margin-top:4px;">/ 27</div>
                </div>
              </div>
              <div class="severity-pill" style="background:{pill_bg};color:{pill_fg};">{sev}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        dedent(
            f"""
            <div class="mini-panel" style="padding:24px;display:flex;flex-direction:column;gap:16px;">
              <div class="result-title">주요 소견</div>
              <div class="body-copy">{narrative}</div>
              <div class="metric-grid">
                <div class="metric-card"><span class="metric-label">검사 일시</span><div class="metric-value">{ts}</div></div>
                <div class="metric-card"><span class="metric-label">응답자</span><div class="metric-value">{name_text}</div></div>
                <div class="metric-card"><span class="metric-label">일상 기능 손상 (10번 문항)</span><div class="metric-value">{functional_value}</div></div>
                <div class="metric-card"><span class="metric-label">자살/자해 관련 응답 (9번 문항)</span><div class="metric-value">{item9_score}점</div></div>
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    st.markdown("</div></section>", unsafe_allow_html=True)

    fig = build_total_severity_bar(total)
    with st.container():
        st.markdown('<section class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">총점 위치</div>', unsafe_allow_html=True)
        st.markdown('<div class="muted-copy" style="margin-top:8px;">PHQ-9 전체 점수 범위 안에서 현재 총점이 위치한 구간을 보여줍니다.</div>', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</section>", unsafe_allow_html=True)

    stat_labels = [
        ("중증도", sev),
        ("기능 손상", functional_value),
        ("자살/자해 관련 응답", f"{item9_score}점"),
        ("미응답 문항", f"{unanswered}개"),
    ]
    stat_tiles = "".join(
        f"<div class='metric-card'><span class='metric-label'>{label}</span><div class='metric-value'>{value}</div></div>" for label, value in stat_labels
    )
    st.markdown(
        f"""
        <section class="card">
          <div class="section-title">핵심 지표 요약</div>
          <div class="muted-copy" style="margin-top:8px;">현재 결과를 빠르게 검토할 수 있도록 주요 지표를 한곳에 정리했습니다.</div>
          <div class="metric-grid" style="margin-top:16px;">{stat_tiles}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    if unanswered > 0:
        st.markdown(f'<div class="notice-banner">⚠️ 미응답 {unanswered}개 문항은 0점으로 계산되었습니다.</div>', unsafe_allow_html=True)

    domain_html = build_domain_profile_html(scores)
    st.markdown(
        dedent(
            f"""
            <section class="card">
              <div class="section-title">증상 영역별 프로파일</div>
              <div class="muted-copy" style="margin:8px 0 18px;">각 영역별 보고된 증상 강도를 확인할 수 있습니다.</div>
              <div style="display:flex;flex-direction:column;gap:18px;">{domain_html}</div>
              <div class="muted-copy" style="margin-top:14px;padding-top:12px;border-top:1px solid #d8e5f5;">※ 각 영역의 점수는 높을수록 해당 영역의 우울 관련 증상이 더 많이 보고되었음을 의미합니다.</div>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )

    if item9_score > 0:
        st.markdown(
            """
            <section class="support-card" style="background:linear-gradient(180deg,#fff5f5 0%,#fff 100%);border-color:rgba(220,38,38,0.28);">
              <div class="section-title" style="font-size:1rem;">안전 안내 (문항 9 관련)</div>
              <div class="body-copy" style="margin-top:8px;"><b>한국: 1393 자살예방상담(24시간)</b>, <b>정신건강상담 1577-0199</b> · 긴급 시 <b>112/119</b>.</div>
            </section>
            """,
            unsafe_allow_html=True,
        )

    prev_clicked, next_clicked = render_navigation_row(
        "닫기",
        "새 검사 시작",
        helper_text="결과를 확인한 뒤 창을 닫거나, 동일한 흐름으로 새로운 검사를 다시 시작할 수 있습니다.",
    )
    if prev_clicked:
        components.html("<script>window.close();</script>", height=0)
        st.info("창이 닫히지 않으면 브라우저 탭을 직접 닫거나 ‘새 검사 시작’을 눌러 주세요.", icon="ℹ️")
    if next_clicked:
        _reset_to_survey()
        st.rerun()

    st.markdown(
        """
        <section class="card footer-card">
          PHQ-9는 공공 도메인(Pfizer 별도 허가 불필요).<br>
          Kroenke, Spitzer, & Williams (2001) JGIM · Spitzer, Kroenke, & Williams (1999) JAMA.
        </section>
        """,
        unsafe_allow_html=True,
    )

    def build_phq9_payload() -> dict:
        total_, sev_, functional_, scores_, ts_, unanswered_ = st.session_state.summary
        somatic_score = sum(scores_[i - 1] for i in SOMATIC)
        cog_aff_score = sum(scores_[i - 1] for i in COG_AFF)
        submitted_ts = kst_iso_now()
        exam_data = {
            "exam": {"title": "PHQ_9", "version": "v1"},
            "examinee": dict(st.session_state.examinee),
            "answers": {**{f"q{i}": scores_[i - 1] for i in range(1, 10)}, "functional_impact": functional_ if functional_ else None},
            "result": {"total": total_, "severity": sev_, "domain_scores": {"somatic": somatic_score, "cog_aff": cog_aff_score}, "unanswered": unanswered_},
            "meta": {"started_ts": st.session_state.consent_ts or "", "submitted_ts": submitted_ts, "consent": st.session_state.consent, "consent_ts": st.session_state.consent_ts},
        }
        return exam_data

    internal_payload = build_phq9_payload()
    exam_data = build_exam_data_phq9(internal_payload)
    auto_db_insert(exam_data)

    if dev_mode:
        required_keys = ["exam_name", "consent_col", "examinee_col", "answers_col", "result_col"]
        st.caption("dev=1 sanity check · standardized exam_data")
        st.json(exam_data, expanded=False)
        st.code(f"exam_data_has_exact_5_keys={list(exam_data.keys()) == required_keys} keys={list(exam_data.keys())}", language="text")


def render_intro_page() -> None:
    render_app_shell_start()
    render_step_strip("intro")
    render_intro_section()
    render_notice_cards()

    st.markdown(
        dedent(
            """
            <section class="card">
              <div class="card-header">
                <div>
                  <h2 class="section-title">검사 시작 동의</h2>
                  <p class="body-copy" style="margin-top:8px;">동의 후 다음 단계에서 응답자 정보를 입력하고 검사를 진행할 수 있습니다.</p>
                </div>
                <div class="helper-box">동의하지 않으면 검사를 진행할 수 없습니다.</div>
              </div>
            </section>
            """
        ),
        unsafe_allow_html=True,
    )

    consent_checked = st.checkbox(
        "개인정보 수집 및 이용에 동의합니다. (필수)",
        key="consent_checkbox",
        value=st.session_state.consent,
    )
    if consent_checked != st.session_state.consent:
        st.session_state.consent = consent_checked
        if not consent_checked:
            st.session_state.consent_ts = None

    _, next_clicked = render_navigation_row(
        "안내 확인",
        "다음",
        helper_text="검사 안내를 확인한 뒤 동의 여부를 점검하고 다음 단계로 이동합니다.",
    )
    if next_clicked:
        if not st.session_state.consent:
            st.warning("동의가 필요합니다.", icon="⚠️")
        else:
            if not st.session_state.consent_ts:
                st.session_state.consent_ts = kst_iso_now()
            st.session_state.page = "examinee"
            st.rerun()
    render_app_shell_end()


def render_examinee_page() -> None:
    render_app_shell_start()
    render_step_strip("examinee")
    prev_clicked, next_clicked = render_respondent_form()
    if prev_clicked:
        st.session_state.page = "intro"
        st.rerun()
    if next_clicked:
        st.session_state.page = "survey"
        st.rerun()
    render_app_shell_end()


def render_survey_page() -> None:
    render_app_shell_start()
    render_step_strip("survey")
    render_questionnaire_progress()
    render_questionnaire_section()
    prev_clicked, next_clicked = render_navigation_row(
        "이전",
        "결과 보기",
        helper_text="미응답 문항이 있더라도 현재 동작과 동일하게 결과를 계산하지만, 가능한 한 모든 문항에 응답해 주세요.",
    )
    if prev_clicked:
        st.session_state.page = "examinee"
        st.rerun()
    if next_clicked:
        scores, unanswered = [], 0
        for i in range(1, 10):
            lab = st.session_state.answers.get(i)
            if lab is None:
                unanswered += 1
                scores.append(0)
            else:
                scores.append(LABEL2SCORE[lab])
        total = sum(scores)
        sev = phq_severity(total)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        st.session_state.summary = (total, sev, st.session_state.functional, scores, ts, unanswered)
        st.session_state.page = "result"
        st.rerun()
    render_app_shell_end()


# ──────────────────────────────────────────────────────────────────────────────
# DB 연동

def _is_db_insert_enabled() -> bool:
    raw = os.getenv("ENABLE_DB_INSERT", "true")
    return str(raw).strip().lower() != "false"


ENABLE_DB_INSERT = _is_db_insert_enabled()

if ENABLE_DB_INSERT:
    from utils.database import Database


def safe_db_insert(exam_data: dict) -> bool:
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


def main() -> None:
    inject_css()
    init_state()

    params = st.query_params
    dev_mode = str(params.get("dev", "0")) == "1"

    if st.session_state.page == "intro":
        render_intro_page()
    elif st.session_state.page == "examinee":
        if not st.session_state.consent:
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            st.rerun()
        render_examinee_page()
    elif st.session_state.page == "survey":
        if not st.session_state.consent:
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            st.rerun()
        if not st.session_state.examinee.get("name", "").strip():
            st.session_state.page = "examinee"
            st.rerun()
        render_survey_page()
    elif st.session_state.page == "result":
        render_app_shell_start()
        render_step_strip("result")
        render_result_section(dev_mode=dev_mode)
        render_app_shell_end()
    else:
        st.session_state.page = "intro"
        st.rerun()


if __name__ == "__main__":
    main()
