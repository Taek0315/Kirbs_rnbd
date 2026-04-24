# -*- coding: utf-8 -*-
"""
KIRBS+ 무료 인지 컨디션 스크리닝 배터리 · single py version
- Brief PVT
- Stroop
- Flanker
- Go/No-Go

실행:
  ENABLE_DB_INSERT=false streamlit run kirbs_cognitive_condition_battery_single.py

운영/병합:
  ENABLE_DB_INSERT=true  -> utils.database.Database().insert(exam_data) 수행
  ENABLE_DB_INSERT=false -> DB insert 미수행 + debug payload 노출

주의:
  Streamlit 기본 위젯 기반 반응시간은 서버 왕복 지연을 포함합니다.
  운영형 정밀 RT 수집은 JS 컴포넌트화가 권장됩니다.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# Streamlit page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KIRBS+ 인지 컨디션 스크리닝",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

KST = timezone(timedelta(hours=9))

EXAM_NAME = "KIRBS_COGNITIVE_CONDITION_BATTERY"
EXAM_TITLE = "KIRBS+ 인지 컨디션 스크리닝"
EXAM_SUBTITLE = "처리속도 · 주의집중 · 억제통제 · 지속주의"
EXAM_VERSION = "streamlit_single_py_1.1"

TASK_ORDER = ["pvt", "stroop", "flanker", "gng"]
TASK_META = {
    "pvt": {
        "title": "Brief PVT",
        "subtitle": "주의 각성도 및 반응속도",
        "description": "신호가 나타나면 가능한 한 빠르게 반응 버튼을 누릅니다.",
        "trials": 8,
    },
    "stroop": {
        "title": "Stroop 색-단어 과제",
        "subtitle": "선택적 주의 및 간섭 억제",
        "description": "글자의 뜻이 아니라 글자의 색을 보고 응답합니다.",
        "trials": 12,
    },
    "flanker": {
        "title": "Flanker 화살표 과제",
        "subtitle": "반응 갈등 및 억제통제",
        "description": "가운데 화살표의 방향만 보고 응답합니다.",
        "trials": 12,
    },
    "gng": {
        "title": "Go/No-Go 과제",
        "subtitle": "지속주의 및 충동 억제",
        "description": "GO 자극에는 반응하고, NO-GO 자극에는 반응을 참습니다.",
        "trials": 16,
    },
}

AGE_GROUP_OPTIONS = ["선택 안 함", "10대", "20대", "30대", "40대", "50대", "60대 이상"]
SEX_OPTIONS = ["선택 안 함", "남성", "여성", "기타/응답 안 함"]
DEVICE_OPTIONS = ["PC/노트북", "태블릿", "모바일", "기타"]
CAFFEINE_OPTIONS = ["아니오", "예", "응답 안 함"]

COLOR_MAP = {
    "빨강": "#ff7373",
    "파랑": "#4f9cff",
    "초록": "#56e39a",
    "노랑": "#ffb454",
}

# ──────────────────────────────────────────────────────────────────────────────
# CSS · 단일 py 내부 고정 테마
# ──────────────────────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  color-scheme: dark !important;
  --content-max-width: 940px;
  --bg: #071225;
  --bg-2: #06101f;
  --surface: #0b1a33;
  --surface-2: #0d2140;
  --surface-3: #10284c;
  --surface-4: #13315d;
  --text: #f8fbff;
  --text-2: #edf5ff;
  --muted: #c7d3e3;
  --muted-2: #9fb0c4;
  --line: rgba(148, 163, 184, 0.30);
  --line-strong: rgba(120, 173, 255, 0.86);
  --primary: #4f9cff;
  --primary-2: #78adff;
  --primary-soft: rgba(79, 156, 255, 0.16);
  --success: #56e39a;
  --warning: #ffb454;
  --danger: #ff7373;
  --field-bg: #10284c;
  --field-bg-hover: #13315d;
  --field-border: rgba(96, 165, 250, 0.56);
  --field-border-strong: rgba(120, 173, 255, 0.96);
  --field-shadow: 0 0 0 3px rgba(79, 156, 255, 0.16);
  --radius-xl: 22px;
  --radius-lg: 18px;
  --radius-md: 14px;
  --shadow-sm: 0 8px 24px rgba(2, 8, 23, 0.28);
  --shadow-md: 0 18px 40px rgba(2, 8, 23, 0.38);
}

* { box-sizing: border-box; }
html, body, .stApp, [data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at top left, rgba(79,156,255,.08), transparent 30%),
    linear-gradient(180deg, var(--bg-2) 0%, var(--bg) 100%) !important;
  color: var(--text) !important;
}
html, body, p, div, span, li, button, label, input, textarea, select {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif !important;
  letter-spacing: -0.01em;
}
[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer, div[data-testid="stDecoration"] {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
}
[data-testid="block-container"], .block-container {
  max-width: var(--content-max-width) !important;
  padding-top: 0.9rem !important;
  padding-bottom: 3.2rem !important;
}

/* 전역 텍스트 색상 고정 */
h1, h2, h3, h4, h5, h6,
p, span, div, li, label,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] * {
  color: var(--text) !important;
  opacity: 1 !important;
}
small, .muted, .caption, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {
  color: var(--muted) !important;
  opacity: 1 !important;
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
  background: linear-gradient(180deg, rgba(255,255,255,.018), rgba(255,255,255,.006)), var(--surface) !important;
  border: 1px solid var(--line) !important;
  border-radius: var(--radius-xl) !important;
  box-shadow: var(--shadow-sm) !important;
  padding: 22px !important;
  margin-bottom: 16px !important;
}
.card.soft { background: linear-gradient(180deg, rgba(255,255,255,.014), rgba(255,255,255,.004)), var(--surface-2) !important; }
.title-lg { font-size: clamp(25px, 3vw, 34px) !important; font-weight: 900 !important; line-height: 1.28 !important; color: var(--text) !important; margin: 6px 0 0 !important; }
.title-md { font-size: clamp(18px, 2.2vw, 21px) !important; font-weight: 800 !important; line-height: 1.35 !important; color: var(--text) !important; margin: 0 0 8px !important; }
.text { font-size: 15px !important; line-height: 1.72 !important; color: var(--muted) !important; }
.badge {
  display: inline-flex !important;
  align-items: center !important;
  padding: 6px 12px !important;
  border-radius: 999px !important;
  background: var(--primary-soft) !important;
  color: #a8ccff !important;
  font-size: 12px !important;
  font-weight: 850 !important;
  margin: 0 6px 8px 0 !important;
  border: 1px solid rgba(79,156,255,.25) !important;
}
.badge * { color: #a8ccff !important; }
.hero {
  background:
    radial-gradient(circle at top right, rgba(79,156,255,.18), transparent 28%),
    linear-gradient(180deg, rgba(13,33,64,.98), rgba(11,26,51,.98)) !important;
  border: 1px solid rgba(120,173,255,.28) !important;
  border-radius: 28px !important;
  box-shadow: var(--shadow-md) !important;
  padding: 30px 28px !important;
  margin-bottom: 16px !important;
}
.hero-kicker { color: #a8ccff !important; font-size: 13px !important; font-weight: 900 !important; letter-spacing: .08em !important; text-transform: uppercase !important; }
.hero-sub { color: var(--muted) !important; font-size: 15px !important; line-height: 1.72 !important; margin-top: 10px !important; }
.intro-bullets { margin: 0; padding-left: 1.15rem; display: grid; gap: .65rem; }
.intro-bullets li { color: var(--muted) !important; line-height: 1.72 !important; word-break: keep-all; }
.notice-box, .warning-box {
  border-radius: 16px !important;
  padding: 15px 16px !important;
  line-height: 1.7 !important;
  font-size: 14px !important;
  margin: 12px 0 14px !important;
}
.notice-box { background: rgba(79,156,255,.07) !important; border: 1px dashed rgba(79,156,255,.28) !important; }
.warning-box { background: rgba(255,180,84,.12) !important; border: 1px solid rgba(255,180,84,.38) !important; }
.notice-box, .notice-box *, .warning-box, .warning-box * { color: var(--text-2) !important; }

/* Stepper */
.stepper { display: flex; align-items: center; justify-content: center; gap: 8px; flex-wrap: wrap; margin: 2px 0 18px; }
.step-item { display: flex; flex-direction: column; align-items: center; min-width: 74px; }
.step-circle { width: 34px; height: 34px; border-radius: 999px; display: flex; align-items: center; justify-content: center; font-weight: 850; font-size: 14px; border: 1px solid rgba(214,226,236,.55); background: rgba(255,255,255,.10); color: #d8e7f5 !important; }
.step-item.active .step-circle { background: var(--primary) !important; border-color: var(--primary) !important; color: #fff !important; }
.step-item.done .step-circle { background: var(--success) !important; border-color: var(--success) !important; color: #fff !important; }
.step-label { margin-top: 6px; font-size: 12px; color: #d8e7f5 !important; font-weight: 750; text-align: center; }
.step-line { width: 42px; height: 2px; background: rgba(214,226,236,.35); border-radius: 999px; }
.step-line.done { background: var(--success); }

/* widget labels */
div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stSlider"] label,
div[data-testid="stCheckbox"] label,
div[data-testid="stRadio"] label,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] *,
[data-testid="stCheckbox"] p,
[data-testid="stCheckbox"] span,
[data-testid="stSlider"] p,
[data-testid="stSlider"] span {
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  font-weight: 750 !important;
  opacity: 1 !important;
}

/* text input */
div[data-testid="stTextInput"] input {
  background: var(--field-bg) !important;
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  caret-color: var(--text) !important;
  border: 1px solid var(--field-border) !important;
  border-radius: 14px !important;
  min-height: 48px !important;
  box-shadow: none !important;
  padding: 12px 14px !important;
  opacity: 1 !important;
}
div[data-testid="stTextInput"] input:hover { background: var(--field-bg-hover) !important; border-color: var(--field-border-strong) !important; }
div[data-testid="stTextInput"] input:focus { border-color: var(--field-border-strong) !important; box-shadow: var(--field-shadow) !important; outline: none !important; }
div[data-testid="stTextInput"] input::placeholder { color: var(--muted-2) !important; -webkit-text-fill-color: var(--muted-2) !important; opacity: 1 !important; }

/* selectbox visible field */
div[data-testid="stSelectbox"] [data-baseweb="select"] { width: 100% !important; }
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
div[data-testid="stSelectbox"] [data-baseweb="select"] div,
div[data-testid="stSelectbox"] [data-baseweb="select"] [role="combobox"],
div[data-testid="stSelectbox"] [data-baseweb="select"] [role="combobox"] * {
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  opacity: 1 !important;
}
div[data-testid="stSelectbox"] [data-baseweb="select"] svg,
div[data-testid="stSelectbox"] [data-baseweb="select"] path { fill: var(--text) !important; color: var(--text) !important; opacity: 1 !important; }

/* dropdown popover */
div[data-baseweb="popover"] { z-index: 99999 !important; }
div[data-baseweb="popover"] [data-baseweb="menu"],
div[data-baseweb="popover"] [role="listbox"],
div[data-baseweb="popover"] ul,
div[role="listbox"], ul[role="listbox"] {
  background: var(--surface-2) !important;
  border: 1px solid var(--field-border) !important;
  border-radius: 14px !important;
  box-shadow: var(--shadow-md) !important;
  overflow: hidden !important;
  padding: 6px 0 !important;
}
div[data-baseweb="popover"] [role="option"],
div[data-baseweb="popover"] li,
div[role="option"], li[role="option"] {
  background: transparent !important;
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  opacity: 1 !important;
  min-height: 42px !important;
  border-radius: 0 !important;
}
div[data-baseweb="popover"] [role="option"] *, div[role="option"] * {
  color: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  opacity: 1 !important;
}
div[data-baseweb="popover"] [role="option"]:hover,
div[data-baseweb="popover"] [aria-selected="true"],
div[role="option"]:hover,
div[role="option"][aria-selected="true"] { background: rgba(79,156,255,.16) !important; }

/* slider */
div[data-testid="stSlider"] [data-baseweb="slider"] div { color: var(--text) !important; }
div[data-testid="stSlider"] [role="slider"] { background-color: var(--primary) !important; border: 2px solid #fff !important; box-shadow: 0 0 0 2px rgba(79,156,255,.25) !important; }
div[data-testid="stSlider"] [data-baseweb="slider"] > div > div { background-color: rgba(148,163,184,.36) !important; }

/* checkbox */
div[data-testid="stCheckbox"] svg { color: var(--primary) !important; fill: var(--primary) !important; }

/* buttons */
div[data-testid="stButton"] > button, .stButton > button {
  border-radius: 12px !important;
  min-height: 46px !important;
  border: 1px solid var(--line) !important;
  background: var(--surface-3) !important;
  color: var(--text) !important;
  font-weight: 800 !important;
  transition: all .18s ease !important;
  box-shadow: none !important;
}
div[data-testid="stButton"] > button *, .stButton > button * { color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; }
div[data-testid="stButton"] > button:hover { border-color: var(--field-border-strong) !important; background: #163864 !important; box-shadow: 0 0 0 2px rgba(79,156,255,.10) !important; }
div[data-testid="stButton"] > button[kind="primary"] {
  border-color: var(--field-border-strong) !important;
  background: linear-gradient(180deg, #1d4f8d, #163f73) !important;
  color: #fff !important;
  box-shadow: 0 0 0 1px rgba(79,156,255,.28), 0 8px 18px rgba(79,156,255,.18) !important;
}
div[data-testid="stButton"] > button[kind="primary"] * { color: #fff !important; -webkit-text-fill-color: #fff !important; }
div[data-testid="stButton"] > button:disabled { opacity: .56 !important; cursor: not-allowed !important; box-shadow: none !important; }

/* alerts / expander / dataframe */
div[data-testid="stAlert"] { background: rgba(255,115,115,.14) !important; border: 1px solid rgba(255,115,115,.24) !important; border-radius: 14px !important; }
div[data-testid="stAlert"] * { color: #ffd6d6 !important; }
div[data-testid="stExpander"] { background: var(--surface-2) !important; border: 1px solid var(--line) !important; border-radius: 16px !important; }

/* task stimulus */
.stimulus-box {
  border: 1px solid rgba(120,173,255,.30) !important;
  background: radial-gradient(circle at top left, rgba(79,156,255,.09), transparent 32%), var(--surface-2) !important;
  border-radius: 24px !important;
  min-height: 220px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
  margin: 18px 0 16px !important;
  padding: 28px !important;
  box-shadow: var(--shadow-sm) !important;
}
.stimulus-big { color: var(--text) !important; font-size: clamp(52px, 10vw, 76px) !important; font-weight: 950 !important; letter-spacing: -0.04em !important; line-height: 1.1 !important; }
.stimulus-mid { color: var(--text) !important; font-size: clamp(36px, 7vw, 50px) !important; font-weight: 900 !important; line-height: 1.25 !important; }
.stimulus-small { color: var(--muted) !important; font-size: 15px !important; line-height: 1.7 !important; margin-top: 8px !important; }
.progress-row { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom: 10px; }
.progress-label { font-size:.88rem; font-weight:750; color: var(--muted) !important; }
.meter { width: 100%; height: 10px; border-radius: 999px; background: rgba(255,255,255,.04); overflow: hidden; border: 1px solid var(--line); }
.meter > span { display:block; height:100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); transition: width .25s ease; }
.result-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.metric-card { background: var(--surface-2); border: 1px solid var(--line); border-radius: 16px; padding: 14px; box-shadow: var(--shadow-sm); }
.metric-label { color: var(--muted) !important; font-size: 12px; font-weight: 750; margin-bottom: 6px; }
.metric-value { color: var(--text) !important; font-size: 24px; font-weight: 900; }
.score-bar { width:100%; height:12px; border-radius:999px; background: rgba(255,255,255,.06); border:1px solid var(--line); overflow:hidden; margin-top:8px; }
.score-bar > span { display:block; height:100%; background: linear-gradient(90deg, #3b82f6, #56e39a); }

@media (max-width: 820px) {
  .result-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .step-line { display:none; }
}
@media (max-width: 640px) {
  [data-testid="block-container"], .block-container { padding-left: .85rem !important; padding-right: .85rem !important; }
  .card, .hero { padding: 18px !important; border-radius: 18px !important; }
  .result-grid { grid-template-columns: 1fr; }
}
</style>
""",
        unsafe_allow_html=True,
    )

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


def clamp(value: Optional[float], low: float = 0.0, high: float = 100.0) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    return float(max(low, min(high, value)))


def safe_mean(values: List[float]) -> Optional[float]:
    arr = [float(v) for v in values if v is not None and not pd.isna(v)]
    return float(np.mean(arr)) if arr else None


def safe_median(values: List[float]) -> Optional[float]:
    arr = [float(v) for v in values if v is not None and not pd.isna(v)]
    return float(np.median(arr)) if arr else None


def safe_sd(values: List[float]) -> Optional[float]:
    arr = [float(v) for v in values if v is not None and not pd.isna(v)]
    return float(np.std(arr, ddof=1)) if len(arr) >= 2 else None


def fmt_ms(value: Optional[float]) -> str:
    return "-" if value is None or pd.isna(value) else f"{value:.0f} ms"


def fmt_pct(value: Optional[float]) -> str:
    return "-" if value is None or pd.isna(value) else f"{value * 100:.1f}%"


def fmt_score(value: Optional[float]) -> str:
    return "-" if value is None or pd.isna(value) else f"{value:.1f}"


def score_label(score: Optional[float]) -> str:
    if score is None or pd.isna(score):
        return "산출 불가"
    if score >= 80:
        return "안정"
    if score >= 60:
        return "보통"
    return "주의"


def _sanitize_csv_value(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).replace("\n", " ").replace("\r", " ").replace(",", " ")
    return s.strip()


def dict_to_kv_csv(d: Dict[str, Any]) -> str:
    if not isinstance(d, dict):
        return ""
    return ",".join(f"{_sanitize_csv_value(k)}={_sanitize_csv_value(v)}" for k, v in d.items())


def get_dev_mode() -> bool:
    try:
        return str(st.query_params.get("dev", "0")) == "1"
    except Exception:
        return False

# ──────────────────────────────────────────────────────────────────────────────
# 상태 초기화
# ──────────────────────────────────────────────────────────────────────────────
def init_state() -> None:
    if "page" not in st.session_state:
        st.session_state.page = "intro"
    if "respondent_id" not in st.session_state:
        st.session_state.respondent_id = str(uuid.uuid4())
    if "meta" not in st.session_state:
        st.session_state.meta = {
            "consent": False,
            "consent_ts": "",
            "started_ts": "",
            "submitted_ts": "",
        }
    if "profile" not in st.session_state:
        st.session_state.profile = {
            "age_group": "선택 안 함",
            "sex": "선택 안 함",
            "device": "PC/노트북",
            "sleep_quality_1to5": 3,
            "fatigue_1to5": 3,
            "caffeine_last_3h": "아니오",
        }
    if "current_task_index" not in st.session_state:
        st.session_state.current_task_index = 0
    if "result_payload" not in st.session_state:
        st.session_state.result_payload = None
    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False
    for task_key in TASK_ORDER:
        if task_key not in st.session_state:
            reset_task(task_key)


def reset_task(task_key: str) -> None:
    st.session_state[task_key] = {
        "started": False,
        "done": False,
        "started_at": "",
        "finished_at": "",
        "trial_index": 0,
        "trials": [],
        "records": [],
        "stimulus_onset": None,
        "phase": "ready",
    }


def reset_all() -> None:
    st.session_state.page = "intro"
    st.session_state.respondent_id = str(uuid.uuid4())
    st.session_state.meta = {"consent": False, "consent_ts": "", "started_ts": "", "submitted_ts": ""}
    st.session_state.profile = {
        "age_group": "선택 안 함",
        "sex": "선택 안 함",
        "device": "PC/노트북",
        "sleep_quality_1to5": 3,
        "fatigue_1to5": 3,
        "caffeine_last_3h": "아니오",
    }
    st.session_state.current_task_index = 0
    st.session_state.result_payload = None
    st.session_state.db_insert_done = False
    for task_key in TASK_ORDER:
        reset_task(task_key)

# ──────────────────────────────────────────────────────────────────────────────
# 자극 생성
# ──────────────────────────────────────────────────────────────────────────────
def seed_for(task_key: str) -> int:
    token = f"{st.session_state.respondent_id}-{task_key}"
    return 20260424 + abs(hash(token)) % 100000


def make_pvt_trials(n_trials: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    return [
        {
            "trial_index": i + 1,
            "task": "pvt",
            "condition": "signal",
            "stimulus": "●",
            "correct_response": "tap",
            "delay_sec": round(rng.uniform(0.75, 2.10), 2),
        }
        for i in range(n_trials)
    ]


def make_stroop_trials(n_trials: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    colors = list(COLOR_MAP.keys())
    trials: List[Dict[str, Any]] = []
    for i in range(n_trials):
        word = rng.choice(colors)
        if i < n_trials // 2:
            ink = word
            condition = "congruent"
        else:
            ink = rng.choice([c for c in colors if c != word])
            condition = "incongruent"
        trials.append({
            "trial_index": i + 1,
            "task": "stroop",
            "condition": condition,
            "stimulus": word,
            "stimulus_word": word,
            "ink_color_name": ink,
            "ink_color_hex": COLOR_MAP[ink],
            "correct_response": ink,
            "response_options": colors,
        })
    rng.shuffle(trials)
    for idx, t in enumerate(trials):
        t["trial_index"] = idx + 1
    return trials


def make_flanker_trials(n_trials: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    trials: List[Dict[str, Any]] = []
    for i in range(n_trials):
        target = rng.choice(["left", "right"])
        congruent = i < n_trials // 2
        if target == "left":
            center, same, diff, correct = "←", "←←", "→→", "left"
        else:
            center, same, diff, correct = "→", "→→", "←←", "right"
        trials.append({
            "trial_index": i + 1,
            "task": "flanker",
            "condition": "congruent" if congruent else "incongruent",
            "stimulus": f"{same if congruent else diff}{center}{same if congruent else diff}",
            "correct_response": correct,
            "response_options": ["left", "right"],
        })
    rng.shuffle(trials)
    for idx, t in enumerate(trials):
        t["trial_index"] = idx + 1
    return trials


def make_gng_trials(n_trials: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    nogo_count = max(4, int(round(n_trials * 0.30)))
    labels = ["nogo"] * nogo_count + ["go"] * (n_trials - nogo_count)
    rng.shuffle(labels)
    trials: List[Dict[str, Any]] = []
    for i, label in enumerate(labels):
        if label == "go":
            stimulus = rng.choice(["GO", "초록 원", "파란 원"])
            correct = "respond"
        else:
            stimulus = rng.choice(["X", "멈춤", "빨간 원"])
            correct = "withhold"
        trials.append({
            "trial_index": i + 1,
            "task": "gng",
            "condition": label,
            "stimulus": stimulus,
            "correct_response": correct,
            "response_options": ["respond", "withhold"],
        })
    return trials


def make_trials(task_key: str) -> List[Dict[str, Any]]:
    n_trials = TASK_META[task_key]["trials"]
    seed = seed_for(task_key)
    if task_key == "pvt":
        return make_pvt_trials(n_trials, seed)
    if task_key == "stroop":
        return make_stroop_trials(n_trials, seed)
    if task_key == "flanker":
        return make_flanker_trials(n_trials, seed)
    if task_key == "gng":
        return make_gng_trials(n_trials, seed)
    raise ValueError(task_key)

# ──────────────────────────────────────────────────────────────────────────────
# 과제 상태/기록
# ──────────────────────────────────────────────────────────────────────────────
def start_task(task_key: str) -> None:
    st.session_state[task_key] = {
        "started": True,
        "done": False,
        "started_at": now_iso(),
        "finished_at": "",
        "trial_index": 0,
        "trials": make_trials(task_key),
        "records": [],
        "stimulus_onset": None,
        "phase": "waiting" if task_key == "pvt" else "stimulus",
    }


def finish_task(task_key: str) -> None:
    state = st.session_state[task_key]
    state["done"] = True
    state["finished_at"] = now_iso()
    state["stimulus_onset"] = None
    state["phase"] = "done"
    st.session_state[task_key] = state


def current_trial(task_key: str) -> Optional[Dict[str, Any]]:
    state = st.session_state[task_key]
    idx = int(state["trial_index"])
    trials = state["trials"]
    return None if idx >= len(trials) else trials[idx]


def record_response(task_key: str, response: str) -> None:
    state = st.session_state[task_key]
    trial = current_trial(task_key)
    if trial is None:
        finish_task(task_key)
        rerun()

    onset = state.get("stimulus_onset")
    rt_ms = (time.perf_counter() - onset) * 1000 if onset is not None else None
    correct_response = trial.get("correct_response")

    state["records"].append({
        "respondent_id": st.session_state.respondent_id,
        "exam_name": EXAM_NAME,
        "exam_version": EXAM_VERSION,
        "task": task_key,
        "trial_index": trial.get("trial_index"),
        "condition": trial.get("condition"),
        "stimulus": trial.get("stimulus"),
        "stimulus_word": trial.get("stimulus_word"),
        "ink_color_name": trial.get("ink_color_name"),
        "correct_response": correct_response,
        "response": response,
        "correct": bool(response == correct_response),
        "rt_ms": round(float(rt_ms), 2) if rt_ms is not None else None,
        "delay_sec": trial.get("delay_sec"),
        "timestamp": now_iso(),
    })
    state["trial_index"] += 1
    state["stimulus_onset"] = None
    if state["trial_index"] >= len(state["trials"]):
        state["done"] = True
        state["finished_at"] = now_iso()
        state["phase"] = "done"
    else:
        state["phase"] = "waiting" if task_key == "pvt" else "stimulus"
    st.session_state[task_key] = state
    rerun()


def all_records() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for task_key in TASK_ORDER:
        records.extend(st.session_state[task_key].get("records", []))
    return records

# ──────────────────────────────────────────────────────────────────────────────
# 점수화
# ──────────────────────────────────────────────────────────────────────────────
def summarize_pvt(df: pd.DataFrame) -> Dict[str, Any]:
    sub = df[df["task"] == "pvt"].copy()
    rt = sub["rt_ms"].dropna().astype(float).tolist() if not sub.empty else []
    median_rt = safe_median(rt)
    mean_rt = safe_mean(rt)
    sd_rt = safe_sd(rt)
    lapse_count = int(np.sum(np.array(rt) >= 800)) if rt else 0
    score = clamp(100 - max(0, (median_rt or 0) - 320) * 0.10 - lapse_count * 6) if median_rt is not None else None
    return {"task": "pvt", "n_trials": int(len(sub)), "mean_rt_ms": mean_rt, "median_rt_ms": median_rt, "sd_rt_ms": sd_rt, "lapse_count_800ms": lapse_count, "score": score, "label": score_label(score)}


def summarize_congruency_task(df: pd.DataFrame, task_key: str) -> Dict[str, Any]:
    sub = df[df["task"] == task_key].copy()
    if sub.empty:
        return {"task": task_key, "n_trials": 0, "accuracy": None, "median_rt_ms": None, "congruent_median_rt_ms": None, "incongruent_median_rt_ms": None, "interference_ms": None, "score": None, "label": "산출 불가"}
    accuracy = float(sub["correct"].mean())
    correct_sub = sub[sub["correct"] == True]
    median_rt = safe_median(correct_sub["rt_ms"].dropna().astype(float).tolist())
    con_med = safe_median(correct_sub[correct_sub["condition"] == "congruent"]["rt_ms"].dropna().astype(float).tolist())
    incon_med = safe_median(correct_sub[correct_sub["condition"] == "incongruent"]["rt_ms"].dropna().astype(float).tolist())
    interference = incon_med - con_med if con_med is not None and incon_med is not None else None
    score = clamp(100 - max(0, interference or 0) * 0.05 - (1 - accuracy) * 60)
    return {"task": task_key, "n_trials": int(len(sub)), "accuracy": accuracy, "median_rt_ms": median_rt, "congruent_median_rt_ms": con_med, "incongruent_median_rt_ms": incon_med, "interference_ms": interference, "score": score, "label": score_label(score)}


def summarize_gng(df: pd.DataFrame) -> Dict[str, Any]:
    sub = df[df["task"] == "gng"].copy()
    if sub.empty:
        return {"task": "gng", "n_trials": 0, "accuracy": None, "go_hit_rate": None, "nogo_correct_rejection_rate": None, "commission_error_rate": None, "omission_error_rate": None, "median_go_rt_ms": None, "score": None, "label": "산출 불가"}
    accuracy = float(sub["correct"].mean())
    go = sub[sub["condition"] == "go"]
    nogo = sub[sub["condition"] == "nogo"]
    go_hit_rate = float((go["response"] == "respond").mean()) if len(go) else None
    omission_error_rate = float((go["response"] == "withhold").mean()) if len(go) else None
    nogo_correct_rate = float((nogo["response"] == "withhold").mean()) if len(nogo) else None
    commission_error_rate = float((nogo["response"] == "respond").mean()) if len(nogo) else None
    median_go_rt = safe_median(go[(go["response"] == "respond") & (go["correct"] == True)]["rt_ms"].dropna().astype(float).tolist())
    score = clamp(100 - (commission_error_rate or 0) * 55 - (omission_error_rate or 0) * 35 - (1 - accuracy) * 25)
    return {"task": "gng", "n_trials": int(len(sub)), "accuracy": accuracy, "go_hit_rate": go_hit_rate, "nogo_correct_rejection_rate": nogo_correct_rate, "commission_error_rate": commission_error_rate, "omission_error_rate": omission_error_rate, "median_go_rt_ms": median_go_rt, "score": score, "label": score_label(score)}


def summarize_consistency(df: pd.DataFrame) -> Dict[str, Any]:
    usable = df[(df["correct"] == True) & (df["rt_ms"].notna())]
    if usable.empty:
        return {"mean_rt_ms": None, "sd_rt_ms": None, "cv": None, "score": None, "label": "산출 불가"}
    rt = usable["rt_ms"].astype(float).tolist()
    mean_rt = safe_mean(rt)
    sd_rt = safe_sd(rt)
    cv = sd_rt / mean_rt if mean_rt and sd_rt is not None and mean_rt > 0 else None
    score = clamp(100 - max(0, (cv or 0) - 0.25) * 180) if cv is not None else None
    return {"mean_rt_ms": mean_rt, "sd_rt_ms": sd_rt, "cv": cv, "score": score, "label": score_label(score)}


def average_score(values: List[Optional[float]]) -> Optional[float]:
    clean = [float(v) for v in values if v is not None and not pd.isna(v)]
    return float(np.mean(clean)) if clean else None


def summarize_all(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    df = pd.DataFrame(records)
    if df.empty:
        return {"pvt": {}, "stroop": {}, "flanker": {}, "gng": {}, "reaction_consistency": {}, "composite": {}}
    pvt = summarize_pvt(df)
    stroop = summarize_congruency_task(df, "stroop")
    flanker = summarize_congruency_task(df, "flanker")
    gng = summarize_gng(df)
    consistency = summarize_consistency(df)
    processing_speed = average_score([pvt.get("score"), stroop.get("score"), flanker.get("score")])
    inhibition_control = average_score([stroop.get("score"), flanker.get("score"), gng.get("score")])
    sustained_attention = average_score([pvt.get("score"), gng.get("score"), consistency.get("score")])
    reaction_consistency = consistency.get("score")
    overall = average_score([processing_speed, inhibition_control, sustained_attention, reaction_consistency])
    return {
        "pvt": pvt,
        "stroop": stroop,
        "flanker": flanker,
        "gng": gng,
        "reaction_consistency": consistency,
        "composite": {
            "processing_speed": processing_speed,
            "inhibition_control": inhibition_control,
            "sustained_attention": sustained_attention,
            "reaction_consistency": reaction_consistency,
            "overall": overall,
            "overall_label": score_label(overall),
        },
    }

# ──────────────────────────────────────────────────────────────────────────────
# HTML/UI 렌더링
# ──────────────────────────────────────────────────────────────────────────────
def render_stepper(current_page: str) -> None:
    steps = [("intro", "안내"), ("task", "과제"), ("result", "결과")]
    idx_map = {key: i for i, (key, _) in enumerate(steps)}
    current_idx = idx_map.get(current_page, 0)
    html_parts = ["<div class='stepper'>"]
    for i, (_key, label) in enumerate(steps):
        state = "done" if i < current_idx else "active" if i == current_idx else "todo"
        html_parts.append(f"<div class='step-item {state}'><div class='step-circle'>{'✓' if state == 'done' else i + 1}</div><div class='step-label'>{label}</div></div>")
        if i < len(steps) - 1:
            html_parts.append(f"<div class='step-line {'done' if i < current_idx else 'todo'}'></div>")
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_hero() -> None:
    st.markdown(
        f"""
        <section class="hero">
          <div class="hero-kicker">KIRBS+ Cognitive Screening</div>
          <h1 class="title-lg">{EXAM_TITLE}</h1>
          <div class="hero-sub">{EXAM_SUBTITLE}<br>현재의 인지적 컨디션을 간단히 확인하기 위한 비진단적 스크리닝 과제입니다.</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def progress_html(done: int, total: int) -> str:
    pct = 0 if total <= 0 else int(done / total * 100)
    return f"<div class='progress-row'><span class='progress-label'>진행률 {done}/{total}</span><span class='progress-label'>{pct}%</span></div><div class='meter'><span style='width:{pct}%;'></span></div>"


def metric_card(label: str, value: str) -> str:
    return f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div></div>"


def score_bar(label: str, score: Optional[float]) -> None:
    val = 0 if score is None or pd.isna(score) else int(round(score))
    st.markdown(
        f"""
        <div class="card soft">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;">
            <div style="font-weight:850;color:var(--text)!important;">{label}</div>
            <div style="font-weight:850;color:var(--primary-2)!important;">{fmt_score(score)} · {score_label(score)}</div>
          </div>
          <div class="score-bar"><span style="width:{val}%;"></span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ──────────────────────────────────────────────────────────────────────────────
# 페이지
# ──────────────────────────────────────────────────────────────────────────────
def page_intro() -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper("intro")
    render_hero()

    st.markdown(
        """
        <section class="card">
          <span class="badge">Brief PVT</span><span class="badge">Stroop</span><span class="badge">Flanker</span><span class="badge">Go/No-Go</span>
          <h2 class="title-md">검사 구성</h2>
          <ul class="intro-bullets">
            <li>반응속도, 지속주의, 간섭 억제, 충동 억제를 짧은 과제 형태로 확인합니다.</li>
            <li>결과는 현재 컨디션과 검사 환경의 영향을 받을 수 있으며 임상적 진단으로 사용하지 않습니다.</li>
            <li>Streamlit 프로토타입 특성상 반응시간에는 브라우저-서버 왕복 지연이 포함될 수 있습니다.</li>
          </ul>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<section class="card soft"><h2 class="title-md">기본 정보</h2><p class="text">개인 식별 없이 검사 환경과 컨디션 정보를 함께 기록합니다.</p>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        age_group = st.selectbox("연령대", AGE_GROUP_OPTIONS, index=AGE_GROUP_OPTIONS.index(st.session_state.profile.get("age_group", "선택 안 함")), key="profile_age_group")
    with c2:
        sex = st.selectbox("성별", SEX_OPTIONS, index=SEX_OPTIONS.index(st.session_state.profile.get("sex", "선택 안 함")), key="profile_sex")
    with c3:
        device = st.selectbox("실시 기기", DEVICE_OPTIONS, index=DEVICE_OPTIONS.index(st.session_state.profile.get("device", "PC/노트북")), key="profile_device")
    c4, c5, c6 = st.columns(3, gap="medium")
    with c4:
        sleep_quality = st.slider("지난밤 수면의 질", 1, 5, int(st.session_state.profile.get("sleep_quality_1to5", 3)), help="1=매우 나쁨, 5=매우 좋음", key="profile_sleep")
    with c5:
        fatigue = st.slider("현재 피로감", 1, 5, int(st.session_state.profile.get("fatigue_1to5", 3)), help="1=거의 없음, 5=매우 피곤함", key="profile_fatigue")
    with c6:
        caffeine = st.selectbox("최근 3시간 내 카페인 섭취", CAFFEINE_OPTIONS, index=CAFFEINE_OPTIONS.index(st.session_state.profile.get("caffeine_last_3h", "아니오")), key="profile_caffeine")
    st.markdown("</section>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="warning-box">
          <b>중요 안내</b><br>
          이 검사는 의학적·임상적 진단을 제공하지 않습니다. 결과는 컨디션, 기기 성능, 인터넷 상태, 키보드/마우스 사용 환경, 피로도 등에 영향을 받을 수 있습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )
    consent = st.checkbox(
        "검사 목적, 비진단적 성격, 익명/비식별 데이터 활용 가능성에 대한 안내를 확인했습니다.",
        value=bool(st.session_state.meta.get("consent", False)),
        key="consent_checkbox",
    )
    st.session_state.meta["consent"] = consent

    if st.button("검사 시작", type="primary", disabled=not consent, use_container_width=True, key="start_exam"):
        now = now_iso()
        st.session_state.profile = {
            "age_group": age_group,
            "sex": sex,
            "device": device,
            "sleep_quality_1to5": sleep_quality,
            "fatigue_1to5": fatigue,
            "caffeine_last_3h": caffeine,
        }
        st.session_state.meta["consent_ts"] = now
        st.session_state.meta["started_ts"] = now
        st.session_state.page = "task"
        st.session_state.current_task_index = 0
        for task_key in TASK_ORDER:
            reset_task(task_key)
        start_task(TASK_ORDER[0])
        rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render_task_header(task_key: str) -> None:
    state = st.session_state[task_key]
    total = len(state.get("trials", [])) or TASK_META[task_key]["trials"]
    done = len(state.get("records", []))
    meta = TASK_META[task_key]
    st.markdown(
        f"""
        <section class="card">
          <span class="badge">{st.session_state.current_task_index + 1} / {len(TASK_ORDER)}</span>
          <h1 class="title-lg">{meta['title']}</h1>
          <p class="text"><b style="color:var(--primary-2)!important;">{meta['subtitle']}</b><br>{meta['description']}</p>
          {progress_html(done, total)}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_pvt(task_key: str) -> None:
    state = st.session_state[task_key]
    trial = current_trial(task_key)
    if trial is None:
        finish_task(task_key)
        rerun()
    if state["phase"] == "waiting":
        st.markdown("<div class='stimulus-box'><div><div class='stimulus-mid'>준비</div><div class='stimulus-small'>잠시 후 신호가 나타납니다.</div></div></div>", unsafe_allow_html=True)
        time.sleep(float(trial["delay_sec"]))
        state["phase"] = "stimulus"
        state["stimulus_onset"] = time.perf_counter()
        st.session_state[task_key] = state
    st.markdown("<div class='stimulus-box'><div><div class='stimulus-big' style='color:var(--primary)!important;'>●</div><div class='stimulus-small'>지금 누르세요</div></div></div>", unsafe_allow_html=True)
    if st.button("반응", type="primary", use_container_width=True, key=f"{task_key}_tap_{state['trial_index']}"):
        record_response(task_key, "tap")


def render_stroop(task_key: str) -> None:
    state = st.session_state[task_key]
    trial = current_trial(task_key)
    if trial is None:
        finish_task(task_key)
        rerun()
    if state["stimulus_onset"] is None:
        state["stimulus_onset"] = time.perf_counter()
        st.session_state[task_key] = state
    st.markdown(
        f"<div class='stimulus-box'><div><div class='stimulus-big' style='color:{trial['ink_color_hex']}!important;'>{trial['stimulus_word']}</div><div class='stimulus-small'>글자의 뜻이 아니라 <b>글자의 색</b>을 선택하세요.</div></div></div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(4, gap="small")
    for idx, option in enumerate(trial["response_options"]):
        with cols[idx]:
            if st.button(option, use_container_width=True, key=f"{task_key}_{state['trial_index']}_{option}"):
                record_response(task_key, option)


def render_flanker(task_key: str) -> None:
    state = st.session_state[task_key]
    trial = current_trial(task_key)
    if trial is None:
        finish_task(task_key)
        rerun()
    if state["stimulus_onset"] is None:
        state["stimulus_onset"] = time.perf_counter()
        st.session_state[task_key] = state
    st.markdown(f"<div class='stimulus-box'><div><div class='stimulus-big'>{trial['stimulus']}</div><div class='stimulus-small'>가운데 화살표의 방향만 선택하세요.</div></div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("← 왼쪽", use_container_width=True, key=f"{task_key}_{state['trial_index']}_left"):
            record_response(task_key, "left")
    with c2:
        if st.button("오른쪽 →", use_container_width=True, key=f"{task_key}_{state['trial_index']}_right"):
            record_response(task_key, "right")


def render_gng(task_key: str) -> None:
    state = st.session_state[task_key]
    trial = current_trial(task_key)
    if trial is None:
        finish_task(task_key)
        rerun()
    if state["stimulus_onset"] is None:
        state["stimulus_onset"] = time.perf_counter()
        st.session_state[task_key] = state
    color = "var(--success)" if trial["condition"] == "go" else "var(--danger)"
    guide = "GO 자극입니다. 반응해야 합니다." if trial["condition"] == "go" else "NO-GO 자극입니다. 반응을 참아야 합니다."
    st.markdown(f"<div class='stimulus-box'><div><div class='stimulus-big' style='color:{color}!important;'>{trial['stimulus']}</div><div class='stimulus-small'>{guide}</div></div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("반응", use_container_width=True, key=f"{task_key}_{state['trial_index']}_respond"):
            record_response(task_key, "respond")
    with c2:
        if st.button("참기 / 다음", use_container_width=True, key=f"{task_key}_{state['trial_index']}_withhold"):
            record_response(task_key, "withhold")


def page_task() -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper("task")
    idx = int(st.session_state.current_task_index)
    if idx >= len(TASK_ORDER):
        st.session_state.page = "result"
        rerun()
    task_key = TASK_ORDER[idx]
    if not st.session_state[task_key].get("started"):
        start_task(task_key)
        rerun()
    render_task_header(task_key)
    state = st.session_state[task_key]
    if state["done"]:
        st.success(f"{TASK_META[task_key]['title']} 완료")
        if idx < len(TASK_ORDER) - 1:
            if st.button("다음 과제로 이동", type="primary", use_container_width=True):
                st.session_state.current_task_index += 1
                start_task(TASK_ORDER[st.session_state.current_task_index])
                rerun()
        else:
            if st.button("결과 보기", type="primary", use_container_width=True):
                st.session_state.meta["submitted_ts"] = now_iso()
                records = all_records()
                st.session_state.result_payload = build_result_payload(records)
                st.session_state.page = "result"
                rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return
    if task_key == "pvt":
        render_pvt(task_key)
    elif task_key == "stroop":
        render_stroop(task_key)
    elif task_key == "flanker":
        render_flanker(task_key)
    elif task_key == "gng":
        render_gng(task_key)
    st.markdown("</div>", unsafe_allow_html=True)


def build_result_payload(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = summarize_all(records)
    return {
        "instrument": EXAM_NAME,
        "title": EXAM_TITLE,
        "version": EXAM_VERSION,
        "respondent_id": st.session_state.respondent_id,
        "consent": st.session_state.meta.get("consent", False),
        "consent_ts": st.session_state.meta.get("consent_ts", ""),
        "started_ts": st.session_state.meta.get("started_ts", ""),
        "submitted_ts": st.session_state.meta.get("submitted_ts", "") or now_iso(),
        "profile": dict(st.session_state.profile),
        "summary": summary,
        "raw_records": records,
        "technical_note": "Streamlit prototype RT includes client-server roundtrip latency.",
    }


def build_exam_data(payload: Dict[str, Any]) -> Dict[str, str]:
    summary = payload.get("summary", {}) or {}
    composite = summary.get("composite", {}) or {}
    result_col = {
        "overall": composite.get("overall"),
        "overall_label": composite.get("overall_label"),
        "processing_speed": composite.get("processing_speed"),
        "inhibition_control": composite.get("inhibition_control"),
        "sustained_attention": composite.get("sustained_attention"),
        "reaction_consistency": composite.get("reaction_consistency"),
        "pvt_median_rt_ms": (summary.get("pvt", {}) or {}).get("median_rt_ms"),
        "stroop_accuracy": (summary.get("stroop", {}) or {}).get("accuracy"),
        "flanker_accuracy": (summary.get("flanker", {}) or {}).get("accuracy"),
        "gng_accuracy": (summary.get("gng", {}) or {}).get("accuracy"),
        "n_raw_records": len(payload.get("raw_records", [])),
    }
    consent_col = {
        "consent": payload.get("consent"),
        "consent_ts": payload.get("consent_ts"),
        "started_ts": payload.get("started_ts"),
        "submitted_ts": payload.get("submitted_ts"),
        "respondent_id": payload.get("respondent_id"),
        "version": payload.get("version"),
    }
    # 기존 검사들과 동일하게 5개 키 구조로 DB에 전달
    return {
        "exam_name": EXAM_NAME,
        "consent_col": dict_to_kv_csv(consent_col),
        "examinee_col": dict_to_kv_csv(payload.get("profile", {}) or {}),
        "answers_col": json.dumps(payload.get("raw_records", []), ensure_ascii=False),
        "result_col": dict_to_kv_csv(result_col),
    }


def page_result(dev_mode: bool = False) -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper("result")
    payload = st.session_state.result_payload or build_result_payload(all_records())
    st.session_state.result_payload = payload
    exam_data = build_exam_data(payload)
    auto_db_insert(exam_data)

    summary = payload["summary"]
    composite = summary["composite"]
    overall = composite.get("overall")
    label = composite.get("overall_label", "산출 불가")

    st.markdown(
        f"""
        <section class="hero">
          <div class="hero-kicker">Result Summary</div>
          <h1 class="title-lg">인지 컨디션 결과 요약</h1>
          <div class="hero-sub">종합 지표는 현재 검사 환경에서의 내부 참고용 지표이며, 의학적·임상적 진단으로 해석하지 않습니다.</div>
        </section>
        <section class="card">
          <div class="result-grid">
            {metric_card('종합 지표', fmt_score(overall))}
            {metric_card('처리속도', fmt_score(composite.get('processing_speed')))}
            {metric_card('억제통제', fmt_score(composite.get('inhibition_control')))}
            {metric_card('지속주의', fmt_score(composite.get('sustained_attention')))}
          </div>
          <p class="text"><b style="color:var(--primary-2)!important;">종합 해석: {label}</b><br>{'현재 과제 수행에서는 반응속도와 정확도가 비교적 안정적으로 나타났습니다.' if overall and overall >= 80 else '피로도, 실시 환경, 기기 지연, 주의집중 상태에 따라 결과가 흔들릴 수 있습니다.'}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    score_bar("처리속도", composite.get("processing_speed"))
    score_bar("억제통제", composite.get("inhibition_control"))
    score_bar("지속주의", composite.get("sustained_attention"))
    score_bar("반응 일관성", composite.get("reaction_consistency"))

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Brief PVT", "Stroop", "Flanker", "Go/No-Go", "원자료"])
    with tab1:
        pvt = summary["pvt"]
        st.markdown("<section class='card soft'>" + "".join([
            metric_card("중앙 반응시간", fmt_ms(pvt.get("median_rt_ms"))),
            metric_card("평균 반응시간", fmt_ms(pvt.get("mean_rt_ms"))),
            metric_card("반응 지연 수", str(pvt.get("lapse_count_800ms", "-"))),
            metric_card("PVT 지표", fmt_score(pvt.get("score"))),
        ]) + "</section>", unsafe_allow_html=True)
    with tab2:
        x = summary["stroop"]
        st.markdown("<section class='card soft'>" + "".join([
            metric_card("정확률", fmt_pct(x.get("accuracy"))),
            metric_card("중앙 RT", fmt_ms(x.get("median_rt_ms"))),
            metric_card("간섭 효과", fmt_ms(x.get("interference_ms"))),
            metric_card("Stroop 지표", fmt_score(x.get("score"))),
        ]) + "</section>", unsafe_allow_html=True)
    with tab3:
        x = summary["flanker"]
        st.markdown("<section class='card soft'>" + "".join([
            metric_card("정확률", fmt_pct(x.get("accuracy"))),
            metric_card("중앙 RT", fmt_ms(x.get("median_rt_ms"))),
            metric_card("간섭 효과", fmt_ms(x.get("interference_ms"))),
            metric_card("Flanker 지표", fmt_score(x.get("score"))),
        ]) + "</section>", unsafe_allow_html=True)
    with tab4:
        x = summary["gng"]
        st.markdown("<section class='card soft'>" + "".join([
            metric_card("전체 정확률", fmt_pct(x.get("accuracy"))),
            metric_card("GO 적중률", fmt_pct(x.get("go_hit_rate"))),
            metric_card("NO-GO 오반응률", fmt_pct(x.get("commission_error_rate"))),
            metric_card("Go/No-Go 지표", fmt_score(x.get("score"))),
        ]) + "</section>", unsafe_allow_html=True)
    with tab5:
        raw_df = pd.DataFrame(payload.get("raw_records", []))
        st.dataframe(raw_df, use_container_width=True)
        st.download_button(
            "원자료 CSV 다운로드",
            data=raw_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{EXAM_NAME}_{payload.get('respondent_id')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("검사 다시하기", type="primary", use_container_width=True):
            reset_all()
            rerun()
    with c2:
        if st.button("처음 화면으로", use_container_width=True):
            reset_all()
            rerun()

    if dev_mode:
        st.caption("dev=1 · standardized exam_data")
        st.json(exam_data, expanded=False)
        st.caption("dev=1 · internal payload")
        st.json(payload, expanded=False)
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

    ok = safe_db_insert(exam_data)
    if ok:
        st.session_state.db_insert_done = True
        st.success("검사 완료")
    else:
        st.warning("DB 저장이 수행되지 않았습니다. 환경/모듈 상태를 확인해 주세요.")

# ──────────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    inject_css()
    init_state()
    dev_mode = get_dev_mode()

    if st.session_state.page == "intro":
        page_intro()
    elif st.session_state.page == "task":
        if not st.session_state.meta.get("consent"):
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            rerun()
        page_task()
    elif st.session_state.page == "result":
        page_result(dev_mode=dev_mode)
    else:
        st.session_state.page = "intro"
        rerun()


if __name__ == "__main__":
    main()
