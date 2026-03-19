# -*- coding: utf-8 -*-
import os
import shutil
import platform
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from textwrap import dedent

import io
import streamlit as st
import streamlit.components.v1 as components  # 창 닫기용
import plotly.graph_objects as go
import plotly.io as pio
from PIL import Image, ImageDraw, ImageFont  # PNG 합성용 (현재 파일 내에서 직접 사용하지 않아도 유지)


# ──────────────────────────────────────────────────────────────────────────────
# 앱 상태 초기화
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
# 페이지 설정
st.set_page_config(page_title="PHQ-9 자기보고 검사", page_icon="📝", layout="centered")

# ──────────────────────────────────────────────────────────────────────────────
# ORCA 초기화 (필수: ORCA만 사용)
def _init_orca():
    """
    ORCA 실행파일을 환경변수 PLOTLY_ORCA 또는 PATH에서 찾고 plotly에 등록한다.
    리눅스/맥 헤드리스 환경은 xvfb 사용을 활성화한다.
    """
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

# 색상 토큰 (라이트 테마 기본값 – CSS 변수로 재정의)
INK     = "#0F172A"   # primary text (dark navy)
SUBTLE  = "#475569"   # secondary text (slate)
CARD_BG = "#FFFFFF"   # cards are clean white
APP_BG  = "#F6F8FB"   # off-white app background
BORDER  = "#E2E8F0"   # subtle border
BRAND   = "#2563EB"   # keep as-is (brand blue)
ACCENT  = "#DC2626"   # keep as-is (danger)

# ──────────────────────────────────────────────────────────────────────────────
# 전역 스타일
def inject_css() -> None:
    st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

:root {
  --bg: #F6F8FB;
  --surface: #FFFFFF;
  --surface-2: #F8FAFC;
  --ink: #0F172A;
  --muted: #475569;
  --muted-2: #64748B;
  --border: #E2E8F0;
  --shadow: 0 10px 30px rgba(15,23,42,.08);
  --radius-lg: 24px;
  --radius-md: 16px;
  --brand: #2563EB;
  --brand-600: #1D4ED8;
  --brand-50: rgba(37,99,235,.10);
  --danger: #DC2626;
  --danger-50: rgba(220,38,38,.10);
}

* {
  box-sizing: border-box;
}

html, body {
  color-scheme: light !important;
  background: var(--bg);
  color: var(--ink);
  font-family: "Inter","Noto Sans KR",system-ui,-apple-system,Segoe UI,Roboto,Apple SD Gothic Neo,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

[data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
}

[data-testid="block-container"] {
  max-width: 100%;
  padding: 0;
  margin: 0;
}

body, p, div, span, li, button, label, input, textarea {
  font-family: "Inter","Noto Sans KR",system-ui,-apple-system,Segoe UI,Roboto,Apple SD Gothic Neo,Helvetica,Arial,sans-serif !important;
}

.app-wrap { max-width: 960px; margin: 0 auto; padding: 0 24px 56px; }
.stack { display:flex; flex-direction:column; gap:16px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow); padding: 28px; }
.card.compact { padding: 20px; border-radius: var(--radius-md); }
.card-header { display:flex; flex-direction:column; gap:10px; }
.title-xl { font-size: 1.6rem; font-weight: 900; letter-spacing: -0.4px; color: var(--ink); }
.title-lg { font-size: 1.15rem; font-weight: 850; color: var(--ink); }
.text { color: var(--muted); line-height: 1.7; font-size: 0.98rem; }
.divider { height:1px; background: var(--border); margin: 10px 0; }
.actions { display:flex; gap:12px; justify-content:center; align-items:center; margin-top: 6px; }
.actions .stButton { margin:0 !important; }
.actions-row { display:flex; gap:12px; }

.badge {
  display: inline-flex;
  padding: 4px 12px;
  border-radius: 999px;
  background: var(--brand-50);
  color: var(--brand);
  font-weight: 800;
  font-size: 12px;
  border: 1px solid rgba(37,99,235,0.25);
  width: fit-content;
}

.instruction-list {
  margin: 12px 0 0;
  padding-left: 18px;
  line-height: 1.7;
  color: var(--ink);
  font-size: 0.98rem;
}

.instruction-list li { margin-bottom: 8px; }

.question-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.question-text {
  font-weight: 700;
  font-size: 1rem;
  line-height: 1.6;
  color: var(--ink);
}

.question-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-card {
  margin-bottom: 32px !important;
}

.question-card {
  margin-bottom: 20px !important;
}

.section-to-question {
  margin-bottom: 40px !important;
}

.result-card {
  margin-bottom: 28px !important;
}

.result-danger {
  margin-top: 36px !important;
}

.result-actions {
  margin-top: 32px !important;
}

.summary-layout {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
  margin-top: 18px;
}

.gauge-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 28px 22px 32px;
  text-align: center;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gauge-circle {
  width: 210px;
  height: 210px;
  border-radius: 50%;
  margin: 0 auto 10px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.06);
}

.gauge-circle::after {
  content: "";
  position: absolute;
  inset: 24px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.06);
}

.gauge-inner {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.gauge-number { font-size: 3rem; font-weight: 900; line-height: 1; color: var(--ink); }
.gauge-denom { font-size: 1rem; font-weight: 700; color: var(--muted); }
.gauge-severity { display: inline-flex; padding: 6px 18px; border-radius: 999px; font-weight: 800; border: 1.5px solid currentColor; font-size: 1rem; }

.narrative-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 26px 28px;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.narrative-title { font-weight: 800; font-size: 1rem; }
.functional-highlight { border-top: 1px solid var(--border); padding-top: 14px; }
.functional-title { font-size: 0.9rem; color: var(--muted-2); font-weight: 700; margin-bottom: 6px; }
.functional-value { font-size: 1.05rem; }

.domain-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 22px 24px;
  background: var(--surface-2);
  box-shadow: var(--shadow);
}

.domain-profile {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.domain-note {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
  color: var(--muted);
  line-height: 1.5;
}

.domain-row {
  display: grid;
  grid-template-columns: 1.4fr 2.2fr 0.6fr;
  gap: 16px;
  align-items: center;
}

.domain-title { font-weight: 700; font-size: 1rem; }
.domain-desc { font-size: 0.85rem; color: var(--muted); margin-top: 4px; }
.domain-bar { position: relative; height: 14px; background: rgba(226,232,240,0.9); border-radius: 999px; overflow: hidden; border: 1px solid rgba(203,213,225,0.9); }
.domain-fill { position: absolute; inset: 0; border-radius: 999px; background: var(--brand); }
.domain-score { justify-self: end; font-weight: 700; }

.severity-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.legend-chip {
  display: flex;
  flex-direction: column;
  padding: 10px 14px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--surface);
  min-width: 140px;
}

.legend-chip strong { font-size: 0.95rem; }
.legend-chip small { color: var(--muted-2); font-size: 0.8rem; }

.warn { background: #FFF7ED; border: 1px solid #FDBA74; color: #7C2D12; border-radius: var(--radius-md); padding: 14px 18px; font-weight: 600; }
.safety-card { background: var(--danger-50); border: 1px solid var(--danger); color: var(--ink); border-radius: var(--radius-lg); padding: 22px 24px; box-shadow: var(--shadow); }
.safety-card .title-lg { color: var(--danger); }

.footer-note { color: var(--muted); font-size: 12px; line-height: 1.5; text-align: center; }

.card p,
.card li {
  line-height: 1.75 !important;
}

[data-testid="stToolbar"], #MainMenu, header, footer { display: none !important; }

/* Inputs */
[data-testid="stTextInput"] label,
[data-testid="stSelectbox"] label {
  color: var(--muted-2) !important;
  font-weight: 700 !important;
}

[data-testid="stTextInput"] div[data-baseweb="input"] > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  background: #fff !important;
  color: var(--ink) !important;
  border: 2px solid #2F3542 !important;
  border-radius: 12px !important;
  min-height: 46px !important;
  height: 46px !important;
  box-shadow: none !important;
  outline: none !important;
  transition: border-color 0.18s ease, box-shadow 0.18s ease !important;
}

[data-testid="stTextInput"] div[data-baseweb="input"],
[data-testid="stSelectbox"] div[data-baseweb="select"],
[data-testid="stTextInput"] div[data-baseweb="input"] *,
[data-testid="stSelectbox"] div[data-baseweb="select"] * {
  box-shadow: none !important;
}

[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] input {
  background: transparent !important;
  color: var(--ink) !important;
  box-shadow: none !important;
  outline: none !important;
  border: 0 !important;
  padding: 0 14px !important;
  height: 42px !important;
  min-height: 42px !important;
}

[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  padding: 0 14px !important;
  display: flex !important;
  align-items: center !important;
}

[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div {
  min-height: 42px !important;
  height: 42px !important;
  display: flex !important;
  align-items: center !important;
}

[data-testid="stSelectbox"] div[data-baseweb="select"] [role="button"] {
  min-height: 42px !important;
  height: 42px !important;
  padding: 0 !important;
  border: 0 !important;
  outline: none !important;
  box-shadow: none !important;
  background: transparent !important;
}

[data-testid="stTextInput"] div[data-baseweb="input"] > div:hover,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {
  border-color: #2F3542 !important;
}

[data-testid="stTextInput"] div[data-baseweb="input"] > div:focus-within,
[data-testid="stTextInput"] input:focus,
[data-testid="stTextInput"] input:focus-visible,
[data-testid="stSelectbox"] div[data-baseweb="select"] div[aria-expanded="true"],
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:has(input:focus),
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:has(input:focus-visible) {
  border-color: var(--brand) !important;
  border-width: 2px !important;
  box-shadow: none !important;
  outline: none !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"] span,
[data-testid="stSelectbox"] [data-baseweb="select"] input,
[data-testid="stSelectbox"] [data-baseweb="select"] svg {
  color: var(--ink) !important;
  fill: var(--ink) !important;
}

/* Checkbox */
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] p,
[data-testid="stCheckbox"] span {
  color: var(--ink) !important;
  opacity: 1 !important;
  font-weight: 700 !important;
}

[data-testid="stCheckbox"] svg {
  color: var(--brand) !important;
}

[data-testid="stCheckbox"] input:focus-visible + div {
  outline: none !important;
  box-shadow: 0 0 0 3px rgba(37,99,235,.18) !important;
  border-radius: 6px;
}

/* Radios */
[data-testid="stRadio"] > div[role="radiogroup"] {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 10px !important;
  align-items: center !important;
}

[data-testid="stRadio"] {
  margin-top: 6px;
}

[data-testid="stRadio"] [role="radio"] {
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
  padding: 10px 16px !important;
  border-radius: 999px !important;
  background: #fff !important;
  border: 1px solid var(--border) !important;
  color: var(--ink) !important;
  font-weight: 700 !important;
  white-space: nowrap !important;
}

[data-testid="stRadio"] [role="radio"][aria-checked="true"] {
  background: var(--brand-50) !important;
  border-color: var(--brand) !important;
}

[data-testid="stRadio"] label,
[data-testid="stRadio"] label span {
  color: var(--ink) !important;
  opacity: 1 !important;
  white-space: nowrap !important;
}

[data-testid="stRadio"] label span {
  color: var(--ink) !important;
  font-weight: 600 !important;
  opacity: 1 !important;
}

[data-testid="stRadio"] input:checked + div {
  outline: 2px solid rgba(37,99,235,.35) !important;
  border-radius: 999px !important;
}

[data-testid="stRadio"] div {
  color: var(--ink) !important;
}

[data-testid="stRadio"] label:focus-within {
  border-color: var(--brand) !important;
  box-shadow: 0 0 0 3px rgba(37,99,235,.18) !important;
}

/* Alerts */
[data-testid="stAlert"] * {
  color: #0F172A !important;
  opacity: 1 !important;
}

/* Buttons */
.stButton > button {
  border-radius: 14px !important;
  min-height: 46px !important;
  font-weight: 900 !important;
  white-space: nowrap !important;
  word-break: keep-all !important;
  padding: 0 22px !important;
}

.stButton > button:focus-visible {
  outline: none !important;
  box-shadow: 0 0 0 3px rgba(37,99,235,.25) !important;
}

.stButton > button[kind="primary"] {
  background: var(--brand) !important;
  border-color: var(--brand) !important;
  color: #FFFFFF !important;
}

.stButton > button[kind="primary"] * {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}

.stButton > button[kind="primary"]:hover {
  background: var(--brand-600) !important;
  border-color: var(--brand-600) !important;
}

.stButton > button:not([kind="primary"]) {
  background: #fff !important;
  color: var(--brand) !important;
  border: 1.5px solid var(--brand) !important;
}

.stButton > button:not([kind="primary"]) * {
  color: var(--brand) !important;
  -webkit-text-fill-color: var(--brand) !important;
}

.stButton > button:disabled {
  background: var(--surface-2) !important;
  color: var(--muted-2) !important;
  border-color: var(--border) !important;
  cursor: not-allowed !important;
}

@media (max-width: 640px) {
  .app-wrap { padding: 0 18px 40px; }
  .gauge-circle { width: 180px; height: 180px; }
  .domain-row { grid-template-columns: 1fr; }
  .domain-score { justify-self: start; }
}
</style>
""",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 상태 관리
def init_state() -> None:
    if "page" not in st.session_state:
        st.session_state.page = "intro"   # 'intro' | 'examinee' | 'survey' | 'result'
    if "consent" not in st.session_state:
        st.session_state.consent = False
    if "consent_ts" not in st.session_state:
        st.session_state.consent_ts = None
    if "answers" not in st.session_state:
        st.session_state.answers: Dict[int, str] = {}
    if "functional" not in st.session_state:
        st.session_state.functional = None
    if "summary" not in st.session_state:
        st.session_state.summary = None  # (total, sev, functional, scores, ts, unanswered)
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

# ──────────────────────────────────────────────────────────────────────────────
# 문항/선택지
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
    {"no":1,"ko":"일상적인 활동(예: 취미나 일상 일과 등)에 흥미나 즐거움을 거의 느끼지 못한다.","domain":"흥미/즐거움 상실"},
    {"no":2,"ko":"기분이 가라앉거나, 우울하거나, 희망이 없다고 느낀다.","domain":"우울한 기분"},
    {"no":3,"ko":"잠들기 어렵거나 자주 깨는 등 수면에 문제가 있었거나, 반대로 너무 많이 잠을 잔다.","domain":"수면 문제"},
    {"no":4,"ko":"평소보다 피곤함을 더 자주 느꼈거나, 기운이 거의 없다.","domain":"피로/에너지 부족"},
    {"no":5,"ko":"식욕이 줄었거나 반대로 평소보다 더 많이 먹는다.","domain":"식욕 변화"},
    {"no":6,"ko":"자신을 부정적으로 느끼거나, 스스로 실패자라고 생각한다.","domain":"죄책감/무가치감"},
    {"no":7,"ko":"일상생활 및 같은 일에 집중하는 것이 어렵다.","domain":"집중력 저하"},
    {"no":8,"ko":"다른 사람들이 눈치챌 정도로 매우 느리게 말하고 움직이거나, 반대로 평소보다 초조하고 안절부절 못한다.","domain":"느려짐/초조함"},
    {"no":9,"ko":"죽는 게 낫겠다는 생각하거나, 어떤 식으로든 자신을 해치고 싶은 생각이 든다.","domain":"자살/자해 생각"},
]
LABELS = ["전혀 아님 (0)", "며칠 동안 (1)", "절반 이상 (2)", "거의 매일 (3)"]
LABEL2SCORE = {LABELS[0]:0, LABELS[1]:1, LABELS[2]:2, LABELS[3]:3}


def _sanitize_csv_value(v) -> str:
    """콤마 구분 문자열에 안전하게 넣기 위해 값 내부 콤마/줄바꿈 제거."""
    if v is None:
        return ""
    s = str(v)
    s = s.replace("\n", " ").replace("\r", " ")
    s = s.replace(",", " ")  # 값 내부 콤마는 공백으로 치환(요구사항: 콤마 구분)
    return s.strip()

def dict_to_kv_csv(d: dict) -> str:
    """{"a":1,"b":2} -> "a=1,b=2" """
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
    """
    DB 저장 레코드(5컬럼):
    - exam_name
    - consent_col
    - examinee_col
    - answers_col
    - result_col
    각 컬럼 값은 "k=v,k2=v2" 형태 문자열
    """
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
    # answers: q1..q9, functional_impact 등

    result = payload.get("result", {}) or {}
    # result: total, severity, domain_scores, unanswered 등

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

# ──────────────────────────────────────────────────────────────────────────────
# 유틸: 중증도 라벨
def phq_severity(total: int) -> str:
    return ("정상" if total<=4 else
            "경미" if total<=9 else
            "중등도" if total<=14 else
            "중증" if total<=19 else
            "심각")

# ──────────────────────────────────────────────────────────────────────────────
# PHQ-9 도메인 인덱스(1-based)
COG_AFF = [1, 2, 6, 7, 9]   # 인지·정서(5문항)
SOMATIC = [3, 4, 5, 8]      # 신체/생리(4문항)

# ──────────────────────────────────────────────────────────────────────────────
SEVERITY_SEGMENTS = [
    {"label": "정상", "display": "0–4",  "start": 0,  "end": 5,  "color": "#CDEED6"},
    {"label": "경미", "display": "5–9",  "start": 5,  "end": 10, "color": "#F8F1C7"},
    {"label": "중등도", "display": "10–14","start": 10, "end": 15, "color": "#FFE0B2"},
    {"label": "중증", "display": "15–19","start": 15, "end": 20, "color": "#FBC0A8"},
    {"label": "심각", "display": "20–27","start": 20, "end": 27, "color": "#F6A6A6"},
]

SEVERITY_PILL = {
    "정상": ("#DBEAFE", "#1E3A8A"),
    "경미": ("#FEF3C7", "#92400E"),
    "중등도": ("#FFE4E6", "#9F1239"),
    "중증": ("#FED7AA", "#9A3412"),
    "심각": ("#FECACA", "#7F1D1D"),
}

SEVERITY_ARC_COLOR = {
    "정상": "#16a34a",
    "경미": "#f59e0b",
    "중등도": "#f97316",
    "중증": "#f43f5e",
    "심각": "#b91c1c",
}

SEVERITY_GUIDANCE = {
    "정상": "현재 보고된 주관적 우울 증상은 정상 범위에 해당하며, 기본적인 자기 관리와 모니터링을 이어가시면 됩니다.",
    "경미": "경미 수준의 우울감이 보고되었습니다. 생활리듬 조정과 상담 자원 안내 등 예방적 개입을 고려할 수 있습니다.",
    "중등도": "임상적으로 의미 있는 중등도 수준으로, 정신건강 전문인의 평가와 치료적 개입을 권장합니다.",
    "중증": "중증 수준의 우울 증상이 보고되어, 신속한 전문 평가와 적극적인 치료 계획 수립이 필요합니다.",
    "심각": "심각 수준의 우울 증상이 보고되었습니다. 안전 평가를 포함한 즉각적인 전문 개입이 권고됩니다.",
}

DOMAIN_META = [
    {
        "name": "신체/생리 증상",
        "desc": "(수면, 피곤함, 식욕, 정신운동 문제)",
        "items": SOMATIC,
        "max": 12,
    },
    {
        "name": "인지/정서 증상",
        "desc": "(흥미저하, 우울감, 죄책감, 집중력, 자살사고)",
        "items": COG_AFF,
        "max": 15,
    },
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
        xaxis=dict(
            range=[0, 27],
            showgrid=False,
            zeroline=False,
            tickvals=[0, 5, 10, 15, 20, 27],
            ticks="outside",
            tickfont=dict(size=11),
        ),
        yaxis=dict(showticklabels=False),
        margin=dict(l=30, r=30, t=50, b=60),
        height=260,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color=INK, family="Inter, 'Noto Sans KR', Arial, sans-serif"),
        annotations=annotations,
    )
    return fig


def render_severity_legend():
    spans = "".join(
        f"<div class='legend-chip'><strong>{seg['label']}</strong><small>{seg['display']}점</small></div>"
        for seg in SEVERITY_SEGMENTS
    )
    st.markdown(
        f"""
<div class="app-wrap">
  <div class="card compact">
    <div class="severity-legend">{spans}</div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )


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
                <div class="domain-row">
                  <div>
                    <div class="domain-title">{meta['name']}</div>
                    <div class="domain-desc">{meta['desc']}</div>
                  </div>
                  <div class="domain-bar">
                    <div class="domain-fill" style="width:{ratio*100:.1f}%"></div>
                  </div>
                  <div class="domain-score">{score} / {meta['max']}</div>
                </div>
                """
            ).strip()
        )
    rows_html = "\n".join(rows)
    note_html = (
        '<div class="domain-note">※ 각 영역의 점수는 높을수록 해당 영역의 우울 관련 증상이 더 많이 보고되었음을 의미합니다.</div>'
    )
    return (
        '<div class="domain-panel">\n'
        '  <div class="domain-profile">\n'
        f'{rows_html}\n'
        '  </div>\n'
        f'{note_html}\n'
        '</div>'
    )


def compose_narrative(total: int, severity: str, functional: str | None, item9: int) -> str:
    base = f"총점 {total}점(27점 만점)으로, [{severity}] 수준의 우울 증상이 보고되었습니다. {SEVERITY_GUIDANCE[severity]}"
    functional_text = (
        f" 응답자 보고에 따르면, 이러한 증상으로 인한 일·집안일·대인관계의 어려움은 ‘{functional}’ 수준입니다."
        if functional else ""
    )
    safety_text = (
        " 특히, 자해/자살 관련 사고(9번 문항)가 보고되어 이에 대한 즉각적인 관심과 평가가 매우 중요합니다."
        if item9 > 0 else ""
    )
    return base + functional_text + safety_text


def kst_iso_now() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).isoformat(timespec="seconds")


# ──────────────────────────────────────────────────────────────────────────────
# UI 헬퍼
def render_question_item(question: Dict[str, str | int]) -> None:
    with st.container():
        st.markdown(
            dedent(
                f"""
                <div class="card compact question-card">
                  <div class="question-header">
                    <div class="badge">문항 {question['no']}</div>
                    <div class="question-text">{question['ko']}</div>
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
        st.markdown("</div>", unsafe_allow_html=True)


def render_functional_block() -> None:
    with st.container():
        st.markdown(
            dedent(
                """
                <div class="card compact question-card">
                  <div class="question-header">
                    <div class="badge">기능 손상</div>
                    <div class="question-text">이 문제들 때문에 일·집안일·대인관계에 얼마나 어려움이 있었습니까?</div>
                    <div class="text" style="margin-top:4px;">가장 가까운 수준을 선택해 주세요.</div>
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
        st.markdown("</div>", unsafe_allow_html=True)


def render_intro_page() -> None:
    with st.container():
        st.markdown('<div class="app-wrap"><div class="stack">', unsafe_allow_html=True)

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="badge">PHQ-9</div>
                    <div class="title-xl">우울 증상 자기보고 검사</div>
                    <div class="text">지난 2주 동안 경험한 증상 빈도를 0~3점 척도로 기록하는 표준화된 자기보고 도구입니다.</div>
                  </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="title-lg">PHQ-9 검사 안내</div>
                  </div>
                  <ul class="instruction-list">
                    <li>목적: 최근 2주간 우울 관련 증상의 빈도를 자가 보고하여 현재 상태를 점검합니다.</li>
                    <li>대상: 만 12세 이상 누구나 스스로 응답할 수 있습니다.</li>
                    <li>응답 방식: 각 문항은 <b>전혀 아님(0)</b>부터 <b>거의 매일(3)</b>까지의 0~3점 척도로 응답합니다.</li>
                  </ul>
                  <div class="text" style="margin-top:10px;">※ 결과 해석은 참고용이며, 의학적 진단을 대신하지 않습니다.</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="title-lg">개인정보 수집·이용 동의</div>
                  </div>
                  <ul class="instruction-list">
                    <li>수집 항목: 이름, 성별, 연령, 거주지역, 이메일, 연락처, 응답 내용, 결과, 제출 시각</li>
                    <li>이용 목적: 검사 수행 및 결과 제공, 통계 및 품질 개선, DB 저장</li>
                    <li>보관 기간: 내부 정책에 따름</li>
                    <li>제3자 제공: 없음</li>
                    <li>동의 거부 권리 및 불이익: 동의하지 않으실 경우 검사를 진행할 수 없습니다.</li>
                  </ul>
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
        st.markdown("</div>", unsafe_allow_html=True)

        actions = st.columns([1, 1], gap="medium")
        with actions[0]:
            st.empty()
        with actions[1]:
            next_clicked = st.button("다음", type="primary", use_container_width=True)
            if next_clicked:
                if not st.session_state.consent:
                    st.warning("동의가 필요합니다.", icon="⚠️")
                else:
                    if not st.session_state.consent_ts:
                        st.session_state.consent_ts = kst_iso_now()
                    st.session_state.page = "examinee"
                    st.rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)


def render_examinee_page() -> None:
    with st.container():
        st.markdown('<div class="app-wrap"><div class="stack">', unsafe_allow_html=True)

        st.markdown(
            """
            <div class="card result-card">
              <div class="card-header">
                <div class="title-lg">응답자 정보</div>
                <div class="text">이름, 성별, 연령, 거주지역은 필수이며 연락처와 이메일은 선택 입력입니다.</div>
              </div>
            """,
            unsafe_allow_html=True,
        )
        row1_col1, row1_col2 = st.columns([1, 1], gap="medium")
        with row1_col1:
            name = st.text_input(
                "이름",
                value=st.session_state.examinee.get("name", ""),
            )
        with row1_col2:
            gender = st.selectbox(
                "성별",
                options=[""] + GENDER_OPTIONS,
                index=([""] + GENDER_OPTIONS).index(st.session_state.examinee.get("gender", ""))
                if st.session_state.examinee.get("gender", "") in GENDER_OPTIONS
                else 0,
            )

        row2_col1, row2_col2 = st.columns([1, 1], gap="medium")
        with row2_col1:
            age = st.text_input(
                "연령",
                value=st.session_state.examinee.get("age", ""),
            )
        with row2_col2:
            region = st.selectbox(
                "거주지역",
                options=[""] + REGION_OPTIONS,
                index=([""] + REGION_OPTIONS).index(st.session_state.examinee.get("region", ""))
                if st.session_state.examinee.get("region", "") in REGION_OPTIONS
                else 0,
            )

        phone = st.text_input(
            "휴대폰번호 (선택)",
            value=st.session_state.examinee.get("phone", ""),
        )
        email = st.text_input(
            "이메일 (선택)",
            value=st.session_state.examinee.get("email", ""),
        )

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
        st.markdown("</div>", unsafe_allow_html=True)

        actions = st.columns([1, 1], gap="medium")
        with actions[0]:
            if st.button("이전", use_container_width=True):
                st.session_state.page = "intro"
                st.rerun()
        with actions[1]:
            if st.button("다음", type="primary", use_container_width=True, disabled=not all_valid):
                st.session_state.page = "survey"
                st.rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)


def render_survey_page() -> None:
    with st.container():
        st.markdown('<div class="app-wrap"><div class="stack">', unsafe_allow_html=True)

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="title-lg">지시문</div>
                  </div>
                  <ul class="instruction-list">
                    <li>각 문항에 대해 지난 2주 동안의 빈도를 <b>전혀 아님(0)</b> · <b>며칠 동안(1)</b> · <b>절반 이상(2)</b> · <b>거의 매일(3)</b> 가운데 가장 가까운 값으로 선택합니다.</li>
                    <li>모든 문항과 기능 손상 질문을 완료한 뒤 ‘결과 보기’를 누르면 총점, 중증도, 영역별 분석을 바로 확인할 수 있습니다.</li>
                  </ul>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="title-lg">질문지 (지난 2주)</div>
                    <div class="text">표준 PHQ-9 · 모든 문항은 동일한 0–3점 척도를 사용합니다.</div>
                  </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-to-question"></div>', unsafe_allow_html=True)

        for q in QUESTIONS:
            render_question_item(q)

        render_functional_block()

        actions = st.columns([1, 1], gap="medium")
        with actions[0]:
            if st.button("이전", use_container_width=True):
                st.session_state.page = "examinee"
                st.rerun()
        with actions[1]:
            if st.button("결과 보기", type="primary", use_container_width=True):
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

        st.markdown("</div></div>", unsafe_allow_html=True)


def render_result_page(dev_mode: bool = False) -> None:
    if not st.session_state.summary:
        st.warning("먼저 설문을 완료해 주세요.")
        st.stop()

    total, sev, functional, scores, ts, unanswered = st.session_state.summary
    item9_score = scores[8] if len(scores) >= 9 else 0

    narrative = compose_narrative(total, sev, functional, item9_score)
    arc_color = SEVERITY_ARC_COLOR.get(sev, BRAND)
    gauge_percent = (max(0, min(total, 27)) / 27) * 100
    functional_value = functional if functional else "미응답"

    st.markdown('<div class="app-wrap"><div class="stack">', unsafe_allow_html=True)

    name_value = st.session_state.examinee.get("name", "").strip()
    name_text = name_value if name_value else "(미입력)"

    st.markdown(
        dedent(
            f"""
            <div class="card result-card">
              <div class="card-header">
                <div class="title-lg">I. 종합 소견</div>
                <div class="text">검사 일시: {ts}</div>
                <div class="text">응답자: {name_text}</div>
              </div>
              <div class="summary-layout">
                <div class="gauge-card">
                  <div class="badge" style="margin: 0 auto;">총점</div>
                  <div class="gauge-circle" style="background: conic-gradient({arc_color} {gauge_percent:.2f}%, rgba(226,232,240,0.9) {gauge_percent:.2f}%, rgba(226,232,240,0.9) 100%);">
                    <div class="gauge-inner">
                      <div class="gauge-number">{total}</div>
                      <div class="gauge-denom">/ 27</div>
                    </div>
                  </div>
                  <div class="gauge-severity" style="color:{arc_color};">{sev}</div>
                </div>
                <div class="narrative-card">
                  <div class="narrative-title">주요 소견</div>
                  <div class="text">{narrative}</div>
                  <div class="functional-highlight">
                    <div class="functional-title">일상 기능 손상 (10번 문항)</div>
                    <div class="functional-value"><strong>{functional_value}</strong></div>
                  </div>
                </div>
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if unanswered > 0:
        st.markdown(
            f'<div class="warn">⚠️ 미응답 {unanswered}개 문항은 0점으로 계산되었습니다.</div>',
            unsafe_allow_html=True,
        )

    domain_html = build_domain_profile_html(scores)
    domain_section_html = dedent(
        """
        <div class="card result-card">
          <div class="card-header">
            <div class="title-lg">II. 증상 영역별 프로파일</div>
            <div class="text">각 영역별 보고된 증상 강도를 확인할 수 있습니다.</div>
          </div>
          {domain_panel}
        </div>
        """
    ).strip().format(domain_panel=domain_html)
    st.markdown(domain_section_html, unsafe_allow_html=True)

    if item9_score > 0:
        st.markdown(
            dedent(
                """
                <div class="card safety-card result-card result-danger">
                  <div class="card-header">
                    <div class="title-lg">안전 안내 (문항 9 관련)</div>
                    <div class="text">자살·자해 생각이 있을 때 즉시 도움 받기</div>
                  </div>
                  <div>한국: <b>1393 자살예방상담(24시간)</b>, <b>정신건강상담 1577-0199</b> · 긴급 시 <b>112/119</b>.</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="result-actions">', unsafe_allow_html=True)
    actions = st.columns([1, 1], gap="medium")
    with actions[0]:
        if st.button("닫기", use_container_width=True):
            components.html("<script>window.close();</script>", height=0)
            st.info("창이 닫히지 않으면 브라우저 탭을 직접 닫거나 ‘새 검사 시작’을 눌러 주세요.", icon="ℹ️")
    with actions[1]:
        if st.button("새 검사 시작", type="primary", use_container_width=True):
            _reset_to_survey()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        dedent(
            """
            <div class="card compact result-card">
              <div class="footer-note">
                PHQ-9는 공공 도메인(Pfizer 별도 허가 불필요).<br>
                Kroenke, Spitzer, & Williams (2001) JGIM · Spitzer, Kroenke, & Williams (1999) JAMA.
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    def build_phq9_payload() -> dict:
        total_, sev_, functional_, scores_, ts_, unanswered_ = st.session_state.summary

        somatic_score = sum(scores_[i - 1] for i in SOMATIC)
        cog_aff_score = sum(scores_[i - 1] for i in COG_AFF)

        submitted_ts = kst_iso_now()

        exam_data = {
            "exam": {"title": "PHQ_9", "version": "v1"},
            "examinee": dict(st.session_state.examinee),  # name/email/phone/user_id
            "answers": {
                **{f"q{i}": scores_[i - 1] for i in range(1, 10)},
                "functional_impact": functional_ if functional_ else None,
            },
            "result": {
                "total": total_,
                "severity": sev_,
                "domain_scores": {
                    "somatic": somatic_score,
                    "cog_aff": cog_aff_score,
                },
                "unanswered": unanswered_,
            },
            "meta": {
                "started_ts": st.session_state.consent_ts or "",
                "submitted_ts": submitted_ts,
                "consent": st.session_state.consent,
                "consent_ts": st.session_state.consent_ts,
            },
        }
        return exam_data

    with st.container():
        
        internal_payload = build_phq9_payload()
        exam_data = build_exam_data_phq9(internal_payload)
        auto_db_insert(exam_data)

        if dev_mode:
            required_keys = ["exam_name", "consent_col", "examinee_col", "answers_col", "result_col"]
            st.caption("dev=1 sanity check · standardized exam_data")
            st.json(exam_data, expanded=False)
            st.code(
                f"exam_data_has_exact_5_keys={list(exam_data.keys()) == required_keys} keys={list(exam_data.keys())}",
                language="text",
            )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
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
    # 중복 방지(성공 시에만 잠금)
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
        render_result_page(dev_mode=dev_mode)
    else:
        st.session_state.page = "intro"
        st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# 끝

if __name__ == "__main__":
    main()
