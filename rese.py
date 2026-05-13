# 운영/병합 환경:
#   ENABLE_DB_INSERT=true   -> DB insert 수행
#   ENABLE_DB_INSERT=false  -> DB insert 미수행 + debug payload 노출
#
# 설계 원칙:
# - 부모 window/document 접근 JS를 사용하지 않음
# - 입력/선택 위젯은 PHQ-9 / GAD-7의 안정 패턴처럼 CSS만으로 제어
# - main() 진입, ENABLE_DB_INSERT 분기, DB import/호출 하단 배치를 유지

# -*- coding: utf-8 -*-
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="자아존중감 자기평가 검사",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

KST = timezone(timedelta(hours=9))

EXAM_NAME = "RSES"
EXAM_TITLE = "자아존중감 자기평가 검사"
EXAM_SUBTITLE = "Rosenberg Self-Esteem Scale 기반"
EXAM_VERSION = "streamlit_2.0"

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


def rses_level(total: int) -> Tuple[str, str]:
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


def result_display_content(level: str, total: int) -> Dict[str, str]:
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
        ("낮음", 10, 21),
        ("보통", 22, 37),
        ("높음", 38, 50),
    ]

    scale_html: List[str] = []
    ticks_html: List[str] = []
    for label, start, end in segments:
        band_start = max(min_score, start - 0.5)
        band_end = min(max_score, end + 0.5)
        center_pct = (((band_start + band_end) / 2) - min_score) / score_span * 100 if score_span else 0
        scale_html.append(f"<span class='bullet-scale-label' style='left:{center_pct:.2f}%;'>{label}</span>")

    for tick in [10, 20, 30, 40, 50]:
        tick_left = ((tick - min_score) / score_span) * 100 if score_span else 0
        ticks_html.append(
            "\n".join(
                [
                    f"<span class='bullet-tick' style='left:{tick_left:.2f}%;'>",
                    "  <span class='bullet-tick-line'></span>",
                    f"  <span class='bullet-tick-text'>{tick}</span>",
                    "</span>",
                ]
            )
        )

    return "\n".join(
        [
            '<div class="bullet-graph-card">',
            '  <div class="bullet-graph-head">',
            '    <div>',
            '      <div class="bullet-graph-title">점수 흐름</div>',
            '      <div class="bullet-graph-caption">전체 범위 안에서 현재 위치를 차분하게 보여드립니다</div>',
            '    </div>',
            f'    <div class="bullet-graph-chip">총점 {total} / {max_score}</div>',
            '  </div>',
            '  <div class="bullet-scale">',
            f'    {"".join(scale_html)}',
            '  </div>',
            '  <div class="bullet-track-wrap">',
            '    <div class="bullet-track">',
            f'      <div class="bullet-fill" style="--target-width:{fill_pct:.2f}%;"></div>',
            f'      <div class="bullet-marker" style="left:{fill_pct:.2f}%">',
            '        <span class="bullet-marker-dot"></span>',
            f'        <span class="bullet-marker-pill">{total}점</span>',
            '      </div>',
            '    </div>',
            '    <div class="bullet-ticks">',
            f'      {"".join(ticks_html)}',
            '    </div>',
            '  </div>',
            '</div>',
        ]
    )


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
                <h1 class="title-lg card-ink">검사 결과</h1>
                <p class="result-subcopy">현재 응답을 바탕으로 산출된 자아존중감 결과를 안내드립니다.</p>
            </div>
            <div class="result-label-chip">✓ {level}</div>
        </div>
        <div class="score-hero score-hero-vertical">
            <div class="score-stack">
                <div class="score-kicker">현재 총점</div>
                <p class="score-big">{total}<span class="score-unit">점</span></p>
            </div>
            <p class="result-summary">{subtitle}</p>
        </div>
        <p class="result-highlight-line">{summary}</p>
        {bullet_graph_html}
        <div class="note-box result-detail-box">
            <h2 class="title-md card-ink result-detail-title">결과 해석</h2>
            <p class="result-detail-copy">{interpretation}</p>
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


def render_bullet_list(items: List[str], css_class: str = "intro-bullets") -> str:
    return f"<ul class='{css_class}'>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def reverse_score(value: int) -> int:
    return 6 - value


def now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def get_dev_mode() -> bool:
    try:
        return str(st.query_params.get("dev", "0")) == "1"
    except Exception:
        try:
            return str(st.experimental_get_query_params().get("dev", ["0"])[0]) == "1"
        except Exception:
            return False


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

    if "answers" not in st.session_state:
        st.session_state.answers = {f"q{i}": None for i in range(1, len(QUESTIONS) + 1)}

    if "result_payload" not in st.session_state:
        st.session_state.result_payload = None

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
        "phone": "",
        "email": "",
    }
    st.session_state.answers = {f"q{i}": None for i in range(1, len(QUESTIONS) + 1)}
    st.session_state.result_payload = None
    st.session_state.db_insert_done = False
    st.session_state.close_attempted = False


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


def _sanitize_csv_value(v) -> str:
    if v is None:
        return ""
    s = str(v)
    s = s.replace("\n", " ").replace("\r", " ")
    s = s.replace(",", " ")
    return s.strip()


def dict_to_kv_csv(d: Dict) -> str:
    if not isinstance(d, dict):
        return ""
    return ",".join(f"{_sanitize_csv_value(k)}={_sanitize_csv_value(v)}" for k, v in d.items())


def build_payload() -> Tuple[Dict, List[str]]:
    total_score = 0
    missing: List[str] = []
    item_scores_raw: Dict[str, Optional[int]] = {}
    item_scores_final: Dict[str, Optional[int]] = {}

    for i in range(1, len(QUESTIONS) + 1):
        key = f"q{i}"
        value = st.session_state.answers.get(key)
        if value is None:
            missing.append(key)
            item_scores_raw[key] = None
            item_scores_final[key] = None
            continue

        raw_value = int(value)
        item_scores_raw[key] = raw_value
        final_value = reverse_score(raw_value) if i in REVERSE_ITEMS else raw_value
        item_scores_final[key] = final_value
        total_score += final_value

    level, interpretation = rses_level(total_score)

    payload = {
        "instrument": EXAM_NAME,
        "title": EXAM_TITLE,
        "version": EXAM_VERSION,
        "respondent_id": st.session_state.meta["respondent_id"],
        "consent": st.session_state.meta["consent"],
        "consent_ts": st.session_state.meta["consent_ts"],
        "started_ts": st.session_state.meta["started_ts"],
        "submitted_ts": st.session_state.meta["submitted_ts"],
        "examinee": dict(st.session_state.examinee),
        "items": {
            "scale": {str(i): label for i, label in enumerate(SCALE_LABELS, start=1)},
            "questions": {f"q{i}": QUESTIONS[i - 1] for i in range(1, len(QUESTIONS) + 1)},
            "answers": {f"q{i}": st.session_state.answers.get(f"q{i}") for i in range(1, len(QUESTIONS) + 1)},
            "scores_raw": item_scores_raw,
            "scores_final": item_scores_final,
            "reverse_items": [f"q{i}" for i in sorted(REVERSE_ITEMS)],
        },
        "result": {
            "total": total_score,
            "level": level,
            "interpretation": interpretation,
            "score_range": {"min": 10, "max": 50},
        },
    }
    return payload, missing


def build_exam_data(payload: Dict) -> Dict:
    examinee = payload.get("examinee", {}) or {}
    answers = ((payload.get("items", {}) or {}).get("answers", {})) or {}
    result = ((payload.get("result", {}) or {})) or {}

    consent_col = {
        "consent": payload.get("consent", False),
        "consent_ts": payload.get("consent_ts", ""),
        "started_ts": payload.get("started_ts", ""),
        "submitted_ts": payload.get("submitted_ts", ""),
        "respondent_id": payload.get("respondent_id", ""),
        "version": payload.get("version", ""),
    }

    examinee_col = {
        "name": examinee.get("name", ""),
        "gender": examinee.get("gender", ""),
        "age": examinee.get("age", ""),
        "region": examinee.get("region", ""),
        "phone": examinee.get("phone", ""),
        "email": examinee.get("email", ""),
    }

    answers_col = {f"q{i}": answers.get(f"q{i}", "") for i in range(1, len(QUESTIONS) + 1)}
    result_col = {
        "total": result.get("total", ""),
        "level": result.get("level", ""),
        "interpretation": result.get("interpretation", ""),
        "reverse_items": "|".join(((payload.get("items", {}) or {}).get("reverse_items", []))),
    }

    return {
        "exam_name": EXAM_NAME,
        "consent_col": dict_to_kv_csv(consent_col),
        "examinee_col": dict_to_kv_csv(examinee_col),
        "answers_col": dict_to_kv_csv(answers_col),
        "result_col": dict_to_kv_csv(result_col),
    }


def render_stepper(current_page: str) -> None:
    steps = [
        ("intro", "동의"),
        ("info", "정보입력"),
        ("survey", "문항응답"),
        ("result", "결과"),
    ]
    idx_map = {key: i for i, (key, _) in enumerate(steps)}
    current_idx = idx_map.get(current_page, 0)

    html_parts: List[str] = ["<div class='stepper'>"]
    for i, (_key, label) in enumerate(steps):
        state = "done" if i < current_idx else "active" if i == current_idx else "todo"
        html_parts.append(
            f"""
            <div class='step-item {state}'>
                <div class='step-circle'>{i + 1}</div>
                <div class='step-label'>{label}</div>
            </div>
            """
        )
        if i < len(steps) - 1:
            line_state = "done" if i < current_idx else "todo"
            html_parts.append(f"<div class='step-line {line_state}'></div>")
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_choice_button_row(*, options: List[str], scores: List[int], state_key: str, columns_count: int = 5) -> Optional[int]:
    current_value = st.session_state.answers.get(state_key)
    cols = st.columns(columns_count, gap="small")
    clicked_value: Optional[int] = None

    for idx, (option, score) in enumerate(zip(options, scores)):
        with cols[idx]:
            is_selected = current_value == score
            if st.button(
                option,
                key=f"{state_key}_choice_{score}",
                type="primary" if is_selected else "secondary",
                use_container_width=True,
            ):
                clicked_value = score

    if clicked_value is not None and clicked_value != current_value:
        st.session_state.answers[state_key] = clicked_value
        st.rerun()

    return st.session_state.answers.get(state_key)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --content-max-width: 940px;

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
            --radius-lg: 18px;
            --radius-md: 14px;
            --shadow-sm: 0 8px 24px rgba(2, 8, 23, 0.28);
            --shadow-md: 0 18px 40px rgba(2, 8, 23, 0.38);

            --card-ink: #16324F;
            --card-muted: #4F6B85;
            --card-border: #D6E2EC;
            --card-surface: #FFFFFF;
            --card-surface-soft: #F8FBFF;
            --green: #2E8B57;
            --green-soft: #EAF7F0;
            --blue: #1E4E79;
            --blue-strong: #2E618F;
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
            padding-top: 0.9rem !important;
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
            animation: fadeIn .22s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .stepper {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            flex-wrap: wrap;
            margin: 4px 0 22px;
        }

        .step-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 74px;
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
            background: rgba(255, 255, 255, 0.10);
            color: #D8E7F5;
        }

        .step-item.active .step-circle {
            background: #FFFFFF;
            border-color: #FFFFFF;
            color: var(--blue);
        }

        .step-item.done .step-circle {
            background: var(--success);
            border-color: var(--success);
            color: #FFFFFF;
        }

        .step-label {
            margin-top: 6px;
            font-size: 12px;
            color: #D8E7F5;
            font-weight: 700;
            text-align: center;
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
            background: var(--success);
        }

        .card {
            background: linear-gradient(180deg, rgba(255,255,255,.015), rgba(255,255,255,.005)), var(--surface);
            border: 1px solid var(--line);
            border-radius: var(--radius-xl);
            box-shadow: var(--shadow-sm);
            padding: 22px;
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
            color: #89beff;
            font-size: 12px;
            font-weight: 800;
            margin-right: 8px;
            margin-bottom: 8px;
            border: 1px solid rgba(79, 156, 255, 0.22);
        }

        .title-lg {
            font-size: clamp(26px, 3vw, 32px) !important;
            font-weight: 850;
            line-height: 1.28;
            color: var(--text);
            margin: 4px 0 0;
        }

        .title-md {
            font-size: clamp(18px, 2.2vw, 20px) !important;
            font-weight: 750;
            line-height: 1.35;
            color: var(--text);
            margin: 0 0 8px;
        }

        .card-ink {
            color: var(--card-ink) !important;
        }

        .text {
            font-size: 15px !important;
            line-height: 1.72;
            color: var(--muted);
        }

        .muted {
            font-size: 14px !important;
            line-height: 1.65;
            color: var(--muted);
        }

        .card p, .card li {
            color: var(--text);
            opacity: 1 !important;
        }

        .intro-bullets {
            margin: 0;
            padding-left: 1.1rem;
            display: grid;
            gap: .68rem;
            color: var(--muted);
        }

        .intro-bullets li {
            line-height: 1.72;
            word-break: keep-all;
        }

        .intro-section {
            display: grid;
            gap: 1rem;
        }

        .intro-note, .privacy-note, .note-box {
            border-radius: 14px;
            padding: 14px 16px;
            border: 1px dashed rgba(96,165,250,.22);
            background: linear-gradient(180deg, rgba(79,156,255,.04), rgba(79,156,255,.02)), var(--surface-2);
            color: var(--muted);
        }

        .section-title {
            font-size: 14px;
            font-weight: 800;
            color: #89beff;
            margin: 0 0 8px;
        }

        /* labels */
        div[data-testid="stTextInput"] label,
        div[data-testid="stSelectbox"] label,
        div[data-testid="stCheckbox"] label,
        div[data-testid="stTextInput"] [data-testid="stWidgetLabel"] *,
        div[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] *,
        div[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] *,
        div[data-testid="stCaptionContainer"] p {
            color: var(--text) !important;
            font-weight: 700 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: var(--text) !important;
        }

        /* input */
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

        div[data-testid="stTextInput"] input:hover {
            background: var(--field-bg-hover) !important;
            border-color: var(--field-border-strong) !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: var(--field-border-strong) !important;
            box-shadow: var(--field-shadow) !important;
            background: var(--field-bg) !important;
        }

        div[data-testid="stTextInput"] input::placeholder {
            color: var(--muted) !important;
            opacity: 1 !important;
            -webkit-text-fill-color: var(--muted) !important;
        }

        /* select visible field */
        div[data-testid="stSelectbox"] [data-baseweb="select"] {
            width: 100% !important;
        }

        div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background: var(--field-bg) !important;
            color: var(--text) !important;
            border: 1px solid var(--field-border) !important;
            border-radius: 14px !important;
            min-height: 48px !important;
            box-shadow: none !important;
            transition: border-color .18s ease, box-shadow .18s ease, background-color .18s ease !important;
            padding: 2px 10px !important;
        }

        div[data-testid="stSelectbox"] [data-baseweb="select"] > div:hover {
            background: var(--field-bg-hover) !important;
            border-color: var(--field-border-strong) !important;
        }

        div[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
            background: var(--field-bg) !important;
            border-color: var(--field-border-strong) !important;
            box-shadow: var(--field-shadow) !important;
        }

        /* select text, selected value, placeholder, icon */
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

        div[data-testid="stSelectbox"] [data-baseweb="select"] div[aria-hidden="true"],
        div[data-testid="stSelectbox"] [data-baseweb="select"] input::placeholder {
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
            opacity: 1 !important;
        }

        div[data-testid="stSelectbox"] [data-baseweb="select"] svg,
        div[data-testid="stSelectbox"] [data-baseweb="select"] path {
            fill: var(--text) !important;
            color: var(--text) !important;
            opacity: 1 !important;
        }

        /* dropdown panel */
        div[data-baseweb="popover"] {
            z-index: 99999 !important;
        }

        div[data-baseweb="popover"] [data-baseweb="menu"],
        div[data-baseweb="popover"] [role="listbox"],
        div[data-baseweb="popover"] ul {
            background: var(--surface-2) !important;
            border: 1px solid var(--field-border) !important;
            border-radius: 14px !important;
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

        /* checkbox */
        div[data-testid="stCheckbox"] svg {
            color: var(--primary) !important;
        }

        /* alerts */
        div[data-testid="stAlert"] {
            background: rgba(255,115,115,.14) !important;
            border: 1px solid rgba(255,115,115,.24) !important;
            border-radius: 14px !important;
            color: #ffd6d6 !important;
        }

        div[data-testid="stAlert"] * {
            color: #ffd6d6 !important;
        }

        /* buttons */
        div[data-testid="stButton"] > button {
            border-radius: 12px !important;
            min-height: 46px;
            border: 1px solid var(--line) !important;
            background: var(--surface-3) !important;
            color: var(--text) !important;
            font-weight: 700 !important;
            transition: all .18s ease;
            box-shadow: none !important;
        }

        div[data-testid="stButton"] > button:hover {
            border-color: var(--field-border-strong) !important;
            background: #163864 !important;
            box-shadow: 0 0 0 2px rgba(79, 156, 255, 0.10) !important;
        }

        div[data-testid="stButton"] > button[kind="primary"] {
            border-color: var(--field-border-strong) !important;
            background: linear-gradient(180deg, #1d4f8d, #163f73) !important;
            color: #ffffff !important;
            box-shadow: 0 0 0 1px rgba(79, 156, 255, 0.28), 0 8px 18px rgba(79, 156, 255, 0.18) !important;
        }

        div[data-testid="stButton"] > button[kind="primary"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        div[data-testid="stButton"] > button:disabled {
            opacity: .56 !important;
            cursor: not-allowed !important;
            box-shadow: none !important;
        }

        .survey-shell {
            width: min(100%, var(--content-max-width));
            margin: 0 auto;
        }

        .question-card {
            background: linear-gradient(180deg, rgba(255,255,255,.015), rgba(255,255,255,.005)), var(--surface);
            border: 1px solid var(--line);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-sm);
            padding: 20px;
            margin-bottom: 14px;
        }

        .question-title {
            font-size: 1rem;
            font-weight: 760;
            color: var(--text);
            margin-bottom: .55rem;
            line-height: 1.62;
        }

        .answer-segments div[data-testid="stHorizontalBlock"] {
            gap: .45rem;
            flex-wrap: nowrap;
        }

        .answer-segments div[data-testid="column"] {
            min-width: 0;
        }

        .answer-segments div[data-testid="stButton"] > button {
            min-height: 50px !important;
            white-space: normal;
            line-height: 1.35;
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

        /* result cards */
        .result-stack {
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        .result-section { margin-bottom: 0; }

        .result-card {
            position: relative;
            overflow: hidden;
            background:
                radial-gradient(circle at top right, rgba(46, 139, 87, 0.12), transparent 28%),
                linear-gradient(180deg, #F5FAFF 0%, #FFFFFF 38%, #F7FBFF 100%);
            border: 1px solid rgba(214, 226, 236, 0.90);
            border-radius: 28px;
            padding: 26px;
            box-shadow: 0 22px 48px rgba(8, 32, 58, 0.20);
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
            flex-wrap: wrap;
        }

        .result-subcopy {
            color: var(--card-muted) !important;
            font-size: 14px;
            line-height: 1.7;
            margin: 8px 0 0;
        }

        .score-hero {
            display: flex;
            flex-wrap: wrap;
            align-items: flex-end;
            gap: 10px 22px;
            margin-top: 18px;
            margin-bottom: 18px;
        }

        .score-stack {
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-width: 150px;
            flex: 0 0 auto;
        }

        .score-kicker {
            font-size: 13px;
            font-weight: 800;
            color: var(--green);
        }

        .score-big {
            font-size: clamp(52px, 9vw, 78px);
            line-height: 0.95;
            font-weight: 900;
            color: #0f2747;
            letter-spacing: -0.04em;
            margin: 0;
        }

        .score-unit {
            font-size: 24px;
            color: var(--blue);
            font-weight: 800;
            margin-left: 6px;
        }

        .result-label-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 14px;
            border-radius: 999px;
            background: rgba(46, 139, 87, 0.10);
            border: 1px solid rgba(46, 139, 87, 0.18);
            color: var(--green);
            font-size: 14px;
            font-weight: 800;
        }

        .result-summary {
            font-size: 16px;
            line-height: 1.75;
            color: var(--card-ink) !important;
            margin: 0;
            text-align: left;
            align-self: flex-end;
            flex: 1 1 320px;
            min-width: 0;
        }

        .result-highlight-line {
            margin: 16px 0 0;
            padding-left: 14px;
            border-left: 4px solid rgba(46, 139, 87, 0.65);
            color: #245F49 !important;
            font-size: 15px;
            line-height: 1.75;
            font-weight: 700;
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
            color: var(--card-ink);
            font-size: 16px;
            font-weight: 800;
            margin-bottom: 2px;
        }

        .bullet-graph-caption {
            color: var(--card-muted);
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
            color: var(--card-muted);
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

        .bullet-fill {
            position: absolute;
            inset: 3px auto 3px 3px;
            width: 0;
            max-width: calc(100% - 6px);
            border-radius: 999px;
            background: linear-gradient(90deg, rgba(30, 78, 121, 0.90) 0%, rgba(46, 139, 87, 0.95) 100%);
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
            background: #0f2747;
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
            color: var(--card-muted);
            font-size: 11px;
            font-weight: 700;
        }

        .result-detail-box {
            margin-top: 24px;
            background: var(--green-soft);
            border: 1px solid rgba(46, 139, 87, 0.20);
            border-radius: 18px;
            padding: 14px 16px;
        }

        .result-detail-copy {
            margin: 0;
            color: var(--card-ink) !important;
            line-height: 1.8;
        }

        .support-card {
            background: linear-gradient(180deg, rgba(248, 251, 255, 1) 0%, rgba(242, 248, 255, 1) 100%);
            border: 1px solid rgba(214, 226, 236, 0.96);
            border-radius: 24px;
            padding: 22px;
            box-shadow: 0 12px 28px rgba(8, 32, 58, 0.12);
        }

        .support-card {
            background: linear-gradient(180deg, rgba(248, 251, 255, 1) 0%, rgba(242, 248, 255, 1) 100%);
            border: 1px solid rgba(214, 226, 236, 0.96);
            border-radius: 24px;
            padding: 22px;
            box-shadow: 0 12px 28px rgba(8, 32, 58, 0.12);
            margin-bottom: 16px;
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

        .support-card .support-title,
        .support-card h2.support-title {
            color: #16324F !important;
            -webkit-text-fill-color: #16324F !important;
            opacity: 1 !important;
            text-shadow: none !important;
            font-size: 18px;
            font-weight: 800;
            margin: 0;
            line-height: 1.35;
        }

        .support-copy {
            color: var(--card-muted) !important;
            font-size: 14px;
            line-height: 1.85;
            margin: 0;
        }

        .support-copy-secondary {
            margin-top: 10px;
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

        @media (max-width: 900px) {
            .answer-segments div[data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }

            .answer-segments div[data-testid="column"] {
                flex: 1 1 calc(50% - .3rem);
            }

            .score-hero {
                flex-direction: column;
                align-items: flex-start;
            }
        }

        @media (max-width: 640px) {
            .block-container {
                padding-left: .85rem !important;
                padding-right: .85rem !important;
            }

            .card, .question-card, .result-card, .support-card {
                padding: 18px;
                border-radius: 18px;
            }

            .stepper {
                gap: 6px;
            }

            .step-line {
                width: 24px;
            }

            .answer-segments div[data-testid="column"] {
                flex: 1 1 100%;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_intro() -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    intro_desc_html = render_bullet_list(INTRO_DESC_BULLETS)
    intro_notice_html = render_bullet_list(INTRO_NOTICE_BULLETS)
    privacy_html = render_bullet_list(PRIVACY_BULLETS)

    st.markdown(
        f"""
        <section class="card intro-section">
            <div>
                <span class="badge">RSES 기반</span>
                <span class="badge">총 10문항</span>
                <h1 class="title-lg">{EXAM_TITLE}</h1>
                <p class="muted" style="margin:8px 0 0;">검사 안내와 유의사항을 확인한 뒤 진행해 주세요.</p>
            </div>
            <div>
                <p class="section-title">검사 설명</p>
                {intro_desc_html}
            </div>
            <div class="intro-note">
                <p class="section-title" style="margin:0;">진행 전 유의사항</p>
                {intro_notice_html}
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <section class="card soft intro-section">
            <div>
                <h2 class="title-md">개인정보 수집 및 검사 진행 동의</h2>
                <p class="muted" style="margin:8px 0 0;">검사 진행과 결과 제공을 위해 아래 내용을 확인해 주세요.</p>
            </div>
            <div>
                {privacy_html}
            </div>
            <div class="privacy-note">
                아래 항목에 동의하시면 검사 시작 버튼이 활성화됩니다.
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    consent = st.checkbox(
        "위 안내를 확인했으며, 개인정보 수집·이용 및 검사 진행에 동의합니다.",
        value=st.session_state.meta["consent"],
        key="rses_consent_checkbox",
    )
    st.session_state.meta["consent"] = consent

    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("검사 시작", type="primary", disabled=not consent, use_container_width=True, key="intro_next"):
            now = now_iso()
            st.session_state.meta["consent_ts"] = now
            st.session_state.meta["started_ts"] = now
            st.session_state.page = "info"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def page_info() -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    st.markdown(
        """
        <section class="card">
            <span class="badge">기본 정보 입력</span>
            <h1 class="title-lg">기본 정보 입력</h1>
            <p class="text">아래 정보를 입력해 주세요. 이름, 성별, 연령, 거주지역은 필수 항목이며 휴대폰번호와 이메일은 선택 입력 항목입니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    gender_options = [""] + GENDER_OPTIONS
    region_options = [""] + REGION_OPTIONS

    row1_col1, row1_col2 = st.columns(2, gap="medium")
    with row1_col1:
        name = st.text_input(
            "이름",
            value=st.session_state.examinee.get("name", ""),
            placeholder="이름을 입력해 주세요",
            key="info_name",
        )
    with row1_col2:
        current_gender = st.session_state.examinee.get("gender", "")
        gender = st.selectbox(
            "성별",
            options=gender_options,
            index=gender_options.index(current_gender) if current_gender in gender_options else 0,
            format_func=lambda x: "선택해 주세요" if x == "" else x,
            key="info_gender",
        )

    row2_col1, row2_col2 = st.columns(2, gap="medium")
    with row2_col1:
        age = st.text_input(
            "연령",
            value=st.session_state.examinee.get("age", ""),
            placeholder="숫자만 입력해 주세요",
            key="info_age",
        )
    with row2_col2:
        current_region = st.session_state.examinee.get("region", "")
        region = st.selectbox(
            "거주지역",
            options=region_options,
            index=region_options.index(current_region) if current_region in region_options else 0,
            format_func=lambda x: "선택해 주세요" if x == "" else x,
            key="info_region",
        )

    phone_input = st.text_input(
        "휴대폰번호 (선택)",
        value=st.session_state.examinee.get("phone", ""),
        placeholder="숫자만 입력해 주세요",
        key="info_phone",
    )
    email = st.text_input(
        "이메일 (선택)",
        value=st.session_state.examinee.get("email", ""),
        placeholder="example@email.com",
        key="info_email",
    )

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

    missing_fields: List[str] = []
    if not name.strip():
        missing_fields.append("이름")
    if not gender.strip():
        missing_fields.append("성별")
    if not age.strip():
        missing_fields.append("연령")
    if not region.strip():
        missing_fields.append("거주지역")

    if missing_fields:
        st.error(f"{', '.join(missing_fields)}을 입력해주세요.")
    if name_error and name.strip():
        st.error(name_error)
    if gender_error and gender.strip():
        st.error(gender_error)
    if age_error and age.strip():
        st.error(age_error)
    if region_error and region.strip():
        st.error(region_error)
    if phone_error:
        st.error(phone_error)
    if email_error:
        st.error(email_error)

    all_valid = not any([name_error, gender_error, age_error, region_error, phone_error, email_error])

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("이전", use_container_width=True, key="info_prev"):
            st.session_state.page = "intro"
            st.rerun()
    with c2:
        if st.button("다음", type="primary", disabled=not all_valid, use_container_width=True, key="info_next"):
            st.session_state.page = "survey"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def page_survey(dev_mode: bool = False) -> None:
    st.markdown("<div class='page-wrap'>", unsafe_allow_html=True)
    render_stepper(st.session_state.page)

    payload, missing = build_payload()
    answered_count = len(QUESTIONS) - len(missing)
    progress_pct = int((answered_count / len(QUESTIONS)) * 100)

    st.markdown("<div class='survey-shell'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <section class="card">
            <span class="badge">문항 10개</span>
            <h1 class="title-lg">문항 응답</h1>
            <p class="text">현재 자신의 모습에 가장 가까운 응답을 선택해 주세요.</p>
            <div class="progress-row">
                <span class="progress-label">진행률 {answered_count}/10</span>
                <span class="progress-label">{progress_pct}%</span>
            </div>
            <div class="meter"><span style="width:{progress_pct}%;"></span></div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    short_labels = [
        "전혀\n그렇지 않다",
        "그렇지 않은\n편이다",
        "보통이다",
        "그런 편이다",
        "매우\n그렇다",
    ]

    for i, question in enumerate(QUESTIONS, start=1):
        q_key = f"q{i}"
        st.markdown(
            f"""
            <section class="question-card">
                <div class="question-title">{i}. {question}</div>
            """,
            unsafe_allow_html=True,
        )
        render_choice_button_row(
            options=short_labels,
            scores=SCALE_SCORES,
            state_key=q_key,
            columns_count=5,
        )
        st.markdown("</section>", unsafe_allow_html=True)

    payload, missing = build_payload()
    if missing:
        st.caption("모든 문항에 응답하면 결과 보기가 활성화됩니다.")

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("이전", use_container_width=True, key="survey_prev"):
            st.session_state.page = "info"
            st.rerun()
    with c2:
        if st.button("결과 보기", type="primary", use_container_width=True, disabled=bool(missing), key="survey_submit"):
            st.session_state.meta["submitted_ts"] = now_iso()
            payload, _ = build_payload()
            st.session_state.result_payload = payload
            st.session_state.page = "result"
            st.rerun()

    if dev_mode:
        st.caption("개발 모드 payload")
        st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")

    st.markdown("</div></div>", unsafe_allow_html=True)


def page_result(dev_mode: bool = False) -> None:
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
    bullet_graph_html = build_bullet_graph_html(total, min_score=10, max_score=50)
    result_section_html = build_result_section_html(
        level=level,
        total=total,
        subtitle=display_content["subtitle"],
        summary=display_content["summary"],
        interpretation=display_content["interpretation"],
        guidance=display_content["guidance"],
        bullet_graph_html=bullet_graph_html,
    )

    st.markdown(f"<div class='result-stack'>{result_section_html}", unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("검사 다시하기", type="primary", use_container_width=True, key="result_restart"):
            reset_all()
            st.rerun()
    with c2:
        if st.button("닫기", use_container_width=True, key="result_close"):
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

    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.close_attempted:
        st.warning("탭이 자동으로 닫히지 않는 경우, 사용자가 직접 탭을 닫아주세요.")

    if dev_mode:
        st.caption("개발 모드 internal payload")
        st.code(json.dumps(internal_payload, ensure_ascii=False, indent=2), language="json")
        st.caption("개발 모드 DB exam_data")
        st.code(json.dumps(exam_data, ensure_ascii=False, indent=2), language="json")

    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    inject_css()
    init_state()
    dev_mode = get_dev_mode()

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
# -----------------------------------------------------------------------------
# KIRBS 가이드 기준: 단일 Streamlit 앱 구조 유지, main 기준 독립 실행,
# ENABLE_DB_INSERT=false 에서는 DB insert 미실행, DB import/호출은 하단 배치.
# -----------------------------------------------------------------------------
def _is_db_insert_enabled() -> bool:
    raw = os.getenv("ENABLE_DB_INSERT", "true")
    return str(raw).strip().lower() != "false"


ENABLE_DB_INSERT = _is_db_insert_enabled()

if ENABLE_DB_INSERT:
    from utils.database import Database


def safe_db_insert(exam_data: Dict) -> bool:
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


def auto_db_insert(exam_data: Dict) -> None:
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
