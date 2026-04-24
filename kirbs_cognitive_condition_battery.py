# -*- coding: utf-8 -*-
"""
KIRBS+ 무료 인지 기능 검사 패키지 v4
- 단일 Streamlit .py 파일
- 외부 .streamlit/config.toml / 정적 파일 불필요
- 과제 실행부는 iframe 내부 JavaScript로 수행
- 반응시간은 브라우저 performance.now() 기준 기록
- 구성: Trail 연결 과제, 2-back, 시선 방향 과제, Flanker, Go/No-Go

실행:
  Windows CMD: set ENABLE_DB_INSERT=false && streamlit run kirbs_cognitive_task_battery_v4_single.py
  macOS/Linux: ENABLE_DB_INSERT=false streamlit run kirbs_cognitive_task_battery_v4_single.py
"""

from __future__ import annotations

import base64
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from textwrap import dedent
from typing import Any, Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components


# ──────────────────────────────────────────────────────────────────────────────
# 기본 설정
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
EXAM_VERSION = "streamlit_js_4.0"

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
            return str(value[0]) if value else default
        return str(value)
    except Exception:
        try:
            params = st.experimental_get_query_params()
            value = params.get(key, [default])
            return str(value[0]) if value else default
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
        return "현재 과제 수행은 내부 기준점에 가까운 범위입니다. 다만 피로, 긴장, 기기 환경에 따라 변동될 수 있습니다."
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
  --content-max-width: 960px;
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
  --danger: #ff7373;
  --field-bg: #10284c;
  --field-bg-hover: #13315d;
  --field-border: rgba(96, 165, 250, 0.52);
  --field-border-strong: rgba(120, 173, 255, 0.92);
  --field-shadow: 0 0 0 3px rgba(79, 156, 255, 0.16);
  --radius-xl: 22px;
  --shadow-sm: 0 8px 24px rgba(2, 8, 23, 0.28);
  --shadow-md: 0 18px 40px rgba(2, 8, 23, 0.38);
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
  background: linear-gradient(180deg, #06101f 0%, #071225 100%) !important;
  color: var(--text) !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif !important;
}

.block-container {
  max-width: var(--content-max-width) !important;
  padding-top: 0.85rem !important;
  padding-bottom: 3rem !important;
}

header[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer, div[data-testid="stDecoration"] {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
}

.page-wrap {
  width: min(100%, var(--content-max-width));
  margin: 0 auto;
}

.card {
  background: linear-gradient(180deg, rgba(255,255,255,.018), rgba(255,255,255,.006)), var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  padding: 22px;
  margin-bottom: 16px;
}
.card.soft { background: linear-gradient(180deg, rgba(255,255,255,.012), rgba(255,255,255,.004)), var(--surface-2); }
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
.title-lg { font-size: clamp(26px, 3vw, 34px) !important; font-weight: 900 !important; line-height: 1.28 !important; color: var(--text) !important; margin: 6px 0 0 !important; }
.title-md { font-size: clamp(18px, 2.2vw, 21px) !important; font-weight: 780 !important; line-height: 1.35 !important; color: var(--text) !important; margin: 0 0 8px !important; }
.text, .muted, .card p, .card li { color: var(--muted) !important; line-height: 1.72 !important; font-size: 15px !important; opacity: 1 !important; }
.intro-bullets { margin: 0; padding-left: 1.15rem; display: grid; gap: .68rem; color: var(--muted); }
.intro-bullets li { line-height: 1.72; word-break: keep-all; }
.stepper { display: flex; align-items: center; justify-content: center; gap: 8px; flex-wrap: wrap; margin: 4px 0 22px; }
.step-item { display: flex; flex-direction: column; align-items: center; min-width: 76px; }
.step-circle { width: 34px; height: 34px; border-radius: 999px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 14px; border: 1px solid rgba(214, 226, 236, 0.55); background: rgba(255, 255, 255, 0.10); color: #D8E7F5; }
.step-label { margin-top: 6px; font-size: 12px; color: #D8E7F5; font-weight: 750; text-align: center; }
.step-item.active .step-circle { background: var(--primary); border-color: var(--primary); color: #fff; }
.step-item.done .step-circle { background: var(--success); border-color: var(--success); color: #fff; }
.step-item.active .step-label, .step-item.done .step-label { color: #fff; }
.step-line { width: 42px; height: 2px; background: rgba(214, 226, 236, 0.45); border-radius: 999px; }
.step-line.done { background: var(--success); }

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
div[data-baseweb="popover"] [data-baseweb="menu"], div[data-baseweb="popover"] [role="listbox"], div[data-baseweb="popover"] ul { background: var(--surface-2) !important; border: 1px solid var(--field-border) !important; border-radius: 14px !important; box-shadow: var(--shadow-md) !important; overflow: hidden !important; padding-top: 6px !important; padding-bottom: 6px !important; }
div[data-baseweb="popover"] [role="option"], div[data-baseweb="popover"] li, div[data-baseweb="popover"] [data-baseweb="menu"] > div { background: transparent !important; color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; opacity: 1 !important; min-height: 42px !important; }
div[data-baseweb="popover"] [role="option"] *, div[data-baseweb="popover"] li *, div[data-baseweb="popover"] [data-baseweb="menu"] > div * { color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; }
div[data-baseweb="popover"] [role="option"]:hover, div[data-baseweb="popover"] li:hover, div[data-baseweb="popover"] [data-baseweb="menu"] > div:hover { background: rgba(79,156,255,.12) !important; }

.stSlider [role="slider"] { background-color: var(--primary) !important; border: 2px solid #fff !important; box-shadow: 0 0 0 2px rgba(79,156,255,.28) !important; }
.stSlider * { color: var(--text) !important; }
div[data-testid="stCheckbox"] p, div[data-testid="stCheckbox"] span, div[data-testid="stCheckbox"] div { color: var(--text) !important; opacity: 1 !important; }
div[data-testid="stCheckbox"] svg { color: var(--primary) !important; }
div[data-testid="stAlert"] { background: rgba(255,115,115,.14) !important; border: 1px solid rgba(255,115,115,.24) !important; border-radius: 14px !important; color: #ffd6d6 !important; }
div[data-testid="stAlert"] * { color: #ffd6d6 !important; }

div[data-testid="stButton"] > button, .stDownloadButton > button { border-radius: 12px !important; min-height: 46px; border: 1px solid var(--line) !important; background: var(--surface-3) !important; color: var(--text) !important; font-weight: 760 !important; transition: all .18s ease; box-shadow: none !important; }
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
# 일반 UI
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
          <span class="badge">Cognitive Task Battery v3</span>
          <span class="badge">Browser reaction timing</span>
          <h1 class="title-lg">{EXAM_TITLE}</h1>
          <p class="text" style="margin-top:10px;">{EXAM_SUBTITLE}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    bullets = [
        "본 검사는 현재의 주의집중, 처리속도, 작업기억, 억제통제 수행을 짧게 확인하기 위한 비진단적 인지 과제 패키지입니다.",
        "색상 표시 안정성이 중요한 Stroop과 단순 반응시간 중심 PVT는 제외하고, 일반 사용자에게 체감이 더 분명한 Trail 연결 과제·2-back·Flanker·Go/No-Go로 구성했습니다.",
        "과제 수행부는 Streamlit 버튼이 아니라 브라우저 내부 JavaScript로 동작하며, 반응시간은 performance.now() 기준으로 기록됩니다.",
        "현재 결과는 규준 기반 상대평가가 아니라 50점을 내부 기준점으로 둔 절대 기준 환산점수입니다.",
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
# JS 과제 실행부
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
  --text:#f8fbff; --muted:#c7d3e3; --line:rgba(148,163,184,.30);
  --primary:#4f9cff; --success:#56e39a; --warn:#ffb454; --danger:#ff7373;
  --shadow:0 18px 40px rgba(2,8,23,.32); --r:22px;
}
*{box-sizing:border-box}
html,body{margin:0;background:transparent;color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif;letter-spacing:-.01em}
.wrap{width:100%;max-width:960px;margin:0 auto;padding:0 0 28px}
.panel{background:linear-gradient(180deg,rgba(255,255,255,.018),rgba(255,255,255,.006)),var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:0 8px 24px rgba(2,8,23,.28);padding:24px;margin-bottom:16px}
.top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
.badge{display:inline-flex;padding:6px 12px;border-radius:999px;background:rgba(79,156,255,.16);border:1px solid rgba(79,156,255,.25);color:#89beff;font-weight:800;font-size:12px;margin-bottom:10px}
.title{font-size:clamp(26px,4vw,38px);line-height:1.2;font-weight:900;margin:0 0 12px;color:#fff}
.sub{color:var(--muted);font-size:15px;line-height:1.72;margin:0}.blue{color:#89beff;font-weight:800}.small{font-size:13px;color:var(--muted);line-height:1.65}.progress-row{display:flex;justify-content:space-between;align-items:center;margin-top:16px;color:#fff;font-weight:800;font-size:14px}.meter{height:10px;background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:999px;overflow:hidden;margin-top:8px}.fill{height:100%;width:0;background:linear-gradient(90deg,#3b82f6,#60a5fa);transition:width .25s ease}
.work{min-height:540px;display:flex;align-items:stretch;justify-content:center;text-align:center;position:relative;overflow:hidden}.center{width:100%;min-height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px}.big{font-size:clamp(64px,10vw,96px);font-weight:950;line-height:1;color:#fff}.mid{font-size:clamp(30px,5vw,54px);font-weight:900;line-height:1.15;color:#fff}.guide{color:var(--muted);font-size:16px;line-height:1.7}.actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.actions.one{grid-template-columns:1fr}.actions.four{grid-template-columns:repeat(4,minmax(0,1fr))}button{border:1px solid var(--line);background:var(--surface3);color:#fff;border-radius:14px;min-height:54px;padding:12px 16px;font-size:16px;font-weight:850;cursor:pointer;transition:.15s ease;box-shadow:none}button:hover{border-color:rgba(120,173,255,.9);background:#163864}button.primary{border-color:rgba(120,173,255,.9);background:linear-gradient(180deg,#1d4f8d,#163f73);box-shadow:0 0 0 1px rgba(79,156,255,.25),0 8px 18px rgba(79,156,255,.16)}button.good{background:linear-gradient(180deg,#168a55,#0f6e44);border-color:rgba(86,227,154,.65)}button.danger{background:linear-gradient(180deg,#8b1d1d,#6e1717);border-color:rgba(255,115,115,.65)}button:disabled{opacity:.48;cursor:not-allowed}.grid-board{width:100%;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;align-content:center;padding:8px}.node{height:86px;border-radius:20px;background:#10284c;border:2px solid rgba(120,173,255,.6);color:#fff;font-size:24px;font-weight:950;display:flex;align-items:center;justify-content:center;user-select:none;cursor:pointer;box-shadow:0 10px 24px rgba(2,8,23,.24)}.node:hover{background:#163864}.node.done{background:#168a55;border-color:#56e39a}.node.next{box-shadow:0 0 0 4px rgba(79,156,255,.28),0 10px 24px rgba(2,8,23,.24)}.node.wrong{animation:shake .25s ease;background:#7f1d1d;border-color:#ff7373}@keyframes shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-4px)}75%{transform:translateX(4px)}}.kv{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;width:100%;max-width:800px}.kv .box{background:var(--surface2);border:1px solid var(--line);border-radius:16px;padding:12px}.kv .label{font-size:12px;color:var(--muted);font-weight:800}.kv .value{font-size:22px;color:#fff;font-weight:950;margin-top:4px}.fix{font-size:88px;font-weight:900;color:#89beff}.flanker{font-size:clamp(58px,9vw,90px);font-weight:950;letter-spacing:.06em;color:#fff}.kbd{display:inline-flex;border:1px solid rgba(255,255,255,.25);border-bottom-width:3px;border-radius:8px;padding:2px 8px;font-size:13px;font-weight:900;color:#fff;background:rgba(255,255,255,.08)}.error{background:rgba(255,115,115,.12);border:1px solid rgba(255,115,115,.4);border-radius:18px;padding:18px;color:#ffd6d6;text-align:left;white-space:pre-wrap;line-height:1.5}.trail-status{width:100%;display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.status-box{background:var(--surface2);border:1px solid var(--line);border-radius:16px;padding:12px;font-weight:900;color:#fff}.status-box span{color:#89beff}.hud{width:100%;display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}.hud-pill{border:1px solid rgba(79,156,255,.28);background:rgba(79,156,255,.12);color:#dbeafe;border-radius:999px;padding:7px 12px;font-size:13px;font-weight:900}.hud-pill.good{border-color:rgba(86,227,154,.35);background:rgba(86,227,154,.12);color:#c8ffe5}.gaze-stage{width:100%;display:grid;grid-template-columns:1fr;place-items:center;gap:18px}.face{position:relative;width:210px;height:210px;border-radius:50%;background:radial-gradient(circle at 35% 28%,#fff7d6 0%,#ffd166 34%,#f59e0b 100%);border:6px solid rgba(255,255,255,.16);box-shadow:0 24px 44px rgba(2,8,23,.34), inset -12px -18px 32px rgba(120,53,15,.25), inset 10px 14px 30px rgba(255,255,255,.28)}.eye{position:absolute;top:74px;width:52px;height:40px;border-radius:50%;background:#fff;border:2px solid rgba(15,23,42,.18);overflow:hidden}.eye.left{left:48px}.eye.right{right:48px}.pupil{position:absolute;width:18px;height:18px;border-radius:50%;background:#0f172a;left:17px;top:11px;transition:transform .08s ease}.face.gaze-left .pupil{transform:translateX(-13px)}.face.gaze-right .pupil{transform:translateX(13px)}.face.gaze-up .pupil{transform:translateY(-10px)}.face.gaze-down .pupil{transform:translateY(10px)}.mouth{position:absolute;left:74px;top:142px;width:62px;height:28px;border-bottom:6px solid rgba(88,28,13,.7);border-radius:0 0 999px 999px}.gaze-pad{width:min(100%,460px);display:grid;grid-template-columns:repeat(3,1fr);grid-template-areas:". up ." "left center right" ". down .";gap:10px}.gaze-pad .up{grid-area:up}.gaze-pad .left{grid-area:left}.gaze-pad .center{grid-area:center}.gaze-pad .right{grid-area:right}.gaze-pad .down{grid-area:down}.gaze-pad button{min-height:64px;font-size:20px}.result-link{display:inline-flex;align-items:center;justify-content:center;margin-top:16px;min-height:58px;padding:0 24px;border-radius:16px;background:linear-gradient(180deg,#1d4f8d,#163f73);border:1px solid rgba(120,173,255,.9);color:#fff!important;text-decoration:none;font-size:18px;font-weight:950;box-shadow:0 0 0 1px rgba(79,156,255,.25),0 8px 18px rgba(79,156,255,.16)}.result-link:hover{background:#1d4f8d}.hidden{display:none!important}@media(max-width:720px){.actions,.actions.four{grid-template-columns:1fr}.kv{grid-template-columns:repeat(2,minmax(0,1fr))}.grid-board{grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.node{height:70px;font-size:20px}.work{min-height:520px}.panel{padding:18px}}
</style>
</head>
<body>
<div id="app" class="wrap"></div>
<script>
(function(){
'use strict';
window.addEventListener('error', function(e){ showFatal('JavaScript 오류가 발생했습니다.\n' + e.message + '\n' + (e.filename||'') + ':' + (e.lineno||'')); });
window.addEventListener('unhandledrejection', function(e){ showFatal('Promise 오류가 발생했습니다.\n' + (e.reason && e.reason.stack ? e.reason.stack : e.reason)); });

const EXAM_NAME = 'KIRBS_COGNITIVE_TASK_BATTERY';
const EXAM_VERSION = 'streamlit_js_4.0';
const app = document.getElementById('app');
const tasks = [
  {key:'trail', title:'Trail 연결 과제', sub:'시각 탐색 · 처리속도 · 전환능력', desc:'화면에 흩어진 항목을 정해진 순서대로 빠르게 선택합니다.'},
  {key:'nback', title:'2-back 작업기억 과제', sub:'작업기억 · 정보 업데이트', desc:'현재 글자가 2개 전에 나온 글자와 같은지 판단합니다.'},
  {key:'gaze', title:'시선 방향 과제', sub:'사회적 주의 · 방향 판단 · 반응속도', desc:'얼굴의 눈동자가 바라보는 방향을 빠르게 선택합니다.'},
  {key:'flanker', title:'Flanker 화살표 과제', sub:'선택적 주의 · 반응 갈등 억제', desc:'방해 화살표를 무시하고 가운데 화살표 방향만 판단합니다.'},
  {key:'gng', title:'Go/No-Go 과제', sub:'지속주의 · 반응 억제', desc:'GO에는 반응하고, X에는 반응을 억제합니다.'}
];
const state = { taskIndex:0, records:[], summaries:{}, startedAt:new Date().toISOString(), locked:false };
function $(id){ return document.getElementById(id); }
function now(){ return performance.now(); }
function round(x,n=2){ return Math.round(x*Math.pow(10,n))/Math.pow(10,n); }
function clamp(x,a=20,b=80){ return Math.max(a,Math.min(b,x)); }
function pct(x){ return Math.round(x) + '%'; }
function median(a){ const b=a.filter(x=>Number.isFinite(x)).sort((x,y)=>x-y); if(!b.length) return null; const m=Math.floor(b.length/2); return b.length%2?b[m]:(b[m-1]+b[m])/2; }
function shuffle(a){ const arr=a.slice(); for(let i=arr.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [arr[i],arr[j]]=[arr[j],arr[i]]; } return arr; }
function sample(a){ return a[Math.floor(Math.random()*a.length)]; }
function escapeHtml(s){ return String(s).replace(/[&<>'"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function headerHtml(idx, trialText, pctValue){
  const t = idx < tasks.length ? tasks[idx] : {title:'결과 산출', sub:'완료', desc:'결과를 정리하고 있습니다.'};
  const p = Number.isFinite(pctValue) ? pctValue : Math.min(idx,tasks.length)/tasks.length*100;
  return `<div class="panel"><div class="top"><div><span class="badge">${idx < tasks.length ? (idx+1)+' / '+tasks.length : '완료'}</span><h1 class="title">${t.title}</h1><p class="sub"><span class="blue">${t.sub}</span><br>${t.desc}</p></div><div class="small">반응시간은 브라우저 내부 시간 기준으로 기록됩니다.</div></div><div class="progress-row"><span>${trialText || Math.min(idx,tasks.length)+' / '+tasks.length}</span><span>${Math.round(p)}%</span></div><div class="meter"><div class="fill" style="width:${p}%"></div></div></div>`;
}
function render(idx, body, actions, trialText, pctValue){
  const actionClass = actions && actions.length===1 ? 'one' : (actions && actions.length===4 ? 'four' : '');
  app.innerHTML = headerHtml(idx, trialText, pctValue) + `<div class="panel work"><div class="center">${body}</div></div><div class="actions ${actionClass}" id="actions">${(actions||[]).map(a=>`<button id="${a.id}" class="${a.cls||''}" ${a.disabled?'disabled':''}>${a.label}</button>`).join('')}</div>`;
}
function setAction(id, fn){ const el=$(id); if(el) el.onclick=fn; }
function showFatal(msg){ app.innerHTML = `<div class="panel"><div class="error">${escapeHtml(msg)}</div><div style="height:12px"></div><button class="primary" onclick="window.location.reload()">다시 불러오기</button></div>`; }
function startBattery(){ state.taskIndex=0; state.records=[]; state.summaries={}; state.startedAt=new Date().toISOString(); runTrail(); }
function nextTask(){ state.taskIndex += 1; if(state.taskIndex===1) runNback(); else if(state.taskIndex===2) runGaze(); else if(state.taskIndex===3) runFlanker(); else if(state.taskIndex===4) runGoNoGo(); else finishBattery(); }
function completeBody(title, lines){ return `<div class="mid">${title}</div><div class="guide">${lines.map(escapeHtml).join('<br>')}</div>`; }
function continueActions(label){ return [{id:'nextBtn', label:label||'다음 과제로 이동', cls:'primary'}]; }
function attachContinue(){ setAction('nextBtn', nextTask); }
function progress(idx, done, total){ return ((idx + done/Math.max(total,1))/tasks.length)*100; }

function renderHome(){
  const body = `<div class="mid">검사 시작 전 안내</div><div class="guide">가능하면 PC/노트북에서 실시하고, 과제 중에는 화면을 벗어나지 마세요.<br>각 과제는 짧은 미니게임처럼 진행되며, 정확도와 반응속도가 함께 기록됩니다.</div><div class="kv"><div class="box"><div class="label">과제 1</div><div class="value">Trail</div></div><div class="box"><div class="label">과제 2</div><div class="value">2-back</div></div><div class="box"><div class="label">과제 3</div><div class="value">Gaze</div></div><div class="box"><div class="label">과제 4</div><div class="value">Flanker</div></div><div class="box"><div class="label">과제 5</div><div class="value">Go/No-Go</div></div></div>`;
  render(0, body, [{id:'startBtn', label:'전체 과제 시작', cls:'primary'}, {id:'reloadBtn', label:'다시 불러오기'}], '0 / 5', 0);
  setAction('startBtn', startBattery); setAction('reloadBtn', ()=>window.location.reload());
}

// Trail 과제: 절대좌표 대신 반응 안정성을 위해 grid-board를 사용한다.
function runTrail(){
  const idx=0;
  const phases=[
    {name:'Trail-A', seq:['1','2','3','4','5','6','7','8','9','10','11','12'], criterionSec:34},
    {name:'Trail-B', seq:['1','가','2','나','3','다','4','라','5','마','6','바'], criterionSec:50}
  ];
  let phaseIndex=0; const phaseResults=[];
  function introPhase(){
    const p=phases[phaseIndex];
    const body = `<div class="mid">${p.name}</div><div class="guide"><b>${p.seq.join(' → ')}</b><br>위 순서대로 항목을 빠르게 클릭하세요.<br>틀리면 오류로 기록되고 다음 목표는 유지됩니다.</div>`;
    render(idx, body, [{id:'startPhase', label:p.name+' 시작', cls:'primary'}], `${p.name} 준비`, progress(idx, phaseIndex, phases.length));
    setAction('startPhase', ()=>startPhase(p));
  }
  function startPhase(p){
    let expected=0, errors=0; const rec=[]; const order=shuffle(p.seq.map((label,i)=>({label,i}))); const startT=now(); let lastT=startT;
    function draw(){
      const board = `<div class="grid-board">${order.map(item=>{
        const cls = item.i < expected ? 'node done' : item.i===expected ? 'node next' : 'node';
        return `<button class="${cls}" id="node_${item.i}" data-i="${item.i}">${item.label}</button>`;
      }).join('')}</div><div class="trail-status"><div class="status-box">다음 목표: <span>${p.seq[expected] || '완료'}</span></div><div class="status-box">오류: <span>${errors}회</span></div></div>`;
      render(idx, board, [{id:'dummy1', label:'과제 진행 중', disabled:true},{id:'dummy2', label:'순서대로 클릭', disabled:true}], `${p.name} 진행 ${expected}/${p.seq.length}`, progress(idx, phaseIndex + expected/p.seq.length, phases.length));
      order.forEach(item=>{ const el=$('node_'+item.i); if(el && item.i>=expected) el.onclick=()=>clickItem(item); });
    }
    function clickItem(item){
      const t=now(); const correct=item.i===expected;
      if(correct){
        rec.push({task:'trail', phase:p.name, target:item.label, order:item.i+1, rt_from_start_ms:round(t-startT), delta_ms:round(t-lastT), correct:true});
        lastT=t; expected++;
        if(expected>=p.seq.length){
          const dur=t-startT; phaseResults.push({phase:p.name, duration_ms:round(dur), errors, click_records:rec});
          state.records.push(...rec.map(r=>({task:'trail', phase:p.name, target:r.target, order:r.order, rt_ms:r.rt_from_start_ms, delta_ms:r.delta_ms, correct:r.correct})));
          phaseIndex++;
          if(phaseIndex<phases.length){ setTimeout(introPhase, 450); } else { setTimeout(finishTrail, 450); }
          return;
        }
        draw();
      } else {
        errors++;
        state.records.push({task:'trail', phase:p.name, target:item.label, expected:p.seq[expected], rt_ms:round(t-startT), correct:false});
        draw();
      }
    }
    draw();
  }
  function finishTrail(){
    const a=phaseResults.find(x=>x.phase==='Trail-A')||{}; const b=phaseResults.find(x=>x.phase==='Trail-B')||{};
    const errors=(a.errors||0)+(b.errors||0); const aSec=(a.duration_ms||0)/1000; const bSec=(b.duration_ms||0)/1000;
    const scoreA=clamp(50+((phases[0].criterionSec-aSec)/phases[0].criterionSec)*16-(a.errors||0)*3);
    const scoreB=clamp(50+((phases[1].criterionSec-bSec)/phases[1].criterionSec)*16-(b.errors||0)*3);
    const score=clamp((scoreA+scoreB)/2-errors*1.2);
    state.summaries.trail={score:round(score,1), trail_a_sec:round(aSec,2), trail_b_sec:round(bSec,2), errors, criterion:'50점=내부 절대 기준점'};
    render(idx, completeBody('Trail 과제 완료',[`Trail-A: ${round(aSec,2)}초`, `Trail-B: ${round(bSec,2)}초`, `오류: ${errors}회`, `환산점수: ${round(score,1)}점`]), continueActions(), 'Trail 완료', 25);
    attachContinue();
  }
  introPhase();
}

function makeNbackSeq(n){
  const letters=['ㄱ','ㄴ','ㄷ','ㄹ','ㅁ','ㅂ','ㅅ','ㅇ']; const seq=[];
  for(let i=0;i<n;i++){
    if(i>=2 && Math.random()<0.30){ seq.push(seq[i-2]); }
    else { let c=sample(letters); let guard=0; while(i>=2 && c===seq[i-2] && guard<30){ c=sample(letters); guard++; } seq.push(c); }
  }
  return seq.map((letter,i)=>({letter,isTarget:i>=2 && letter===seq[i-2]}));
}
function runNback(){
  const idx=1; const trials=makeNbackSeq(22); let ti=0; const rec=[]; let onset=0;
  const intro=`<div class="mid">2-back</div><div class="guide">현재 글자가 <b>2개 전</b> 글자와 같으면 일치입니다.<br>처음 두 문항은 비교할 2개 전 글자가 없으므로 불일치로 응답하세요.</div>`;
  render(idx, intro, [{id:'startN',label:'2-back 시작',cls:'primary'}], '2-back 준비', 25);
  setAction('startN', next);
  function next(){
    if(ti>=trials.length) return finish();
    const tr=trials[ti]; onset=now(); state.locked=false;
    render(idx, `<div class="big">${tr.letter}</div><div class="guide">2개 전 글자와 비교해 응답하세요.</div>`, [{id:'nNo',label:'불일치'}, {id:'nYes',label:'일치',cls:'primary'}], `진행률 ${ti}/${trials.length}`, progress(idx, ti, trials.length));
    setAction('nNo',()=>respond(false)); setAction('nYes',()=>respond(true));
  }
  function respond(ans){ if(state.locked) return; state.locked=true; const tr=trials[ti]; const rt=now()-onset; const correct=ans===tr.isTarget; rec.push({task:'nback',trial:ti+1,stimulus:tr.letter,target:tr.isTarget,response:ans,correct,rt_ms:round(rt)}); ti++; setTimeout(next,140); }
  function finish(){
    state.records.push(...rec); const acc=rec.filter(r=>r.correct).length/rec.length; const med=median(rec.map(r=>r.rt_ms)); const targets=rec.filter(r=>r.target); const foils=rec.filter(r=>!r.target); const hit=targets.length?targets.filter(r=>r.response===true).length/targets.length:0; const fa=foils.length?foils.filter(r=>r.response===true).length/foils.length:0; const score=clamp(50+(acc-.70)*45+Math.max(0,(950-(med||950))/950)*5-fa*10);
    state.summaries.nback={score:round(score,1),accuracy:round(acc,3),median_rt_ms:round(med||0),hit_rate:round(hit,3),false_alarm_rate:round(fa,3),criterion:'50점=내부 절대 기준점'};
    render(idx, completeBody('2-back 완료',[`정확률: ${pct(acc*100)}`, `중앙 반응시간: ${Math.round(med||0)}ms`, `환산점수: ${round(score,1)}점`]), continueActions(), '2-back 완료', 50); attachContinue();
  }
}


function makeGazeTrials(n){ const dirs=['up','down','left','right']; const labels={up:'위',down:'아래',left:'왼쪽',right:'오른쪽'}; const trials=[]; for(let i=0;i<n;i++){ const dir=dirs[i%4]; trials.push({dir,label:labels[dir]}); } return shuffle(trials); }
function runGaze(){
  const idx=2; const trials=makeGazeTrials(18); let ti=0; const rec=[]; let onset=0; let combo=0; let bestCombo=0;
  const intro=`<div class="mid">시선 방향 과제</div><div class="guide">얼굴의 <b>눈동자</b>가 바라보는 방향을 빠르게 선택하세요.<br>키보드 사용 시 <span class="kbd">↑</span> <span class="kbd">↓</span> <span class="kbd">←</span> <span class="kbd">→</span> 방향키로도 응답할 수 있습니다.</div>`;
  render(idx, intro, [{id:'startGaze',label:'시선 방향 과제 시작',cls:'primary'}], '시선 방향 과제 준비', progress(idx,0,1));
  setAction('startGaze', ()=>{ window.addEventListener('keydown', keyHandler); next(); });
  function keyHandler(e){ const map={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right'}; if(map[e.key]){ e.preventDefault(); respond(map[e.key]); } }
  function faceHtml(dir){ return `<div class="gaze-stage"><div class="hud"><span class="hud-pill good">콤보 ${combo}</span><span class="hud-pill">남은 문항 ${trials.length-ti}</span></div><div class="face gaze-${dir}"><div class="eye left"><div class="pupil"></div></div><div class="eye right"><div class="pupil"></div></div><div class="mouth"></div></div><div class="guide">눈동자가 보는 방향은?</div></div>`; }
  function next(){ if(ti>=trials.length) return finish(); const tr=trials[ti]; onset=now(); state.locked=false; render(idx, faceHtml(tr.dir), [{id:'gUp',label:'↑ 위'},{id:'gLeft',label:'← 왼쪽'},{id:'gRight',label:'오른쪽 →',cls:'primary'},{id:'gDown',label:'↓ 아래'}], `진행률 ${ti}/${trials.length}`, progress(idx,ti,trials.length)); setAction('gUp',()=>respond('up')); setAction('gDown',()=>respond('down')); setAction('gLeft',()=>respond('left')); setAction('gRight',()=>respond('right')); }
  function respond(ans){ if(state.locked) return; state.locked=true; const tr=trials[ti]; const rt=now()-onset; const correct=ans===tr.dir; combo=correct?combo+1:0; bestCombo=Math.max(bestCombo,combo); rec.push({task:'gaze',trial:ti+1,stimulus:'face_gaze_'+tr.dir,correct_response:tr.dir,response:ans,correct,rt_ms:round(rt),combo_after:combo}); ti++; setTimeout(next, correct?110:230); }
  function finish(){ window.removeEventListener('keydown', keyHandler); state.records.push(...rec); const acc=rec.filter(r=>r.correct).length/rec.length; const correct=rec.filter(r=>r.correct); const med=median(correct.map(r=>r.rt_ms)); const score=clamp(50+(acc-.82)*42+Math.max(0,(760-(med||760))/760)*8+Math.min(bestCombo,8)*.55); state.summaries.gaze={score:round(score,1),accuracy:round(acc,3),median_rt_ms:round(med||0),best_combo:bestCombo,criterion:'50점=내부 절대 기준점'}; render(idx, completeBody('시선 방향 과제 완료',[`정확률: ${pct(acc*100)}`, `중앙 반응시간: ${Math.round(med||0)}ms`, `최고 콤보: ${bestCombo}`, `환산점수: ${round(score,1)}점`]), continueActions(), 'Gaze 완료', progress(idx,1,1)); attachContinue(); }
}

function makeFlankerTrials(n){ const arr=[]; for(let i=0;i<n;i++){ const dir=Math.random()<.5?'left':'right'; const congruent=i<n/2; const center=dir==='left'?'←':'→'; const same=dir==='left'?'←←':'→→'; const diff=dir==='left'?'→→':'←←'; arr.push({dir,condition:congruent?'congruent':'incongruent',stim:congruent?`${same}${center}${same}`:`${diff}${center}${diff}`}); } return shuffle(arr); }
function runFlanker(){
  const idx=3; const trials=makeFlankerTrials(20); let ti=0; const rec=[]; let onset=0;
  const intro=`<div class="mid">Flanker</div><div class="guide">가운데 화살표 방향만 선택합니다.<br>키보드 사용 시 <span class="kbd">←</span> <span class="kbd">→</span> 방향키로도 응답할 수 있습니다.</div>`;
  render(idx, intro, [{id:'startF',label:'Flanker 시작',cls:'primary'}], 'Flanker 준비', 50);
  setAction('startF', ()=>{ window.addEventListener('keydown', keyHandler); next(); });
  function keyHandler(e){ if(e.key==='ArrowLeft'){ e.preventDefault(); respond('left'); } if(e.key==='ArrowRight'){ e.preventDefault(); respond('right'); } }
  function next(){ if(ti>=trials.length) return finish(); const tr=trials[ti]; onset=now(); state.locked=false; render(idx, `<div class="flanker">${tr.stim}</div><div class="guide">가운데 화살표의 방향은?</div>`, [{id:'fLeft',label:'← 왼쪽'}, {id:'fRight',label:'오른쪽 →',cls:'primary'}], `진행률 ${ti}/${trials.length}`, progress(idx, ti, trials.length)); setAction('fLeft',()=>respond('left')); setAction('fRight',()=>respond('right')); }
  function respond(ans){ if(state.locked) return; state.locked=true; const tr=trials[ti]; const rt=now()-onset; const correct=ans===tr.dir; rec.push({task:'flanker',trial:ti+1,condition:tr.condition,stimulus:tr.stim,correct_response:tr.dir,response:ans,correct,rt_ms:round(rt)}); ti++; setTimeout(next,150); }
  function finish(){ window.removeEventListener('keydown', keyHandler); state.records.push(...rec); const acc=rec.filter(r=>r.correct).length/rec.length; const correct=rec.filter(r=>r.correct); const con=correct.filter(r=>r.condition==='congruent').map(r=>r.rt_ms); const incon=correct.filter(r=>r.condition==='incongruent').map(r=>r.rt_ms); const med=median(correct.map(r=>r.rt_ms)); const interference=(median(incon)||0)-(median(con)||0); const score=clamp(50+(acc-.82)*42-Math.max(0,interference-130)*.035-Math.max(0,(med||0)-850)*.01); state.summaries.flanker={score:round(score,1),accuracy:round(acc,3),median_rt_ms:round(med||0),interference_ms:round(interference),criterion:'50점=내부 절대 기준점'}; render(idx, completeBody('Flanker 완료',[`정확률: ${pct(acc*100)}`, `간섭 효과: ${Math.round(interference)}ms`, `환산점수: ${round(score,1)}점`]), continueActions(), 'Flanker 완료', 75); attachContinue(); }
}

function makeGngTrials(n){ const arr=[]; const nogoN=Math.round(n*.30); for(let i=0;i<n;i++) arr.push({type:i<nogoN?'nogo':'go'}); return shuffle(arr).map(x=>({type:x.type,stim:x.type==='go'?'GO':'X'})); }
function runGoNoGo(){
  const idx=4; const trials=makeGngTrials(22); let ti=0; const rec=[]; let onset=0; let responded=false; let timer=null;
  const intro=`<div class="mid">Go/No-Go</div><div class="guide"><b>GO</b>가 나오면 빠르게 반응하세요.<br><b>X</b>가 나오면 아무것도 누르지 마세요.<br>키보드 사용 시 <span class="kbd">Space</span>로도 반응할 수 있습니다.</div>`;
  render(idx, intro, [{id:'startG',label:'Go/No-Go 시작',cls:'primary'}], 'Go/No-Go 준비', 75);
  setAction('startG', ()=>{ window.addEventListener('keydown', keyHandler); next(); });
  function keyHandler(e){ if(e.code==='Space'){ e.preventDefault(); respond(); } }
  function next(){
    if(ti>=trials.length) return finish(); const tr=trials[ti]; responded=false;
    render(idx, `<div class="fix">+</div><div class="guide">준비</div>`, [{id:'gResp',label:'반응 / Space',cls:'primary'}, {id:'noResp',label:'X는 누르지 않기',disabled:true}], `진행률 ${ti}/${trials.length}`, progress(idx, ti, trials.length));
    setAction('gResp', respond);
    setTimeout(()=>{ onset=now(); const color=tr.type==='go'?'#56e39a':'#ff7373'; render(idx, `<div class="big" style="color:${color}">${tr.stim}</div><div class="guide">${tr.type==='go'?'지금 반응':'누르지 마세요'}</div>`, [{id:'gResp',label:'반응 / Space',cls:'primary'}, {id:'noResp',label:'X는 누르지 않기',disabled:true}], `진행률 ${ti}/${trials.length}`, progress(idx, ti, trials.length)); setAction('gResp', respond); timer=setTimeout(()=>{ if(!responded){ const correct=tr.type==='nogo'; rec.push({task:'gng',trial:ti+1,condition:tr.type,stimulus:tr.stim,response:null,correct,rt_ms:null}); ti++; setTimeout(next,120); } },900); },260);
  }
  function respond(){ if(ti>=trials.length || responded) return; responded=true; if(timer) clearTimeout(timer); const tr=trials[ti]; const rt=now()-onset; const correct=tr.type==='go'; rec.push({task:'gng',trial:ti+1,condition:tr.type,stimulus:tr.stim,response:'press',correct,rt_ms:round(rt)}); ti++; setTimeout(next,120); }
  function finish(){ window.removeEventListener('keydown', keyHandler); if(timer) clearTimeout(timer); state.records.push(...rec); const go=rec.filter(r=>r.condition==='go'), nogo=rec.filter(r=>r.condition==='nogo'); const goHit=go.length?go.filter(r=>r.response==='press').length/go.length:0; const omission=1-goHit; const commission=nogo.length?nogo.filter(r=>r.response==='press').length/nogo.length:0; const acc=rec.filter(r=>r.correct).length/rec.length; const med=median(go.filter(r=>r.correct).map(r=>r.rt_ms)); const score=clamp(50+(acc-.86)*45-commission*22-omission*16-Math.max(0,(med||0)-650)*.01); state.summaries.gng={score:round(score,1),accuracy:round(acc,3),go_hit_rate:round(goHit,3),commission_error_rate:round(commission,3),omission_error_rate:round(omission,3),median_go_rt_ms:round(med||0),criterion:'50점=내부 절대 기준점'}; render(idx, completeBody('Go/No-Go 완료',[`전체 정확률: ${pct(acc*100)}`, `NO-GO 오반응률: ${pct(commission*100)}`, `환산점수: ${round(score,1)}점`]), [{id:'finishBtn',label:'결과 정리하기',cls:'primary'}], 'Go/No-Go 완료', 100); setAction('finishBtn', finishBattery); }
}

function makeResultUrl(b64){
  let base='';
  try{ base = window.parent && window.parent.location ? window.parent.location.href : ''; }catch(e){ base=''; }
  if(!base && document.referrer) base=document.referrer;
  if(!base) base=window.location.href;
  const url=new URL(base);
  url.searchParams.set('cog_done','1');
  url.searchParams.set('cog_data',b64);
  return url.toString();
}
function finishBattery(){
  const s=state.summaries;
  const domains={
    processing_speed: round(((s.trail?.score||50)+(s.flanker?.score||50))/2,1),
    working_memory: s.nback?.score || null,
    visual_attention: s.gaze?.score || null,
    inhibition_control: round(((s.flanker?.score||50)+(s.gng?.score||50))/2,1),
    sustained_attention: s.gng?.score || null
  };
  const vals=Object.values(domains).filter(v=>v!==null && Number.isFinite(v));
  const overall=round(vals.reduce((a,b)=>a+b,0)/vals.length,1);
  const payload={exam_name:EXAM_NAME, exam_version:EXAM_VERSION, started_at:state.startedAt, finished_at:new Date().toISOString(), scoring_note:'criterion-referenced transformed score; 50 = internal criterion point, not population percentile', summaries:s, domains, overall_score:overall, records:state.records};
  const b64=btoa(unescape(encodeURIComponent(JSON.stringify(payload)))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  const href=makeResultUrl(b64);
  const body=`<div class="mid">과제 완료</div><div class="guide">자동 이동은 배포 환경에서 차단될 수 있어, 아래 버튼을 직접 눌러 결과 화면으로 이동합니다.</div><a class="result-link" href="${href.replace(/&/g,'&amp;').replace(/"/g,'&quot;')}" target="_top" rel="noopener">결과 확인하기</a><div class="small" style="margin-top:12px;">버튼이 작동하지 않으면 새 탭 열기를 사용하세요.</div><a class="result-link" style="font-size:14px;min-height:44px;background:#10284c;" href="${href.replace(/&/g,'&amp;').replace(/"/g,'&quot;')}" target="_blank" rel="noopener">새 탭에서 결과 열기</a>`;
  render(tasks.length, body, [{id:'restartBtn',label:'과제 다시하기'}], '완료', 100);
  setAction('restartBtn', renderHome);
}


renderHome();
})();
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
    components.html(cognitive_task_html(), height=1060, scrolling=True)
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
        "visual_attention": domains.get("visual_attention", ""),
        "sustained_attention": domains.get("sustained_attention", ""),
        "scoring_note": payload.get("scoring_note", ""),
        "task_count": 5,
        "record_count": len(records),
    }

    return {
        "exam_name": EXAM_NAME,
        "consent_col": dict_to_kv_csv(consent_col),
        "examinee_col": dict_to_kv_csv(examinee_col),
        "answers_col": dict_to_kv_csv(answers_col),
        "result_col": dict_to_kv_csv(result_col),
    }


def render_score_bar(label: str, score: Optional[float]) -> None:
    score_value = 0 if score is None else max(0, min(100, float(score)))
    display = "-" if score is None else f"{score_value:.1f}점 · {criterion_label(score_value)}"
    st.markdown(
        f"""
        <div class="result-panel">
          <div style="display:flex;justify-content:space-between;gap:12px;margin-bottom:10px;">
            <div style="color:#f8fbff;font-weight:850;">{label}</div>
            <div style="color:#c7d3e3;font-weight:800;">{display}</div>
          </div>
          <div class="score-bar"><div class="score-fill" style="width:{score_value}%;"></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_result(dev_mode: bool = False) -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper("result")

    payload = st.session_state.cog_payload
    if not payload:
        st.warning("결과 데이터가 없습니다. 다시 진행해 주세요.")
        if st.button("처음으로", type="primary", use_container_width=True):
            reset_all()
            rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    exam_data = build_exam_data(payload)
    auto_db_insert(exam_data)

    domains = payload.get("domains", {}) or {}
    overall = payload.get("overall_score")
    overall_label = criterion_label(overall)

    st.markdown(
        f"""
        <section class="card">
          <span class="badge">결과</span>
          <h1 class="title-lg">인지 기능 검사 결과</h1>
          <p class="text">본 점수는 현재 데이터가 없는 초기 버전이므로 상대평가·백분위가 아니라 절대 기준 환산점수입니다. <b>50점은 인구 평균이 아니라 내부 기준점</b>입니다.</p>
          <div class="metric-grid">
            <div class="metric-card"><div class="metric-label">종합 점수</div><div class="metric-value">{overall if overall is not None else '-'}</div></div>
            <div class="metric-card"><div class="metric-label">판정</div><div class="metric-value" style="font-size:22px;">{overall_label}</div></div>
            <div class="metric-card"><div class="metric-label">기록 수</div><div class="metric-value">{len(payload.get('records', []) or [])}</div></div>
            <div class="metric-card"><div class="metric-label">기준</div><div class="metric-value" style="font-size:22px;">50점</div></div>
          </div>
          <p class="text"><b>해석:</b> {score_desc(overall)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("영역별 결과")
    render_score_bar("처리속도 / 시각탐색", domains.get("processing_speed"))
    render_score_bar("작업기억", domains.get("working_memory"))
    render_score_bar("시각/사회적 주의", domains.get("visual_attention"))
    render_score_bar("억제통제", domains.get("inhibition_control"))
    render_score_bar("지속주의", domains.get("sustained_attention"))

    with st.expander("과제별 요약 확인", expanded=False):
        st.json(payload.get("summaries", {}))

    with st.expander("원자료 확인", expanded=False):
        st.json(payload.get("records", []))

    if dev_mode or not ENABLE_DB_INSERT:
        with st.expander("DB 저장용 exam_data 확인", expanded=False):
            st.json(exam_data)

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("검사 다시하기", type="primary", use_container_width=True):
            reset_all()
            rerun()
    with c2:
        if st.button("닫기", use_container_width=True):
            st.session_state.close_attempted = True
            components.html("<script>try{window.close();}catch(e){}</script>", height=0)
            rerun()

    if st.session_state.close_attempted:
        st.warning("탭이 자동으로 닫히지 않는 경우, 사용자가 직접 탭을 닫아주세요.")

    st.markdown(
        """
        <div class="footer-note">
        ※ 본 검사는 비진단적 스크리닝 도구입니다. 추후 표본 수집 후 연령대·기기·실시환경별 기준, 신뢰도, 반복측정 안정성 검토가 필요합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# DB 저장 분기
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
    dev_mode = get_query_value("dev", "0") == "1"

    decoded = decode_payload_from_query()
    if decoded:
        st.session_state.cog_payload = decoded
        st.session_state.meta["submitted_ts"] = now_iso()
        st.session_state.page = "result"
        clear_query_params()
        rerun()

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
