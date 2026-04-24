# -*- coding: utf-8 -*-
"""
KIRBS+ 무료 인지 기능 검사 패키지 v2
- 단일 Streamlit .py 파일
- 외부 .streamlit/config.toml 또는 별도 정적 파일 불필요
- JS 기반 과제 실행부로 반응시간(performance.now) 측정
- Trail 연결 과제, 2-back, Flanker, Go/No-Go 구성

실행:
  ENABLE_DB_INSERT=false streamlit run kirbs_cognitive_task_battery_v2.py
  Windows CMD: set ENABLE_DB_INSERT=false && streamlit run kirbs_cognitive_task_battery_v2.py
"""

from __future__ import annotations

import base64
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import streamlit.components.v1 as components


# ──────────────────────────────────────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KIRBS+ 인지 기능 검사",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

KST = timezone(timedelta(hours=9))

EXAM_NAME = "KIRBS_COGNITIVE_TASK_BATTERY"
EXAM_TITLE = "KIRBS+ 인지 기능 검사"
EXAM_SUBTITLE = "주의 · 처리속도 · 작업기억 · 억제통제"
EXAM_VERSION = "streamlit_js_2.0"

REGION_OPTIONS = ["수도권", "충청권", "강원권", "전라권", "경상권", "제주도"]
GENDER_OPTIONS = ["남성", "여성", "기타", "응답하지 않음"]
DEVICE_OPTIONS = ["PC/노트북", "태블릿", "모바일", "기타"]


# ──────────────────────────────────────────────────────────────────────────────
# 공통 유틸
# ──────────────────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def get_query_value(key: str, default: str = "") -> str:
    try:
        value = st.query_params.get(key, default)
        if isinstance(value, list):
            return value[0] if value else default
        return str(value)
    except Exception:
        try:
            params = st.experimental_get_query_params()
            value = params.get(key, [default])
            return value[0] if value else default
        except Exception:
            return default


def clear_query_params() -> None:
    try:
        st.query_params.clear()
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass


def decode_payload_from_query() -> Optional[Dict[str, Any]]:
    raw = get_query_value("cog_data", "")
    done = get_query_value("cog_done", "")
    if done != "1" or not raw:
        return None
    try:
        padded = raw + "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
        if isinstance(payload, dict) and payload.get("exam_name") == EXAM_NAME:
            return payload
    except Exception as e:
        st.warning(f"검사 결과 데이터를 읽는 중 문제가 발생했습니다: {e}")
    return None


def b64_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8").rstrip("=")


def _sanitize_csv_value(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    s = s.replace("\n", " ").replace("\r", " ").replace(",", " ")
    return s.strip()


def dict_to_kv_csv(d: Dict[str, Any]) -> str:
    if not isinstance(d, dict):
        return ""
    return ",".join(f"{_sanitize_csv_value(k)}={_sanitize_csv_value(v)}" for k, v in d.items())


def validate_name(name: str) -> Optional[str]:
    return None if name.strip() else "이름을 입력해 주세요."


def validate_gender(gender: str) -> Optional[str]:
    if not gender.strip():
        return "성별을 선택해 주세요."
    if gender not in GENDER_OPTIONS:
        return "성별을 다시 선택해 주세요."
    return None


def validate_age(age: str) -> Optional[str]:
    value = age.strip()
    if not value:
        return "연령을 입력해 주세요."
    if not value.isdigit():
        return "연령은 숫자만 입력해 주세요."
    age_num = int(value)
    if not 1 <= age_num <= 120:
        return "연령은 1세부터 120세 사이로 입력해 주세요."
    return None


def validate_region(region: str) -> Optional[str]:
    if not region.strip():
        return "거주지역을 선택해 주세요."
    if region not in REGION_OPTIONS:
        return "거주지역을 다시 선택해 주세요."
    return None


def validate_phone(phone: str) -> Optional[str]:
    value = phone.strip()
    if not value:
        return None
    if not re.fullmatch(r"[0-9-]+", value):
        return "휴대폰번호는 숫자와 하이픈(-)만 입력해 주세요."
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) not in (10, 11):
        return "휴대폰번호는 숫자 기준 10자리 또는 11자리여야 합니다."
    return None


def validate_email(email: str) -> Optional[str]:
    value = email.strip()
    if not value:
        return None
    if not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", value):
        return "이메일 형식이 올바르지 않습니다."
    return None


def normalize_phone(phone: str) -> str:
    value = (phone or "").strip().replace(" ", "")
    value = re.sub(r"[^0-9-]", "", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def criterion_label(score: Optional[float]) -> str:
    if score is None:
        return "산출 불가"
    if score >= 65:
        return "양호"
    if score >= 45:
        return "보통"
    return "주의"


def score_desc(score: Optional[float]) -> str:
    if score is None:
        return "응답 데이터가 충분하지 않아 산출하지 못했습니다."
    if score >= 65:
        return "현재 과제 수행에서는 속도와 정확도가 비교적 안정적으로 나타났습니다."
    if score >= 45:
        return "현재 과제 수행은 기준 범위에 가까우나, 피로·긴장·기기 환경에 따라 변동될 수 있습니다."
    return "일부 과제에서 반응 지연, 오류 증가, 반응 억제 어려움 또는 작업기억 부담이 관찰되었습니다."


# ──────────────────────────────────────────────────────────────────────────────
# 상태 관리
# ──────────────────────────────────────────────────────────────────────────────
def init_state() -> None:
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
            "device": "PC/노트북",
            "phone": "",
            "email": "",
        }
    if "context" not in st.session_state:
        st.session_state.context = {
            "sleep_quality_1to5": 3,
            "fatigue_1to5": 3,
            "caffeine_last_3h": "응답 안 함",
        }
    if "cog_payload" not in st.session_state:
        st.session_state.cog_payload = None
    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False
    if "close_attempted" not in st.session_state:
        st.session_state.close_attempted = False


def reset_all() -> None:
    st.session_state.page = "intro"
    st.session_state.meta = {
        "respondent_id": str(uuid.uuid4()),
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
        "device": "PC/노트북",
        "phone": "",
        "email": "",
    }
    st.session_state.context = {
        "sleep_quality_1to5": 3,
        "fatigue_1to5": 3,
        "caffeine_last_3h": "응답 안 함",
    }
    st.session_state.cog_payload = None
    st.session_state.db_insert_done = False
    st.session_state.close_attempted = False
    clear_query_params()


# ──────────────────────────────────────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  color-scheme: dark !important;
  --content-max-width: 980px;
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
  --radius-xl: 22px;
  --radius-lg: 18px;
  --radius-md: 14px;
  --shadow-sm: 0 8px 24px rgba(2, 8, 23, 0.28);
  --shadow-md: 0 18px 40px rgba(2, 8, 23, 0.38);
}

html, body, .stApp {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif !important;
  letter-spacing: -0.01em;
}

.stApp {
  background:
    radial-gradient(circle at top left, rgba(79,156,255,.08), transparent 30%),
    linear-gradient(180deg, #06101f 0%, #071225 100%) !important;
}

.block-container {
  max-width: var(--content-max-width) !important;
  padding-top: 0.85rem !important;
  padding-bottom: 3.2rem !important;
}

header[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer, div[data-testid="stDecoration"] {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
}

.page-wrap {
  width: min(100%, var(--content-max-width));
  margin: 0 auto;
  animation: fadeIn .22s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.card {
  background: linear-gradient(180deg, rgba(255,255,255,.018), rgba(255,255,255,.006)), var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  padding: 24px;
  margin-bottom: 16px;
}

.card.soft {
  background: linear-gradient(180deg, rgba(255,255,255,.012), rgba(255,255,255,.004)), var(--surface-2);
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--primary-soft);
  color: #89beff !important;
  font-size: 12px;
  font-weight: 800;
  margin-right: 8px;
  margin-bottom: 8px;
  border: 1px solid rgba(79, 156, 255, 0.22);
}

.title-lg {
  font-size: clamp(26px, 3vw, 34px) !important;
  font-weight: 880 !important;
  line-height: 1.28 !important;
  color: var(--text) !important;
  margin: 6px 0 0 !important;
}

.title-md {
  font-size: clamp(18px, 2.2vw, 21px) !important;
  font-weight: 780 !important;
  line-height: 1.35 !important;
  color: var(--text) !important;
  margin: 0 0 8px !important;
}

.text, .muted, .card p, .card li {
  color: var(--muted) !important;
  line-height: 1.72 !important;
  font-size: 15px !important;
  opacity: 1 !important;
}

.intro-bullets {
  margin: 0;
  padding-left: 1.15rem;
  display: grid;
  gap: .68rem;
  color: var(--muted);
}

.intro-bullets li {
  line-height: 1.72;
  word-break: keep-all;
}

.note-box {
  border-radius: 14px;
  padding: 14px 16px;
  border: 1px dashed rgba(96,165,250,.22);
  background: linear-gradient(180deg, rgba(79,156,255,.04), rgba(79,156,255,.02)), var(--surface-2);
  color: var(--muted);
}

.stepper {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 4px 0 22px;
}

.step-item { display: flex; flex-direction: column; align-items: center; min-width: 76px; }
.step-circle {
  width: 34px; height: 34px; border-radius: 999px; display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; border: 1px solid rgba(214, 226, 236, 0.55);
  background: rgba(255, 255, 255, 0.10); color: #D8E7F5;
}
.step-label { margin-top: 6px; font-size: 12px; color: #D8E7F5; font-weight: 750; text-align: center; }
.step-item.active .step-circle { background: var(--primary); border-color: var(--primary); color: #fff; }
.step-item.done .step-circle { background: var(--success); border-color: var(--success); color: #fff; }
.step-item.active .step-label, .step-item.done .step-label { color: #fff; }
.step-line { width: 42px; height: 2px; background: rgba(214, 226, 236, 0.45); border-radius: 999px; }
.step-line.done { background: var(--success); }

/* labels */
div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stCheckbox"] label,
div[data-testid="stSlider"] label,
div[data-testid="stTextInput"] [data-testid="stWidgetLabel"] *,
div[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] *,
div[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] *,
div[data-testid="stSlider"] [data-testid="stWidgetLabel"] *,
div[data-testid="stCaptionContainer"] p {
  color: var(--text) !important;
  font-weight: 720 !important;
  opacity: 1 !important;
  -webkit-text-fill-color: var(--text) !important;
}

/* input/select visible field */
div[data-testid="stTextInput"] input {
  background: var(--field-bg) !important;
  color: var(--text) !important;
  border: 1px solid var(--field-border) !important;
  border-radius: 14px !important;
  min-height: 48px !important;
  box-shadow: none !important;
  padding: 12px 14px !important;
  -webkit-text-fill-color: var(--text) !important;
  caret-color: var(--text) !important;
  opacity: 1 !important;
}

div[data-testid="stTextInput"] input:hover { background: var(--field-bg-hover) !important; border-color: var(--field-border-strong) !important; }
div[data-testid="stTextInput"] input:focus { border-color: var(--field-border-strong) !important; box-shadow: var(--field-shadow) !important; }
div[data-testid="stTextInput"] input::placeholder { color: var(--muted) !important; opacity: 1 !important; -webkit-text-fill-color: var(--muted) !important; }

div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
  background: var(--field-bg) !important;
  color: var(--text) !important;
  border: 1px solid var(--field-border) !important;
  border-radius: 14px !important;
  min-height: 48px !important;
  box-shadow: none !important;
  padding: 2px 10px !important;
}

div[data-testid="stSelectbox"] [data-baseweb="select"] > div:hover { background: var(--field-bg-hover) !important; border-color: var(--field-border-strong) !important; }
div[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within { border-color: var(--field-border-strong) !important; box-shadow: var(--field-shadow) !important; }

div[data-testid="stSelectbox"] [data-baseweb="select"] > div *,
div[data-testid="stSelectbox"] [data-baseweb="select"] span,
div[data-testid="stSelectbox"] [data-baseweb="select"] input,
div[data-testid="stSelectbox"] [data-baseweb="select"] div {
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  opacity: 1 !important;
}

div[data-testid="stSelectbox"] [data-baseweb="select"] svg,
div[data-testid="stSelectbox"] [data-baseweb="select"] path { fill: var(--text) !important; color: var(--text) !important; opacity: 1 !important; }

div[data-baseweb="popover"] { z-index: 99999 !important; }
div[data-baseweb="popover"] [data-baseweb="menu"], div[data-baseweb="popover"] [role="listbox"], div[data-baseweb="popover"] ul {
  background: var(--surface-2) !important;
  border: 1px solid var(--field-border) !important;
  border-radius: 14px !important;
  box-shadow: var(--shadow-md) !important;
  overflow: hidden !important;
  padding-top: 6px !important;
  padding-bottom: 6px !important;
}
div[data-baseweb="popover"] [role="option"], div[data-baseweb="popover"] li, div[data-baseweb="popover"] [data-baseweb="menu"] > div {
  background: transparent !important;
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  opacity: 1 !important;
  min-height: 42px !important;
}
div[data-baseweb="popover"] [role="option"] *, div[data-baseweb="popover"] li *, div[data-baseweb="popover"] [data-baseweb="menu"] > div * { color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; }
div[data-baseweb="popover"] [role="option"]:hover, div[data-baseweb="popover"] li:hover, div[data-baseweb="popover"] [data-baseweb="menu"] > div:hover { background: rgba(79,156,255,.12) !important; }

/* slider */
.stSlider [role="slider"] { background-color: var(--primary) !important; border: 2px solid #fff !important; box-shadow: 0 0 0 2px rgba(79,156,255,.28) !important; }
.stSlider * { color: var(--text) !important; }

/* checkbox */
div[data-testid="stCheckbox"] p, div[data-testid="stCheckbox"] span, div[data-testid="stCheckbox"] div { color: var(--text) !important; opacity: 1 !important; }
div[data-testid="stCheckbox"] svg { color: var(--primary) !important; }

/* alerts */
div[data-testid="stAlert"] { background: rgba(255,115,115,.14) !important; border: 1px solid rgba(255,115,115,.24) !important; border-radius: 14px !important; color: #ffd6d6 !important; }
div[data-testid="stAlert"] * { color: #ffd6d6 !important; }

/* buttons */
div[data-testid="stButton"] > button, .stDownloadButton > button {
  border-radius: 12px !important;
  min-height: 46px;
  border: 1px solid var(--line) !important;
  background: var(--surface-3) !important;
  color: var(--text) !important;
  font-weight: 760 !important;
  transition: all .18s ease;
  box-shadow: none !important;
}
div[data-testid="stButton"] > button:hover, .stDownloadButton > button:hover { border-color: var(--field-border-strong) !important; background: #163864 !important; }
div[data-testid="stButton"] > button[kind="primary"] { border-color: var(--field-border-strong) !important; background: linear-gradient(180deg, #1d4f8d, #163f73) !important; color: #fff !important; }
div[data-testid="stButton"] > button[kind="primary"] * { color: #fff !important; -webkit-text-fill-color: #fff !important; }
div[data-testid="stButton"] > button:disabled { opacity: .56 !important; cursor: not-allowed !important; }

.metric-grid { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; margin: 18px 0; }
.metric-card { background: var(--surface-2); border:1px solid var(--line); border-radius:18px; padding:16px; }
.metric-label { color: var(--muted); font-size:13px; font-weight:700; margin-bottom:8px; }
.metric-value { color: var(--text); font-size:28px; font-weight:900; line-height:1; }
.result-panel { background: var(--surface-2); border:1px solid var(--line); border-radius:18px; padding:18px; margin-bottom:14px; }
.score-bar { height: 12px; border-radius:999px; background: rgba(255,255,255,.08); border:1px solid var(--line); overflow:hidden; }
.score-fill { height:100%; background: linear-gradient(90deg, #3b82f6, #56e39a); border-radius:999px; }
.footer-note { color: var(--muted); font-size: 12px; line-height:1.6; text-align:center; margin-top:18px; }

@media (max-width: 720px) {
  .metric-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .block-container { padding-left: .85rem !important; padding-right: .85rem !important; }
  .card { padding: 18px; border-radius:18px; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# UI 구성
# ──────────────────────────────────────────────────────────────────────────────
def render_stepper(current_page: str) -> None:
    steps = [("intro", "동의"), ("info", "정보입력"), ("task", "과제수행"), ("result", "결과")]
    idx_map = {key: i for i, (key, _) in enumerate(steps)}
    current_idx = idx_map.get(current_page, 0)

    html_parts: List[str] = ["<div class='stepper'>"]
    for i, (_key, label) in enumerate(steps):
        state = "done" if i < current_idx else "active" if i == current_idx else "todo"
        html_parts.append(
            f"""
            <div class='step-item {state}'>
                <div class='step-circle'>{'✓' if state == 'done' else i + 1}</div>
                <div class='step-label'>{label}</div>
            </div>
            """
        )
        if i < len(steps) - 1:
            line_state = "done" if i < current_idx else "todo"
            html_parts.append(f"<div class='step-line {line_state}'></div>")
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_bullet_list(items: List[str]) -> str:
    return "<ul class='intro-bullets'>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def page_intro() -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper("intro")

    st.markdown(
        f"""
        <section class="card">
          <span class="badge">Cognitive Task Battery v2</span>
          <span class="badge">JS reaction timing</span>
          <h1 class="title-lg">{EXAM_TITLE}</h1>
          <p class="text" style="margin-top:10px;">{EXAM_SUBTITLE}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    bullets = [
        "본 검사는 현재의 주의집중, 처리속도, 작업기억, 억제통제 수행을 짧게 확인하기 위한 비진단적 인지 과제 패키지입니다.",
        "기존 상용 검사 원본을 복제하지 않고, 공개 인지실험 패러다임을 KIRBS+용 자체 과제로 재구성했습니다.",
        "이번 버전에서는 단순 PVT와 색상 의존 Stroop을 제외하고, Trail 연결 과제·2-back·Flanker·Go/No-Go로 구성했습니다.",
        "과제 수행부는 Streamlit 버튼이 아니라 브라우저 내부 JavaScript로 동작하여 반응시간을 performance.now() 기준으로 기록합니다.",
    ]
    privacy = [
        "검사 진행을 위해 이름, 성별, 연령, 거주지역, 실시기기 등 기본 정보를 입력받습니다. 휴대폰 번호와 이메일은 선택 항목입니다.",
        "수집된 응답과 반응시간 데이터는 비식별 처리 후 검사 고도화, 규준 구축, 서비스 개선, 데이터 분석 목적으로 활용될 수 있습니다.",
        "검사 결과는 의학적·임상적 진단이 아니며, 현재 컨디션과 실시 환경에 따라 달라질 수 있습니다.",
    ]

    st.markdown(
        f"""
        <section class="card soft">
          <h2 class="title-md">검사 구성</h2>
          {render_bullet_list(bullets)}
        </section>
        <section class="card soft">
          <h2 class="title-md">개인정보 및 데이터 활용 안내</h2>
          {render_bullet_list(privacy)}
        </section>
        """,
        unsafe_allow_html=True,
    )

    consent = st.checkbox(
        "위 안내를 확인했으며, 개인정보 수집·이용 및 검사 진행에 동의합니다.",
        value=bool(st.session_state.meta.get("consent")),
        key="consent_checkbox",
    )
    st.session_state.meta["consent"] = bool(consent)

    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("검사 시작", type="primary", disabled=not consent, use_container_width=True):
            ts = now_iso()
            st.session_state.meta["consent_ts"] = ts
            st.session_state.meta["started_ts"] = ts
            st.session_state.page = "info"
            rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def page_info() -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper("info")

    st.markdown(
        """
        <section class="card">
          <span class="badge">기본 정보 입력</span>
          <h1 class="title-lg">검사 대상자 정보</h1>
          <p class="text">검사 진행과 결과 저장을 위해 필요한 정보를 입력해 주세요.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    gender_options = [""] + GENDER_OPTIONS
    region_options = [""] + REGION_OPTIONS
    device_options = DEVICE_OPTIONS

    r1c1, r1c2 = st.columns(2, gap="medium")
    with r1c1:
        name = st.text_input("이름", value=st.session_state.examinee.get("name", ""), placeholder="이름을 입력해 주세요")
    with r1c2:
        current_gender = st.session_state.examinee.get("gender", "")
        gender = st.selectbox(
            "성별",
            options=gender_options,
            index=gender_options.index(current_gender) if current_gender in gender_options else 0,
            format_func=lambda x: "선택해 주세요" if x == "" else x,
        )

    r2c1, r2c2 = st.columns(2, gap="medium")
    with r2c1:
        age = st.text_input("연령", value=st.session_state.examinee.get("age", ""), placeholder="숫자만 입력해 주세요")
    with r2c2:
        current_region = st.session_state.examinee.get("region", "")
        region = st.selectbox(
            "거주지역",
            options=region_options,
            index=region_options.index(current_region) if current_region in region_options else 0,
            format_func=lambda x: "선택해 주세요" if x == "" else x,
        )

    r3c1, r3c2 = st.columns(2, gap="medium")
    with r3c1:
        current_device = st.session_state.examinee.get("device", "PC/노트북")
        device = st.selectbox(
            "실시기기",
            options=device_options,
            index=device_options.index(current_device) if current_device in device_options else 0,
        )
    with r3c2:
        caffeine = st.selectbox("최근 3시간 내 카페인 섭취", ["아니오", "예", "응답 안 함"], index=2)

    r4c1, r4c2 = st.columns(2, gap="medium")
    with r4c1:
        sleep_quality = st.slider("지난밤 수면의 질", 1, 5, int(st.session_state.context.get("sleep_quality_1to5", 3)))
    with r4c2:
        fatigue = st.slider("현재 피로감", 1, 5, int(st.session_state.context.get("fatigue_1to5", 3)))

    phone_input = st.text_input("휴대폰번호 (선택)", value=st.session_state.examinee.get("phone", ""), placeholder="010-0000-0000")
    email = st.text_input("이메일 (선택)", value=st.session_state.examinee.get("email", ""), placeholder="example@email.com")

    normalized_phone = normalize_phone(phone_input)
    st.session_state.examinee = {
        "name": name.strip(),
        "gender": gender.strip(),
        "age": age.strip(),
        "region": region.strip(),
        "device": device.strip(),
        "phone": normalized_phone,
        "email": email.strip(),
    }
    st.session_state.context = {
        "sleep_quality_1to5": sleep_quality,
        "fatigue_1to5": fatigue,
        "caffeine_last_3h": caffeine,
    }

    errors = [
        validate_name(name),
        validate_gender(gender),
        validate_age(age),
        validate_region(region),
        validate_phone(normalized_phone),
        validate_email(email),
    ]
    active_errors = [e for e in errors if e]

    if active_errors:
        st.warning(" / ".join(active_errors))

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("이전", use_container_width=True):
            st.session_state.page = "intro"
            rerun()
    with c2:
        if st.button("과제 시작", type="primary", disabled=bool(active_errors), use_container_width=True):
            st.session_state.page = "task"
            rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# JS 인지 과제 컴포넌트
# ──────────────────────────────────────────────────────────────────────────────
def cognitive_task_html() -> str:
    return dedent(
        r'''
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
:root{
  --bg:#071225; --surface:#0b1a33; --surface2:#0d2140; --surface3:#10284c;
  --text:#f8fbff; --muted:#c7d3e3; --line:rgba(148,163,184,.28);
  --primary:#4f9cff; --success:#56e39a; --warn:#ffb454; --danger:#ff7373;
  --shadow:0 18px 40px rgba(2,8,23,.32); --r:22px;
}
*{box-sizing:border-box}
html,body{margin:0;background:transparent;color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif;letter-spacing:-.01em}
.wrap{width:100%;max-width:960px;margin:0 auto;padding:0 0 28px}
.card{background:linear-gradient(180deg,rgba(255,255,255,.018),rgba(255,255,255,.006)),var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:0 8px 24px rgba(2,8,23,.28);padding:24px;margin-bottom:16px}
.top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
.badge{display:inline-flex;padding:6px 12px;border-radius:999px;background:rgba(79,156,255,.16);border:1px solid rgba(79,156,255,.25);color:#89beff;font-weight:800;font-size:12px;margin-bottom:10px}
.title{font-size:clamp(28px,4vw,38px);line-height:1.2;font-weight:900;margin:0 0 12px;color:#fff}
.sub{color:var(--muted);font-size:15px;line-height:1.72;margin:0}.blue{color:#89beff;font-weight:800}.small{font-size:13px;color:var(--muted);line-height:1.65}.progress-row{display:flex;justify-content:space-between;align-items:center;margin-top:16px;color:#fff;font-weight:800;font-size:14px}.meter{height:10px;background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:999px;overflow:hidden;margin-top:8px}.fill{height:100%;width:0;background:linear-gradient(90deg,#3b82f6,#60a5fa);transition:width .25s ease}.stim-card{min-height:360px;display:flex;align-items:center;justify-content:center;text-align:center;position:relative;overflow:hidden}.center{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px}.big{font-size:clamp(64px,10vw,96px);font-weight:950;line-height:1;color:#fff}.mid{font-size:clamp(32px,5vw,54px);font-weight:900;line-height:1.15;color:#fff}.guide{color:var(--muted);font-size:16px;line-height:1.7}.btnrow{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:12px}.btnrow.four{grid-template-columns:repeat(4,minmax(0,1fr))}button{border:1px solid var(--line);background:var(--surface3);color:#fff;border-radius:14px;min-height:54px;padding:12px 16px;font-size:16px;font-weight:850;cursor:pointer;transition:.15s ease;box-shadow:none}button:hover{border-color:rgba(120,173,255,.9);background:#163864}button.primary{border-color:rgba(120,173,255,.9);background:linear-gradient(180deg,#1d4f8d,#163f73);box-shadow:0 0 0 1px rgba(79,156,255,.25),0 8px 18px rgba(79,156,255,.16)}button.good{background:linear-gradient(180deg,#168a55,#0f6e44);border-color:rgba(86,227,154,.65)}button.warn{background:linear-gradient(180deg,#9a5b16,#74420f);border-color:rgba(255,180,84,.65)}button:disabled{opacity:.45;cursor:not-allowed}.trail-board{position:relative;width:100%;height:520px;background:linear-gradient(180deg,rgba(79,156,255,.05),rgba(79,156,255,.02)),#09172d;border:1px solid var(--line);border-radius:22px;overflow:hidden}.node{position:absolute;width:54px;height:54px;border-radius:999px;display:flex;align-items:center;justify-content:center;background:#10284c;border:2px solid rgba(120,173,255,.6);color:#fff;font-size:20px;font-weight:900;cursor:pointer;user-select:none;box-shadow:0 10px 24px rgba(2,8,23,.25)}.node:hover{background:#163864}.node.done{background:#168a55;border-color:#56e39a;color:#fff}.node.next{box-shadow:0 0 0 4px rgba(79,156,255,.22),0 10px 24px rgba(2,8,23,.25)}.node.wrong{animation:shake .25s ease;background:#7f1d1d;border-color:#ff7373}@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-4px)}75%{transform:translateX(4px)}}.kv{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.kv .box{background:var(--surface2);border:1px solid var(--line);border-radius:16px;padding:12px}.kv .label{font-size:12px;color:var(--muted);font-weight:800}.kv .value{font-size:24px;color:#fff;font-weight:950;margin-top:4px}.fix{font-size:88px;font-weight:900;color:#89beff}.flanker{font-size:clamp(58px,9vw,90px);font-weight:950;letter-spacing:.06em;color:#fff}.result-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.result-card{background:var(--surface2);border:1px solid var(--line);border-radius:18px;padding:16px}.bar{height:12px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid var(--line);overflow:hidden;margin-top:10px}.bar span{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#3b82f6,#56e39a)}.countdown{font-size:80px;font-weight:950;color:#fff}.hidden{display:none!important}.kbd{display:inline-flex;border:1px solid rgba(255,255,255,.25);border-bottom-width:3px;border-radius:8px;padding:2px 8px;font-size:13px;font-weight:900;color:#fff;background:rgba(255,255,255,.08)}@media(max-width:720px){.btnrow,.btnrow.four{grid-template-columns:1fr}.kv{grid-template-columns:repeat(2,minmax(0,1fr))}.trail-board{height:480px}.result-grid{grid-template-columns:1fr}.node{width:48px;height:48px;font-size:18px}.card{padding:18px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="card" id="headerCard">
    <div class="top">
      <div>
        <span class="badge" id="taskBadge">대기</span>
        <h1 class="title" id="taskTitle">인지 과제 준비</h1>
        <p class="sub" id="taskDesc">아래 안내를 확인한 뒤 시작해 주세요.</p>
      </div>
      <div class="small" id="taskHint">반응시간은 브라우저 내부 시간 기준으로 기록됩니다.</div>
    </div>
    <div class="progress-row"><span id="progressText">0 / 4</span><span id="progressPct">0%</span></div>
    <div class="meter"><div class="fill" id="progressFill"></div></div>
  </div>

  <div class="card stim-card" id="mainCard">
    <div class="center" id="mainArea">
      <div class="mid">검사 시작 전 안내</div>
      <div class="guide">가능하면 PC/노트북에서 실시하고, 과제 중에는 화면을 벗어나지 마세요.<br>각 과제는 연습문제 없이 바로 시작됩니다.</div>
      <div class="kv" style="width:100%;max-width:760px;margin-top:12px">
        <div class="box"><div class="label">과제 1</div><div class="value" style="font-size:18px">Trail</div></div>
        <div class="box"><div class="label">과제 2</div><div class="value" style="font-size:18px">2-back</div></div>
        <div class="box"><div class="label">과제 3</div><div class="value" style="font-size:18px">Flanker</div></div>
        <div class="box"><div class="label">과제 4</div><div class="value" style="font-size:18px">Go/No-Go</div></div>
      </div>
    </div>
  </div>

  <div id="actionArea" class="btnrow">
    <button class="primary" id="startBtn">전체 과제 시작</button>
    <button id="cancelBtn">처음 안내 다시 보기</button>
  </div>
</div>

<script>
const EXAM_NAME = "KIRBS_COGNITIVE_TASK_BATTERY";
const EXAM_VERSION = "streamlit_js_2.0";

const state = {
  taskIndex: 0,
  records: [],
  summaries: {},
  startedAt: new Date().toISOString(),
  seed: Math.floor(Math.random() * 1000000),
  current: null,
  locked: false,
};

const tasks = [
  {key:'trail', title:'Trail 연결 과제', sub:'시각 탐색 · 처리속도 · 전환능력', desc:'제시된 원을 순서대로 빠르게 클릭합니다. A는 숫자 순서, B는 숫자-글자 교대 순서입니다.'},
  {key:'nback', title:'2-back 작업기억 과제', sub:'작업기억 · 정보 업데이트', desc:'현재 글자가 2개 전에 나온 글자와 같으면 일치, 아니면 불일치를 선택합니다.'},
  {key:'flanker', title:'Flanker 화살표 과제', sub:'선택적 주의 · 반응 갈등 억제', desc:'가운데 화살표의 방향만 보고 왼쪽 또는 오른쪽을 선택합니다.'},
  {key:'gng', title:'Go/No-Go 과제', sub:'지속주의 · 반응 억제', desc:'GO 자극에는 빠르게 반응하고, NO-GO 자극에는 반응하지 않습니다.'}
];

const $ = (id) => document.getElementById(id);
function now(){ return performance.now(); }
function round(x,n=2){ return Math.round(x * Math.pow(10,n)) / Math.pow(10,n); }
function mean(a){ const b=a.filter(x=>Number.isFinite(x)); return b.length ? b.reduce((s,x)=>s+x,0)/b.length : null; }
function median(a){ const b=a.filter(x=>Number.isFinite(x)).sort((x,y)=>x-y); if(!b.length) return null; const m=Math.floor(b.length/2); return b.length%2?b[m]:(b[m-1]+b[m])/2; }
function clamp(x,a=20,b=80){ return Math.max(a, Math.min(b, x)); }
function pct(x){ return `${Math.round(x)}%`; }
function shuffle(arr){ for(let i=arr.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [arr[i],arr[j]]=[arr[j],arr[i]]; } return arr; }
function sample(arr){ return arr[Math.floor(Math.random()*arr.length)]; }

function setHeader(idx, trialText=''){
  const t = tasks[idx] || {title:'결과 산출', sub:'완료', desc:'결과를 정리하고 있습니다.'};
  $('taskBadge').textContent = idx < tasks.length ? `${idx+1} / ${tasks.length}` : '완료';
  $('taskTitle').textContent = t.title;
  $('taskDesc').innerHTML = `<span class="blue">${t.sub}</span><br>${t.desc}`;
  const completed = Math.min(idx, tasks.length);
  const p = completed / tasks.length * 100;
  $('progressText').textContent = trialText || `${completed} / ${tasks.length}`;
  $('progressPct').textContent = `${Math.round(p)}%`;
  $('progressFill').style.width = `${p}%`;
}
function setTrialProgress(idx, done, total){
  const pTotal = ((idx + (done/Math.max(total,1))) / tasks.length) * 100;
  $('progressText').textContent = `진행률 ${done}/${total}`;
  $('progressPct').textContent = `${Math.round(pTotal)}%`;
  $('progressFill').style.width = `${pTotal}%`;
}
function setMain(html){ $('mainArea').innerHTML = html; }
function setActions(html){ $('actionArea').innerHTML = html; }
function continueButton(label='다음 과제로 이동'){
  setActions(`<button class="primary" id="nextBtn">${label}</button>`);
  $('nextBtn').onclick = () => nextTask();
}
function taskCompleteCard(title, lines){
  setMain(`<div class="center"><div class="mid">${title}</div><div class="guide">${lines.join('<br>')}</div></div>`);
}

function startBattery(){
  state.taskIndex = 0; state.records = []; state.summaries = {}; state.startedAt = new Date().toISOString();
  runTrail();
}
function nextTask(){
  state.taskIndex += 1;
  if(state.taskIndex === 1) runNback();
  else if(state.taskIndex === 2) runFlanker();
  else if(state.taskIndex === 3) runGoNoGo();
  else finishBattery();
}

// ───────────────────────────────── Trail ─────────────────────────────────
function nonOverlapPositions(n, w, h, r){
  const pts=[]; let attempts=0;
  while(pts.length<n && attempts<5000){
    attempts++;
    const x = 35 + Math.random() * (w-70);
    const y = 35 + Math.random() * (h-70);
    let ok = true;
    for(const p of pts){ const d=Math.hypot(x-p.x,y-p.y); if(d<r){ ok=false; break; } }
    if(ok) pts.push({x,y});
  }
  while(pts.length<n) pts.push({x:35+Math.random()*(w-70), y:35+Math.random()*(h-70)});
  return pts;
}
function runTrail(){
  const idx = 0; setHeader(idx);
  const phases = [
    {name:'Trail-A', seq:['1','2','3','4','5','6','7','8','9','10','11','12']},
    {name:'Trail-B', seq:['1','가','2','나','3','다','4','라','5','마','6','바']}
  ];
  let phaseIdx = 0;
  const phaseResults = [];

  function startPhase(){
    const phase = phases[phaseIdx];
    let expected = 0, errors = 0;
    const clickRecords = [];
    setHeader(idx, `${phase.name} 준비`);
    setMain(`<div class="center"><div class="mid">${phase.name}</div><div class="guide">${phase.seq.join(' → ')} 순서로 원을 클릭하세요.</div></div>`);
    setActions(`<button class="primary" id="trailStart">${phase.name} 시작</button>`);
    $('trailStart').onclick = () => {
      const boardW = Math.min(900, $('mainCard').clientWidth - 48);
      const boardH = window.innerWidth < 720 ? 480 : 520;
      const positions = nonOverlapPositions(phase.seq.length, boardW, boardH, 82);
      const items = phase.seq.map((label,i)=>({label, i, ...positions[i]}));
      const startT = now(); let lastT = startT;
      $('mainArea').innerHTML = `<div class="trail-board" id="trailBoard" style="height:${boardH}px"></div>`;
      setActions(`<button id="trailInfo" disabled>다음 목표: ${phase.seq[0]}</button><button id="trailErr" disabled>오류 0회</button>`);
      const board = $('trailBoard');
      items.forEach(item=>{
        const d = document.createElement('div'); d.className='node'; d.textContent=item.label; d.style.left=(item.x-27)+'px'; d.style.top=(item.y-27)+'px'; d.dataset.index=item.i;
        if(item.i===0) d.classList.add('next');
        d.onclick = () => {
          const clickT = now();
          const correct = item.i === expected;
          if(correct){
            d.classList.remove('next'); d.classList.add('done');
            clickRecords.push({task:phase.name, target:item.label, order:item.i+1, rt_from_start_ms:round(clickT-startT), delta_ms:round(clickT-lastT), correct:true});
            lastT = clickT; expected++;
            if(expected < phase.seq.length){
              $('trailInfo').textContent = `다음 목표: ${phase.seq[expected]}`;
              const nextNode = board.querySelector(`[data-index="${expected}"]`); if(nextNode) nextNode.classList.add('next');
            } else {
              const duration = clickT - startT;
              phaseResults.push({phase:phase.name, duration_ms:round(duration), errors, click_records:clickRecords});
              setTrialProgress(idx, phaseIdx+1, phases.length);
              state.records.push(...clickRecords.map(r=>({task:'trail', phase:phase.name, target:r.target, order:r.order, rt_ms:r.rt_from_start_ms, delta_ms:r.delta_ms, correct:r.correct})));
              setTimeout(()=>{ phaseIdx++; phaseIdx<phases.length ? startPhase() : finishTrail(); }, 500);
            }
          } else {
            errors++; $('trailErr').textContent = `오류 ${errors}회`; d.classList.add('wrong'); setTimeout(()=>d.classList.remove('wrong'),260);
            state.records.push({task:'trail', phase:phase.name, target:item.label, expected:phase.seq[expected], rt_ms:round(clickT-startT), correct:false});
          }
        };
        board.appendChild(d);
      });
    };
  }
  function finishTrail(){
    const a = phaseResults.find(x=>x.phase==='Trail-A') || {}; const b = phaseResults.find(x=>x.phase==='Trail-B') || {};
    const errors = (a.errors||0)+(b.errors||0);
    const aSec = (a.duration_ms||0)/1000, bSec = (b.duration_ms||0)/1000;
    const scoreA = clamp(50 + ((32 - aSec)/32)*18 - (a.errors||0)*3);
    const scoreB = clamp(50 + ((48 - bSec)/48)*18 - (b.errors||0)*3);
    const score = clamp((scoreA+scoreB)/2 - errors*1.5);
    state.summaries.trail = {score:round(score,1), trail_a_sec:round(aSec,2), trail_b_sec:round(bSec,2), errors, criterion:'50점=내부 절대 기준점'};
    taskCompleteCard('Trail 과제 완료', [`Trail-A: ${round(aSec,2)}초`, `Trail-B: ${round(bSec,2)}초`, `오류: ${errors}회`, `환산점수: ${round(score,1)}점`]);
    continueButton();
  }
  startPhase();
}

// ───────────────────────────────── N-back ─────────────────────────────────
function makeNbackSeq(n=24){
  const letters = ['ㄱ','ㄴ','ㄷ','ㄹ','ㅁ','ㅂ','ㅅ','ㅇ'];
  const seq=[]; const targets = new Set();
  for(let i=0;i<n;i++){
    if(i>=2 && Math.random()<0.30){ seq.push(seq[i-2]); targets.add(i); }
    else {
      let cand = sample(letters); let guard=0;
      while(i>=2 && cand===seq[i-2] && guard<20){ cand=sample(letters); guard++; }
      seq.push(cand);
    }
  }
  return seq.map((letter,i)=>({letter, isTarget: i>=2 && letter===seq[i-2]}));
}
function runNback(){
  const idx=1; setHeader(idx);
  const trials = makeNbackSeq(24); let ti=0; const rec=[]; let onset=0;
  setMain(`<div class="center"><div class="mid">2-back</div><div class="guide">현재 글자가 <b>2개 전</b> 글자와 같으면 일치입니다.<br>처음 두 문항은 원칙상 불일치로 응답하세요.</div></div>`);
  setActions(`<button class="primary" id="nbackStart">2-back 시작</button>`);
  $('nbackStart').onclick = next;
  function next(){
    if(ti>=trials.length) return finish();
    const tr=trials[ti]; onset=now(); setTrialProgress(idx, ti, trials.length);
    setMain(`<div class="center"><div class="big">${tr.letter}</div><div class="guide">2개 전 글자와 비교해 응답하세요.</div></div>`);
    setActions(`<button id="nNo">불일치</button><button class="primary" id="nYes">일치</button>`);
    $('nNo').onclick=()=>respond(false); $('nYes').onclick=()=>respond(true);
  }
  function respond(ans){
    const rt=now()-onset; const tr=trials[ti]; const correct = ans===tr.isTarget;
    rec.push({task:'nback', trial:ti+1, stimulus:tr.letter, target:tr.isTarget, response:ans, correct, rt_ms:round(rt)});
    ti++; setTimeout(next,150);
  }
  function finish(){
    state.records.push(...rec);
    const acc = rec.filter(r=>r.correct).length / rec.length;
    const med = median(rec.map(r=>r.rt_ms));
    const targets = rec.filter(r=>r.target); const foils = rec.filter(r=>!r.target);
    const hit = targets.length ? targets.filter(r=>r.response===true).length/targets.length : 0;
    const fa = foils.length ? foils.filter(r=>r.response===true).length/foils.length : 0;
    const score = clamp(50 + (acc-.70)*45 + Math.max(0, (950-(med||950))/950)*5 - fa*10);
    state.summaries.nback = {score:round(score,1), accuracy:round(acc,3), median_rt_ms:round(med||0), hit_rate:round(hit,3), false_alarm_rate:round(fa,3), criterion:'50점=내부 절대 기준점'};
    taskCompleteCard('2-back 완료', [`정확률: ${pct(acc*100)}`, `중앙 반응시간: ${Math.round(med||0)}ms`, `환산점수: ${round(score,1)}점`]);
    continueButton();
  }
}

// ───────────────────────────────── Flanker ─────────────────────────────────
function makeFlankerTrials(n=24){
  const arr=[];
  for(let i=0;i<n;i++){
    const dir = Math.random()<.5 ? 'left' : 'right'; const congruent = i < n/2;
    const center = dir==='left' ? '←' : '→';
    const same = dir==='left' ? '←←' : '→→'; const diff = dir==='left' ? '→→' : '←←';
    arr.push({dir, condition:congruent?'congruent':'incongruent', stim:congruent ? `${same}${center}${same}` : `${diff}${center}${diff}`});
  }
  return shuffle(arr);
}
function runFlanker(){
  const idx=2; setHeader(idx);
  const trials = makeFlankerTrials(24); let ti=0; const rec=[]; let onset=0;
  setMain(`<div class="center"><div class="mid">Flanker</div><div class="guide">가운데 화살표 방향만 선택합니다.<br>키보드 사용 시 <span class="kbd">←</span> <span class="kbd">→</span> 방향키로도 응답할 수 있습니다.</div></div>`);
  setActions(`<button class="primary" id="flankerStart">Flanker 시작</button>`);
  $('flankerStart').onclick = next;
  function keyHandler(e){ if(e.key==='ArrowLeft') respond('left'); if(e.key==='ArrowRight') respond('right'); }
  function next(){
    if(ti>=trials.length) return finish();
    const tr=trials[ti]; onset=now(); state.locked=false; setTrialProgress(idx, ti, trials.length);
    setMain(`<div class="center"><div class="flanker">${tr.stim}</div><div class="guide">가운데 화살표의 방향은?</div></div>`);
    setActions(`<button id="fLeft">← 왼쪽</button><button class="primary" id="fRight">오른쪽 →</button>`);
    $('fLeft').onclick=()=>respond('left'); $('fRight').onclick=()=>respond('right');
  }
  function respond(ans){
    if(state.locked) return; state.locked=true;
    const tr=trials[ti]; const rt=now()-onset; const correct=ans===tr.dir;
    rec.push({task:'flanker', trial:ti+1, condition:tr.condition, stimulus:tr.stim, correct_response:tr.dir, response:ans, correct, rt_ms:round(rt)});
    ti++; setTimeout(next,180);
  }
  window.addEventListener('keydown', keyHandler);
  function finish(){
    window.removeEventListener('keydown', keyHandler); state.records.push(...rec);
    const acc=rec.filter(r=>r.correct).length/rec.length; const correct=rec.filter(r=>r.correct);
    const con=correct.filter(r=>r.condition==='congruent').map(r=>r.rt_ms); const incon=correct.filter(r=>r.condition==='incongruent').map(r=>r.rt_ms);
    const med=median(correct.map(r=>r.rt_ms)); const interference=(median(incon)||0)-(median(con)||0);
    const score=clamp(50+(acc-.82)*42-Math.max(0,interference-130)*.035-Math.max(0,(med||0)-850)*.01);
    state.summaries.flanker={score:round(score,1), accuracy:round(acc,3), median_rt_ms:round(med||0), interference_ms:round(interference), criterion:'50점=내부 절대 기준점'};
    taskCompleteCard('Flanker 완료', [`정확률: ${pct(acc*100)}`, `간섭 효과: ${Math.round(interference)}ms`, `환산점수: ${round(score,1)}점`]);
    continueButton();
  }
}

// ───────────────────────────────── Go/No-Go ─────────────────────────────────
function makeGngTrials(n=28){
  const arr=[]; const nogoN=Math.round(n*.28);
  for(let i=0;i<n;i++) arr.push({type:i<nogoN?'nogo':'go'});
  shuffle(arr);
  return arr.map(x=>({type:x.type, stim:x.type==='go'?'GO':'X'}));
}
function runGoNoGo(){
  const idx=3; setHeader(idx);
  const trials=makeGngTrials(28); let ti=0; const rec=[]; let onset=0; let responded=false; let timer=null;
  setMain(`<div class="center"><div class="mid">Go/No-Go</div><div class="guide"><b>GO</b>가 나오면 빠르게 반응하세요.<br><b>X</b>가 나오면 아무것도 누르지 마세요.<br>키보드 사용 시 <span class="kbd">Space</span>로도 반응할 수 있습니다.</div></div>`);
  setActions(`<button class="primary" id="gngStart">Go/No-Go 시작</button>`);
  $('gngStart').onclick = () => { setActions(`<button class="primary" id="gngResp">반응 / Space</button><button disabled>NO-GO는 누르지 않기</button>`); $('gngResp').onclick=()=>respond(); next(); };
  function keyHandler(e){ if(e.code==='Space'){ e.preventDefault(); respond(); } }
  window.addEventListener('keydown', keyHandler);
  function next(){
    if(ti>=trials.length) return finish();
    const tr=trials[ti]; responded=false; setTrialProgress(idx, ti, trials.length);
    setMain(`<div class="center"><div class="fix">+</div><div class="guide">준비</div></div>`);
    setTimeout(()=>{
      onset=now(); const color=tr.type==='go'?'#56e39a':'#ff7373';
      setMain(`<div class="center"><div class="big" style="color:${color}">${tr.stim}</div><div class="guide">${tr.type==='go'?'지금 반응':'누르지 마세요'}</div></div>`);
      timer=setTimeout(()=>{
        if(!responded){
          const correct = tr.type==='nogo';
          rec.push({task:'gng', trial:ti+1, condition:tr.type, stimulus:tr.stim, response:null, correct, rt_ms:null});
          ti++; setTimeout(next,180);
        }
      },900);
    },300);
  }
  function respond(){
    if(ti>=trials.length || responded) return;
    responded=true; if(timer) clearTimeout(timer);
    const tr=trials[ti]; const rt=now()-onset; const correct=tr.type==='go';
    rec.push({task:'gng', trial:ti+1, condition:tr.type, stimulus:tr.stim, response:'press', correct, rt_ms:round(rt)});
    ti++; setTimeout(next,180);
  }
  function finish(){
    window.removeEventListener('keydown', keyHandler); if(timer) clearTimeout(timer); state.records.push(...rec);
    const go=rec.filter(r=>r.condition==='go'), nogo=rec.filter(r=>r.condition==='nogo');
    const goHit=go.length?go.filter(r=>r.response==='press').length/go.length:0;
    const omission=1-goHit; const commission=nogo.length?nogo.filter(r=>r.response==='press').length/nogo.length:0;
    const acc=rec.filter(r=>r.correct).length/rec.length; const med=median(go.filter(r=>r.correct).map(r=>r.rt_ms));
    const score=clamp(50+(acc-.86)*45-commission*22-omission*16-Math.max(0,(med||0)-650)*.01);
    state.summaries.gng={score:round(score,1), accuracy:round(acc,3), go_hit_rate:round(goHit,3), commission_error_rate:round(commission,3), omission_error_rate:round(omission,3), median_go_rt_ms:round(med||0), criterion:'50점=내부 절대 기준점'};
    taskCompleteCard('Go/No-Go 완료', [`전체 정확률: ${pct(acc*100)}`, `NO-GO 오반응률: ${pct(commission*100)}`, `환산점수: ${round(score,1)}점`]);
    continueButton('결과 정리하기');
  }
}

// ───────────────────────────────── Finish ─────────────────────────────────
function finishBattery(){
  setHeader(4);
  const s=state.summaries;
  const domains={
    processing_speed: round(((s.trail?.score||50)+(s.flanker?.score||50))/2,1),
    working_memory: s.nback?.score || null,
    inhibition_control: round(((s.flanker?.score||50)+(s.gng?.score||50))/2,1),
    sustained_attention: s.gng?.score || null
  };
  const vals=Object.values(domains).filter(v=>v!==null && Number.isFinite(v));
  const overall=round(vals.reduce((a,b)=>a+b,0)/vals.length,1);
  const payload={
    exam_name:EXAM_NAME,
    exam_version:EXAM_VERSION,
    started_at:state.startedAt,
    finished_at:new Date().toISOString(),
    scoring_note:'criterion-referenced transformed score; 50 = internal criterion point, not population percentile',
    summaries:s,
    domains,
    overall_score:overall,
    records:state.records
  };
  setMain(`<div class="center"><div class="mid">과제 완료</div><div class="guide">결과를 Streamlit으로 전달합니다.<br>잠시만 기다려 주세요.</div></div>`);
  setActions(`<button class="primary" disabled>결과 전달 중</button>`);
  const json=JSON.stringify(payload);
  const b64=btoa(unescape(encodeURIComponent(json))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  setTimeout(()=>{
    try{
      const url=new URL(window.parent.location.href);
      url.searchParams.set('cog_done','1');
      url.searchParams.set('cog_data',b64);
      window.parent.location.href=url.toString();
    }catch(e){
      setMain(`<div class="center"><div class="mid">전달 오류</div><div class="guide">결과 전달에 실패했습니다. 새로고침 후 다시 시도해 주세요.<br>${e}</div></div>`);
    }
  },500);
}

$('startBtn').onclick = startBattery;
$('cancelBtn').onclick = () => window.location.reload();
setHeader(0);
</script>
</body>
</html>
        '''
    )


def page_task() -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper("task")
    st.markdown(
        """
        <section class="card">
          <span class="badge">JS 기반 과제 실행부</span>
          <h1 class="title-lg">과제 수행</h1>
          <p class="text">아래 과제 영역 안에서 모든 인지 과제가 진행됩니다. 반응시간은 Streamlit 버튼 클릭 시간이 아니라 브라우저 내부 JavaScript 시간 기준으로 기록됩니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    components.html(cognitive_task_html(), height=1120, scrolling=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# 결과/저장
# ──────────────────────────────────────────────────────────────────────────────
def build_exam_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    examinee = st.session_state.examinee or {}
    context = st.session_state.context or {}
    meta = st.session_state.meta or {}

    consent_col = {
        "consent": meta.get("consent", False),
        "consent_ts": meta.get("consent_ts", ""),
        "started_ts": meta.get("started_ts", ""),
        "submitted_ts": meta.get("submitted_ts", "") or now_iso(),
        "respondent_id": meta.get("respondent_id", ""),
        "version": EXAM_VERSION,
    }

    examinee_col = {
        "name": examinee.get("name", ""),
        "gender": examinee.get("gender", ""),
        "age": examinee.get("age", ""),
        "region": examinee.get("region", ""),
        "device": examinee.get("device", ""),
        "phone": examinee.get("phone", ""),
        "email": examinee.get("email", ""),
        "sleep_quality_1to5": context.get("sleep_quality_1to5", ""),
        "fatigue_1to5": context.get("fatigue_1to5", ""),
        "caffeine_last_3h": context.get("caffeine_last_3h", ""),
    }

    summaries = payload.get("summaries", {}) or {}
    domains = payload.get("domains", {}) or {}
    records = payload.get("records", []) or []

    answers_col = {
        "task_records_b64": b64_json(records),
        "task_summaries_b64": b64_json(summaries),
    }

    result_col = {
        "overall_score": payload.get("overall_score", ""),
        "overall_label": criterion_label(payload.get("overall_score")),
        "processing_speed": domains.get("processing_speed", ""),
        "working_memory": domains.get("working_memory", ""),
        "inhibition_control": domains.get("inhibition_control", ""),
        "sustained_attention": domains.get("sustained_attention", ""),
        "trail_score": (summaries.get("trail", {}) or {}).get("score", ""),
        "nback_score": (summaries.get("nback", {}) or {}).get("score", ""),
        "flanker_score": (summaries.get("flanker", {}) or {}).get("score", ""),
        "gng_score": (summaries.get("gng", {}) or {}).get("score", ""),
        "scoring_note": payload.get("scoring_note", ""),
        "raw_trial_count": len(records),
    }

    return {
        "exam_name": EXAM_NAME,
        "consent_col": dict_to_kv_csv(consent_col),
        "examinee_col": dict_to_kv_csv(examinee_col),
        "answers_col": dict_to_kv_csv(answers_col),
        "result_col": dict_to_kv_csv(result_col),
    }


def render_score_line(label: str, score: Optional[float]) -> None:
    if score is None:
        width = 0
        score_text = "-"
    else:
        width = max(0, min(100, (score / 80) * 100))
        score_text = f"{score:.1f}점 · {criterion_label(score)}"
    st.markdown(
        f"""
        <div class="result-panel">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;">
            <div style="font-weight:850;color:#fff;">{label}</div>
            <div style="font-weight:850;color:#89beff;">{score_text}</div>
          </div>
          <div class="score-bar"><div class="score-fill" style="width:{width:.1f}%;"></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_result(dev_mode: bool = False) -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper("result")

    payload = st.session_state.cog_payload
    if not payload:
        st.warning("검사 결과 데이터가 없습니다. 과제를 다시 진행해 주세요.")
        if st.button("과제로 이동", type="primary", use_container_width=True):
            st.session_state.page = "task"
            rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    overall = payload.get("overall_score")
    domains = payload.get("domains", {}) or {}
    summaries = payload.get("summaries", {}) or {}
    records = payload.get("records", []) or []
    st.session_state.meta["submitted_ts"] = st.session_state.meta.get("submitted_ts") or now_iso()

    exam_data = build_exam_data(payload)
    auto_db_insert(exam_data)

    st.markdown(
        f"""
        <section class="card">
          <span class="badge">결과</span>
          <h1 class="title-lg">인지 기능 검사 결과</h1>
          <p class="text">본 점수는 현재 데이터가 없는 초기 버전이므로 상대평가/백분위가 아니라 <b>절대 기준 환산점수</b>입니다. 50점은 인구 평균이 아니라 내부 기준점입니다.</p>
        </section>
        <div class="metric-grid">
          <div class="metric-card"><div class="metric-label">종합</div><div class="metric-value">{overall if overall is not None else '-'} </div></div>
          <div class="metric-card"><div class="metric-label">판정</div><div class="metric-value" style="font-size:24px">{criterion_label(overall)}</div></div>
          <div class="metric-card"><div class="metric-label">기록 수</div><div class="metric-value">{len(records)}</div></div>
          <div class="metric-card"><div class="metric-label">기준점</div><div class="metric-value">50</div></div>
        </div>
        <section class="card soft">
          <h2 class="title-md">요약 해석</h2>
          <p class="text">{score_desc(overall)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<section class='card'><h2 class='title-md'>영역별 환산점수</h2>", unsafe_allow_html=True)
    render_score_line("처리속도 / 시각탐색", domains.get("processing_speed"))
    render_score_line("작업기억", domains.get("working_memory"))
    render_score_line("억제통제", domains.get("inhibition_control"))
    render_score_line("지속주의", domains.get("sustained_attention"))
    st.markdown("</section>", unsafe_allow_html=True)

    st.markdown("<section class='card'><h2 class='title-md'>과제별 세부 지표</h2>", unsafe_allow_html=True)
    for key, title in [("trail", "Trail 연결"), ("nback", "2-back"), ("flanker", "Flanker"), ("gng", "Go/No-Go")]:
        s = summaries.get(key, {}) or {}
        st.markdown(f"<div class='result-panel'><b style='color:#fff'>{title}</b><br><pre style='white-space:pre-wrap;color:#c7d3e3;font-size:13px;margin-bottom:0'>{json.dumps(s, ensure_ascii=False, indent=2)}</pre></div>", unsafe_allow_html=True)
    st.markdown("</section>", unsafe_allow_html=True)

    json_payload = json.dumps({"exam_data": exam_data, "internal_payload": payload}, ensure_ascii=False, indent=2)
    st.download_button(
        "결과 JSON 다운로드",
        data=json_payload.encode("utf-8"),
        file_name=f"{EXAM_NAME}_{st.session_state.meta.get('respondent_id','')}.json",
        mime="application/json",
        use_container_width=True,
    )

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("새 검사 시작", type="primary", use_container_width=True):
            reset_all()
            rerun()
    with c2:
        if st.button("닫기", use_container_width=True):
            st.session_state.close_attempted = True
            components.html("<script>try{window.close();}catch(e){}</script>", height=0)
            rerun()

    if st.session_state.close_attempted:
        st.warning("탭이 자동으로 닫히지 않는 경우, 사용자가 직접 탭을 닫아주세요.")

    if dev_mode:
        st.caption("개발 모드 DB exam_data")
        st.json(exam_data, expanded=False)
        st.caption("개발 모드 internal payload")
        st.json(payload, expanded=False)

    st.markdown("<div class='footer-note'>※ 본 검사는 진단 도구가 아니며, 초기 버전의 절대 기준 환산점수는 향후 표본 데이터 축적 후 보정되어야 합니다.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# 데이터 저장 분기 + DB 연동 전용 블록
# ──────────────────────────────────────────────────────────────────────────────
def _is_db_insert_enabled() -> bool:
    raw = os.getenv("ENABLE_DB_INSERT", "false")
    return str(raw).strip().lower() == "true"


ENABLE_DB_INSERT = _is_db_insert_enabled()

if ENABLE_DB_INSERT:
    from utils.database import Database


def safe_db_insert(exam_data: Dict[str, Any]) -> bool:
    if not ENABLE_DB_INSERT:
        return False
    try:
        db = Database()
        db.insert(exam_data)
        return True
    except Exception as e:
        print(f"[DB INSERT ERROR] {e}")
        return False


def auto_db_insert(exam_data: Dict[str, Any]) -> None:
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


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    inject_css()
    init_state()

    query_payload = decode_payload_from_query()
    if query_payload is not None:
        st.session_state.cog_payload = query_payload
        st.session_state.page = "result"

    dev_mode = get_query_value("dev", "0") == "1"

    if st.session_state.page == "intro":
        page_intro()
    elif st.session_state.page == "info":
        if not st.session_state.meta.get("consent"):
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            rerun()
        page_info()
    elif st.session_state.page == "task":
        if not st.session_state.meta.get("consent"):
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            rerun()
        if not st.session_state.examinee.get("name", "").strip():
            st.session_state.page = "info"
            rerun()
        page_task()
    elif st.session_state.page == "result":
        page_result(dev_mode=dev_mode)
    else:
        st.session_state.page = "intro"
        rerun()


if __name__ == "__main__":
    main()
