# -*- coding: utf-8 -*-
"""
KIRBS+ 무료 인지 컨디션 스크리닝 배터리
- Brief PVT
- Stroop
- Flanker
- Go/No-Go

주의:
1. 본 코드는 Streamlit 기반 1차 프로토타입입니다.
2. Streamlit 기본 위젯 기반 반응시간은 브라우저-서버 왕복 지연을 포함합니다.
3. 정밀 심리측정용 RT 수집이 필요하면 추후 JS 기반 컴포넌트로 전환하는 것이 권장됩니다.
4. SDMT, TMT, 상용 Stroop 검사 등 기존 상용 검사의 문항/자극/규준을 복제하지 않고,
   공개 인지실험 패러다임을 자체 구현한 형태입니다.
"""

from __future__ import annotations

import os
import json
import time
import uuid
import random
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st


# =========================================================
# 0. 기본 설정
# =========================================================

EXAM_NAME = "KIRBS_COGNITIVE_CONDITION_BATTERY"
EXAM_TITLE = "KIRBS+ 인지 컨디션 스크리닝"
EXAM_SUBTITLE = "처리속도 · 주의집중 · 억제통제 · 지속주의"
EXAM_VERSION = "streamlit_proto_1.0.0"

BASE_DIR = Path(__file__).resolve().parent
LOCAL_RESULT_DIR = BASE_DIR / "local_results"

ENABLE_DB_INSERT = os.getenv("ENABLE_DB_INSERT", "false").strip().lower() == "true"
SAVE_LOCAL_JSON = os.getenv("SAVE_LOCAL_JSON", "true").strip().lower() == "true"

RANDOM_SEED_BASE = 20260424


TASK_ORDER = ["pvt", "stroop", "flanker", "gng"]

TASK_META = {
    "pvt": {
        "title": "1. Brief PVT",
        "subtitle": "주의 각성도 및 반응속도",
        "description": "화면에 신호가 나타나면 가능한 한 빠르게 버튼을 누릅니다.",
        "trials": 8,
    },
    "stroop": {
        "title": "2. Stroop 색-단어 과제",
        "subtitle": "선택적 주의 및 간섭 억제",
        "description": "글자의 뜻이 아니라 글자의 색을 보고 응답합니다.",
        "trials": 12,
    },
    "flanker": {
        "title": "3. Flanker 화살표 과제",
        "subtitle": "반응 갈등 및 억제통제",
        "description": "가운데 화살표의 방향만 보고 응답합니다.",
        "trials": 12,
    },
    "gng": {
        "title": "4. Go/No-Go 과제",
        "subtitle": "지속주의 및 충동 억제",
        "description": "GO 자극에는 반응하고, NO-GO 자극에는 반응을 참습니다.",
        "trials": 16,
    },
}


# =========================================================
# 1. Streamlit 기본 세팅
# =========================================================

st.set_page_config(
    page_title=EXAM_TITLE,
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def rerun() -> None:
    """Streamlit 버전 차이를 고려한 rerun wrapper."""
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #f5f7fb;
            --panel: #ffffff;
            --text: #111827;
            --muted: #6b7280;
            --line: #e5e7eb;
            --blue: #2563eb;
            --blue-soft: #eff6ff;
            --green: #16a34a;
            --red: #dc2626;
            --amber: #d97706;
            --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
            --radius: 22px;
        }

        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", sans-serif;
        }

        .block-container {
            max-width: 1120px;
            padding-top: 2.4rem;
            padding-bottom: 4rem;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        .main-card {
            background: var(--panel);
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
            border-radius: var(--radius);
            padding: 30px 34px;
            margin-bottom: 22px;
        }

        .hero {
            background:
                radial-gradient(circle at top left, rgba(37,99,235,0.14), transparent 32%),
                linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
            border: 1px solid #dbeafe;
            border-radius: 28px;
            padding: 38px 40px;
            margin-bottom: 24px;
            box-shadow: var(--shadow);
        }

        .hero-kicker {
            color: var(--blue);
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }

        .hero-title {
            color: var(--text);
            font-size: 34px;
            line-height: 1.25;
            font-weight: 900;
            letter-spacing: -0.04em;
            margin-bottom: 10px;
        }

        .hero-sub {
            color: var(--muted);
            font-size: 17px;
            line-height: 1.7;
        }

        .task-title {
            font-size: 26px;
            font-weight: 900;
            letter-spacing: -0.03em;
            margin-bottom: 6px;
        }

        .task-subtitle {
            color: var(--blue);
            font-size: 15px;
            font-weight: 800;
            margin-bottom: 12px;
        }

        .task-desc {
            color: var(--muted);
            font-size: 15px;
            line-height: 1.7;
            margin-bottom: 12px;
        }

        .stimulus-box {
            border: 1px solid #dbeafe;
            background: #f8fbff;
            border-radius: 26px;
            min-height: 230px;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            margin: 22px 0 18px 0;
            padding: 32px;
        }

        .stimulus-big {
            font-size: 74px;
            font-weight: 950;
            letter-spacing: -0.04em;
            line-height: 1.1;
        }

        .stimulus-mid {
            font-size: 48px;
            font-weight: 900;
            letter-spacing: 0.02em;
            line-height: 1.25;
        }

        .stimulus-small {
            color: var(--muted);
            font-size: 16px;
            line-height: 1.7;
        }

        .progress-label {
            color: var(--muted);
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .notice-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 18px 20px;
            color: #475569;
            font-size: 14px;
            line-height: 1.7;
        }

        .warning-box {
            background: #fffbeb;
            border: 1px solid #fde68a;
            border-radius: 18px;
            padding: 18px 20px;
            color: #92400e;
            font-size: 14px;
            line-height: 1.7;
        }

        .result-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 22px;
            padding: 24px;
            box-shadow: 0 6px 22px rgba(15, 23, 42, 0.06);
            margin-bottom: 16px;
        }

        .result-title {
            font-size: 18px;
            font-weight: 900;
            margin-bottom: 6px;
        }

        .result-desc {
            color: var(--muted);
            font-size: 14px;
            line-height: 1.65;
        }

        .pill {
            display: inline-block;
            padding: 7px 12px;
            border-radius: 999px;
            background: #eff6ff;
            color: #1d4ed8;
            font-size: 13px;
            font-weight: 800;
            margin-right: 6px;
            margin-bottom: 6px;
        }

        .footer-note {
            color: #64748b;
            font-size: 13px;
            line-height: 1.7;
            margin-top: 20px;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 16px;
            box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
        }

        .stButton > button {
            border-radius: 14px;
            border: 1px solid #d1d5db;
            padding: 0.72rem 1rem;
            font-weight: 800;
        }

        .stButton > button[kind="primary"] {
            border: 1px solid #2563eb;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()


# =========================================================
# 2. 세션 상태 초기화
# =========================================================

def init_session() -> None:
    defaults = {
        "page": "intro",
        "participant_uuid": str(uuid.uuid4()),
        "started_at": None,
        "finished_at": None,
        "current_task_index": 0,
        "consent_checked": False,
        "demographics": {},
        "exam_saved": False,
        "exam_data": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session()


# =========================================================
# 3. 유틸 함수
# =========================================================

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    if np.isnan(value):
        return np.nan
    return float(max(low, min(high, value)))


def safe_mean(values: List[float]) -> Optional[float]:
    arr = [v for v in values if v is not None and not pd.isna(v)]
    if not arr:
        return None
    return float(np.mean(arr))


def safe_median(values: List[float]) -> Optional[float]:
    arr = [v for v in values if v is not None and not pd.isna(v)]
    if not arr:
        return None
    return float(np.median(arr))


def safe_sd(values: List[float]) -> Optional[float]:
    arr = [v for v in values if v is not None and not pd.isna(v)]
    if len(arr) < 2:
        return None
    return float(np.std(arr, ddof=1))


def percent(value: float) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value * 100:.1f}%"


def ms(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:.0f} ms"


def score_label(score: Optional[float]) -> str:
    if score is None or pd.isna(score):
        return "산출 불가"
    if score >= 80:
        return "안정"
    if score >= 60:
        return "보통"
    return "주의"


def score_description(score: Optional[float]) -> str:
    if score is None or pd.isna(score):
        return "응답 데이터가 충분하지 않아 지표를 산출하지 못했습니다."
    if score >= 80:
        return "현재 과제 수행에서는 반응속도와 정확도가 비교적 안정적으로 나타났습니다."
    if score >= 60:
        return "전반적으로 보통 수준의 수행입니다. 피로, 수면, 긴장도에 따라 결과가 흔들릴 수 있습니다."
    return "반응속도 지연, 오류 증가, 반응 일관성 저하 중 일부가 관찰되었습니다. 컨디션 요인을 함께 확인하는 것이 좋습니다."


def draw_score_bar(label: str, score: Optional[float]) -> None:
    if score is None or pd.isna(score):
        st.write(f"**{label}**: 산출 불가")
        st.progress(0)
        return

    st.write(f"**{label}**: {score:.1f}점 · {score_label(score)}")
    st.progress(int(round(score)))


# =========================================================
# 4. 과제 자극 생성
# =========================================================

def make_pvt_trials(n_trials: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    trials = []
    for i in range(n_trials):
        trials.append(
            {
                "trial_index": i + 1,
                "task": "pvt",
                "condition": "signal",
                "stimulus": "●",
                "correct_response": "tap",
                "delay_sec": round(rng.uniform(0.8, 2.2), 2),
            }
        )
    return trials


def make_stroop_trials(n_trials: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    color_map = {
        "빨강": "#dc2626",
        "파랑": "#2563eb",
        "초록": "#16a34a",
        "노랑": "#d97706",
    }
    color_names = list(color_map.keys())

    trials = []
    for i in range(n_trials):
        word = rng.choice(color_names)
        if i < n_trials // 2:
            ink = word
            condition = "congruent"
        else:
            candidates = [c for c in color_names if c != word]
            ink = rng.choice(candidates)
            condition = "incongruent"

        trials.append(
            {
                "trial_index": i + 1,
                "task": "stroop",
                "condition": condition,
                "stimulus_word": word,
                "ink_color_name": ink,
                "ink_color_hex": color_map[ink],
                "correct_response": ink,
                "response_options": color_names,
            }
        )

    rng.shuffle(trials)
    for idx, t in enumerate(trials):
        t["trial_index"] = idx + 1

    return trials


def make_flanker_trials(n_trials: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    trials = []

    for i in range(n_trials):
        target = rng.choice(["left", "right"])
        congruent = i < n_trials // 2

        if target == "left":
            center = "←"
            flank_same = "←←"
            flank_diff = "→→"
            correct = "left"
        else:
            center = "→"
            flank_same = "→→"
            flank_diff = "←←"
            correct = "right"

        if congruent:
            stimulus = f"{flank_same}{center}{flank_same}"
            condition = "congruent"
        else:
            stimulus = f"{flank_diff}{center}{flank_diff}"
            condition = "incongruent"

        trials.append(
            {
                "trial_index": i + 1,
                "task": "flanker",
                "condition": condition,
                "stimulus": stimulus,
                "correct_response": correct,
                "response_options": ["left", "right"],
            }
        )

    rng.shuffle(trials)
    for idx, t in enumerate(trials):
        t["trial_index"] = idx + 1

    return trials


def make_gng_trials(n_trials: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    trials = []

    no_go_count = max(4, int(round(n_trials * 0.30)))
    labels = ["nogo"] * no_go_count + ["go"] * (n_trials - no_go_count)
    rng.shuffle(labels)

    for i, label in enumerate(labels):
        if label == "go":
            stimulus = rng.choice(["초록 원", "파란 원", "GO"])
            correct = "respond"
            condition = "go"
        else:
            stimulus = rng.choice(["빨간 원", "X", "멈춤"])
            correct = "withhold"
            condition = "nogo"

        trials.append(
            {
                "trial_index": i + 1,
                "task": "gng",
                "condition": condition,
                "stimulus": stimulus,
                "correct_response": correct,
                "response_options": ["respond", "withhold"],
            }
        )

    return trials


def make_trials(task_key: str) -> List[Dict[str, Any]]:
    seed = RANDOM_SEED_BASE + abs(hash(st.session_state["participant_uuid"] + task_key)) % 100000
    n_trials = TASK_META[task_key]["trials"]

    if task_key == "pvt":
        return make_pvt_trials(n_trials, seed)
    if task_key == "stroop":
        return make_stroop_trials(n_trials, seed)
    if task_key == "flanker":
        return make_flanker_trials(n_trials, seed)
    if task_key == "gng":
        return make_gng_trials(n_trials, seed)

    raise ValueError(f"Unknown task_key: {task_key}")


# =========================================================
# 5. 과제 상태 관리
# =========================================================

def reset_task(task_key: str) -> None:
    st.session_state[task_key] = {
        "started": False,
        "done": False,
        "started_at": None,
        "finished_at": None,
        "trial_index": 0,
        "trials": [],
        "records": [],
        "stimulus_onset": None,
        "phase": "ready",
    }


def ensure_task_state(task_key: str) -> None:
    if task_key not in st.session_state:
        reset_task(task_key)


def start_task(task_key: str) -> None:
    ensure_task_state(task_key)
    st.session_state[task_key] = {
        "started": True,
        "done": False,
        "started_at": now_iso(),
        "finished_at": None,
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
    idx = state["trial_index"]
    trials = state["trials"]
    if idx >= len(trials):
        return None
    return trials[idx]


def task_progress(task_key: str) -> tuple[int, int]:
    state = st.session_state[task_key]
    completed = len(state["records"])
    total = len(state["trials"])
    return completed, total


def record_response(task_key: str, response: str) -> None:
    state = st.session_state[task_key]
    trial = current_trial(task_key)

    if trial is None:
        finish_task(task_key)
        return

    onset = state.get("stimulus_onset")
    rt_ms = None
    if onset is not None:
        rt_ms = (time.perf_counter() - onset) * 1000

    correct_response = trial.get("correct_response")
    correct = response == correct_response

    record = {
        "participant_uuid": st.session_state["participant_uuid"],
        "exam_name": EXAM_NAME,
        "exam_version": EXAM_VERSION,
        "task": task_key,
        "trial_index": trial.get("trial_index"),
        "condition": trial.get("condition"),
        "stimulus": trial.get("stimulus", trial.get("stimulus_word")),
        "stimulus_word": trial.get("stimulus_word"),
        "ink_color_name": trial.get("ink_color_name"),
        "correct_response": correct_response,
        "response": response,
        "correct": bool(correct),
        "rt_ms": round(rt_ms, 2) if rt_ms is not None else None,
        "delay_sec": trial.get("delay_sec"),
        "timestamp": now_iso(),
    }

    state["records"].append(record)
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


def get_all_records() -> List[Dict[str, Any]]:
    records = []
    for task_key in TASK_ORDER:
        ensure_task_state(task_key)
        records.extend(st.session_state[task_key].get("records", []))
    return records


# =========================================================
# 6. 화면 컴포넌트
# =========================================================

def render_header() -> None:
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-kicker">KIRBS+ Cognitive Screening</div>
            <div class="hero-title">{EXAM_TITLE}</div>
            <div class="hero-sub">{EXAM_SUBTITLE}<br>
            본 검사는 현재의 인지적 컨디션을 간단히 확인하기 위한 비진단적 스크리닝 과제입니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_progress_overview() -> None:
    cols = st.columns(len(TASK_ORDER))
    for i, task_key in enumerate(TASK_ORDER):
        ensure_task_state(task_key)
        meta = TASK_META[task_key]
        state = st.session_state[task_key]
        completed, total = task_progress(task_key)
        with cols[i]:
            if state["done"]:
                status = "완료"
            elif st.session_state["current_task_index"] == i:
                status = "진행 중"
            else:
                status = "대기"
            st.markdown(f"**{meta['title']}**")
            st.caption(status)
            st.progress(0 if total == 0 else int(completed / total * 100))


def render_task_shell(task_key: str) -> None:
    meta = TASK_META[task_key]
    completed, total = task_progress(task_key)

    st.markdown(
        f"""
        <div class="main-card">
            <div class="task-title">{meta["title"]}</div>
            <div class="task-subtitle">{meta["subtitle"]}</div>
            <div class="task-desc">{meta["description"]}</div>
            <div class="progress-label">진행률: {completed} / {total if total else meta["trials"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.progress(0 if total == 0 else int(completed / total * 100))


def render_intro_page() -> None:
    render_header()

    st.markdown(
        """
        <div class="main-card">
            <div class="task-title">검사 구성</div>
            <div class="task-desc">
                아래 과제는 임상 진단용 검사가 아니라, 현재의 반응속도·주의집중·억제통제·반응 일관성을
                짧게 확인하기 위한 스크리닝 패키지입니다.
            </div>
            <span class="pill">Brief PVT</span>
            <span class="pill">Stroop</span>
            <span class="pill">Flanker</span>
            <span class="pill">Go/No-Go</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.subheader("기본 정보")
        c1, c2, c3 = st.columns(3)
        with c1:
            age_group = st.selectbox(
                "연령대",
                ["선택 안 함", "10대", "20대", "30대", "40대", "50대", "60대 이상"],
            )
        with c2:
            sex = st.selectbox(
                "성별",
                ["선택 안 함", "남성", "여성", "기타/응답 안 함"],
            )
        with c3:
            device = st.selectbox(
                "실시 기기",
                ["PC/노트북", "태블릿", "모바일", "기타"],
            )

        c4, c5, c6 = st.columns(3)
        with c4:
            sleep_quality = st.slider("지난밤 수면의 질", 1, 5, 3, help="1=매우 나쁨, 5=매우 좋음")
        with c5:
            fatigue = st.slider("현재 피로감", 1, 5, 3, help="1=거의 없음, 5=매우 피곤함")
        with c6:
            caffeine = st.selectbox("최근 3시간 내 카페인 섭취", ["아니오", "예", "응답 안 함"])

    st.markdown(
        """
        <div class="warning-box">
            <b>중요 안내</b><br>
            이 검사는 의학적·임상적 진단을 제공하지 않습니다. 결과는 현재 컨디션, 기기 성능, 인터넷 상태,
            키보드/마우스 사용 환경, 피로도 등에 영향을 받을 수 있습니다.
            특히 Streamlit 프로토타입에서는 반응시간에 서버 왕복 지연이 포함될 수 있습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    consent = st.checkbox(
        "검사 목적, 비진단적 성격, 익명/비식별 데이터 활용 가능성에 대한 안내를 확인했습니다.",
        value=st.session_state.get("consent_checked", False),
    )
    st.session_state["consent_checked"] = consent

    start_disabled = not consent

    if st.button("검사 시작", type="primary", use_container_width=True, disabled=start_disabled):
        st.session_state["demographics"] = {
            "age_group": age_group,
            "sex": sex,
            "device": device,
            "sleep_quality_1to5": sleep_quality,
            "fatigue_1to5": fatigue,
            "caffeine_last_3h": caffeine,
        }
        st.session_state["started_at"] = now_iso()
        st.session_state["page"] = "task"
        st.session_state["current_task_index"] = 0

        for task_key in TASK_ORDER:
            reset_task(task_key)

        start_task(TASK_ORDER[0])
        rerun()


# =========================================================
# 7. 과제 렌더링
# =========================================================

def render_pvt(task_key: str) -> None:
    state = st.session_state[task_key]
    trial = current_trial(task_key)

    if trial is None:
        finish_task(task_key)
        rerun()

    if state["phase"] == "waiting":
        st.markdown(
            """
            <div class="stimulus-box">
                <div>
                    <div class="stimulus-mid">준비</div>
                    <div class="stimulus-small">잠시 후 신호가 나타납니다. 신호가 나타나면 최대한 빠르게 누르세요.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        time.sleep(float(trial["delay_sec"]))

        state["phase"] = "stimulus"
        state["stimulus_onset"] = time.perf_counter()
        st.session_state[task_key] = state

    st.markdown(
        """
        <div class="stimulus-box">
            <div>
                <div class="stimulus-big" style="color:#2563eb;">●</div>
                <div class="stimulus-small">지금 누르세요</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    word = trial["stimulus_word"]
    ink_hex = trial["ink_color_hex"]

    st.markdown(
        f"""
        <div class="stimulus-box">
            <div>
                <div class="stimulus-big" style="color:{ink_hex};">{word}</div>
                <div class="stimulus-small">글자의 뜻이 아니라 <b>글자의 색</b>을 선택하세요.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
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

    stimulus = trial["stimulus"]

    st.markdown(
        f"""
        <div class="stimulus-box">
            <div>
                <div class="stimulus-big">{stimulus}</div>
                <div class="stimulus-small">가운데 화살표의 방향만 선택하세요.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
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

    stimulus = trial["stimulus"]
    condition = trial["condition"]

    if condition == "go":
        color = "#16a34a"
        guide = "GO 자극입니다. 반응해야 합니다."
    else:
        color = "#dc2626"
        guide = "NO-GO 자극입니다. 반응을 참아야 합니다."

    st.markdown(
        f"""
        <div class="stimulus-box">
            <div>
                <div class="stimulus-big" style="color:{color};">{stimulus}</div>
                <div class="stimulus-small">{guide}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("반응", use_container_width=True, key=f"{task_key}_{state['trial_index']}_respond"):
            record_response(task_key, "respond")
    with c2:
        if st.button("참기 / 다음", use_container_width=True, key=f"{task_key}_{state['trial_index']}_withhold"):
            record_response(task_key, "withhold")


def render_current_task_page() -> None:
    render_progress_overview()

    current_idx = st.session_state["current_task_index"]

    if current_idx >= len(TASK_ORDER):
        st.session_state["page"] = "result"
        rerun()

    task_key = TASK_ORDER[current_idx]
    ensure_task_state(task_key)

    state = st.session_state[task_key]
    if not state["started"]:
        start_task(task_key)
        rerun()

    render_task_shell(task_key)

    if state["done"]:
        st.success(f"{TASK_META[task_key]['title']} 완료")

        if current_idx < len(TASK_ORDER) - 1:
            if st.button("다음 과제로 이동", type="primary", use_container_width=True):
                st.session_state["current_task_index"] += 1
                next_task = TASK_ORDER[st.session_state["current_task_index"]]
                start_task(next_task)
                rerun()
        else:
            if st.button("결과 보기", type="primary", use_container_width=True):
                st.session_state["finished_at"] = now_iso()
                st.session_state["page"] = "result"
                rerun()

        return

    if task_key == "pvt":
        render_pvt(task_key)
    elif task_key == "stroop":
        render_stroop(task_key)
    elif task_key == "flanker":
        render_flanker(task_key)
    elif task_key == "gng":
        render_gng(task_key)


# =========================================================
# 8. 결과 산출
# =========================================================

def summarize_pvt(df: pd.DataFrame) -> Dict[str, Any]:
    sub = df[df["task"] == "pvt"].copy()
    rt = sub["rt_ms"].dropna().astype(float).tolist()

    median_rt = safe_median(rt)
    mean_rt = safe_mean(rt)
    sd_rt = safe_sd(rt)
    lapse_count = int(np.sum(np.array(rt) >= 800)) if rt else 0

    if median_rt is None:
        score = None
    else:
        score = clamp(100 - max(0, median_rt - 320) * 0.10 - lapse_count * 6)

    return {
        "task": "pvt",
        "n_trials": int(len(sub)),
        "mean_rt_ms": mean_rt,
        "median_rt_ms": median_rt,
        "sd_rt_ms": sd_rt,
        "lapse_count_800ms": lapse_count,
        "score": score,
        "label": score_label(score),
    }


def summarize_congruency_task(df: pd.DataFrame, task_key: str) -> Dict[str, Any]:
    sub = df[df["task"] == task_key].copy()

    if sub.empty:
        return {
            "task": task_key,
            "n_trials": 0,
            "accuracy": None,
            "median_rt_ms": None,
            "congruent_median_rt_ms": None,
            "incongruent_median_rt_ms": None,
            "interference_ms": None,
            "score": None,
            "label": "산출 불가",
        }

    correct_sub = sub[sub["correct"] == True]
    accuracy = float(sub["correct"].mean()) if len(sub) else None
    median_rt = safe_median(correct_sub["rt_ms"].dropna().astype(float).tolist())

    con = correct_sub[correct_sub["condition"] == "congruent"]["rt_ms"].dropna().astype(float).tolist()
    incon = correct_sub[correct_sub["condition"] == "incongruent"]["rt_ms"].dropna().astype(float).tolist()

    con_med = safe_median(con)
    incon_med = safe_median(incon)
    interference = None
    if con_med is not None and incon_med is not None:
        interference = incon_med - con_med

    if accuracy is None:
        score = None
    else:
        interference_penalty = max(0, interference or 0) * 0.05
        error_penalty = (1 - accuracy) * 60
        score = clamp(100 - interference_penalty - error_penalty)

    return {
        "task": task_key,
        "n_trials": int(len(sub)),
        "accuracy": accuracy,
        "median_rt_ms": median_rt,
        "congruent_median_rt_ms": con_med,
        "incongruent_median_rt_ms": incon_med,
        "interference_ms": interference,
        "score": score,
        "label": score_label(score),
    }


def summarize_gng(df: pd.DataFrame) -> Dict[str, Any]:
    sub = df[df["task"] == "gng"].copy()

    if sub.empty:
        return {
            "task": "gng",
            "n_trials": 0,
            "accuracy": None,
            "go_hit_rate": None,
            "nogo_correct_rejection_rate": None,
            "commission_error_rate": None,
            "omission_error_rate": None,
            "median_go_rt_ms": None,
            "score": None,
            "label": "산출 불가",
        }

    accuracy = float(sub["correct"].mean())

    go = sub[sub["condition"] == "go"]
    nogo = sub[sub["condition"] == "nogo"]

    go_hit_rate = float((go["response"] == "respond").mean()) if len(go) else None
    omission_error_rate = float((go["response"] == "withhold").mean()) if len(go) else None

    nogo_correct_rate = float((nogo["response"] == "withhold").mean()) if len(nogo) else None
    commission_error_rate = float((nogo["response"] == "respond").mean()) if len(nogo) else None

    median_go_rt = safe_median(
        go[(go["response"] == "respond") & (go["correct"] == True)]["rt_ms"].dropna().astype(float).tolist()
    )

    score = clamp(
        100
        - (commission_error_rate or 0) * 55
        - (omission_error_rate or 0) * 35
        - (1 - accuracy) * 25
    )

    return {
        "task": "gng",
        "n_trials": int(len(sub)),
        "accuracy": accuracy,
        "go_hit_rate": go_hit_rate,
        "nogo_correct_rejection_rate": nogo_correct_rate,
        "commission_error_rate": commission_error_rate,
        "omission_error_rate": omission_error_rate,
        "median_go_rt_ms": median_go_rt,
        "score": score,
        "label": score_label(score),
    }


def summarize_reaction_consistency(df: pd.DataFrame) -> Dict[str, Any]:
    usable = df[(df["correct"] == True) & (df["rt_ms"].notna())].copy()

    if usable.empty:
        return {
            "mean_rt_ms": None,
            "sd_rt_ms": None,
            "cv": None,
            "score": None,
            "label": "산출 불가",
        }

    rt = usable["rt_ms"].astype(float).tolist()
    mean_rt = safe_mean(rt)
    sd_rt = safe_sd(rt)

    if mean_rt is None or sd_rt is None or mean_rt <= 0:
        cv = None
        score = None
    else:
        cv = sd_rt / mean_rt
        score = clamp(100 - max(0, cv - 0.25) * 180)

    return {
        "mean_rt_ms": mean_rt,
        "sd_rt_ms": sd_rt,
        "cv": cv,
        "score": score,
        "label": score_label(score),
    }


def summarize_all(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    df = pd.DataFrame(records)

    if df.empty:
        return {
            "pvt": {},
            "stroop": {},
            "flanker": {},
            "gng": {},
            "reaction_consistency": {},
            "composite": {},
        }

    pvt = summarize_pvt(df)
    stroop = summarize_congruency_task(df, "stroop")
    flanker = summarize_congruency_task(df, "flanker")
    gng = summarize_gng(df)
    consistency = summarize_reaction_consistency(df)

    processing_speed_scores = [
        pvt.get("score"),
        stroop.get("score"),
        flanker.get("score"),
    ]
    inhibition_scores = [
        stroop.get("score"),
        flanker.get("score"),
        gng.get("score"),
    ]
    attention_scores = [
        pvt.get("score"),
        gng.get("score"),
        consistency.get("score"),
    ]

    def avg_score(values: List[Optional[float]]) -> Optional[float]:
        clean = [v for v in values if v is not None and not pd.isna(v)]
        if not clean:
            return None
        return float(np.mean(clean))

    processing_speed = avg_score(processing_speed_scores)
    inhibition_control = avg_score(inhibition_scores)
    sustained_attention = avg_score(attention_scores)
    reaction_consistency = consistency.get("score")

    overall = avg_score([
        processing_speed,
        inhibition_control,
        sustained_attention,
        reaction_consistency,
    ])

    composite = {
        "processing_speed": processing_speed,
        "inhibition_control": inhibition_control,
        "sustained_attention": sustained_attention,
        "reaction_consistency": reaction_consistency,
        "overall": overall,
        "overall_label": score_label(overall),
        "overall_description": score_description(overall),
    }

    return {
        "pvt": pvt,
        "stroop": stroop,
        "flanker": flanker,
        "gng": gng,
        "reaction_consistency": consistency,
        "composite": composite,
    }


# =========================================================
# 9. 결과 화면
# =========================================================

def render_result_page() -> None:
    records = get_all_records()
    summary = summarize_all(records)

    st.markdown(
        """
        <div class="hero">
            <div class="hero-kicker">Result Summary</div>
            <div class="hero-title">인지 컨디션 결과 요약</div>
            <div class="hero-sub">
                본 결과는 현재 검사 환경에서의 상대적 수행 지표이며, 의학적·임상적 진단으로 해석하지 않습니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    composite = summary["composite"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("종합 지표", "-" if composite.get("overall") is None else f"{composite['overall']:.1f}")
    with c2:
        st.metric("처리속도", "-" if composite.get("processing_speed") is None else f"{composite['processing_speed']:.1f}")
    with c3:
        st.metric("억제통제", "-" if composite.get("inhibition_control") is None else f"{composite['inhibition_control']:.1f}")
    with c4:
        st.metric("지속주의", "-" if composite.get("sustained_attention") is None else f"{composite['sustained_attention']:.1f}")

    st.markdown(
        f"""
        <div class="result-card">
            <div class="result-title">종합 해석: {composite.get("overall_label", "산출 불가")}</div>
            <div class="result-desc">{composite.get("overall_description", "")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("영역별 지표")
    draw_score_bar("처리속도", composite.get("processing_speed"))
    draw_score_bar("억제통제", composite.get("inhibition_control"))
    draw_score_bar("지속주의", composite.get("sustained_attention"))
    draw_score_bar("반응 일관성", composite.get("reaction_consistency"))

    st.divider()

    st.subheader("과제별 세부 결과")

    pvt = summary["pvt"]
    stroop = summary["stroop"]
    flanker = summary["flanker"]
    gng = summary["gng"]
    consistency = summary["reaction_consistency"]

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Brief PVT", "Stroop", "Flanker", "Go/No-Go", "원자료"]
    )

    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("중앙 반응시간", ms(pvt.get("median_rt_ms")))
        c2.metric("평균 반응시간", ms(pvt.get("mean_rt_ms")))
        c3.metric("반응 지연 수", pvt.get("lapse_count_800ms", "-"))
        c4.metric("PVT 지표", "-" if pvt.get("score") is None else f"{pvt['score']:.1f}")
        st.caption("반응 지연 수는 800ms 이상 반응을 임시 기준으로 산출한 프로토타입 지표입니다.")

    with tab2:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("정확률", percent(stroop.get("accuracy")))
        c2.metric("중앙 RT", ms(stroop.get("median_rt_ms")))
        c3.metric("간섭 효과", ms(stroop.get("interference_ms")))
        c4.metric("Stroop 지표", "-" if stroop.get("score") is None else f"{stroop['score']:.1f}")
        st.caption("간섭 효과는 불일치 조건 중앙 RT - 일치 조건 중앙 RT입니다.")

    with tab3:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("정확률", percent(flanker.get("accuracy")))
        c2.metric("중앙 RT", ms(flanker.get("median_rt_ms")))
        c3.metric("간섭 효과", ms(flanker.get("interference_ms")))
        c4.metric("Flanker 지표", "-" if flanker.get("score") is None else f"{flanker['score']:.1f}")
        st.caption("간섭 효과는 불일치 조건 중앙 RT - 일치 조건 중앙 RT입니다.")

    with tab4:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("전체 정확률", percent(gng.get("accuracy")))
        c2.metric("GO 적중률", percent(gng.get("go_hit_rate")))
        c3.metric("NO-GO 오반응률", percent(gng.get("commission_error_rate")))
        c4.metric("Go/No-Go 지표", "-" if gng.get("score") is None else f"{gng['score']:.1f}")

        c5, c6 = st.columns(2)
        c5.metric("GO 중앙 RT", ms(gng.get("median_go_rt_ms")))
        c6.metric("누락 오류율", percent(gng.get("omission_error_rate")))

    with tab5:
        raw_df = pd.DataFrame(records)
        st.dataframe(raw_df, use_container_width=True)

        st.download_button(
            "원자료 CSV 다운로드",
            data=raw_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{EXAM_NAME}_{st.session_state['participant_uuid']}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    exam_data = build_exam_data(summary, records)
    st.session_state["exam_data"] = exam_data

    st.divider()

    if not st.session_state.get("exam_saved", False):
        if st.button("결과 저장", type="primary", use_container_width=True):
            save_exam_data(exam_data)
            st.session_state["exam_saved"] = True
            rerun()
    else:
        st.success("결과 저장 처리가 완료되었습니다.")

    with st.expander("저장 데이터 구조 확인"):
        st.json(exam_data)

    st.markdown(
        """
        <div class="footer-note">
            ※ 본 프로토타입의 점수는 임상 규준 점수가 아니라 내부 확인용 지표입니다.
            실제 무료 배포 전에는 표본 수집 후 연령대·기기·실시환경별 분포 확인, 신뢰도 검토,
            반복측정 안정성 검토, 결과 해석 문구 검토가 필요합니다.
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# 10. 저장 데이터 생성
# =========================================================

def build_exam_data(summary: Dict[str, Any], records: List[Dict[str, Any]]) -> Dict[str, Any]:
    exam_data = {
        "exam_meta": {
            "exam_name": EXAM_NAME,
            "exam_title": EXAM_TITLE,
            "exam_subtitle": EXAM_SUBTITLE,
            "exam_version": EXAM_VERSION,
            "platform": "streamlit",
            "created_at": now_iso(),
            "started_at": st.session_state.get("started_at"),
            "finished_at": st.session_state.get("finished_at") or now_iso(),
        },
        "participant": {
            "participant_uuid": st.session_state.get("participant_uuid"),
            "demographics": st.session_state.get("demographics", {}),
            "consent_checked": bool(st.session_state.get("consent_checked", False)),
        },
        "summary": summary,
        "raw_records": records,
        "technical_note": {
            "enable_db_insert": ENABLE_DB_INSERT,
            "save_local_json": SAVE_LOCAL_JSON,
            "rt_warning": "Streamlit prototype RT includes client-server roundtrip latency.",
        },
    }
    return exam_data


# =========================================================
# 11. 저장 처리
# =========================================================

def save_local_json(exam_data: Dict[str, Any]) -> None:
    LOCAL_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    participant_uuid = exam_data["participant"]["participant_uuid"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = LOCAL_RESULT_DIR / f"{EXAM_NAME}_{participant_uuid}_{timestamp}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(exam_data, f, ensure_ascii=False, indent=2)

    st.info(f"로컬 JSON 저장 완료: {out_path}")


def insert_exam_data_to_db(exam_data: Dict[str, Any]) -> None:
    """
    운영 환경에서만 호출되는 DB 저장 함수.

    전산센터 공통 모듈 경로가 프로젝트마다 다를 수 있으므로,
    실제 병합 시 아래 import 경로만 전산센터 기준에 맞게 확인하면 됩니다.

    가이드 기준:
        db = Database()
        db.insert(exam_data)
    """

    try:
        from database import Database  # type: ignore
    except ImportError:
        try:
            from db import Database  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Database 공통 모듈을 찾지 못했습니다. "
                "전산센터 병합 환경의 Database import 경로를 확인해야 합니다."
            ) from e

    db = Database()
    db.insert(exam_data)


def save_exam_data(exam_data: Dict[str, Any]) -> None:
    """
    저장 정책:
    - 로컬/개발 환경: ENABLE_DB_INSERT=false → DB insert 미실행
    - 운영/병합 환경: ENABLE_DB_INSERT=true → DB insert 실행
    - SAVE_LOCAL_JSON=true이면 로컬 JSON 백업 저장
    """

    if SAVE_LOCAL_JSON:
        save_local_json(exam_data)

    if ENABLE_DB_INSERT:
        insert_exam_data_to_db(exam_data)
        st.success("DB 저장 완료")
    else:
        st.warning("ENABLE_DB_INSERT=false 상태입니다. DB 저장은 실행되지 않았습니다.")


# =========================================================
# 12. 메인
# =========================================================

def main() -> None:
    if st.session_state["page"] == "intro":
        render_intro_page()

    elif st.session_state["page"] == "task":
        render_current_task_page()

    elif st.session_state["page"] == "result":
        render_result_page()

    else:
        st.session_state["page"] = "intro"
        rerun()


if __name__ == "__main__":
    main()