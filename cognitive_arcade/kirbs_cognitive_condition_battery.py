# -*- coding: utf-8 -*-
"""
KIRBS+ 인지 미니게임 3과제 버전

구성
- Trail 연결 과제: 무작위 숫자 원형 노드 3단계 연결
- Gaze 방향 판단 과제: 시선 방향 판단 + 반응속도
- Flanker 화살표 과제: 선택적 주의 + 간섭 억제

핵심 원칙
- 무료 배포용으로 과제 수와 난도를 낮추고, 게임형 진행감을 강화함
- n-back, Go/No-Go 제거
- Streamlit iframe 상위 페이지 이동 방식 제거
- declare_component + Streamlit component message protocol로 JS 결과를 Python에 직접 반환
- 결과 화면 자동 전환
- 사용자에게 raw JSON/과제 요약 expander 노출 없음(dev=1에서만 확인)
- 점수는 정답률과 RT를 결합한 내부 기준 환산점수로 산출
- 테스타리움 병합 기준에 맞춰 ENABLE_DB_INSERT 환경변수로 DB 저장 분기

실행 예
    ENABLE_DB_INSERT=false streamlit run kirbs_cognitive_arcade_3tasks.py
"""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
import streamlit.components.v1 as components


# ──────────────────────────────────────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KIRBS+ 인지 미니게임",
    page_icon="🎮",
    layout="centered",
    initial_sidebar_state="collapsed",
)

KST = timezone(timedelta(hours=9))

EXAM_NAME = "KIRBS_COGNITIVE_ARCADE_3TASKS"
EXAM_TITLE = "KIRBS+ 인지 미니게임"
EXAM_SUBTITLE = "처리속도 · 시각 탐색 · 시선 판단 · 간섭 억제"
EXAM_VERSION = "streamlit_component_arcade_3tasks_v1.3_layout_fix"

REGION_OPTIONS = ["수도권", "충청권", "강원권", "전라권", "경상권", "제주도"]
GENDER_OPTIONS = ["남성", "여성", "기타", "응답하지 않음"]


# ──────────────────────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def get_dev_mode() -> bool:
    try:
        return str(st.query_params.get("dev", "0")) == "1"
    except Exception:
        return False


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


def to_b64_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def normalize_phone(phone: str) -> str:
    value = (phone or "").strip().replace(" ", "")
    value = re.sub(r"[^0-9-]", "", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def validate_name(name: str) -> Optional[str]:
    return None if (name or "").strip() else "이름을 입력해 주세요."


def validate_gender(gender: str) -> Optional[str]:
    if not (gender or "").strip():
        return "성별을 선택해 주세요."
    if gender not in GENDER_OPTIONS:
        return "성별을 다시 선택해 주세요."
    return None


def validate_age(age: str) -> Optional[str]:
    value = (age or "").strip()
    if not value:
        return "연령을 입력해 주세요."
    if not value.isdigit():
        return "연령은 숫자로 입력해 주세요."
    age_num = int(value)
    if age_num < 1 or age_num > 120:
        return "연령은 1세 이상 120세 이하로 입력해 주세요."
    return None


def validate_region(region: str) -> Optional[str]:
    if not (region or "").strip():
        return "거주지역을 선택해 주세요."
    if region not in REGION_OPTIONS:
        return "거주지역을 다시 선택해 주세요."
    return None


def validate_phone(phone: str) -> Optional[str]:
    value = (phone or "").strip()
    if not value:
        return None
    if not re.fullmatch(r"[0-9-]+", value):
        return "휴대폰번호는 숫자와 하이픈(-)만 입력해 주세요."
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) not in (10, 11):
        return "휴대폰번호는 숫자 기준 10자리 또는 11자리여야 합니다."
    return None


def validate_email(email: str) -> Optional[str]:
    value = (email or "").strip()
    if not value:
        return None
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    if not re.match(pattern, value):
        return "이메일 형식이 올바르지 않습니다."
    return None


# ──────────────────────────────────────────────────────────────────────────────
# 상태
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
            "phone": "",
            "email": "",
        }
    if "task_payload" not in st.session_state:
        st.session_state.task_payload = None
    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False


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
        "phone": "",
        "email": "",
    }
    st.session_state.task_payload = None
    st.session_state.db_insert_done = False


# ──────────────────────────────────────────────────────────────────────────────
# CSS: Streamlit 외곽 UI 고정
# ──────────────────────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  color-scheme: dark !important;
  --bg: #06101f;
  --surface: #0b1a33;
  --surface-2: #0d2140;
  --surface-3: #10284c;
  --line: rgba(148, 163, 184, 0.28);
  --line-strong: rgba(96, 165, 250, 0.48);
  --text: #f8fbff;
  --muted: #c7d3e3;
  --muted-2: #9fb2c8;
  --primary: #4f9cff;
  --primary-2: #7bb7ff;
  --success: #56e39a;
  --warning: #ffcc66;
  --danger: #ff7373;
  --card-radius: 24px;
  --shadow: 0 18px 42px rgba(2, 8, 23, 0.36);
  --content-max-width: 920px;
}

html, body, .stApp {
  background:
    radial-gradient(circle at top left, rgba(79,156,255,.10), transparent 32%),
    radial-gradient(circle at bottom right, rgba(86,227,154,.06), transparent 34%),
    linear-gradient(180deg, #06101f 0%, #071225 100%) !important;
  color: var(--text) !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif !important;
  letter-spacing: -0.01em;
}

.block-container {
  max-width: var(--content-max-width) !important;
  padding-top: 0.8rem !important;
  padding-bottom: 2.4rem !important;
  overflow: visible !important;
}

header[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer, div[data-testid="stDecoration"] {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
}

.k-wrap { width: min(100%, var(--content-max-width)); margin: 0 auto; }
.k-card {
  background: linear-gradient(180deg, rgba(255,255,255,.022), rgba(255,255,255,.006)), var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--card-radius);
  box-shadow: var(--shadow);
  padding: 24px;
  margin-bottom: 16px;
}
.k-hero {
  background:
    radial-gradient(circle at top right, rgba(86,227,154,.10), transparent 30%),
    linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.006)), var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: 28px;
  box-shadow: var(--shadow);
  padding: 30px 28px;
  margin-bottom: 18px;
}
.k-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 850;
  color: #b9dcff;
  border: 1px solid rgba(79,156,255,.28);
  background: rgba(79,156,255,.14);
  margin: 0 6px 8px 0;
}
.k-title {
  margin: 0;
  color: var(--text) !important;
  font-size: clamp(28px, 4vw, 42px);
  line-height: 1.15;
  font-weight: 950;
  letter-spacing: -0.05em;
}
.k-title-md {
  margin: 0 0 8px;
  color: var(--text) !important;
  font-size: clamp(20px, 3vw, 26px);
  line-height: 1.25;
  font-weight: 900;
}
.k-text, .k-text p, .k-card p, .k-card li {
  color: var(--muted) !important;
  font-size: 15px;
  line-height: 1.75;
}
.k-list { margin: 12px 0 0; padding-left: 1.1rem; display: grid; gap: 8px; }
.k-note {
  background: rgba(79,156,255,.08);
  border: 1px dashed rgba(79,156,255,.26);
  border-radius: 16px;
  padding: 14px 16px;
  color: var(--muted) !important;
  line-height: 1.7;
}
.k-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.k-mini {
  background: rgba(16,40,76,.74);
  border: 1px solid rgba(96,165,250,.28);
  border-radius: 18px;
  padding: 16px;
}
.k-mini-title { color: var(--text); font-weight: 900; margin-bottom: 6px; }
.k-mini-copy { color: var(--muted); font-size: 13px; line-height: 1.6; }

/* Streamlit widgets */
div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stCheckbox"] label,
div[data-testid="stTextInput"] [data-testid="stWidgetLabel"] *,
div[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] *,
div[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] * {
  color: var(--text) !important;
  font-weight: 750 !important;
  opacity: 1 !important;
  -webkit-text-fill-color: var(--text) !important;
}

/* 입력창 하단 잘림 방지: Streamlit/BaseWeb 래퍼와 실제 input을 모두 같은 높이로 고정 */
div[data-testid="stTextInput"],
div[data-testid="stSelectbox"] {
  margin-bottom: 18px !important;
  overflow: visible !important;
}
div[data-testid="stTextInput"] > div,
div[data-testid="stSelectbox"] > div {
  overflow: visible !important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stTextInput"] div[data-baseweb="base-input"],
div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
  min-height: 56px !important;
  height: 56px !important;
  display: flex !important;
  align-items: center !important;
  box-sizing: border-box !important;
  background: var(--surface-3) !important;
  color: var(--text) !important;
  border: 1px solid rgba(96,165,250,.52) !important;
  border-radius: 14px !important;
  box-shadow: none !important;
  overflow: visible !important;
  -webkit-text-fill-color: var(--text) !important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stTextInput"] textarea {
  min-height: 54px !important;
  height: 54px !important;
  line-height: normal !important;
  display: block !important;
  box-sizing: border-box !important;
  padding: 0 16px 1px 16px !important;
  margin: 0 !important;
  background: transparent !important;
  color: var(--text) !important;
  border: 0 !important;
  outline: 0 !important;
  box-shadow: none !important;
  overflow: visible !important;
  -webkit-text-fill-color: var(--text) !important;
  font-weight: 700 !important;
}
div[data-testid="stTextInput"] input::placeholder { color: var(--muted-2) !important; opacity: 1 !important; }
div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
div[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
  border-color: rgba(123,183,255,.95) !important;
  box-shadow: 0 0 0 3px rgba(79,156,255,.18) !important;
}
div[data-testid="stSelectbox"] [data-baseweb="select"] span,
div[data-testid="stSelectbox"] [data-baseweb="select"] div,
div[data-testid="stSelectbox"] [data-baseweb="select"] input,
div[data-testid="stSelectbox"] [data-baseweb="select"] svg {
  color: var(--text) !important;
  fill: var(--text) !important;
  -webkit-text-fill-color: var(--text) !important;
  opacity: 1 !important;
}

div[data-baseweb="popover"] [role="listbox"], div[role="listbox"] {
  background: var(--surface-2) !important;
  border: 1px solid rgba(96,165,250,.42) !important;
  border-radius: 14px !important;
  box-shadow: var(--shadow) !important;
}
div[role="option"], li[role="option"] {
  background: transparent !important;
  color: var(--text) !important;
  min-height: 44px !important;
}
div[role="option"] *, li[role="option"] * { color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; }
div[role="option"]:hover, div[role="option"][aria-selected="true"] { background: rgba(79,156,255,.16) !important; }

.stButton > button {
  width: 100% !important;
  min-height: 48px !important;
  border-radius: 14px !important;
  border: 1px solid rgba(96,165,250,.44) !important;
  background: var(--surface-3) !important;
  color: var(--text) !important;
  font-weight: 850 !important;
  box-shadow: none !important;
  transition: .18s ease !important;
}
.stButton > button * { color: inherit !important; -webkit-text-fill-color: inherit !important; }
.stButton > button:hover { background: #163864 !important; border-color: rgba(123,183,255,.94) !important; transform: translateY(-1px); }
.stButton > button[kind="primary"] {
  background: linear-gradient(180deg, #1d5fa8 0%, #164a84 100%) !important;
  color: #ffffff !important;
  border-color: rgba(123,183,255,.98) !important;
  box-shadow: 0 0 0 1px rgba(79,156,255,.28), 0 8px 18px rgba(79,156,255,.18) !important;
}
.stButton > button:disabled { opacity: .52 !important; cursor: not-allowed !important; transform: none !important; }

[data-testid="stCheckbox"] p, [data-testid="stCheckbox"] span { color: var(--text) !important; opacity: 1 !important; }
[data-testid="stCheckbox"] svg { color: var(--primary) !important; }
[data-testid="stAlert"] { border-radius: 16px !important; background: rgba(255,115,115,.14) !important; border: 1px solid rgba(255,115,115,.28) !important; }
[data-testid="stAlert"] * { color: #ffd6d6 !important; }

.result-score-card {
  background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.01)), var(--surface);
  border: 1px solid rgba(96,165,250,.34);
  border-radius: 22px;
  padding: 20px;
  box-shadow: var(--shadow);
}
.score-big { font-size: 56px; font-weight: 950; letter-spacing: -0.06em; color: var(--text); line-height: .95; }
.score-unit { font-size: 18px; font-weight: 850; color: var(--muted); margin-left: 4px; }
.score-label { color: var(--primary-2); font-size: 13px; font-weight: 850; margin-bottom: 8px; }
.score-desc { color: var(--muted); font-size: 14px; line-height: 1.65; margin-top: 8px; }
.meter { height: 10px; background: rgba(255,255,255,.06); border: 1px solid rgba(148,163,184,.22); border-radius: 999px; overflow: hidden; margin-top: 12px; }
.meter > span { display:block; height:100%; background: linear-gradient(90deg, #3b82f6, #56e39a); width: var(--w); }
.task-table { width: 100%; border-collapse: separate; border-spacing: 0 10px; }
.task-table th { color: var(--muted-2); font-size: 12px; text-align: left; padding: 0 10px; }
.task-table td { background: rgba(16,40,76,.78); color: var(--text); padding: 12px 10px; border-top: 1px solid rgba(96,165,250,.22); border-bottom: 1px solid rgba(96,165,250,.22); }
.task-table td:first-child { border-left: 1px solid rgba(96,165,250,.22); border-radius: 14px 0 0 14px; font-weight: 850; }
.task-table td:last-child { border-right: 1px solid rgba(96,165,250,.22); border-radius: 0 14px 14px 0; }

@media (max-width: 720px) {
  .block-container { padding-left: .8rem !important; padding-right: .8rem !important; }
  .k-card, .k-hero { padding: 20px; border-radius: 20px; }
  .k-grid { grid-template-columns: 1fr; }
  .score-big { font-size: 46px; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Streamlit JS Component 생성
# ──────────────────────────────────────────────────────────────────────────────
COMPONENT_NAME = "kirbs_cog_arcade_3tasks_v13"
COMPONENT_DIR = Path(tempfile.gettempdir()) / COMPONENT_NAME


COMPONENT_HTML = r"""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
:root {
  color-scheme: dark;
  --bg: #071225;
  --surface: #0b1a33;
  --surface2: #0d2140;
  --surface3: #10284c;
  --line: rgba(148, 163, 184, 0.28);
  --line2: rgba(96, 165, 250, 0.45);
  --text: #f8fbff;
  --muted: #c7d3e3;
  --muted2: #9fb2c8;
  --blue: #4f9cff;
  --blue2: #7bb7ff;
  --green: #56e39a;
  --yellow: #ffcc66;
  --red: #ff7373;
  --purple: #b78cff;
  --gold: #ffe08a;
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background:
    radial-gradient(circle at top left, rgba(79,156,255,.08), transparent 32%),
    radial-gradient(circle at bottom right, rgba(86,227,154,.05), transparent 34%),
    linear-gradient(180deg, #06101f 0%, #071225 100%);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
  letter-spacing: -0.01em;
  overflow: hidden;
}
button { font-family: inherit; }
.app {
  width: 100%;
  min-height: 0;
  padding: 0 2px 0;
  background:
    radial-gradient(circle at top left, rgba(79,156,255,.08), transparent 32%),
    radial-gradient(circle at bottom right, rgba(86,227,154,.05), transparent 34%),
    linear-gradient(180deg, #06101f 0%, #071225 100%);
}
.card {
  background: linear-gradient(180deg, rgba(255,255,255,.020), rgba(255,255,255,.006)), var(--surface);
  border: 1px solid var(--line);
  border-radius: 24px;
  box-shadow: 0 18px 42px rgba(2, 8, 23, 0.34);
  padding: 24px;
  margin: 0 0 16px;
}
.hud { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.badge, .pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 12px; border-radius: 999px;
  background: rgba(79,156,255,.16); border: 1px solid rgba(79,156,255,.28);
  color: #b9dcff; font-weight: 900; font-size: 12px;
}
.pill.green { background:rgba(86,227,154,.12); border-color:rgba(86,227,154,.30); color:#c8ffe4; }
.pill.gold { background:rgba(255,224,138,.13); border-color:rgba(255,224,138,.30); color:#ffeeb8; }
.title {
  margin: 14px 0 8px; color: #fff;
  font-size: clamp(30px, 5vw, 44px); line-height: 1.12;
  font-weight: 950; letter-spacing: -0.055em;
  text-shadow: 0 2px 0 rgba(255,100,70,.34);
}
.subtitle { color: var(--blue2); font-weight: 900; margin-bottom: 6px; }
.copy { color: var(--muted); line-height: 1.68; font-size: 15px; }
.note { color: var(--muted2); font-size: 13px; line-height:1.55; }
.progress-row { display:flex; align-items:center; justify-content:space-between; margin-top: 16px; color:#fff; font-size: 13px; font-weight:900; }
.progress { height: 10px; background: rgba(255,255,255,.05); border: 1px solid rgba(148,163,184,.24); border-radius:999px; overflow:hidden; margin-top:8px; }
.progress > span { display:block; height:100%; width:var(--w); background: linear-gradient(90deg, #4f9cff, #56e39a); transition: width .25s ease; }

.status-grid { display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 14px; }
.status { background:rgba(255,255,255,.045); border:1px solid rgba(148,163,184,.20); border-radius:14px; padding:10px 11px; }
.status span { display:block; color:var(--muted2); font-size:11px; font-weight:800; }
.status strong { display:block; color:#fff; font-size:18px; margin-top:2px; }

.game-board {
  min-height: 430px;
  display: flex; flex-direction: column; gap: 16px; align-items: center; justify-content: center;
  background:
    radial-gradient(circle at top right, rgba(86,227,154,.07), transparent 30%),
    radial-gradient(circle at bottom left, rgba(183,140,255,.06), transparent 28%),
    linear-gradient(180deg, rgba(16,40,76,.72), rgba(11,26,51,.90));
  border-color: rgba(96,165,250,.34);
  position: relative; overflow: hidden;
}
.game-board::before {
  content:""; position:absolute; inset:0;
  background-image:
    linear-gradient(rgba(123,183,255,.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(123,183,255,.045) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(circle at center, black 0%, transparent 74%);
  pointer-events:none;
}
.game-inner { position: relative; z-index: 1; width: 100%; }
.start-panel { text-align:center; max-width: 680px; margin: 0 auto; }
.start-icon { font-size: 58px; margin-bottom: 10px; filter: drop-shadow(0 12px 18px rgba(79,156,255,.16)); }
.start-title { font-size: clamp(26px, 4vw, 42px); line-height:1.2; font-weight:950; margin-bottom: 12px; color: #fff; }
.start-copy { color: var(--muted); line-height:1.75; }
.mission-row { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:10px; margin:18px auto 0; max-width:680px; }
.mission { background:rgba(16,40,76,.78); border:1px solid rgba(96,165,250,.24); border-radius:16px; padding:12px; text-align:left; }
.mission strong { color:#fff; display:block; font-size:14px; margin-bottom:4px; }
.mission span { color:var(--muted); font-size:12px; line-height:1.45; }

.primary-btn, .ghost-btn, .choice-btn, .tile, .dir-btn {
  border-radius: 16px; border: 1px solid rgba(96,165,250,.48);
  background: linear-gradient(180deg, #1b579a, #16477e);
  color: #fff; font-weight: 900; cursor: pointer;
  transition: transform .12s ease, border-color .12s ease, background .12s ease, box-shadow .12s ease;
  box-shadow: 0 8px 18px rgba(79,156,255,.16);
}
.primary-btn:hover, .choice-btn:hover, .tile:hover, .dir-btn:hover { transform: translateY(-1px); border-color: rgba(123,183,255,.95); box-shadow: 0 12px 24px rgba(79,156,255,.24); }
.primary-btn { min-width: 220px; padding: 15px 24px; font-size: 17px; margin-top: 18px; }
.ghost-btn { padding: 12px 18px; background: var(--surface3); box-shadow:none; }

.trail-board {
  position: relative;
  width: min(100%, 700px);
  height: 420px;
  margin: 0 auto;
  border-radius: 24px;
  overflow: hidden;
  background:
    radial-gradient(circle at 24% 20%, rgba(79,156,255,.14), transparent 26%),
    radial-gradient(circle at 76% 72%, rgba(86,227,154,.12), transparent 28%),
    linear-gradient(180deg, rgba(7,18,37,.64), rgba(16,40,76,.52));
  border: 1px solid rgba(96,165,250,.26);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.025), 0 16px 36px rgba(2,8,23,.18);
}
.trail-board::before {
  content:"";
  position:absolute;
  inset:0;
  background-image:
    linear-gradient(rgba(123,183,255,.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(123,183,255,.045) 1px, transparent 1px);
  background-size: 32px 32px;
  pointer-events:none;
}
.trail-svg { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; z-index:1; }
.trail-line {
  stroke: url(#trailGrad);
  stroke-width: 7;
  stroke-linecap: round;
  filter: drop-shadow(0 0 7px rgba(86,227,154,.26));
  stroke-dasharray: 900;
  stroke-dashoffset: 900;
  animation: drawLine .28s ease-out forwards;
}
@keyframes drawLine { to { stroke-dashoffset: 0; } }
.trail-node {
  position:absolute;
  width: 56px;
  height: 56px;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  z-index: 2;
  border: 2px solid rgba(123,183,255,.72);
  background:
    radial-gradient(circle at 34% 24%, rgba(255,255,255,.95) 0 9%, transparent 10%),
    linear-gradient(180deg, #1e66b2, #123968);
  color:#fff;
  font-size: 21px;
  font-weight: 950;
  display:grid;
  place-items:center;
  cursor:pointer;
  box-shadow: 0 12px 24px rgba(79,156,255,.22), inset 0 -8px 18px rgba(2,8,23,.22);
  transition: transform .12s ease, border-color .12s ease, box-shadow .12s ease, opacity .12s ease;
}
.trail-node:hover { transform: translate(-50%, -50%) scale(1.06); border-color: rgba(255,255,255,.88); box-shadow: 0 16px 30px rgba(79,156,255,.30), inset 0 -8px 18px rgba(2,8,23,.22); }
.trail-node.done {
  background:
    radial-gradient(circle at 34% 24%, rgba(255,255,255,.96) 0 9%, transparent 10%),
    linear-gradient(180deg, #45d689, #1b8b59);
  border-color: rgba(186,248,212,.86);
  color:#062416;
  transform: translate(-50%, -50%) scale(.88);
  opacity:.82;
}
.trail-node.current {
  border-color: rgba(255,224,138,.96);
  box-shadow: 0 0 0 6px rgba(255,224,138,.10), 0 16px 32px rgba(255,224,138,.18), inset 0 -8px 18px rgba(2,8,23,.22);
}
.trail-node.wrong { animation: wrongNode .24s ease; border-color: var(--red); }
@keyframes wrongNode { 0%,100% { transform: translate(-50%, -50%); } 35% { transform: translate(calc(-50% - 6px), -50%); } 70% { transform: translate(calc(-50% + 6px), -50%); } }
.target-chip { display:inline-flex; align-items:center; justify-content:center; min-width: 88px; padding: 10px 14px; border-radius:999px; background:rgba(86,227,154,.13); border:1px solid rgba(86,227,154,.32); color:#c8ffe4; font-weight:950; }
.target-chip.muted { background:rgba(255,224,138,.12); border-color:rgba(255,224,138,.34); color:#ffeeb8; }
.trail-guide { color: var(--muted2); font-size: 13px; line-height: 1.5; text-align:center; margin: 10px 0 14px; }

.stimulus { font-size: clamp(78px, 18vw, 142px); font-weight: 950; line-height:1; text-align:center; color:#fff; text-shadow: 0 12px 28px rgba(2,8,23,.30); }
.stimulus.small { font-size: clamp(54px, 12vw, 90px); letter-spacing: .06em; }
.choice-row { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; width: min(100%, 560px); margin: 22px auto 0; }
.choice-row.four { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.choice-btn, .dir-btn { min-height: 58px; padding: 12px; font-size: 17px; }
.score-strip { display:flex; gap:10px; flex-wrap:wrap; justify-content:center; margin: 14px 0 0; }
.score-chip { padding: 7px 11px; border-radius:999px; background:rgba(255,255,255,.06); border:1px solid rgba(148,163,184,.22); color: var(--muted); font-size:13px; font-weight:800; }
.score-chip.good { color:#c8ffe4; border-color:rgba(86,227,154,.30); background:rgba(86,227,154,.10); }
.score-chip.gold { color:#ffeeb8; border-color:rgba(255,224,138,.30); background:rgba(255,224,138,.10); }
.feedback { min-height: 28px; text-align:center; font-weight:900; color: var(--muted); }
.feedback.ok { color: var(--green); }
.feedback.bad { color: var(--red); }

.gaze-scene { display:flex; flex-direction:column; align-items:center; gap: 18px; }
.mascot-wrap {
  position:relative; width: 230px; height: 230px; border-radius: 50px;
  background: radial-gradient(circle at 30% 18%, #ffffff 0 7%, transparent 8%), linear-gradient(145deg, #7bb7ff, #4f9cff 48%, #2b6cb0);
  border: 2px solid rgba(255,255,255,.24);
  box-shadow: 0 28px 48px rgba(79,156,255,.26), inset 0 -14px 30px rgba(2,8,23,.20);
  display:flex; align-items:center; justify-content:center;
}
.mascot-wrap::before {
  content:"K"; position:absolute; top: 16px; left: 18px;
  width: 34px; height: 34px; border-radius: 12px;
  background: rgba(255,255,255,.18); color: rgba(255,255,255,.82);
  font-weight:950; display:grid; place-items:center;
}
.ear { position:absolute; width:42px; height:42px; border-radius:15px; top: -15px; background:#2b6cb0; border:2px solid rgba(255,255,255,.18); }
.ear.left { left: 34px; transform:rotate(-12deg); }
.ear.right { right: 34px; transform:rotate(12deg); }
.face-panel {
  width: 176px; height: 122px; border-radius: 34px;
  background: linear-gradient(180deg, #f8fbff, #dfeeff);
  box-shadow: inset 0 3px 12px rgba(15,39,71,.10);
  display:flex; align-items:center; justify-content:center; gap: 22px;
}
.eye { width: 50px; height: 50px; border-radius: 999px; background:#fff; border: 2px solid #cfe2f5; position:relative; box-shadow: inset 0 2px 6px rgba(15,39,71,.08); }
.pupil {
  position:absolute; width: 20px; height: 20px; border-radius:999px;
  background: radial-gradient(circle at 35% 30%, #ffffff 0 10%, #0f2747 11% 100%);
  left: 50%; top: 50%;
  transform: translate(calc(-50% + var(--px)), calc(-50% + var(--py)));
  transition: transform .12s ease;
}
.mouth { position:absolute; width: 46px; height: 18px; border-bottom: 5px solid rgba(15,39,71,.62); border-radius: 50%; bottom: 43px; left:50%; transform:translateX(-50%); }
.direction-label { color:#fff; font-weight:900; font-size:18px; }

.done-panel { text-align:center; max-width: 680px; margin: 0 auto; }
.done-title { font-size: clamp(30px, 5vw, 48px); font-weight:950; margin-bottom: 12px; }
.done-grid { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }
.done-mini { background:rgba(16,40,76,.72); border:1px solid rgba(96,165,250,.26); border-radius:18px; padding:14px; }
.done-mini strong { display:block; color:#fff; font-size: 24px; margin-bottom: 4px; }
.done-mini span { color: var(--muted); font-size: 12px; }

@media (max-width: 720px) {
  .card { padding: 20px; border-radius: 20px; }
  .game-board { min-height: 0; }
  .trail-board { height: 500px; border-radius: 20px; }
  .trail-node { width: 50px; height: 50px; font-size: 18px; }
  .choice-row.four { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .mission-row, .status-grid, .done-grid { grid-template-columns: 1fr; }
  .mascot-wrap { width: 200px; height: 200px; }
  .face-panel { width: 154px; height: 108px; }
}
</style>
</head>
<body>
<div id="root" class="app"></div>
<script>
const Streamlit = {
  setComponentReady: function(){ window.parent.postMessage({isStreamlitMessage:true, type:"streamlit:componentReady", apiVersion:1}, "*"); },
  setFrameHeight: function(height){ window.parent.postMessage({isStreamlitMessage:true, type:"streamlit:setFrameHeight", height:height}, "*"); },
  setComponentValue: function(value){ window.parent.postMessage({isStreamlitMessage:true, type:"streamlit:setComponentValue", value:value, dataType:"json"}, "*"); }
};

const root = document.getElementById('root');
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const mean = arr => arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : null;
const median = arr => {
  if (!arr.length) return null;
  const x = [...arr].sort((a,b)=>a-b);
  const m = Math.floor(x.length/2);
  return x.length % 2 ? x[m] : (x[m-1]+x[m])/2;
};
const shuffle = arr => {
  const a = [...arr];
  for (let i=a.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; }
  return a;
};
const round = (v, d=1) => (v === null || v === undefined || Number.isNaN(v)) ? null : Number(v.toFixed(d));

let state = {
  taskIndex: 0,
  phase: 'start',
  startedAt: new Date().toISOString(),
  finishedAt: null,
  records: [],
  summaries: {},
  overall: null,
  domains: {},
  combo: 0,
  bestCombo: 0,
  totalXp: 0,
  stars: 0,
  feedback: '',
  feedbackClass: '',
  taskState: {}
};

const tasks = [
  {key:'trail', title:'Trail 연결 챌린지', sub:'시각 탐색 · 처리속도 · 주의전환', desc:'무작위로 나타나는 숫자 원을 단계별 규칙에 맞춰 연결합니다.', icon:'🧭'},
  {key:'gaze', title:'시선 포착 챌린지', sub:'시선 방향 판단 · 반응속도', desc:'KIRBIE의 눈동자가 바라보는 방향을 빠르게 선택합니다.', icon:'🤖'},
  {key:'flanker', title:'화살표 집중 챌린지', sub:'선택적 주의 · 간섭 억제', desc:'양옆 화살표는 무시하고 가운데 화살표의 방향만 판단합니다.', icon:'↔️'}
];

function setHeight(){
  setTimeout(()=>{
    const rect = root.getBoundingClientRect();
    const h = Math.max(20, Math.ceil(rect.height) + 2);
    Streamlit.setFrameHeight(h);
  }, 40);
}
function task(){ return tasks[state.taskIndex]; }
function updateGlobalXp(correct, rtMs=null){
  if(correct){
    state.combo += 1;
    state.bestCombo = Math.max(state.bestCombo, state.combo);
    const speedBonus = rtMs ? clamp(Math.round((900-rtMs)/90), 0, 5) : 0;
    state.totalXp += 10 + Math.min(state.combo, 10) + speedBonus;
  } else {
    state.combo = 0;
    state.totalXp = Math.max(0, state.totalXp - 2);
  }
}
function taskProgress(){
  const k = task().key;
  const ts = state.taskState[k] || {};
  if (k === 'trail') {
    const seqLen = ts.seq ? ts.seq.length : 1;
    const stageBase = ts.stage === 2 ? 0.5 : 0;
    return stageBase + ((ts.index || 0) / seqLen) * 0.5;
  }
  return (ts.index || 0) / (ts.trials ? ts.trials.length : 1);
}
function headerHtml(){
  const t = task();
  const p = Math.round(taskProgress()*100);
  return `
  <div class="card">
    <div class="hud">
      <div>
        <span class="badge">MISSION ${state.taskIndex+1} / ${tasks.length}</span>
        <span class="pill green">Easy Arcade</span>
        <h1 class="title">${t.title}</h1>
        <div class="subtitle">${t.sub}</div>
        <div class="copy">${t.desc}</div>
      </div>
      <div class="note">반응시간은 브라우저 내부 시간<br>performance.now() 기준으로 기록됩니다.</div>
    </div>
    <div class="status-grid">
      <div class="status"><span>XP</span><strong>${state.totalXp}</strong></div>
      <div class="status"><span>현재 콤보</span><strong>${state.combo}</strong></div>
      <div class="status"><span>최고 콤보</span><strong>${state.bestCombo}</strong></div>
      <div class="status"><span>진행률</span><strong>${p}%</strong></div>
    </div>
    <div class="progress"><span style="--w:${p}%"></span></div>
  </div>`;
}
function render(){
  if (state.phase === 'done') { renderDone(); return; }
  root.innerHTML = headerHtml() + `<div class="card game-board"><div class="game-inner" id="game"></div></div>`;
  const game = document.getElementById('game');
  if (state.phase === 'start') {
    const t = task();
    game.innerHTML = `<div class="start-panel"><div class="start-icon">${t.icon}</div><div class="start-title">${t.title}</div><div class="start-copy">${t.desc}<br>정확도를 우선하고, 익숙해지면 빠르게 반응해 주세요.</div><div class="mission-row"><div class="mission"><strong>3단계 Trail</strong><span>순차, 짝수-홀수, 역순 규칙으로 진행합니다.</span></div><div class="mission"><strong>부분 힌트</strong><span>각 단계의 시작 2개만 힌트로 표시됩니다.</span></div><div class="mission"><strong>경로 연결</strong><span>정답 클릭마다 선이 이어집니다.</span></div></div><button class="primary-btn" onclick="startCurrentTask()">미션 시작</button></div>`;
  } else {
    const k = task().key;
    if (k==='trail') renderTrail(game);
    if (k==='gaze') renderGaze(game);
    if (k==='flanker') renderFlanker(game);
  }
  setHeight();
}
function nextTask(){
  state.taskIndex += 1;
  state.phase = 'start';
  state.feedback = '';
  state.feedbackClass = '';
  state.combo = 0;
  if (state.taskIndex >= tasks.length) finishAll();
  else render();
}
function completeTask(){
  const k = task().key;
  state.summaries[k] = summarizeTask(k);
  state.stars += starFromScore(state.summaries[k].score);
  nextTask();
}
function startCurrentTask(){
  state.phase = 'play';
  state.feedback = '';
  state.feedbackClass = '';
  state.combo = 0;
  const k = task().key;
  if (k==='trail') initTrail();
  if (k==='gaze') initGaze();
  if (k==='flanker') initFlanker();
  render();
}

// Trail: 숫자 원형 노드를 무작위 좌표에 배치하고, 정답 클릭 시 직선 연결 애니메이션을 표시함
function buildTrailSequence(stage){
  if(stage === 1) return Array.from({length:10}, (_,i)=>String(i+1));
  if(stage === 2) return [2,4,6,8,10,12,1,3,5,7,9,11].map(String);
  return Array.from({length:12}, (_,i)=>String(12-i));
}
function trailStageTitle(stage){
  if(stage === 1) return '1단계: 1부터 10까지 순서대로';
  if(stage === 2) return '2단계: 짝수 오름차순 후 홀수 오름차순';
  return '3단계: 12부터 1까지 거꾸로';
}
function trailStageStartMessage(stage){
  if(stage === 1) return '1단계 시작!';
  if(stage === 2) return '짝수 우선 단계 시작!';
  return '역순 단계 시작!';
}
function getTrailCanvasSize(){
  const fallbackWidth = Math.min(700, Math.max(320, window.innerWidth - 46));
  const measuredWidth = root && root.clientWidth ? root.clientWidth - 6 : fallbackWidth;
  const canvasW = Math.round(clamp(Math.min(700, measuredWidth), 300, 700));
  const canvasH = window.innerWidth <= 720 ? 500 : 430;
  return {canvasW, canvasH};
}
function generateTrailNodes(seq, canvasW, canvasH){
  const nodeSize = window.innerWidth <= 720 ? 50 : 56;
  const margin = Math.max(34, nodeSize * .78);
  const minDist = nodeSize + (seq.length >= 12 ? 14 : 18);
  const nodes = [];
  for(const label of seq){
    let placed = false;
    for(let attempt=0; attempt<1600; attempt++){
      const x = margin + Math.random() * (canvasW - margin*2);
      const y = margin + Math.random() * (canvasH - margin*2);
      const ok = nodes.every(n => Math.hypot(n.x - x, n.y - y) >= minDist);
      if(ok){ nodes.push({label, x:round(x,1), y:round(y,1)}); placed = true; break; }
    }
    if(!placed){
      const cols = canvasW < 420 ? 3 : 4;
      const rows = Math.ceil(seq.length / cols);
      const idx = nodes.length;
      const cellW = (canvasW - margin*2) / cols;
      const cellH = (canvasH - margin*2) / rows;
      const jitterX = (Math.random() - .5) * Math.min(16, cellW*.16);
      const jitterY = (Math.random() - .5) * Math.min(16, cellH*.16);
      nodes.push({label, x:round(margin + (idx % cols + .5) * cellW + jitterX,1), y:round(margin + (Math.floor(idx / cols) + .5) * cellH + jitterY,1)});
    }
  }
  return shuffle(nodes);
}
function resetTrailStage(stage){
  const seq = buildTrailSequence(stage);
  const now = performance.now();
  const {canvasW, canvasH} = getTrailCanvasSize();
  return {stage, seq, canvasW, canvasH, nodes:generateTrailNodes(seq, canvasW, canvasH), index:0, stageStart:now, last:now, errors:0, stageTimes:{}};
}
function initTrail(){
  state.taskState.trail = resetTrailStage(1);
  state.feedback = trailStageStartMessage(1);
  state.feedbackClass = 'ok';
}
function renderTrail(game){
  const ts = state.taskState.trail;
  const target = ts.seq[ts.index];
  const nodeByLabel = Object.fromEntries(ts.nodes.map(n => [n.label, n]));
  const completedLabels = ts.seq.slice(0, ts.index);
  const hintLabels = ts.seq.slice(0, 2);
  const showHint = ts.index < 2;
  const lines = [];
  for(let i=1; i<completedLabels.length; i++){
    const a = nodeByLabel[completedLabels[i-1]];
    const b = nodeByLabel[completedLabels[i]];
    if(a && b){ lines.push(`<line class="trail-line" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" style="animation-delay:${Math.min(i*24, 160)}ms"></line>`); }
  }
  const hintHtml = showHint
    ? `<span class="target-chip">시작 힌트: ${hintLabels.join(' → ')}</span>`
    : `<span class="target-chip muted">힌트 종료 · 다음 숫자는 직접 찾기</span>`;
  game.innerHTML = `
    <div style="text-align:center;margin-bottom:8px;">${hintHtml}</div>
    <div class="trail-guide"><b>${trailStageTitle(ts.stage)}</b><br>원은 매번 다른 위치에 나타납니다. 각 단계의 시작 2개만 표시되고 이후 순서는 직접 찾아야 합니다.</div>
    <div class="trail-board">
      <svg class="trail-svg" viewBox="0 0 ${ts.canvasW} ${ts.canvasH}" preserveAspectRatio="none" aria-hidden="true">
        <defs><linearGradient id="trailGrad" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#4f9cff"/><stop offset="100%" stop-color="#56e39a"/></linearGradient></defs>
        ${lines.join('')}
      </svg>
      ${ts.nodes.map(n => {
        const done = completedLabels.includes(n.label);
        const current = showHint && n.label === target;
        return `<button class="trail-node ${done ? 'done' : ''} ${current ? 'current' : ''}" style="left:${(n.x/ts.canvasW)*100}%; top:${(n.y/ts.canvasH)*100}%;" onclick="trailClick('${n.label}', this)" aria-label="${n.label} 원">${n.label}</button>`;
      }).join('')}
    </div>
    <div class="score-strip"><span class="score-chip">레벨 ${ts.stage} / 3</span><span class="score-chip">오류 ${ts.errors}</span><span class="score-chip good">콤보 ${state.combo}</span></div>
    <div class="feedback ${state.feedbackClass}">${state.feedback || '&nbsp;'}</div>`;
}
function trailClick(value, el){
  const ts = state.taskState.trail;
  const target = ts.seq[ts.index];
  const now = performance.now();
  const correct = value === target;
  const delta = now - ts.last;
  const clickedNode = ts.nodes.find(n => n.label === value) || null;
  state.records.push({
    task:'trail', stage:ts.stage, stage_rule:trailStageTitle(ts.stage), target, response:value, order:ts.index+1,
    node_x: clickedNode ? clickedNode.x : null, node_y: clickedNode ? clickedNode.y : null,
    rt_ms:round(now-ts.stageStart,1), delta_ms:round(delta,1), correct
  });
  ts.last = now;
  updateGlobalXp(correct, delta);
  if(correct){
    ts.index += 1;
    state.feedback = ts.index >= 2 ? '경로 연결!' : '좋아요!';
    state.feedbackClass = 'ok';
    if(ts.index >= ts.seq.length){
      ts.stageTimes[`stage_${ts.stage}_ms`] = round(now-ts.stageStart,1);
      if(ts.stage < 3){
        const nextStage = ts.stage + 1;
        const prevTimes = {...ts.stageTimes};
        const prevErrors = ts.errors;
        state.taskState.trail = resetTrailStage(nextStage);
        state.taskState.trail.stageTimes = prevTimes;
        state.taskState.trail.errors = prevErrors;
        state.feedback = trailStageStartMessage(nextStage); state.feedbackClass = 'ok';
      } else { completeTask(); return; }
    }
  } else {
    ts.errors += 1;
    state.feedback = ts.index < 2 ? `시작 힌트를 다시 확인하세요` : '순서를 다시 확인하세요';
    state.feedbackClass = 'bad';
    if(el){ el.classList.add('wrong'); setTimeout(()=>el.classList.remove('wrong'), 240); }
  }
  render();
}

// Gaze: 짧은 20시행, 네 방향 균형 배치
function initGaze(){
  const dirs=['up','down','left','right'];
  const trials=shuffle([...dirs,...dirs,...dirs,...dirs,...dirs]);
  state.taskState.gaze = {trials, index:0, onset:performance.now()};
}
function dirKo(d){ return {up:'위',down:'아래',left:'왼쪽',right:'오른쪽'}[d]; }
function arrowLabel(d){ return {up:'↑',down:'↓',left:'←',right:'→'}[d]; }
function pupil(d){ return {up:['0px','-12px'],down:['0px','12px'],left:['-12px','0px'],right:['12px','0px']}[d]; }
function renderGaze(game){
  const ts=state.taskState.gaze, d=ts.trials[ts.index];
  if(!d) { completeTask(); return; }
  const [px,py] = pupil(d);
  if(!ts.onset) ts.onset=performance.now();
  game.innerHTML = `<div class="gaze-scene"><div class="mascot-wrap"><div class="ear left"></div><div class="ear right"></div><div class="face-panel"><div class="eye"><span class="pupil" style="--px:${px};--py:${py}"></span></div><div class="eye"><span class="pupil" style="--px:${px};--py:${py}"></span></div></div><div class="mouth"></div></div><div class="direction-label">KIRBIE의 시선 방향은?</div><div class="choice-row four">${['up','down','left','right'].map(x=>`<button class="dir-btn" onclick="gazeAnswer('${x}')">${arrowLabel(x)} ${dirKo(x)}</button>`).join('')}</div><div class="score-strip"><span class="score-chip good">콤보 ${state.combo}</span><span class="score-chip gold">XP ${state.totalXp}</span><span class="score-chip">${ts.index+1} / ${ts.trials.length}</span></div><div class="feedback ${state.feedbackClass}">${state.feedback || '&nbsp;'}</div></div>`;
}
function gazeAnswer(resp){
  const ts=state.taskState.gaze, d=ts.trials[ts.index], now=performance.now();
  const rt = now-ts.onset;
  const correct = resp === d;
  updateGlobalXp(correct, rt);
  state.records.push({task:'gaze', trial:ts.index+1, target:d, response:resp, correct, rt_ms:round(rt,1)});
  state.feedback = correct ? '시선 포착!' : `정답은 ${dirKo(d)}`; state.feedbackClass = correct ? 'ok' : 'bad';
  ts.index += 1; ts.onset=performance.now();
  if(ts.index >= ts.trials.length) { completeTask(); return; }
  render();
}

// Flanker: 22시행, congruent 8 + incongruent 14. 너무 길지 않지만 오답이 나기 쉬운 구성
function initFlanker(){
  const trials=[];
  for(let i=0;i<8;i++){
    const target = Math.random()<.5 ? 'left' : 'right';
    const center = target==='left'?'←':'→';
    trials.push({level:1, condition:'congruent', stimulus:center+center+center+center+center, correct:target});
  }
  for(let i=0;i<14;i++){
    const target = Math.random()<.5 ? 'left' : 'right';
    const center = target==='left'?'←':'→';
    const flank = target==='left'?'→':'←';
    trials.push({level:2, condition:'incongruent', stimulus:flank+flank+center+flank+flank, correct:target});
  }
  state.taskState.flanker = {trials:shuffle(trials), index:0, onset:performance.now()};
}
function renderFlanker(game){
  const ts=state.taskState.flanker, tr=ts.trials[ts.index];
  if(!tr){ completeTask(); return; }
  if(!ts.onset) ts.onset=performance.now();
  game.innerHTML = `<div class="stimulus small">${tr.stimulus}</div><div class="copy" style="text-align:center;margin-top:16px;">가운데 화살표 방향만 선택하세요.</div><div class="choice-row"><button class="choice-btn" onclick="flankerAnswer('left')">← 왼쪽</button><button class="choice-btn" onclick="flankerAnswer('right')">오른쪽 →</button></div><div class="score-strip"><span class="score-chip">레벨 ${tr.level}</span><span class="score-chip good">콤보 ${state.combo}</span><span class="score-chip gold">XP ${state.totalXp}</span><span class="score-chip">${ts.index+1} / ${ts.trials.length}</span></div><div class="feedback ${state.feedbackClass}">${state.feedback || '&nbsp;'}</div>`;
}
function flankerAnswer(resp){
  const ts=state.taskState.flanker, tr=ts.trials[ts.index], now=performance.now();
  const rt = now-ts.onset;
  const correct = resp === tr.correct;
  updateGlobalXp(correct, rt);
  state.records.push({task:'flanker', trial:ts.index+1, level:tr.level, condition:tr.condition, stimulus:tr.stimulus, correct_response:tr.correct, response:resp, correct, rt_ms:round(rt,1)});
  state.feedback = correct ? '정답!' : '중앙 방향만 보세요'; state.feedbackClass = correct ? 'ok' : 'bad';
  ts.index += 1; ts.onset=performance.now();
  if(ts.index >= ts.trials.length) { completeTask(); return; }
  render();
}

document.addEventListener('keydown', (e)=>{
  if(state.phase !== 'play') return;
  const k=task().key;
  if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight',' '].includes(e.key)) e.preventDefault();
  if(k==='gaze'){
    const map={ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right'};
    if(map[e.key]) gazeAnswer(map[e.key]);
  }
  if(k==='flanker'){
    if(e.key==='ArrowLeft') flankerAnswer('left');
    if(e.key==='ArrowRight') flankerAnswer('right');
  }
});

function scoreFromAccuracyRt({accuracy, medianRt, refRt, accRef=0.86, accWeight=48, rtWeight=28, penalty=0}){
  const accPart = ((accuracy ?? 0) - accRef) * accWeight;
  const rtPart = medianRt ? ((refRt - medianRt) / refRt) * rtWeight : 0;
  return round(clamp(50 + accPart + rtPart - penalty, 20, 85),1);
}
function summarizeTask(k){
  const rec = state.records.filter(r=>r.task===k);
  if(k==='trail'){
    const s1 = rec.filter(r=>r.stage===1);
    const s2 = rec.filter(r=>r.stage===2);
    const s3 = rec.filter(r=>r.stage===3);
    const s1Sec = s1.length ? s1[s1.length-1].rt_ms/1000 : null;
    const s2Sec = s2.length ? s2[s2.length-1].rt_ms/1000 : null;
    const s3Sec = s3.length ? s3[s3.length-1].rt_ms/1000 : null;
    const errors = rec.filter(r=>!r.correct).length;
    const totalSec = (s1Sec||0) + (s2Sec||0) + (s3Sec||0);
    const refSec = 58;
    const speedPart = ((refSec - totalSec) / refSec) * 34;
    const score = round(clamp(50 + speedPart - errors*3.4, 20, 85),1);
    return {score, level1_sec:round(s1Sec,2), level2_sec:round(s2Sec,2), level3_sec:round(s3Sec,2), total_sec:round(totalSec,2), errors, criterion:'50점=임시 내부 기준점'};
  }
  if(k==='gaze'){
    const acc = mean(rec.map(r=>r.correct?1:0));
    const med = median(rec.filter(r=>r.correct).map(r=>r.rt_ms).filter(x=>x!==null));
    const score = scoreFromAccuracyRt({accuracy:acc, medianRt:med, refRt:820, accRef:.86, accWeight:46, rtWeight:30});
    return {score, accuracy:round(acc,3), median_rt_ms:round(med,1), criterion:'50점=임시 내부 기준점'};
  }
  if(k==='flanker'){
    const acc = mean(rec.map(r=>r.correct?1:0));
    const med = median(rec.filter(r=>r.correct).map(r=>r.rt_ms).filter(x=>x!==null));
    const con = rec.filter(r=>r.correct && r.condition==='congruent').map(r=>r.rt_ms);
    const incon = rec.filter(r=>r.correct && r.condition==='incongruent').map(r=>r.rt_ms);
    const interference = (median(incon) !== null && median(con) !== null) ? median(incon)-median(con) : null;
    const penalty = Math.max(0, (interference || 0) - 140) * .023;
    const score = scoreFromAccuracyRt({accuracy:acc, medianRt:med, refRt:860, accRef:.88, accWeight:48, rtWeight:26, penalty});
    return {score, accuracy:round(acc,3), median_rt_ms:round(med,1), interference_ms:round(interference,1), criterion:'50점=임시 내부 기준점'};
  }
  return {};
}
function starFromScore(score){
  if(score === null || score === undefined) return 0;
  if(score >= 68) return 3;
  if(score >= 55) return 2;
  return 1;
}
function finishAll(){
  state.finishedAt = new Date().toISOString();
  const s=state.summaries;
  state.domains = {
    processing_speed: round(mean([s.trail?.score, s.gaze?.score, s.flanker?.score].filter(x=>x!==undefined && x!==null)),1),
    attention_shift: s.trail?.score ?? null,
    social_attention: s.gaze?.score ?? null,
    interference_control: s.flanker?.score ?? null
  };
  state.overall = round(mean(Object.values(state.domains).filter(x=>x!==null)),1);
  state.phase = 'done';
  const payload = {
    exam_name: 'KIRBS_COGNITIVE_ARCADE_3TASKS',
    exam_version: 'streamlit_component_arcade_3tasks_v1.2_trail_3stage',
    started_at: state.startedAt,
    finished_at: state.finishedAt,
    scoring_note: 'criterion-referenced transformed score; 50 = temporary internal reference point, not population percentile',
    task_set: ['trail','gaze','flanker'],
    removed_tasks: ['nback','go_nogo'],
    total_xp: state.totalXp,
    best_combo: state.bestCombo,
    stars: state.stars,
    summaries: state.summaries,
    domains: state.domains,
    overall_score: state.overall,
    records: state.records
  };
  Streamlit.setComponentValue(payload);
  renderDone();
}
function renderDone(){
  root.innerHTML = `<div class="card game-board"><div class="game-inner"><div class="done-panel"><div class="start-icon">🏁</div><div class="done-title">미션 완료!</div><div class="start-copy">응답 기록을 Streamlit 결과 화면으로 전달했습니다.<br>결과 화면으로 자동 전환됩니다.</div><div class="done-grid"><div class="done-mini"><strong>${state.overall ?? '-'}</strong><span>종합 환산점수</span></div><div class="done-mini"><strong>${state.totalXp}</strong><span>획득 XP</span></div><div class="done-mini"><strong>${state.stars}</strong><span>미션 별</span></div></div></div></div></div>`;
  setHeight();
}

Streamlit.setComponentReady();
setHeight();
if (window.ResizeObserver) new ResizeObserver(setHeight).observe(document.body);
render();
</script>
</body>
</html>
"""


def ensure_component_files() -> None:
    COMPONENT_DIR.mkdir(parents=True, exist_ok=True)
    index_file = COMPONENT_DIR / "index.html"
    if not index_file.exists() or index_file.read_text(encoding="utf-8") != COMPONENT_HTML:
        index_file.write_text(COMPONENT_HTML, encoding="utf-8")


ensure_component_files()
_cog_component = components.declare_component(COMPONENT_NAME, path=str(COMPONENT_DIR))


def run_cognitive_component(key: str) -> Optional[Dict[str, Any]]:
    value = _cog_component(key=key, default=None)
    return value


# ──────────────────────────────────────────────────────────────────────────────
# 페이지 렌더링
# ──────────────────────────────────────────────────────────────────────────────
def page_intro() -> None:
    st.markdown("<div class='k-wrap'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <section class="k-hero">
          <span class="k-badge">Cognitive Arcade</span>
          <span class="k-badge">3 Mini Games</span>
          <h1 class="k-title">{EXAM_TITLE}</h1>
          <p class="k-text" style="margin-top:12px;">{EXAM_SUBTITLE}<br>짧고 간편한 3개의 미니게임을 통해 현재의 처리속도, 시각 탐색, 시선 판단, 간섭 억제 경향을 확인합니다.</p>
        </section>
        <section class="k-card">
          <h2 class="k-title-md">검사 구성</h2>
          <div class="k-grid">
            <div class="k-mini"><div class="k-mini-title">🧭 Trail 연결 챌린지</div><div class="k-mini-copy">무작위 위치의 숫자 원을 3단계 규칙에 맞춰 연결합니다.</div></div>
            <div class="k-mini"><div class="k-mini-title">🤖 시선 포착 챌린지</div><div class="k-mini-copy">캐릭터 눈동자의 방향을 빠르게 판단합니다.</div></div>
            <div class="k-mini"><div class="k-mini-title">↔️ 화살표 집중 챌린지</div><div class="k-mini-copy">중앙 화살표에 집중해 간섭 정보를 억제합니다.</div></div>
          </div>
        </section>
        <section class="k-card">
          <h2 class="k-title-md">진행 전 안내</h2>
          <ul class="k-list k-text">
            <li>이 검사는 의학적·임상적 진단을 제공하지 않는 비진단적 인지 과제입니다.</li>
            <li>주의력의 3요소인 주의 집중, 전환, 억제를 테스트하기 위해 제작되었습니다.</li>
            <li>반응시간은 기기 성능, 브라우저, 화면 크기, 입력장치의 영향을 받을 수 있습니다.</li>
            <li>평가된 인지 능력은 현재까지 검사를 진행한 참여자 전체 평균 대비 능력을 표현하고 있습니다.</li>
          </ul>
          <div class="k-note" style="margin-top:14px;">검사 진행을 위해 이름, 성별, 연령, 거주지역 등 기본 정보를 입력받습니다. 휴대폰 번호와 이메일은 선택 입력 항목입니다.
          입력된 개인정보는 KIRBS+의 개인정보 관련 약관에 적용되며 약관에 따라 저장 및 활용될 수 있습니다.
          동의 후 검사 시작 시점과 동의 시점 정보가 기록되며, 이후 응답 내용은 결과 산출에 사용됩니다.</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    consent = st.checkbox(
        "검사 목적, 비진단적 성격, 반응시간 측정 방식, 비식별 데이터 활용 가능성에 대한 안내를 확인했습니다.",
        value=bool(st.session_state.meta.get("consent")),
    )
    st.session_state.meta["consent"] = consent
    c1, c2 = st.columns([2, 1])
    with c2:
        if st.button("검사 시작", type="primary", use_container_width=True, disabled=not consent):
            ts = now_iso()
            st.session_state.meta["consent_ts"] = ts
            st.session_state.meta["started_ts"] = ts
            st.session_state.page = "info"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def page_info() -> None:
    st.markdown("<div class='k-wrap'>", unsafe_allow_html=True)
    st.markdown(
        """
        <section class="k-card">
          <span class="k-badge">기본 정보</span>
          <h1 class="k-title-md">검사 대상자 정보</h1>
          <p class="k-text">이름, 성별, 연령, 거주지역은 필수 항목이며 휴대폰번호와 이메일은 선택 입력 항목입니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    gender_options = [""] + GENDER_OPTIONS
    region_options = [""] + REGION_OPTIONS

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        name = st.text_input("이름", value=st.session_state.examinee.get("name", ""), placeholder="이름을 입력해 주세요")
    with col2:
        current_gender = st.session_state.examinee.get("gender", "")
        gender = st.selectbox(
            "성별",
            options=gender_options,
            index=gender_options.index(current_gender) if current_gender in gender_options else 0,
            format_func=lambda x: "선택해 주세요" if x == "" else x,
        )
    col3, col4 = st.columns(2, gap="medium")
    with col3:
        age = st.text_input("연령", value=st.session_state.examinee.get("age", ""), placeholder="숫자만 입력")
    with col4:
        current_region = st.session_state.examinee.get("region", "")
        region = st.selectbox(
            "거주지역",
            options=region_options,
            index=region_options.index(current_region) if current_region in region_options else 0,
            format_func=lambda x: "선택해 주세요" if x == "" else x,
        )
    phone_input = st.text_input("휴대폰번호 (선택)", value=st.session_state.examinee.get("phone", ""), placeholder="010-0000-0000")
    email = st.text_input("이메일 (선택)", value=st.session_state.examinee.get("email", ""), placeholder="example@email.com")

    normalized_phone = normalize_phone(phone_input)
    st.session_state.examinee = {
        "name": name.strip(),
        "gender": gender.strip(),
        "age": age.strip(),
        "region": region.strip(),
        "phone": normalized_phone,
        "email": email.strip(),
    }

    errors = [
        validate_name(name),
        validate_gender(gender),
        validate_age(age),
        validate_region(region),
        validate_phone(normalized_phone),
        validate_email(email),
    ]
    errors = [e for e in errors if e]
    if errors:
        st.warning(" / ".join(errors))

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("이전", use_container_width=True):
            st.session_state.page = "intro"
            st.rerun()
    with c2:
        if st.button("다음", type="primary", use_container_width=True, disabled=bool(errors)):
            st.session_state.page = "task"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def page_task() -> None:
    st.markdown("<div class='k-wrap'>", unsafe_allow_html=True)
    st.markdown(
        """
        <section class="k-card">
          <span class="k-badge">실시간 미니게임</span>
          <h1 class="k-title-md">인지 미니게임 진행</h1>
          <p class="k-text">키보드와 마우스 모두 사용할 수 있습니다. 모든 미션 완료 즉시 결과 화면으로 자동 전환됩니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    component_value = run_cognitive_component(key=f"cog_arcade_{st.session_state.meta['respondent_id']}")
    if component_value and not st.session_state.task_payload:
        st.session_state.task_payload = component_value
        st.session_state.meta["submitted_ts"] = now_iso()
        st.session_state.page = "result"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def score_label(score: Optional[float]) -> str:
    if score is None:
        return "산출 불가"
    if score >= 65:
        return "강점"
    if score >= 55:
        return "양호"
    if score >= 45:
        return "기준 범위"
    if score >= 35:
        return "관찰 필요"
    return "주의"


def score_desc(score: Optional[float]) -> str:
    if score is None:
        return "응답 데이터가 충분하지 않아 산출하지 못했습니다."
    if score >= 65:
        return "정확성과 반응속도가 내부 기준점보다 높은 편으로 산출되었습니다."
    if score >= 55:
        return "정확성과 반응속도가 내부 기준점보다 다소 안정적으로 산출되었습니다."
    if score >= 45:
        return "정확성과 반응속도가 임시 내부 기준점 주변으로 산출되었습니다."
    if score >= 35:
        return "정확도 또는 반응속도 중 일부 지표에서 관찰이 필요한 범위로 산출되었습니다."
    return "정확도 저하나 반응시간 지연이 상대적으로 크게 반영되었습니다."


def fmt(v: Any, suffix: str = "") -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.1f}{suffix}"
    return f"{v}{suffix}"


def fmt_pct(raw_prop: Optional[float]) -> str:
    if raw_prop is None:
        return "-"
    return f"{raw_prop * 100:.1f}%"


def build_exam_data(payload: Dict[str, Any]) -> Dict[str, str]:
    meta_col = {
        "consent": st.session_state.meta.get("consent"),
        "consent_ts": st.session_state.meta.get("consent_ts"),
        "started_ts": st.session_state.meta.get("started_ts"),
        "submitted_ts": st.session_state.meta.get("submitted_ts"),
        "respondent_id": st.session_state.meta.get("respondent_id"),
        "version": EXAM_VERSION,
    }
    examinee_col = dict(st.session_state.examinee)
    answers_col = {
        "records_b64": to_b64_json(payload.get("records", [])),
        "summaries_b64": to_b64_json(payload.get("summaries", {})),
        "domains_b64": to_b64_json(payload.get("domains", {})),
        "task_set": ";".join(payload.get("task_set", [])),
    }
    result_col = {
        "overall_score": payload.get("overall_score"),
        "overall_label": score_label(payload.get("overall_score")),
        "processing_speed": (payload.get("domains", {}) or {}).get("processing_speed"),
        "attention_shift": (payload.get("domains", {}) or {}).get("attention_shift"),
        "social_attention": (payload.get("domains", {}) or {}).get("social_attention"),
        "interference_control": (payload.get("domains", {}) or {}).get("interference_control"),
        "total_xp": payload.get("total_xp"),
        "best_combo": payload.get("best_combo"),
        "stars": payload.get("stars"),
        "scoring_note": payload.get("scoring_note", ""),
    }
    return {
        "exam_name": EXAM_NAME,
        "consent_col": dict_to_kv_csv(meta_col),
        "examinee_col": dict_to_kv_csv(examinee_col),
        "answers_col": dict_to_kv_csv(answers_col),
        "result_col": dict_to_kv_csv(result_col),
    }


def page_result(dev_mode: bool = False) -> None:
    payload = st.session_state.task_payload
    if not payload:
        st.warning("결과 데이터가 없습니다. 검사를 다시 진행해 주세요.")
        if st.button("처음으로", type="primary"):
            reset_all()
            st.rerun()
        return

    exam_data = build_exam_data(payload)
    auto_db_insert(exam_data)

    domains = payload.get("domains", {}) or {}
    summaries = payload.get("summaries", {}) or {}
    overall = payload.get("overall_score")

    st.markdown("<div class='k-wrap'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <section class="k-hero">
          <span class="k-badge">Result</span>
          <span class="k-badge">3-Task Arcade</span>
          <h1 class="k-title">인지 미니게임 결과</h1>
          <p class="k-text" style="margin-top:12px;">본 점수는 현재 규준 데이터가 없는 초기 버전이므로 상대평가·백분위가 아닙니다. 50점은 인구 평균이 아니라 임시 내부 기준점입니다.</p>
        </section>
        <section class="result-score-card">
          <div class="score-label">종합 환산점수</div>
          <div><span class="score-big">{fmt(overall)}</span><span class="score-unit">점</span></div>
          <div class="meter" style="--w:{min(max(float(overall or 0), 0), 85)}%"><span></span></div>
          <div class="score-desc"><b>{score_label(overall)}</b> · {score_desc(overall)}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<section class='k-card'><h2 class='k-title-md'>게임형 지표</h2>", unsafe_allow_html=True)
    cols = st.columns(3)
    with cols[0]:
        st.metric("획득 XP", payload.get("total_xp", 0))
    with cols[1]:
        st.metric("최고 콤보", payload.get("best_combo", 0))
    with cols[2]:
        st.metric("미션 별", payload.get("stars", 0))
    st.markdown("</section>", unsafe_allow_html=True)

    st.markdown("<section class='k-card'><h2 class='k-title-md'>영역별 결과</h2>", unsafe_allow_html=True)
    cols = st.columns(4)
    domain_labels = [
        ("처리속도", domains.get("processing_speed")),
        ("주의전환", domains.get("attention_shift")),
        ("시선 판단", domains.get("social_attention")),
        ("간섭 억제", domains.get("interference_control")),
    ]
    for col, (label, score) in zip(cols, domain_labels):
        with col:
            st.metric(label, "-" if score is None else f"{float(score):.1f}점")
    st.markdown("</section>", unsafe_allow_html=True)

    trail = summaries.get("trail", {})
    gaze = summaries.get("gaze", {})
    flanker = summaries.get("flanker", {})

    rows = [
        ("Trail 연결", trail.get("score"), f"총 {fmt(trail.get('total_sec'), '초')}", f"오류 {trail.get('errors', '-')}") ,
        ("시선 방향", gaze.get("score"), f"정확률 {fmt_pct(gaze.get('accuracy'))}", f"중앙 RT {fmt(gaze.get('median_rt_ms'), 'ms')}") ,
        ("Flanker", flanker.get("score"), f"정확률 {fmt_pct(flanker.get('accuracy'))}", f"간섭 {fmt(flanker.get('interference_ms'), 'ms')}") ,
    ]
    table_rows = "".join(
        f"<tr><td>{name}</td><td>{fmt(score)}점</td><td>{a}</td><td>{b}</td><td>{score_label(score)}</td></tr>"
        for name, score, a, b in rows
    )
    st.markdown(
        f"""
        <section class="k-card">
          <h2 class="k-title-md">과제별 결과</h2>
          <table class="task-table">
            <thead><tr><th>과제</th><th>환산점수</th><th>주요 지표 1</th><th>주요 지표 2</th><th>해석</th></tr></thead>
            <tbody>{table_rows}</tbody>
          </table>
          <div class="k-note" style="margin-top:12px;">점수는 정답률과 반응시간을 결합해 산출했습니다. 현재 기준값은 규준자료가 아닌 내부 임시 기준이며, 실제 상품화 전 표본 데이터로 재보정해야 합니다.</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("검사 다시하기", type="primary", use_container_width=True):
            reset_all()
            st.rerun()
    with c2:
        if st.button("처음으로", use_container_width=True):
            reset_all()
            st.rerun()

    if dev_mode:
        with st.expander("dev=1 DB exam_data"):
            st.json(exam_data)
        st.download_button(
            "dev=1 원자료 JSON 다운로드",
            data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"{EXAM_NAME}_{st.session_state.meta.get('respondent_id')}.json",
            mime="application/json",
            use_container_width=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# 데이터 저장 분기 + DB 연동 전용 블록
# ──────────────────────────────────────────────────────────────────────────────
def _is_db_insert_enabled() -> bool:
    raw = os.getenv("ENABLE_DB_INSERT", "false")
    return str(raw).strip().lower() == "true"


ENABLE_DB_INSERT = _is_db_insert_enabled()


def safe_db_insert(exam_data: Dict[str, str]) -> bool:
    if not ENABLE_DB_INSERT:
        return False
    try:
        from utils.database import Database  # type: ignore
        db = Database()
        db.insert(exam_data)
        return True
    except Exception as e:
        print(f"[DB INSERT ERROR] {e}")
        return False


def auto_db_insert(exam_data: Dict[str, str]) -> None:
    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False
    if st.session_state.db_insert_done:
        return
    if not ENABLE_DB_INSERT:
        return
    if not st.session_state.examinee.get("name"):
        st.error("이름을 입력해 주세요.")
        return
    ok = safe_db_insert(exam_data)
    if ok:
        st.session_state.db_insert_done = True
        st.success("검사 결과가 저장되었습니다.")
    else:
        st.warning("DB 저장이 수행되지 않았습니다. 환경/모듈 상태를 확인해 주세요.")


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    inject_css()
    init_state()
    dev_mode = get_dev_mode()

    if st.session_state.page == "intro":
        page_intro()
    elif st.session_state.page == "info":
        if not st.session_state.meta.get("consent"):
            st.session_state.page = "intro"
            st.rerun()
        page_info()
    elif st.session_state.page == "task":
        if not st.session_state.meta.get("consent"):
            st.session_state.page = "intro"
            st.rerun()
        if not st.session_state.examinee.get("name", "").strip():
            st.session_state.page = "info"
            st.rerun()
        page_task()
    elif st.session_state.page == "result":
        page_result(dev_mode=dev_mode)
    else:
        st.session_state.page = "intro"
        st.rerun()


if __name__ == "__main__":
    main()
