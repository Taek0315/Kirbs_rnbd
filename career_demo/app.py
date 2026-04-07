from pathlib import Path
import re
import html

import pandas as pd
import streamlit as st
from data_loader import load_job_data, search_jobs, get_job_detail

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "career_jobs.xlsx"

st.set_page_config(
    page_title="AI 직업 탐색 가이드",
    page_icon="🔎",
    layout="wide",
)


def inject_css():
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            color: #1f2937;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(191,219,254,.45), transparent 26%),
                linear-gradient(180deg, #f8fbff 0%, #f4f7fb 100%);
        }

        .block-container {
            max-width: 1380px;
            padding-top: 1.6rem;
            padding-bottom: 2.4rem;
        }

        h1, h2, h3 {
            color: #12355b !important;
            font-weight: 800 !important;
            letter-spacing: -0.01em;
        }

        p, li, label, span, div {
            color: #334155;
        }

        .hero-box {
            background: linear-gradient(135deg, #eff6ff 0%, #ffffff 55%, #eef8ff 100%);
            border: 1px solid #dbeafe;
            border-radius: 28px;
            padding: 34px 36px;
            margin-bottom: 22px;
            box-shadow: 0 14px 40px rgba(15, 23, 42, 0.06);
            position: relative;
            overflow: hidden;
        }

        .hero-box::after {
            content: "";
            position: absolute;
            width: 240px;
            height: 240px;
            right: -70px;
            top: -60px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(59,130,246,.16) 0%, rgba(59,130,246,0) 70%);
        }

        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 7px 12px;
            background: #dbeafe;
            border: 1px solid #bfdbfe;
            color: #1d4ed8;
            border-radius: 999px;
            font-size: 0.84rem;
            font-weight: 800;
            margin-bottom: 14px;
        }

        .hero-title {
            font-size: 2.25rem;
            font-weight: 900;
            color: #102f4c;
            line-height: 1.2;
            margin-bottom: 10px;
        }

        .hero-sub {
            font-size: 1rem;
            color: #475569;
            line-height: 1.8;
            margin-bottom: 0;
            max-width: 860px;
        }

        .story-card {
            background: rgba(255,255,255,.88);
            border: 1px solid #e5eef9;
            border-radius: 22px;
            padding: 22px 22px;
            box-shadow: 0 10px 28px rgba(15,23,42,.05);
            margin-bottom: 16px;
            backdrop-filter: blur(6px);
        }

        .story-kicker {
            font-size: .8rem;
            font-weight: 800;
            color: #2563eb;
            text-transform: uppercase;
            letter-spacing: .08em;
            margin-bottom: 8px;
        }

        .story-title {
            font-size: 1.18rem;
            font-weight: 800;
            color: #12355b;
            margin-bottom: 8px;
        }

        .story-text {
            font-size: .95rem;
            line-height: 1.7;
            color: #64748b;
        }

        .journey-wrap {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin: 14px 0 4px 0;
        }

        .journey-step {
            background: #f8fbff;
            border: 1px solid #dceafb;
            border-radius: 18px;
            padding: 14px 14px 12px 14px;
        }

        .journey-no {
            font-size: .76rem;
            font-weight: 900;
            color: #2563eb;
            margin-bottom: 6px;
            letter-spacing: .04em;
        }

        .journey-label {
            font-size: .96rem;
            font-weight: 800;
            color: #12355b;
            margin-bottom: 4px;
        }

        .journey-desc {
            font-size: .88rem;
            line-height: 1.55;
            color: #64748b;
        }

        .report-shell {
            background: linear-gradient(180deg, rgba(255,255,255,.95), rgba(248,250,252,.98));
            border: 1px solid #dbe5f1;
            border-radius: 26px;
            padding: 24px 24px 12px 24px;
            box-shadow: 0 16px 40px rgba(15,23,42,.06);
            min-height: 720px;
        }

        .report-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 18px;
            margin-bottom: 18px;
            flex-wrap: wrap;
        }

        .report-title {
            font-size: 1.8rem;
            font-weight: 900;
            color: #102f4c;
            margin-bottom: 6px;
        }

        .report-sub {
            font-size: .97rem;
            color: #64748b;
            line-height: 1.7;
            max-width: 760px;
        }

        .report-chip {
            display: inline-block;
            background: #eff6ff;
            color: #1d4ed8;
            border: 1px solid #bfdbfe;
            border-radius: 999px;
            font-size: .83rem;
            font-weight: 800;
            padding: 8px 12px;
            margin-right: 6px;
            margin-bottom: 6px;
        }

        .insight-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin: 12px 0 18px 0;
        }

        .insight-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 16px 16px;
        }

        .insight-label {
            font-size: .8rem;
            color: #64748b;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .insight-value {
            font-size: 1rem;
            line-height: 1.6;
            color: #0f172a;
            font-weight: 800;
        }

        .section-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 20px;
            padding: 20px 22px;
            margin-bottom: 14px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
        }

        .section-title {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.05rem;
            font-weight: 900;
            color: #12355b;
            margin-bottom: 12px;
        }

        .section-index {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #dbeafe;
            color: #1d4ed8;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: .84rem;
            font-weight: 900;
            flex: 0 0 auto;
        }

        .section-body {
            color: #334155;
            line-height: 1.78;
            font-size: .96rem;
        }

        .section-body ul {
            padding-left: 1.1rem;
            margin-bottom: 0;
        }

        .section-body li {
            margin-bottom: .45rem;
            line-height: 1.68;
        }

        .empty-text {
            color: #94a3b8;
            font-size: 0.95rem;
        }

        .result-count {
            color: #64748b;
            font-size: .93rem;
            margin-top: 10px;
            margin-bottom: 8px;
        }

        .mini-guide {
            background: #f8fbff;
            border: 1px dashed #cfe1fb;
            border-radius: 18px;
            padding: 14px 16px;
            margin-top: 12px;
            font-size: .9rem;
            line-height: 1.65;
            color: #64748b;
        }

        .focus-note {
            background: #eff6ff;
            border: 1px solid #dbeafe;
            border-radius: 18px;
            padding: 14px 16px;
            margin-bottom: 14px;
            color: #1e3a8a;
            font-size: .92rem;
            line-height: 1.7;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            background: #ffffff !important;
            color: #111827 !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 14px !important;
            min-height: 48px !important;
            box-shadow: none !important;
        }

        input {
            color: #111827 !important;
        }

        input::placeholder {
            color: #94a3b8 !important;
        }

        .stSelectbox label,
        .stTextInput label,
        .stMultiSelect label {
            color: #334155 !important;
            font-weight: 800 !important;
        }

        .stAlert, .stInfo {
            border-radius: 16px !important;
        }

        @media (max-width: 1100px) {
            .journey-wrap,
            .insight-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def get_data():
    return load_job_data(DATA_FILE)


def split_lines(text: str):
    if not text or (isinstance(text, float) and pd.isna(text)):
        return []

    text = str(text).strip()
    if not text:
        return []

    parts = []
    for block in re.split(r"\n|;", text):
        block = block.strip()
        if not block:
            continue
        if "," in block and "\n" not in block and len(block) < 120:
            sub_parts = [x.strip() for x in block.split(",") if x.strip()]
            parts.extend(sub_parts)
        else:
            parts.append(block)

    lines = []
    for line in parts:
        line = re.sub(r"^[\\-•·]\s*", "", line).strip()
        if line:
            lines.append(line)
    return lines


def collect_prefixed_values(detail: dict, prefix: str):
    collected = []
    for key, value in detail.items():
        if key.startswith(prefix) and value and str(value).strip():
            collected.append(str(value).strip())
    return collected


def render_card(title: str, content_html: str, index: int = None):
    number_html = f'<span class="section-index">{index}</span>' if index is not None else ""
    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">{number_html}<span>{html.escape(title)}</span></div>
            <div class="section-body">
                {content_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_text_section(title: str, text: str, index: int = None):
    lines = split_lines(text)
    if not lines:
        render_card(title, '<div class="empty-text">등록된 내용이 없습니다.</div>', index=index)
        return

    items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
    render_card(title, f"<ul>{items}</ul>", index=index)


def render_list_section(title: str, items, index: int = None):
    clean_items = [str(item).strip() for item in items if str(item).strip()]
    if not clean_items:
        render_card(title, '<div class="empty-text">등록된 내용이 없습니다.</div>', index=index)
        return

    items_html = "".join(f"<li>{html.escape(item)}</li>" for item in clean_items)
    render_card(title, f"<ul>{items_html}</ul>", index=index)


def get_similar_jobs(detail: dict):
    raw = detail.get("similarJob", "")
    return split_lines(raw)


def get_major_list(detail: dict):
    majors = collect_prefixed_values(detail, "major_")
    return [m for m in majors if m.lower() != "nan"]


def get_contact_list(detail: dict):
    contacts = detail.get("contact_list", [])
    prefixed = collect_prefixed_values(detail, "contact_")
    all_contacts = list(contacts) + prefixed
    seen = set()
    deduped = []
    for item in all_contacts:
        item = str(item).strip()
        if not item or item.lower() == "nan":
            continue
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def make_brief(detail: dict):
    summary = split_lines(detail.get("summary", ""))
    aptitude = split_lines(detail.get("aptitude", ""))
    employment = split_lines(detail.get("employment", ""))

    intro = summary[0] if summary else "이 직업의 기본 역할 설명이 준비되어 있습니다."
    fit = aptitude[0] if aptitude else "적성과 흥미 정보가 함께 제공됩니다."
    outlook = employment[0] if employment else "전망 정보가 함께 제공됩니다."
    return intro, fit, outlook


def render_report_header(detail: dict, focus_labels: list):
    job_name = detail.get("job", "-")
    intro, fit, outlook = make_brief(detail)

    focus_chips = "".join(
        f'<span class="report-chip">{html.escape(label)}</span>' for label in focus_labels
    )

    st.markdown(
        f"""
        <div class="report-shell">
            <div class="report-top">
                <div>
                    <div class="report-title">{html.escape(job_name)} 탐색 리포트</div>
                    <div class="report-sub">
                        입력한 직업을 기준으로 핵심 역할, 준비 방법, 전망, 연결 가능한 진로 정보를
                        한 번에 읽기 쉽게 정리했습니다.
                    </div>
                </div>
                <div>{focus_chips}</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="insight-grid">
            <div class="insight-card">
                <div class="insight-label">이 직업은 어떤 일인가요?</div>
                <div class="insight-value">{html.escape(intro)}</div>
            </div>
            <div class="insight-card">
                <div class="insight-label">어떤 사람에게 잘 맞나요?</div>
                <div class="insight-value">{html.escape(fit)}</div>
            </div>
            <div class="insight-card">
                <div class="insight-label">앞으로의 가능성은 어떤가요?</div>
                <div class="insight-value">{html.escape(outlook)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_report_footer():
    st.markdown("</div>", unsafe_allow_html=True)


def render_job_detail(detail: dict, focus_labels: list):
    render_report_header(detail, focus_labels)

    focus_map = {
        "직업 소개": True,
        "준비 방법": True,
        "전망/임금": True,
        "비슷한 직업": True,
        "관련 학과": True,
        "추가 기관/정보": True,
    }
    selected = {label: (label in focus_labels) for label in focus_map}

    if not focus_labels:
        selected = {key: True for key in focus_map}

    st.markdown(
        """
        <div class="focus-note">
            AI 탐색 흐름은 <strong>이 직업이 무엇인지 → 어떻게 준비하는지 → 앞으로 어떤 가능성이 있는지 → 함께 볼 직업은 무엇인지</strong> 순서로 구성되어 있습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_idx = 1

    if selected.get("직업 소개", False):
        render_text_section("어떤 직업을 찾고 있나요?", detail.get("summary", ""), index=section_idx)
        section_idx += 1

        similar_jobs = get_similar_jobs(detail)
        aptitude = detail.get("aptitude", "")
        combined_html = ""

        aptitude_lines = split_lines(aptitude)
        if aptitude_lines:
            aptitude_html = "".join(f"<li>{html.escape(x)}</li>" for x in aptitude_lines)
            combined_html += f"<p><strong>어울리는 적성 및 흥미</strong></p><ul>{aptitude_html}</ul>"

        if similar_jobs and not selected.get("비슷한 직업", False):
            sim_html = "".join(f"<li>{html.escape(x)}</li>" for x in similar_jobs)
            combined_html += f"<p style='margin-top:12px;'><strong>함께 떠오르는 유사 직업</strong></p><ul>{sim_html}</ul>"

        if combined_html:
            render_card("이런 사람에게 잘 맞아요", combined_html, index=section_idx)
            section_idx += 1

    if selected.get("준비 방법", False):
        prepare_parts = []
        for subtitle, key in [
            ("진입 경로", "empway"),
            ("준비 방법", "prepareway"),
            ("훈련 및 교육", "training"),
            ("자격 및 면허", "certification"),
        ]:
            lines = split_lines(detail.get(key, ""))
            if lines:
                items = "".join(f"<li>{html.escape(x)}</li>" for x in lines)
                prepare_parts.append(f"<p><strong>{subtitle}</strong></p><ul>{items}</ul>")

        if prepare_parts:
            render_card("이 직업은 어떻게 준비하나요?", "".join(prepare_parts), index=section_idx)
        else:
            render_card("이 직업은 어떻게 준비하나요?", '<div class="empty-text">등록된 내용이 없습니다.</div>', index=section_idx)
        section_idx += 1

    if selected.get("전망/임금", False):
        outlook_parts = []
        for subtitle, key in [
            ("직업 가능성", "job_possibility"),
            ("고용 전망", "employment"),
            ("임금 수준", "salery"),
        ]:
            lines = split_lines(detail.get(key, ""))
            if lines:
                items = "".join(f"<li>{html.escape(x)}</li>" for x in lines)
                outlook_parts.append(f"<p><strong>{subtitle}</strong></p><ul>{items}</ul>")

        if outlook_parts:
            render_card("앞으로의 가능성과 현실적인 조건은?", "".join(outlook_parts), index=section_idx)
        else:
            render_card("앞으로의 가능성과 현실적인 조건은?", '<div class="empty-text">등록된 내용이 없습니다.</div>', index=section_idx)
        section_idx += 1

    if selected.get("비슷한 직업", False):
        render_list_section("비슷한 직업은 무엇이 있나요?", get_similar_jobs(detail), index=section_idx)
        section_idx += 1

    if selected.get("관련 학과", False):
        render_list_section("관련 학과는 무엇이 있나요?", get_major_list(detail), index=section_idx)
        section_idx += 1

    if selected.get("추가 기관/정보", False):
        render_list_section("추가로 찾아볼 기관 및 정보", get_contact_list(detail), index=section_idx)
        section_idx += 1

    render_report_footer()


def main():
    inject_css()

    if not DATA_FILE.exists():
        st.error(
            f"기본 데이터 파일을 찾지 못했습니다: {DATA_FILE.name}\\n\\n"
            "app.py와 같은 폴더에 엑셀 파일이 있는지 확인해 주세요."
        )
        st.stop()

    df = get_data()

    st.markdown(
        """
        <div class="hero-box">
            <div class="eyebrow">AI CAREER GUIDE</div>
            <div class="hero-title">직업 정보를 찾는 과정을<br>하나의 탐색 여정처럼 보여드립니다.</div>
            <p class="hero-sub">
                단순히 직업 설명을 나열하지 않고, 사용자가 어떤 직업을 찾는지부터
                어떤 정보가 필요한지, 함께 볼 만한 직업과 학과가 무엇인지까지
                순서대로 읽히는 구조로 정리해 드립니다.
            </p>
            <div class="journey-wrap">
                <div class="journey-step">
                    <div class="journey-no">STEP 1</div>
                    <div class="journey-label">어떤 직업이 궁금한가요?</div>
                    <div class="journey-desc">직업명이나 관심 키워드로 탐색을 시작합니다.</div>
                </div>
                <div class="journey-step">
                    <div class="journey-no">STEP 2</div>
                    <div class="journey-label">무엇을 알고 싶나요?</div>
                    <div class="journey-desc">직업 소개, 준비 방법, 전망, 학과 등 원하는 정보에 집중합니다.</div>
                </div>
                <div class="journey-step">
                    <div class="journey-no">STEP 3</div>
                    <div class="journey-label">AI가 구조적으로 정리합니다</div>
                    <div class="journey-desc">핵심 정보와 연결 정보까지 한 흐름으로 읽을 수 있게 제공합니다.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([1.05, 1.95], gap="large")

    with left_col:
        st.markdown(
            """
            <div class="story-card">
                <div class="story-kicker">Search Story</div>
                <div class="story-title">탐색을 시작해 보세요</div>
                <div class="story-text">
                    먼저 궁금한 직업이나 키워드를 입력하면, 관련 직업 후보를 보여드리고
                    선택한 직업을 중심으로 AI 탐색 리포트를 구성합니다.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        search_query = st.text_input(
            "어떤 직업을 찾고 싶나요?",
            placeholder="예: 행정학연구원, 심리, 상담, 디자인, 공무원",
        )

        focus_labels = st.multiselect(
            "어떤 정보가 특히 궁금한가요?",
            options=["직업 소개", "준비 방법", "전망/임금", "비슷한 직업", "관련 학과", "추가 기관/정보"],
            default=["직업 소개", "준비 방법", "전망/임금"],
        )

        results = search_jobs(df, search_query, top_n=30)

        st.markdown(
            f'<div class="result-count">탐색 후보 {len(results)}건</div>',
            unsafe_allow_html=True,
        )

        if results.empty:
            st.warning("검색 결과가 없습니다. 다른 직업명이나 키워드로 다시 찾아보세요.")
            st.markdown(
                """
                <div class="mini-guide">
                    예시 키워드: <strong>심리</strong>, <strong>상담</strong>, <strong>디자인</strong>, <strong>연구원</strong>, <strong>기상</strong>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        job_options = results["job"].dropna().astype(str).tolist()

        if "selected_job" not in st.session_state:
            st.session_state.selected_job = job_options[0]

        if st.session_state.selected_job not in job_options:
            st.session_state.selected_job = job_options[0]

        selected_job = st.selectbox(
            "어떤 직업을 중심으로 볼까요?",
            options=job_options,
            index=job_options.index(st.session_state.selected_job),
        )
        st.session_state.selected_job = selected_job

        st.markdown(
            """
            <div class="mini-guide">
                선택한 직업을 기준으로 오른쪽 화면에서
                <strong>핵심 소개 → 준비 경로 → 전망 → 연결 직업/학과</strong>
                순서로 정보를 확인할 수 있습니다.
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right_col:
        detail = get_job_detail(df, st.session_state.selected_job)
        if detail:
            render_job_detail(detail, focus_labels)
        else:
            st.error("선택한 직업 정보를 찾을 수 없습니다.")


if __name__ == "__main__":
    main()