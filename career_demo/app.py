from pathlib import Path
import re
import html
import streamlit as st
from data_loader import load_job_data, search_jobs, get_job_detail

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "career_jobs.xlsx"

st.set_page_config(
    page_title="직업 정보 검색 데모",
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
            background: #f5f7fb;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1300px;
        }

        h1, h2, h3 {
            color: #12355b !important;
            font-weight: 800 !important;
        }

        p, li, label, span, div {
            color: #334155;
        }

        .hero-box {
            background: linear-gradient(135deg, #eaf3ff 0%, #f7fbff 100%);
            border: 1px solid #d8e7fb;
            border-radius: 20px;
            padding: 28px 32px;
            margin-bottom: 24px;
        }

        .hero-title {
            font-size: 2.2rem;
            font-weight: 800;
            color: #12355b;
            margin-bottom: 8px;
        }

        .hero-sub {
            font-size: 1rem;
            color: #4b5563;
            margin-bottom: 0;
        }

        .section-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 22px 24px;
            margin-bottom: 18px;
            box-shadow: 0 6px 20px rgba(15, 23, 42, 0.05);
        }

        .section-body {
            color: #334155;
            line-height: 1.75;
        }

        .empty-text {
            color: #94a3b8;
            font-size: 0.95rem;
        }

        .section-title {
            font-size: 1.08rem;
            font-weight: 800;
            color: #12355b;
            margin-bottom: 14px;
        }

        .result-badge {
            display: inline-block;
            background: #e8f1ff;
            color: #1d4ed8;
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 0.88rem;
            font-weight: 700;
            margin-bottom: 10px;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div {
            background: #ffffff !important;
            color: #111827 !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 12px !important;
            min-height: 46px !important;
            box-shadow: none !important;
        }

        input {
            color: #111827 !important;
        }

        input::placeholder {
            color: #94a3b8 !important;
        }

        .stSelectbox label,
        .stTextInput label {
            color: #334155 !important;
            font-weight: 700 !important;
        }

        button[kind="secondary"] {
            border-radius: 12px !important;
        }

        div[role="tablist"] {
            gap: 8px;
            margin-top: 8px;
            margin-bottom: 8px;
        }

        button[role="tab"] {
            background: #eef4fb !important;
            color: #37516b !important;
            border-radius: 12px !important;
            padding: 10px 14px !important;
            border: 1px solid #d8e2ee !important;
        }

        button[role="tab"][aria-selected="true"] {
            background: #dbeafe !important;
            color: #1d4ed8 !important;
            border: 1px solid #93c5fd !important;
            font-weight: 700 !important;
        }

        .stInfo, .stAlert {
            border-radius: 14px !important;
        }

        ul {
            padding-left: 1.1rem;
        }

        li {
            margin-bottom: 0.45rem;
            line-height: 1.65;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def get_data():
    return load_job_data(DATA_FILE)


def split_lines(text: str):
    if not text:
        return []
    lines = []
    for line in str(text).split("\n"):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\-•·]\s*", "", line)
        if line:
            lines.append(line)
    return lines


def render_card(title: str, content_html: str):
    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">{html.escape(title)}</div>
            <div class="section-body">
                {content_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_text_section(title: str, text: str):
    lines = split_lines(text)

    if not lines:
        render_card(title, '<div class="empty-text">등록된 내용이 없습니다.</div>')
        return

    items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
    content_html = f"<ul>{items}</ul>"
    render_card(title, content_html)


def render_list_section(title: str, items):
    clean_items = [str(item).strip() for item in items if str(item).strip()]

    if not clean_items:
        render_card(title, '<div class="empty-text">등록된 내용이 없습니다.</div>')
        return

    items_html = "".join(f"<li>{html.escape(item)}</li>" for item in clean_items)
    content_html = f"<ul>{items_html}</ul>"
    render_card(title, content_html)


def render_job_detail(detail: dict):
    st.markdown(f"## {detail.get('job', '-')}")
    st.markdown('<div class="result-badge">직업 상세 정보</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["직업 소개", "필요한 것", "직업 가능성", "추가 정보", "관련 학과"]
    )

    with tab1:
        render_text_section("직업에 대해 알아봐요", detail.get("summary", ""))

        similar_job = detail.get("similarJob", "")
        aptitude = detail.get("aptitude", "")

        if similar_job:
            render_text_section("유사 직업", similar_job)
        if aptitude:
            render_text_section("적성 및 흥미", aptitude)

    with tab2:
        empway = detail.get("empway", "")
        prepareway = detail.get("prepareway", "")
        training = detail.get("training", "")
        certification = detail.get("certification", "")

        render_text_section("직업이 되기 위해 필요한 것", empway)

        if prepareway:
            render_text_section("준비 방법", prepareway)
        if training:
            render_text_section("훈련 및 교육", training)
        if certification:
            render_text_section("자격 및 면허", certification)

    with tab3:
        job_possibility = detail.get("job_possibility", "")
        employment = detail.get("employment", "")
        salery = detail.get("salery", "")

        render_text_section("이런 가능성이 있어요", job_possibility)

        if employment:
            render_text_section("고용 전망", employment)
        if salery:
            render_text_section("임금 수준", salery)

    with tab4:
        render_list_section("추가 정보", detail.get("contact_list", []))

    with tab5:
        render_list_section("관련 학과", detail.get("major_list", []))


def main():
    inject_css()

    if not DATA_FILE.exists():
        st.error(
            f"기본 데이터 파일을 찾지 못했습니다: {DATA_FILE.name}\n\n"
            "app.py와 같은 폴더에 엑셀 파일이 있는지 확인해 주세요."
        )
        st.stop()

    df = get_data()

    st.markdown(
        """
        <div class="hero-box">
            <div class="hero-title">직업 정보 검색 데모</div>
            <p class="hero-sub">
                희망 직업이나 관심 키워드를 검색하면 관련 직업의 소개, 준비 방법, 전망, 추가 정보를 확인할 수 있습니다.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_query = st.text_input(
        "직업명 또는 키워드 검색",
        placeholder="예: 행정학연구원, 심리, 상담, 디자인, 공무원",
    )

    results = search_jobs(df, search_query, top_n=30)

    left_col, right_col = st.columns([1.05, 1.95], gap="large")

    with left_col:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### 검색 결과")
        st.caption(f"검색 결과 {len(results)}건")

        if results.empty:
            st.warning("검색 결과가 없습니다.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        job_options = results["job"].tolist()

        if "selected_job" not in st.session_state:
            st.session_state.selected_job = job_options[0]

        if st.session_state.selected_job not in job_options:
            st.session_state.selected_job = job_options[0]

        selected_job = st.selectbox(
            "직업 선택",
            options=job_options,
            index=job_options.index(st.session_state.selected_job),
        )
        st.session_state.selected_job = selected_job
        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        detail = get_job_detail(df, st.session_state.selected_job)
        if detail:
            render_job_detail(detail)
        else:
            st.error("선택한 직업 정보를 찾을 수 없습니다.")


if __name__ == "__main__":
    main()