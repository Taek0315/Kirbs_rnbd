# 실행 방법:
#   streamlit run cad_7.py

# -*- coding: utf-8 -*-
import json
import uuid
from datetime import datetime, timedelta, timezone

import streamlit as st

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
    if label is None:
        return None
    try:
        return int(label.split("(")[-1].split(")")[0])
    except Exception:
        return None


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
    return


def get_level_key(level_text: str) -> str:
    if "최소/거의 없음" in level_text:
        return "minimal"
    if "경도" in level_text:
        return "mild"
    if "중등도" in level_text:
        return "moderate"
    return "severe"


def stepper(current: str):
    steps = [
        ("intro", "1", "안내/동의"),
        ("survey", "2", "문항 응답"),
        ("result", "3", "결과 확인"),
    ]

    current_idx = 0
    for idx, (key, _, _) in enumerate(steps):
        if key == current:
            current_idx = idx
            break

    items = []
    for idx, (_, num, label) in enumerate(steps):
        status = "done" if idx < current_idx else "active" if idx == current_idx else "todo"
        items.append(
            f"""
            <div class=\"step-item {status}\">
                <div class=\"step-dot\">{num}</div>
                <div class=\"step-label\">{label}</div>
            </div>
            """
        )

    st.markdown(f"<div class='stepper'>{''.join(items)}</div>", unsafe_allow_html=True)


def inject_css():
    st.markdown(
        """
        <style>
        :root {
            --bg: #f6f8fc;
            --surface: #ffffff;
            --surface-2: #f8fafc;
            --text: #0f172a;
            --muted: #475569;
            --line: #e2e8f0;
            --primary: #2563eb;
            --primary-soft: #dbeafe;
            --success: #16a34a;
            --success-soft: #dcfce7;
            --warning: #d97706;
            --warning-soft: #ffedd5;
            --danger: #dc2626;
            --danger-soft: #fee2e2;
            --radius-xl: 20px;
            --radius-lg: 14px;
            --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.06);
            --shadow-md: 0 12px 28px rgba(15, 23, 42, 0.08);
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #0b1220;
                --surface: #111827;
                --surface-2: #172033;
                --text: #e5e7eb;
                --muted: #cbd5e1;
                --line: #334155;
                --primary: #60a5fa;
                --primary-soft: rgba(96,165,250,.15);
                --success: #4ade80;
                --success-soft: rgba(74,222,128,.15);
                --warning: #fbbf24;
                --warning-soft: rgba(251,191,36,.16);
                --danger: #f87171;
                --danger-soft: rgba(248,113,113,.16);
                --shadow-sm: none;
                --shadow-md: none;
            }
        }

        .stApp {
            background: radial-gradient(circle at top left, rgba(37,99,235,.08), transparent 35%), var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
            letter-spacing: -0.01em;
        }

        .block-container {
            max-width: 860px;
            padding-top: 1.6rem;
            padding-bottom: 3.2rem;
        }

        .page-wrap {
            animation: fadeIn .35s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow-sm);
            padding: 20px;
            margin-bottom: 12px;
        }

        .card.soft { background: var(--surface-2); }

        .title-lg { font-size: clamp(1.35rem, 2.8vw, 1.8rem); font-weight: 800; line-height: 1.3; color: var(--text); }
        .title-md { font-size: clamp(1.05rem, 2.2vw, 1.2rem); font-weight: 750; line-height: 1.35; color: var(--text); }
        .text { font-size: clamp(.95rem, 1.9vw, 1rem); line-height: 1.72; color: var(--muted); }
        .muted { font-size: .86rem; line-height: 1.6; color: var(--muted); }

        .badge {
            display: inline-block;
            background: var(--primary-soft);
            color: var(--primary);
            font-weight: 700;
            font-size: .8rem;
            border-radius: 999px;
            padding: 6px 10px;
            margin: 0 6px 8px 0;
        }

        .stepper {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
            margin: 0 0 14px;
        }

        .step-item {
            border-radius: 14px;
            padding: 10px 8px;
            text-align: center;
            border: 1px solid var(--line);
            background: var(--surface);
            transition: all .2s ease;
        }
        .step-dot {
            width: 30px; height: 30px; margin: 0 auto 6px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            font-size: .86rem;
            font-weight: 700;
            border: 1px solid var(--line);
            color: var(--muted);
            background: var(--surface-2);
        }
        .step-label { font-size: .83rem; font-weight: 700; color: var(--muted); }
        .step-item.active { border-color: var(--primary); background: var(--primary-soft); box-shadow: var(--shadow-sm); }
        .step-item.active .step-dot { background: var(--primary); border-color: var(--primary); color: white; }
        .step-item.active .step-label { color: var(--text); }
        .step-item.done .step-dot { background: var(--success); border-color: var(--success); color: #fff; }

        .progress-row { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom: 10px; }
        .progress-label { font-size:.88rem; font-weight:700; color: var(--muted); }

        .meter {
            width: 100%;
            height: 10px;
            border-radius: 999px;
            background: var(--surface-2);
            overflow: hidden;
            border: 1px solid var(--line);
        }
        .meter > span { display:block; height:100%; background: linear-gradient(90deg, var(--primary), #60a5fa); transition: width .25s ease; }

        .question-title { font-size: 1rem; font-weight: 750; color: var(--text); margin-bottom: .45rem; }

        div[data-testid="stRadio"] {
            margin-top: .2rem;
        }

        div[data-testid="stRadio"] > div[role="radiogroup"] {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
        }

        div[data-testid="stRadio"] > div[role="radiogroup"] > label {
            margin: 0 !important;
            border: 1px solid var(--line);
            background: var(--surface-2);
            border-radius: 12px;
            min-height: 54px;
            padding: 10px 8px;
            transition: transform .14s ease, border-color .14s ease, box-shadow .14s ease, background .14s ease;
            cursor: pointer;
        }

        div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
            transform: translateY(-1px);
            border-color: var(--primary);
            box-shadow: var(--shadow-sm);
        }

        div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:focus-visible) {
            outline: 2px solid var(--primary);
            outline-offset: 2px;
        }

        div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
            border-color: var(--primary);
            background: var(--primary-soft);
            box-shadow: inset 0 0 0 1px var(--primary);
            transform: scale(1.01);
        }

        div[data-testid="stRadio"] > div[role="radiogroup"] > label > div {
            width: 100%;
            margin: 0 !important;
            justify-content: center;
            text-align: center;
            font-size: .9rem;
            font-weight: 700;
            color: var(--text);
            line-height: 1.3;
        }

        div[data-testid="stRadio"] > div[role="radiogroup"] > label > div > div:first-child {
            display: none;
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
        .chip-danger { color: var(--danger); background: var(--danger-soft); }
        .chip-warning { color: var(--warning); background: var(--warning-soft); }
        .chip-success { color: var(--success); background: var(--success-soft); }

        .result-score { font-size: clamp(2.4rem, 7vw, 3.3rem); font-weight: 900; line-height: 1.05; color: var(--text); }
        .result-sub { color: var(--muted); font-size: .95rem; }
        .level-badge {
            display:inline-block;
            margin-top: 8px;
            border-radius: 999px;
            padding: 7px 12px;
            font-size: .86rem;
            font-weight: 750;
        }

        .level-minimal { color: #065f46; background: #d1fae5; }
        .level-mild { color: #92400e; background: #fef3c7; }
        .level-moderate { color: #1d4ed8; background: #dbeafe; }
        .level-severe { color: #991b1b; background: #fee2e2; }

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

        @media (max-width: 768px) {
            .block-container { padding-left: .8rem; padding-right: .8rem; }
            .card { padding: 16px; border-radius: 16px; }
            .step-label { font-size: .76rem; }
            div[data-testid="stRadio"] > div[role="radiogroup"] { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }

        @media (max-width: 420px) {
            div[data-testid="stRadio"] > div[role="radiogroup"] > label { min-height: 50px; padding: 8px 6px; }
            div[data-testid="stRadio"] > div[role="radiogroup"] > label > div { font-size: .83rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_intro():
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    stepper("intro")

    st.markdown(
        """
        <section class="card">
            <span class="badge">GAD-7</span>
            <span class="badge">최근 2주</span>
            <h1 class="title-lg">불안검사 (Generalized Anxiety Disorder-7)</h1>
            <p class="text" style="margin-top:8px;">
                본 검사는 최근 2주 동안 경험한 불안 관련 증상의 빈도를 확인하기 위한 자기보고식 척도입니다.
                약 2~3분 내에 완료하실 수 있습니다.
            </p>
            <div class="note-box" style="margin-top:12px;">
                <p class="text" style="margin:0;">
                    <strong>안내:</strong> 본 결과는 참고용이며 의학적 진단을 대체하지 않습니다.
                    불편감이 지속되거나 일상 기능 저하가 있다면 전문가 상담을 권장드립니다.
                </p>
                <p class="muted" style="margin:8px 0 0;">
                    입력하신 응답은 현재 세션에서 결과 산출을 위해 사용되며, 별도 저장은 연동 환경에 따라 달라질 수 있습니다.
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
            <p class="text">검사 진행 및 결과 산출에 동의하시면 아래를 선택해 주세요.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    consent = st.checkbox("예, 위 안내를 확인하였고 검사 진행에 동의합니다.", value=st.session_state.meta["consent"])
    st.session_state.meta["consent"] = consent

    c1, c2 = st.columns(2)
    with c1:
        if st.button("검사 시작", type="primary", disabled=not consent, use_container_width=True):
            now = datetime.now(KST).isoformat()
            st.session_state.meta["consent_ts"] = now
            st.session_state.meta["started_ts"] = now
            st.session_state.page = "survey"
            st.rerun()
    with c2:
        if st.button("초기화", use_container_width=True):
            reset_all()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def page_survey(dev_mode: bool = False):
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    stepper("survey")

    payload, missing = build_payload()
    answered_count = 7 - len(missing)
    progress_pct = int((answered_count / 7) * 100)

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
        index = SCALE_LABELS.index(current_answer) if current_answer in SCALE_LABELS else None

        st.markdown(
            f"""
            <section class="card">
                <div class="question-title">{i}. {q}</div>
            """,
            unsafe_allow_html=True,
        )

        selected = st.radio(
            label=f"문항 {i} 응답 선택",
            options=SCALE_LABELS,
            index=index,
            key=f"radio_{key}",
            horizontal=False,
            label_visibility="collapsed",
            format_func=lambda x: SCALE_SHORT.get(x, x),
        )
        st.session_state.answers[key] = selected
        st.markdown("</section>", unsafe_allow_html=True)

    payload, missing = build_payload()
    all_done = len(missing) == 0

    if missing:
        missing_idx = ", ".join([str(int(m[1:])) for m in missing])
        st.info(f"아직 응답하지 않은 문항: {missing_idx}번 문항")

    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        if st.button("결과 보기", type="primary", disabled=not all_done, use_container_width=True):
            st.session_state.meta["submitted_ts"] = datetime.now(KST).isoformat()
            st.session_state.page = "result"
            st.rerun()
    with c2:
        if st.button("안내로 돌아가기", use_container_width=True):
            st.session_state.page = "intro"
            st.rerun()
    with c3:
        if st.button("초기화", use_container_width=True):
            reset_all()
            st.rerun()

    if dev_mode:
        with st.expander("개발자 보기: payload/result", expanded=True):
            st.json(payload, expanded=False)
    else:
        with st.expander("개발자 보기", expanded=False):
            st.caption("URL에 ?dev=1 파라미터를 추가하면 상세 payload를 확인하실 수 있습니다.")

    st.markdown("</div>", unsafe_allow_html=True)


def page_result(dev_mode: bool = False):
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    stepper("result")

    payload, _ = build_payload()
    total = payload["result"]["total"]
    level = payload["result"]["level"]
    interp = payload["result"]["interpretation"]
    flags = payload["result"]["flags"]

    auto_db_insert(payload)

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
        if st.button("다시 검사", type="primary", use_container_width=True):
            reset_all()
            st.rerun()
    with c2:
        if st.button("문항으로 돌아가기", use_container_width=True):
            st.session_state.page = "survey"
            st.rerun()

    if dev_mode:
        with st.expander("개발자 보기: payload JSON", expanded=True):
            st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")

    st.markdown("</div>", unsafe_allow_html=True)


def main():
    inject_css()
    init_state()

    params = st.query_params
    dev_mode = str(params.get("dev", "0")) == "1"

    st.caption("GAD-7 (Spitzer et al., 2006) · Streamlit 웹 인터페이스")

    if st.session_state.page == "intro":
        page_intro()
    elif st.session_state.page == "survey":
        if not st.session_state.meta.get("consent"):
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            st.rerun()
        page_survey(dev_mode=dev_mode)
    elif st.session_state.page == "result":
        page_result(dev_mode=dev_mode)
    else:
        st.session_state.page = "intro"
        st.rerun()


if __name__ == "__main__":
    main()
