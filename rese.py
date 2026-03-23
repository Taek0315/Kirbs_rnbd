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

EXAM_NAME = "RSES"
EXAM_TITLE = "자아존중감 자기평가 검사"
EXAM_SUBTITLE = "Rosenberg Self-Esteem Scale 기반"
EXAM_VERSION = "streamlit_1.0"

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

SCALE_LABELS = [
    "전혀 그렇지 않다",
    "그렇지 않은 편이다",
    "보통이다",
    "그런 편이다",
    "매우 그렇다",
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

# 최종 문구 교체 예정: intro 화면 안내 문구를 한 곳에서 쉽게 수정할 수 있도록 상수로 분리합니다.
INTRO_DESC_BULLETS = [
    "이 검사는 현재 자신을 어떻게 인식하고 있는지 전반적인 경향을 살펴보기 위한 자기보고식 검사입니다.",
    "총 10개 문항으로 구성되어 있으며, 일반적으로 약 2~3분 안에 완료할 수 있습니다.",
    "문항에는 정답이 없으므로 최근의 나를 가장 잘 설명하는 응답을 선택해 주세요.",
]

INTRO_NOTICE_BULLETS = [
    "검사 결과는 현재 응답을 바탕으로 제공되는 참고용 안내이며, 전문적 진단이나 평가를 대체하지 않습니다.",
    "최근의 스트레스나 컨디션에 따라 결과가 달라질 수 있으므로, 필요 시 충분한 휴식 후 다시 확인해 보셔도 됩니다.",
    "지속적인 불편감이나 일상 기능의 어려움이 있다면 전문가 상담과 같은 추가적인 도움을 고려해 주세요.",
]

PRIVACY_BULLETS = [
    "검사 진행을 위해 이름, 성별, 연령, 거주지역 등 기본 정보를 입력받습니다. 휴대폰 번호와 이메일은 선택 입력 항목입니다.",
    "입력된 개인정보는 KIRBS+의 개인정보 관련 약관에 적용되며 약관에 따라 저장 및 활용될 수 있습니다.",
    "동의 후 검사 시작 시점과 동의 시점 정보가 기록되며, 이후 응답 내용은 결과 산출에 사용됩니다.",
]


def rses_level(total: int):
    if total >= 38:
        return (
            "높은 자아존중감",
            "전반적으로 자신을 긍정적으로 인식하고 있으며, 자기 가치감과 자기 존중감이 비교적 안정적인 수준으로 해석될 수 있습니다.",
        )
    if total >= 22:
        return (
            "보통 수준의 자아존중감",
            "자아존중감이 전반적으로 평균적인 수준으로 보입니다. 상황에 따라 자신에 대한 평가가 다소 흔들릴 수 있으나 전반적 적응은 무난한 편으로 볼 수 있습니다.",
        )
    return (
        "낮은 자아존중감",
        "자신에 대한 부정적 평가나 낮은 자기 가치감이 상대적으로 높을 수 있습니다. 이러한 느낌이 지속되거나 일상생활에 영향을 준다면 보다 세심한 자기이해와 정서적 점검이 도움이 될 수 있습니다.",
    )


def result_display_content(level: str, total: int) -> dict[str, str]:
    if level == "높은 자아존중감":
        return {
            "subtitle": "현재의 자기 인식을 차분하게 잘 지지하고 있는 상태예요",
            "summary": "자신의 강점과 가치를 비교적 안정적으로 바라보고 계신 편으로 읽힙니다.",
            "interpretation": (
                f"현재 점수는 {total}점으로, 전반적인 자아존중감이 비교적 안정적인 높은 범위에 놓여 있습니다. "
                "이는 여러 상황에서 자신의 가치와 강점을 대체로 균형 있게 인식하고 있을 가능성을 시사합니다. "
                "물론 누구나 환경에 따라 자신감이 흔들릴 수 있지만, 지금의 결과는 스스로를 대하는 기본적인 시선이 비교적 단단하게 유지되고 있음을 보여줍니다."
            ),
            "guidance": (
                "지금의 균형감을 유지하기 위해 평소 자신에게 도움이 되었던 회복 방법이나 일상 습관을 함께 돌아보는 것도 좋습니다. "
                "만약 최근의 부담이나 변화로 인해 마음의 여유가 줄어든다면, 충분한 휴식과 주변의 지지를 통해 현재의 안정감을 부드럽게 이어가 보세요."
            ),
        }
    if level == "보통 수준의 자아존중감":
        return {
            "subtitle": "대체로 균형 잡힌 자기 시선을 유지하고 있는 모습으로 보입니다",
            "summary": "상황에 따라 흔들릴 수는 있지만, 기본적인 자기 평가는 무난한 범위에 가깝습니다.",
            "interpretation": (
                f"현재 점수는 {total}점으로, 전반적인 자아존중감이 평균적인 범위에 해당합니다. "
                "이는 많은 상황에서 자신을 비교적 균형 있게 바라볼 수 있음을 뜻하지만, 스트레스나 관계의 영향에 따라 자기평가가 일시적으로 흔들릴 수도 있음을 함께 보여줍니다. "
                "현재의 결과는 지나치게 부정적이기보다, 일상 속 경험에 따라 자신감의 높낮이가 자연스럽게 달라질 수 있는 상태로 이해하시면 좋습니다."
            ),
            "guidance": (
                "최근 스스로를 조금 더 지지해 주었던 순간과 반대로 위축되었던 순간을 함께 떠올려 보면 도움이 됩니다. "
                "만약 자신을 낮게 평가하는 생각이 자주 반복된다면, 혼자 견디기보다 신뢰할 수 있는 사람이나 전문가와 차분히 이야기해 보는 것도 좋은 방법입니다."
            ),
        }
    return {
        "subtitle": "지금은 자신을 대하는 시선이 다소 지쳐 있을 가능성이 있어요",
        "summary": "최근의 부담이나 반복된 자기비판이 자기 가치감을 낮추고 있을 수 있습니다.",
        "interpretation": (
            f"현재 점수는 {total}점으로, 자아존중감이 비교적 낮은 범위에 머물러 있는 것으로 보입니다. "
            "이 결과는 요즘 자신을 바라보는 마음이 다소 엄격해졌거나, 스스로의 장점과 가치를 충분히 느끼기 어려운 상태일 수 있음을 시사합니다. "
            "다만 이는 현재 시점의 자기보고 결과이며, 곧바로 어떤 상태를 단정하거나 진단하는 의미는 아닙니다. "
            "최근의 스트레스, 관계 경험, 피로 등이 함께 영향을 주었을 가능성도 차분히 살펴볼 필요가 있습니다."
        ),
        "guidance": (
            "이와 같은 느낌이 한동안 이어지거나 일상에서의 의욕, 관계, 감정 조절에까지 영향을 준다면 혼자만의 문제로 두지 않으셔도 괜찮습니다. "
            "자신을 비난하기보다 현재의 어려움을 이해하려는 태도로 접근하고, 필요하다면 상담기관이나 정신건강 전문가의 도움을 받아 보다 세심하게 살펴보시길 권합니다."
        ),
    }


def build_bullet_graph_html(total: int, min_score: int = 10, max_score: int = 50) -> str:
    score_span = max_score - min_score
    normalized_pct = ((total - min_score) / score_span) * 100 if score_span else 0
    fill_pct = max(0.0, min(100.0, normalized_pct))

    segments = [
        ("낮음", 10, 21, "band band-low"),
        ("보통", 22, 37, "band band-mid"),
        ("높음", 38, 50, "band band-high"),
    ]

    band_html: list[str] = []
    scale_html: list[str] = []
    for label, start, end, band_class in segments:
        band_start = max(min_score, start - 0.5)
        band_end = min(max_score, end + 0.5)
        left_pct = ((band_start - min_score) / score_span) * 100 if score_span else 0
        width_pct = ((band_end - band_start) / score_span) * 100 if score_span else 0
        center_pct = left_pct + (width_pct / 2)
        band_html.append(
            f"<span class='{band_class}' style='left:{left_pct:.2f}%; width:{width_pct:.2f}%;'></span>"
        )
        scale_html.append(
            f"<span class='bullet-scale-label' style='left:{center_pct:.2f}%;'>{label}</span>"
        )

    tick_values = [10, 20, 30, 40, 50]
    ticks: list[str] = []
    for tick in tick_values:
        tick_left = ((tick - min_score) / score_span) * 100 if score_span else 0
        ticks.append(
            "\n".join(
                [
                    f"<span class='bullet-tick' style='left:{tick_left:.2f}%;'>",
                    "    <span class='bullet-tick-line'></span>",
                    f"    <span class='bullet-tick-text'>{tick}</span>",
                    "</span>",
                ]
            )
        )

    graph_html = [
        '<div class="bullet-graph-card">',
        '    <div class="bullet-graph-head">',
        '        <div>',
        '            <div class="bullet-graph-title">점수 흐름</div>',
        '            <div class="bullet-graph-caption">전체 범위 안에서 현재 위치를 차분하게 보여드립니다</div>',
        '        </div>',
        f'        <div class="bullet-graph-chip">총점 {total} / {max_score}</div>',
        '    </div>',
        '    <div class="bullet-scale">',
        f"        {''.join(scale_html)}",
        '    </div>',
        '    <div class="bullet-track-wrap">',
        '        <div class="bullet-track">',
        f"            {''.join(band_html)}",
        f'            <div class="bullet-fill" style="--target-width:{fill_pct:.2f}%;"></div>',
        f'            <div class="bullet-marker" style="left:{fill_pct:.2f}%;">',
        '                <span class="bullet-marker-dot"></span>',
        f'                <span class="bullet-marker-pill">{total}점</span>',
        '            </div>',
        '        </div>',
        '        <div class="bullet-ticks">',
        f"            {''.join(ticks)}",
        '        </div>',
        '    </div>',
        '</div>',
    ]
    return "\n".join(graph_html)

def build_result_section_html(
    level: str,
    total: int,
    subtitle: str,
    summary: str,
    interpretation: str,
    guidance: str,
    bullet_graph_html: str,
) -> str:
    return f"""
    <section class="result-card result-section">
        <div class="result-topline">
            <div>
                <span class="badge">검사 완료</span>
                <h1 class="title-lg">검사 결과</h1>
                <p class="result-subcopy">현재 응답을 바탕으로 산출된 자아존중감 결과를 안내드립니다.</p>
            </div>
            <div class="result-label-chip">✓ {level}</div>
        </div>
        <div class="score-hero">
            <div class="score-stack">
                <div class="score-kicker">현재 총점</div>
                <p class="score-big">{total}<span class="score-unit">점</span></p>
            </div>
            <p class="result-summary">{subtitle}</p>
        </div>
        <p class="result-highlight-line">{summary}</p>
        {bullet_graph_html}
        <div class="note-box result-detail-box">
            <h2 class="title-md result-detail-title">결과 해석</h2>
            <p class="text result-detail-copy">{interpretation}</p>
        </div>
    </section>
    <section class="support-card result-section">
        <div class="support-card-head">
            <div class="support-icon">☘</div>
            <div>
                <h2 class="support-title">안내 드립니다.</h2>
            </div>
        </div>
        <p class="support-copy">{guidance}</p>
        <p class="support-copy support-copy-secondary">
            본 결과는 현재 시점의 자기보고를 바탕으로 한 참고 정보이며, 개인의 상태를 종합적으로 판단하는 전문적 평가나 진단을 대신하지 않습니다.
        </p>
    </section>
    """


def render_bullet_list(items: list[str], css_class: str = "intro-bullets") -> str:
    bullet_items = []
    for item in items:
        bullet_items.append(f"<li>{item}</li>")
    return f"<ul class='{css_class}'>" + "".join(bullet_items) + "</ul>"


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


def serialize_answers_payload(answers: dict[str, int] | None = None) -> str:
    source = answers if answers is not None else st.session_state.answers
    normalized = {}
    for i in range(1, len(QUESTIONS) + 1):
        key = f"q{i}"
        value = source.get(key) if isinstance(source, dict) else None
        if value in SCALE_SCORES:
            normalized[key] = int(value)
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def normalize_answers_dict(raw_answers: dict | None) -> dict[str, int]:
    normalized_answers = {}
    source = raw_answers if isinstance(raw_answers, dict) else {}
    for i in range(1, len(QUESTIONS) + 1):
        key = f"q{i}"
        value = source.get(key)
        if value is None:
            continue
        try:
            value_int = int(value)
        except (TypeError, ValueError):
            continue
        if value_int in SCALE_SCORES:
            normalized_answers[key] = value_int
    return normalized_answers


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



def inject_css():
    st.markdown(
        """
        <style>
        :root {
            --navy: #0F2747;
            --navy-deep: #0B1F38;
            --blue: #1E4E79;
            --surface: #F5FAFF;
            --surface-soft: #F8FBFF;
            --card: #FFFFFF;
            --border: #D6E2EC;
            --text: #16324F;
            --muted: #4F6B85;
            --green: #2E8B57;
            --green-soft: #EAF7F0;
            --widget-bg: rgba(13, 39, 71, 0.78);
            --widget-bg-soft: rgba(13, 39, 71, 0.92);
            --widget-border: rgba(214, 226, 236, 0.48);
            --widget-text: #F5FBFF;
            --widget-label: #F4F8FD;
            --widget-placeholder: rgba(225, 236, 246, 0.78);
            --widget-menu-bg: #0f3158;
            --widget-menu-hover: rgba(255, 255, 255, 0.10);
            --widget-menu-selected: rgba(255, 255, 255, 0.18);
        }

        html, body, .stApp,
        .stApp [data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, var(--navy-deep) 0%, var(--navy) 22%, #163B63 100%);
        }

        .stApp [data-testid="stMainBlockContainer"],
        .block-container {
            max-width: 980px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        .page-wrap {
            max-width: 920px;
            margin: 0 auto;
            padding: 0 0 88px;
        }

        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 24px;
            box-shadow: 0 18px 42px rgba(8, 32, 58, 0.18);
            margin-bottom: 18px;
        }

        .card.soft {
            background: var(--surface-soft);
        }

        .badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 999px;
            background: rgba(30, 78, 121, 0.1);
            color: var(--blue);
            font-size: 12px;
            font-weight: 800;
            margin-right: 8px;
            margin-bottom: 8px;
            border: 1px solid rgba(30, 78, 121, 0.18);
        }

        .title-lg,
        .title-md,
        .question-title,
        .result-score {
            color: var(--text);
            opacity: 1;
            text-shadow: none;
            filter: none;
            -webkit-text-fill-color: currentColor;
        }

        .title-lg {
            font-size: 28px;
            font-weight: 800;
            line-height: 1.3;
            margin: 6px 0 0;
        }

        .title-md {
            font-size: 20px;
            font-weight: 700;
            line-height: 1.35;
            margin: 0 0 8px;
        }

        .text {
            font-size: 15px;
            line-height: 1.7;
            color: var(--text);
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .muted,
        .footer-note,
        .progress-label {
            font-size: 13px;
            line-height: 1.7;
            color: var(--muted);
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .note-box {
            background: var(--green-soft);
            border: 1px solid rgba(46, 139, 87, 0.2);
            border-radius: 18px;
            padding: 14px 16px;
        }

        .intro-section {
            display: flex;
            flex-direction: column;
            gap: 18px;
        }

        .intro-section + .intro-section {
            margin-top: 8px;
        }

        .intro-subtitle {
            font-size: 14px;
            font-weight: 800;
            color: var(--blue);
            letter-spacing: 0.01em;
            margin: 0 0 10px;
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .intro-bullets {
            margin: 0;
            padding-left: 1.2rem;
            display: grid;
            gap: 10px;
        }

        .intro-bullets li {
            color: var(--text);
            font-size: 15px;
            line-height: 1.72;
            padding-left: 0.1rem;
            word-break: keep-all;
            overflow-wrap: anywhere;
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .intro-note,
        .privacy-note {
            border-radius: 18px;
            padding: 14px 16px;
            font-size: 13px;
            line-height: 1.7;
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .intro-note {
            background: rgba(30, 78, 121, 0.06);
            border: 1px solid rgba(30, 78, 121, 0.12);
            color: var(--muted);
        }

        .privacy-note {
            background: rgba(46, 139, 87, 0.08);
            border: 1px solid rgba(46, 139, 87, 0.16);
            color: #245F49;
        }

        .result-detail-box {
            margin-top: 24px;
        }

        .result-detail-title {
            margin-bottom: 8px;
        }

        .result-detail-copy {
            margin: 0;
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
            border: 1px solid rgba(214, 226, 236, 0.55);
            background: rgba(255, 255, 255, 0.1);
            color: #D8E7F5;
            backdrop-filter: blur(6px);
            -webkit-text-fill-color: currentColor;
        }

        .step-item.active .step-circle {
            background: #FFFFFF;
            border-color: #FFFFFF;
            color: var(--blue);
        }

        .step-item.done .step-circle {
            background: var(--green);
            border-color: var(--green);
            color: #FFFFFF;
        }

        .step-label {
            margin-top: 6px;
            font-size: 12px;
            color: #D8E7F5;
            font-weight: 700;
            text-align: center;
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .step-item.active .step-label,
        .step-item.done .step-label {
            color: #FFFFFF;
        }

        .step-line {
            width: 42px;
            height: 2px;
            background: rgba(214, 226, 236, 0.45);
            border-radius: 999px;
        }

        .step-line.done {
            background: var(--green);
        }

        .question-title {
            font-size: 18px;
            font-weight: 700;
            line-height: 1.55;
            margin-bottom: 0;
        }

        .progress-row {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            margin-top: 12px;
            margin-bottom: 8px;
        }

        .meter {
            width: 100%;
            height: 10px;
            background: #DBE8F4;
            border-radius: 999px;
            overflow: hidden;
        }

        .meter > span {
            display: block;
            height: 100%;
            background: linear-gradient(90deg, var(--blue) 0%, var(--green) 100%);
            border-radius: 999px;
        }

        .result-level {
            font-size: 18px;
            font-weight: 700;
            color: var(--green);
            margin: 6px 0 0;
        }

        .result-stack {
            display: flex;
            flex-direction: column;
        }

        .result-section {
            margin-bottom: 24px;
        }

        .result-stack > .result-section:last-child {
            margin-bottom: 0;
        }

        .result-card {
            position: relative;
            overflow: hidden;
            background:
                radial-gradient(circle at top right, rgba(46, 139, 87, 0.12), transparent 28%),
                linear-gradient(180deg, rgba(245, 250, 255, 1) 0%, rgba(255, 255, 255, 1) 38%, rgba(247, 251, 255, 1) 100%);
            border: 1px solid rgba(214, 226, 236, 0.9);
            border-radius: 28px;
            padding: 26px;
            box-shadow: 0 22px 48px rgba(8, 32, 58, 0.2);
        }

        .result-card::after {
            content: "";
            position: absolute;
            inset: auto -40px -80px auto;
            width: 220px;
            height: 220px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(30, 78, 121, 0.08), transparent 70%);
            pointer-events: none;
        }

        .result-topline {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 6px;
            flex-wrap: wrap;
        }

        .result-subcopy {
            color: var(--muted);
            font-size: 14px;
            line-height: 1.7;
            margin: 8px 0 0;
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .score-hero {
            display: grid;
            grid-template-columns: minmax(0, 240px) minmax(0, 1fr);
            gap: 20px;
            align-items: center;
            margin-top: 18px;
            margin-bottom: 18px;
        }

        .score-stack {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .score-kicker {
            font-size: 13px;
            font-weight: 800;
            color: var(--green);
            letter-spacing: 0.01em;
        }

        .score-big {
            font-size: clamp(52px, 9vw, 78px);
            line-height: 0.95;
            font-weight: 900;
            color: var(--navy);
            letter-spacing: -0.04em;
            margin: 0;
            -webkit-text-fill-color: currentColor;
        }

        .score-unit {
            font-size: 24px;
            color: var(--blue);
            font-weight: 800;
            margin-left: 6px;
            -webkit-text-fill-color: currentColor;
        }

        .result-label-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 14px;
            border-radius: 999px;
            background: rgba(46, 139, 87, 0.1);
            border: 1px solid rgba(46, 139, 87, 0.18);
            color: var(--green);
            font-size: 14px;
            font-weight: 800;
            -webkit-text-fill-color: currentColor;
        }

        .result-summary {
            font-size: 16px;
            line-height: 1.75;
            color: var(--text);
            margin: 0;
            text-align: left;
            align-self: center;
            max-width: 100%;
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .result-highlight-line {
            margin: 24px 0 0;
            padding-left: 14px;
            border-left: 4px solid rgba(46, 139, 87, 0.65);
            color: #245F49;
            font-size: 15px;
            line-height: 1.75;
            font-weight: 700;
            -webkit-text-fill-color: currentColor;
        }

        .bullet-graph-card {
            margin: 24px 0 0;
            padding: 18px 18px 14px;
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(242, 248, 255, 0.92) 0%, rgba(255, 255, 255, 0.96) 100%);
            border: 1px solid rgba(214, 226, 236, 0.95);
        }

        .bullet-graph-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            flex-wrap: wrap;
            margin-bottom: 18px;
        }

        .bullet-graph-title {
            color: var(--text);
            font-size: 16px;
            font-weight: 800;
            margin-bottom: 2px;
        }

        .bullet-graph-caption {
            color: var(--muted);
            font-size: 13px;
            line-height: 1.6;
        }

        .bullet-graph-chip {
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(15, 39, 71, 0.06);
            color: var(--blue);
            font-size: 13px;
            font-weight: 800;
        }

        .bullet-scale {
            position: relative;
            height: 18px;
            margin-bottom: 8px;
        }

        .bullet-scale-label {
            position: absolute;
            transform: translateX(-50%);
            font-size: 12px;
            font-weight: 800;
            color: var(--muted);
            white-space: nowrap;
        }

        .bullet-track-wrap {
            position: relative;
            padding-top: 26px;
        }

        .bullet-track {
            position: relative;
            height: 20px;
            border-radius: 999px;
            background: linear-gradient(90deg, rgba(198, 220, 239, 0.88) 0%, rgba(207, 227, 244, 0.96) 50%, rgba(184, 230, 206, 0.98) 100%);
            overflow: visible;
            box-shadow: inset 0 1px 2px rgba(15, 39, 71, 0.08);
        }

        .band {
            position: absolute;
            top: 0;
            bottom: 0;
            border-radius: 999px;
            background: transparent;
            pointer-events: none;
        }

        .band-low,
        .band-mid,
        .band-high {
            background: transparent;
        }

        .bullet-fill {
            position: absolute;
            inset: 3px auto 3px 3px;
            width: 0;
            max-width: calc(100% - 6px);
            border-radius: 999px;
            background: linear-gradient(90deg, rgba(30, 78, 121, 0.9) 0%, rgba(46, 139, 87, 0.95) 100%);
            box-shadow: 0 10px 18px rgba(46, 139, 87, 0.18);
            animation: bulletGrow 1.2s cubic-bezier(0.2, 0.7, 0.2, 1) forwards;
        }

        .bullet-marker {
            position: absolute;
            top: -20px;
            transform: translateX(-50%);
            animation: markerAppear 0.7s ease-out forwards;
        }

        .bullet-marker::after {
            content: "";
            position: absolute;
            left: 50%;
            top: 26px;
            transform: translateX(-50%);
            width: 2px;
            height: 34px;
            background: rgba(15, 39, 71, 0.28);
        }

        .bullet-marker-dot {
            display: block;
            width: 14px;
            height: 14px;
            margin: 0 auto 6px;
            border-radius: 999px;
            background: #FFFFFF;
            border: 4px solid var(--green);
            box-shadow: 0 8px 14px rgba(15, 39, 71, 0.14);
        }

        .bullet-marker-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 6px 10px;
            border-radius: 999px;
            background: var(--navy);
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 800;
            white-space: nowrap;
        }

        .bullet-ticks {
            position: relative;
            height: 26px;
            margin-top: 10px;
        }

        .bullet-tick {
            position: absolute;
            top: 0;
            transform: translateX(-50%);
            text-align: center;
        }

        .bullet-tick-line {
            display: block;
            width: 1px;
            height: 8px;
            background: rgba(15, 39, 71, 0.18);
            margin: 0 auto 4px;
        }

        .bullet-tick-text {
            display: block;
            color: var(--muted);
            font-size: 11px;
            font-weight: 700;
        }

        .support-card {
            background: linear-gradient(180deg, rgba(248, 251, 255, 1) 0%, rgba(242, 248, 255, 1) 100%);
            border: 1px solid rgba(214, 226, 236, 0.96);
            border-radius: 24px;
            padding: 22px;
            box-shadow: 0 12px 28px rgba(8, 32, 58, 0.12);
        }

        .support-card-head {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 10px;
        }

        .support-icon {
            width: 42px;
            height: 42px;
            border-radius: 14px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, rgba(30, 78, 121, 0.12) 0%, rgba(46, 139, 87, 0.16) 100%);
            color: var(--green);
            font-size: 20px;
        }

        .support-title {
            color: var(--text);
            font-size: 18px;
            font-weight: 800;
            margin: 0;
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .support-copy {
            color: var(--muted);
            font-size: 14px;
            line-height: 1.85;
            margin: 0;
            opacity: 1;
            -webkit-text-fill-color: currentColor;
        }

        .support-copy-secondary {
            margin-top: 10px;
        }

        .result-actions {
            padding-top: 0;
        }

        @keyframes bulletGrow {
            from { width: 0; }
            to { width: min(var(--target-width), calc(100% - 6px)); }
        }

        @keyframes markerAppear {
            from {
                opacity: 0;
                transform: translateX(-50%) translateY(6px);
            }
            to {
                opacity: 1;
                transform: translateX(-50%) translateY(0);
            }
        }

        .question-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 22px;
            margin-bottom: 14px;
            box-shadow: 0 14px 36px rgba(8, 32, 58, 0.12);
        }

        .survey-actions {
            padding-top: 8px;
            margin-top: 8px;
            margin-bottom: 18px;
        }

        .survey-payload-bridge,
        div[data-testid="stTextArea"]:has(textarea[aria-label="survey_payload_bridge"]) {
            display: none;
        }

        /* ---------- widget labels ---------- */
        .stApp [data-testid="stWidgetLabel"] p,
        .stApp div[data-testid="stTextInput"] label p,
        .stApp div[data-testid="stSelectbox"] label p,
        .stApp div[data-testid="stCheckbox"] label p,
        .stApp div[data-testid="stCheckbox"] label span,
        .stApp div[data-testid="stNumberInput"] label p {
            color: var(--widget-label) !important;
            opacity: 1 !important;
            text-shadow: none !important;
            filter: none !important;
            -webkit-text-fill-color: var(--widget-label) !important;
            font-weight: 700 !important;
            line-height: 1.55 !important;
        }

        .stApp div[data-testid="stCheckbox"] label {
            gap: 0.6rem !important;
            align-items: flex-start !important;
        }

        .stApp div[data-testid="stCheckbox"] input {
            accent-color: #FF6B6B;
        }

        /* ---------- text input ---------- */
        .stApp div[data-testid="stTextInput"] [data-baseweb="input"],
        .stApp div[data-testid="stTextInput"] > div {
            background: transparent !important;
        }

        .stApp div[data-testid="stTextInput"] [data-baseweb="input"] > div,
        .stApp div[data-testid="stTextInput"] input {
            border-radius: 16px !important;
        }

        .stApp div[data-testid="stTextInput"] [data-baseweb="input"] > div {
            background: var(--widget-bg-soft) !important;
            border: 1px solid var(--widget-border) !important;
            min-height: 46px !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04) !important;
        }

        .stApp div[data-testid="stTextInput"] input {
            color: var(--widget-text) !important;
            caret-color: var(--widget-text) !important;
            -webkit-text-fill-color: var(--widget-text) !important;
            background: transparent !important;
        }

        .stApp div[data-testid="stTextInput"] input::placeholder {
            color: var(--widget-placeholder) !important;
            opacity: 1 !important;
            -webkit-text-fill-color: var(--widget-placeholder) !important;
        }

        /* ---------- selectbox control ---------- */
        .stApp div[data-testid="stSelectbox"] [data-baseweb="select"] {
            background: transparent !important;
        }

        .stApp div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background: var(--widget-bg-soft) !important;
            border: 1px solid var(--widget-border) !important;
            border-radius: 16px !important;
            min-height: 46px !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04) !important;
        }

        .stApp div[data-testid="stSelectbox"] [data-baseweb="select"] input,
        .stApp div[data-testid="stSelectbox"] [data-baseweb="select"] span,
        .stApp div[data-testid="stSelectbox"] [data-baseweb="select"] div {
            color: var(--widget-text) !important;
            opacity: 1 !important;
            -webkit-text-fill-color: var(--widget-text) !important;
        }

        .stApp div[data-testid="stSelectbox"] [data-baseweb="select"] input::placeholder,
        .stApp div[data-testid="stSelectbox"] [data-baseweb="select"] div[aria-hidden="true"] {
            color: var(--widget-placeholder) !important;
            -webkit-text-fill-color: var(--widget-placeholder) !important;
            opacity: 1 !important;
        }

        .stApp div[data-testid="stSelectbox"] svg {
            fill: #D7E8F7 !important;
            color: #D7E8F7 !important;
        }

        /* ---------- selectbox dropdown menu ---------- */
        body [data-baseweb="popover"],
        body [data-baseweb="popover"] > div,
        body ul[role="listbox"],
        body div[role="listbox"] {
            background: var(--widget-menu-bg) !important;
            border: 1px solid rgba(214, 226, 236, 0.18) !important;
            border-radius: 14px !important;
            box-shadow: 0 16px 30px rgba(4, 18, 34, 0.32) !important;
        }

        body li[role="option"],
        body div[role="option"] {
            color: #F6FBFF !important;
            -webkit-text-fill-color: #F6FBFF !important;
            background: transparent !important;
        }

        body li[role="option"] *,
        body div[role="option"] * {
            color: inherit !important;
            -webkit-text-fill-color: inherit !important;
            opacity: 1 !important;
        }

        body li[role="option"]:hover,
        body div[role="option"]:hover {
            background: var(--widget-menu-hover) !important;
        }

        body li[role="option"][aria-selected="true"],
        body div[role="option"][aria-selected="true"] {
            background: var(--widget-menu-selected) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }

        /* ---------- captions / alerts ---------- */
        .stApp div[data-testid="stCaptionContainer"] p {
            color: #DCEAF8 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #DCEAF8 !important;
        }

        .stApp div[data-testid="stAlertContainer"] p,
        .stApp div[data-testid="stAlertContainer"] [role="alert"] {
            opacity: 1 !important;
        }

        /* ---------- radio cards ---------- */
        div[data-testid="stRadio"] > label {
            display: none !important;
        }

        div[data-testid="stRadio"] {
            width: 100%;
            margin: 0 0 22px;
        }

        div[data-testid="stRadio"] [role="radiogroup"] {
            display: grid !important;
            grid-template-columns: repeat(5, minmax(0, 1fr)) !important;
            gap: 12px !important;
            width: 100% !important;
            align-items: stretch !important;
            justify-items: stretch !important;
        }

        div[data-testid="stRadio"] [role="radiogroup"] > label,
        div[data-testid="stRadio"] [role="radiogroup"] > div {
            width: 100% !important;
            min-width: 0 !important;
            max-width: none !important;
            display: flex !important;
            align-items: stretch !important;
        }

        div[data-testid="stRadio"] [role="radiogroup"] > div > label,
        div[data-testid="stRadio"] [role="radiogroup"] > label,
        div[data-testid="stRadio"] [data-baseweb="radio"] {
            position: relative !important;
            margin: 0 !important;
            min-height: 68px !important;
            width: 100% !important;
            height: 100% !important;
            border: 1px solid rgba(165, 188, 212, 0.9) !important;
            border-radius: 16px !important;
            background: linear-gradient(180deg, #FFFFFF 0%, #F6FBFF 100%) !important;
            padding: 0 !important;
            display: flex !important;
            align-items: stretch !important;
            justify-content: stretch !important;
            overflow: hidden !important;
            cursor: pointer !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92) !important;
            transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease, background 0.16s ease !important;
        }

        div[data-testid="stRadio"] [role="radiogroup"] > div > label:hover,
        div[data-testid="stRadio"] [role="radiogroup"] > label:hover,
        div[data-testid="stRadio"] [data-baseweb="radio"]:hover {
            border-color: rgba(30, 78, 121, 0.58) !important;
            background: linear-gradient(180deg, #FFFFFF 0%, #EDF6FF 100%) !important;
            transform: translateY(-1px);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.96), 0 10px 20px rgba(15, 39, 71, 0.09) !important;
        }

        div[data-testid="stRadio"] [role="radiogroup"] > div > label[data-selected="true"],
        div[data-testid="stRadio"] [role="radiogroup"] > div > label:has(input[type="radio"]:checked),
        div[data-testid="stRadio"] [role="radiogroup"] > label[data-selected="true"],
        div[data-testid="stRadio"] [role="radiogroup"] > label:has(input[type="radio"]:checked),
        div[data-testid="stRadio"] [data-baseweb="radio"]:has(input[type="radio"]:checked) {
            border-color: #1F6FB2 !important;
            background: linear-gradient(135deg, rgba(217, 239, 255, 0.98) 0%, rgba(231, 247, 238, 0.98) 100%) !important;
            transform: translateY(-1px);
            box-shadow:
                inset 0 0 0 2px rgba(31, 111, 178, 0.22),
                inset 0 1px 0 rgba(255, 255, 255, 0.96),
                0 14px 28px rgba(19, 74, 120, 0.18) !important;
        }

        div[data-testid="stRadio"] [role="radiogroup"] > div > label > div:first-child:not([data-testid="stMarkdownContainer"]),
        div[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child:not([data-testid="stMarkdownContainer"]),
        div[data-testid="stRadio"] [data-baseweb="radio"] > div:first-child,
        div[data-testid="stRadio"] input[type="radio"],
        div[data-testid="stRadio"] svg {
            position: absolute !important;
            opacity: 0 !important;
            pointer-events: none !important;
            width: 0 !important;
            height: 0 !important;
            margin: 0 !important;
            display: none !important;
        }

        div[data-testid="stRadio"] [role="radiogroup"] > div > label > div:last-child,
        div[data-testid="stRadio"] [role="radiogroup"] > label > div:last-child,
        div[data-testid="stRadio"] [data-baseweb="radio"] > div:last-child,
        div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] {
            display: flex !important;
            align-items: stretch !important;
            justify-content: stretch !important;
            width: 100% !important;
            min-width: 0 !important;
            min-height: 68px !important;
            margin: 0 !important;
            flex: 1 1 auto !important;
        }

        div[data-testid="stRadio"] [role="radiogroup"] p {
            margin: 0 !important;
            width: 100% !important;
            min-width: 0 !important;
            min-height: 68px !important;
            height: 100% !important;
            padding: 14px 12px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
            white-space: normal !important;
            word-break: keep-all !important;
            overflow-wrap: anywhere !important;
            color: var(--text) !important;
            font-size: 13px !important;
            font-weight: 700 !important;
            line-height: 1.25 !important;
            -webkit-text-fill-color: var(--text) !important;
            transition: color 0.16s ease, font-weight 0.16s ease !important;
        }

        div[data-testid="stRadio"] [role="radiogroup"] > div > label[data-selected="true"] p,
        div[data-testid="stRadio"] [role="radiogroup"] > div > label:has(input[type="radio"]:checked) p,
        div[data-testid="stRadio"] [role="radiogroup"] > label[data-selected="true"] p,
        div[data-testid="stRadio"] [role="radiogroup"] > label:has(input[type="radio"]:checked) p,
        div[data-testid="stRadio"] [data-baseweb="radio"]:has(input[type="radio"]:checked) p {
            color: #0D3F68 !important;
            font-weight: 800 !important;
            -webkit-text-fill-color: #0D3F68 !important;
        }

        /* ---------- buttons ---------- */
        div[data-testid="stButton"] {
            width: 100%;
        }

        div[data-testid="stButton"] > button {
            width: 100%;
            border-radius: 14px;
            min-height: 46px;
            border: 1px solid var(--border);
            background: #FFFFFF;
            color: var(--text);
            font-weight: 700;
        }

        div[data-testid="stButton"] > button[kind="primary"] {
            background: linear-gradient(90deg, var(--blue) 0%, var(--green) 100%);
            color: #FFFFFF;
            border: none;
            box-shadow: 0 14px 24px rgba(30, 78, 121, 0.2);
        }

        div[data-testid="stButton"] > button:hover {
            border-color: rgba(30, 78, 121, 0.6);
            color: var(--blue);
        }

        div[data-testid="stButton"] > button[kind="primary"]:hover {
            color: #FFFFFF;
            filter: brightness(1.03);
        }

        @media (max-width: 900px) {
            div[data-testid="stRadio"] [role="radiogroup"] {
                grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            }

            .page-wrap {
                padding-bottom: 96px;
            }

            .score-hero {
                grid-template-columns: 1fr;
                align-items: start;
            }
        }

        @media (max-width: 640px) {
            .card,
            .question-card,
            .result-card,
            .support-card {
                padding: 20px 18px;
            }

            .intro-section {
                gap: 16px;
            }

            .intro-bullets {
                padding-left: 1.05rem;
                gap: 8px;
            }

            .intro-bullets li {
                font-size: 14px;
                line-height: 1.68;
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

    st.markdown(
        f"""
        <section class="card">
            <span class="badge">RSES 기반</span>
            <span class="badge">총 10문항</span>
            <div class="intro-section">
                <div>
                    <h1 class="title-lg">{EXAM_TITLE}</h1>
                    <p class="muted" style="margin:8px 0 0;">검사 안내와 유의사항을 확인한 뒤 진행해 주세요.</p>
                </div>
                <div>
                    <p class="intro-subtitle">검사 설명</p>
                    {intro_desc_html}
                </div>
                <div>
                    <p class="intro-subtitle">진행 전 유의사항</p>
                    {intro_notice_html}
                </div>
                <div class="intro-note">
                    입력하신 응답은 현재 세션에서 결과 산출에 사용되며, 재접속시 검사를 다시 진행하셔야합니다.
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <section class="card soft">
            <div class="intro-section">
                <div>
                    <h2 class="title-md">개인정보 수집 및 검사 진행 동의</h2>
                    <p class="muted" style="margin:8px 0 0;">검사 진행과 결과 제공을 위해 아래 내용을 확인해 주세요.</p>
                </div>
                <div>
                    {privacy_html}
                </div>
                <div class="privacy-note">
                    아래 항목에 동의하시면 검사 시작 버튼이 활성화되며, 기존 동의 및 시작 시각 기록 로직은 동일하게 적용됩니다.
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    consent = st.checkbox(
        "위 안내를 확인했으며, 개인정보 수집·이용 및 검사 진행에 동의합니다.",
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
    answered_count = len(st.session_state.answers)
    progress_pct = int((answered_count / len(QUESTIONS)) * 100)

    st.markdown(
        f"""
        <section class="card">
            <span class="badge">문항 10개</span>
            <h1 class="title-lg">문항 응답</h1>
            <p class="text">현재 자신의 모습에 가장 가까운 응답을 선택해 주세요.</p>
            <div class="progress-row">
                <span class="progress-label">저장된 진행률 {answered_count}/10</span>
                <span class="progress-label">{progress_pct}%</span>
            </div>
            <div class="meter"><span style="width:{progress_pct}%;"></span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    for i, question in enumerate(QUESTIONS, start=1):
        key = f"q{i}"
        selected_score = st.session_state.answers.get(key)
        radio_key = f"{key}_radio"

        if radio_key not in st.session_state:
            st.session_state[radio_key] = label_from_score(selected_score)

        st.markdown(f"<section class='question-card'><div class='question-title'>{i}. {question}</div>", unsafe_allow_html=True)
        selected_label = st.radio(
            f"{i}. {question}",
            options=SCALE_LABELS,
            index=(selected_score - 1) if selected_score in SCALE_SCORES else None,
            key=radio_key,
            horizontal=True,
            label_visibility="collapsed",
        )
        st.markdown("</section>", unsafe_allow_html=True)

        score = score_from_label(selected_label)
        if score is None:
            st.session_state.answers.pop(key, None)
        else:
            st.session_state.answers[key] = score

    payload, missing = build_payload()
    answered_count = len(st.session_state.answers)


    if len(missing) != 0:
        st.caption("모든 문항에 응답하면 결과 보기가 활성화됩니다.")

    st.markdown("<div class='survey-actions'>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    prev_clicked = c1.button("이전", use_container_width=True)
    submit_clicked = c2.button("결과 보기", type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if prev_clicked:
        st.session_state.page = "info"
        st.rerun()

    if submit_clicked:
        payload, missing = build_payload()
        all_done = len(missing) == 0

        if all_done:
            st.session_state.meta["submitted_ts"] = now_iso()
            payload, missing = build_payload()
            st.session_state.result_payload = payload
            st.session_state.page = "result"
            st.rerun()
        else:
            st.error("모든 문항에 응답해 주세요.")

    payload, missing = build_payload()
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
    display_content = result_display_content(level, total)
    subtitle = display_content["subtitle"]
    summary = display_content["summary"]
    interpretation = display_content["interpretation"]
    guidance = display_content["guidance"]
    score_min = result.get("score_range", {}).get("min", 10)
    score_max = result.get("score_range", {}).get("max", 50)
    bullet_graph_html = build_bullet_graph_html(total, min_score=score_min, max_score=score_max)
    result_section_html = build_result_section_html(
        level=level,
        total=total,
        subtitle=subtitle,
        summary=summary,
        interpretation=interpretation,
        guidance=guidance,
        bullet_graph_html=bullet_graph_html,
    )
    st.markdown(
        "<div class='result-stack'>"
        f"{result_section_html}"
        "<section class='result-actions result-section'>",
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
    st.markdown("</div></div>", unsafe_allow_html=True)

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
    raw = os.getenv("ENABLE_DB_INSERT", "false")
    return str(raw).strip().lower() == "true"


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
