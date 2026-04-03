from pathlib import Path
import re
import streamlit as st
from data_loader import load_job_data, search_jobs, get_job_detail

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_FILE_PATH = BASE_DIR / "career_jobs.xlsx"

st.set_page_config(
    page_title="직업 정보 검색 데모",
    page_icon="🔎",
    layout="wide",
)


@st.cache_data
def get_data_from_path(file_path: str):
    return load_job_data(file_path)


@st.cache_data
def get_data_from_upload(uploaded_file):
    return load_job_data(uploaded_file)


def split_lines(text: str):
    if not text:
        return []
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\-•·]\s*", "", line)
        lines.append(line)
    return lines


def render_text_section(title: str, text: str):
    st.markdown(f"### {title}")
    lines = split_lines(text)

    if not lines:
        st.info("등록된 내용이 없습니다.")
        return

    for line in lines:
        st.markdown(f"- {line}")


def render_list_section(title: str, items):
    st.markdown(f"### {title}")
    clean_items = [str(item).strip() for item in items if str(item).strip()]

    if not clean_items:
        st.info("등록된 내용이 없습니다.")
        return

    for item in clean_items:
        st.markdown(f"- {item}")


def render_job_detail(detail: dict):
    st.markdown(f"## {detail.get('job', '-')}")
    st.caption("직업 상세 정보")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "직업 소개",
        "필요한 것",
        "직업 가능성",
        "추가 정보",
        "관련 학과",
    ])

    with tab1:
        render_text_section("직업에 대해 알아봐요", detail.get("summary", ""))

        similar_job = detail.get("similarJob", "")
        aptitude = detail.get("aptitude", "")

        if similar_job:
            st.markdown("### 유사 직업")
            st.write(similar_job)

        if aptitude:
            st.markdown("### 적성 및 흥미")
            st.write(aptitude)

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
            st.markdown("### 임금 수준")
            st.write(salery)

    with tab4:
        render_list_section("추가 정보", detail.get("contact_list", []))

    with tab5:
        render_list_section("관련 학과", detail.get("major_list", []))


def load_dataframe():
    st.sidebar.markdown("## 데이터 설정")

    use_uploaded = st.sidebar.checkbox("엑셀 파일 직접 업로드해서 사용", value=False)

    if use_uploaded:
        uploaded_file = st.sidebar.file_uploader(
            "직업 정보 엑셀 업로드",
            type=["xlsx"]
        )
        if uploaded_file is None:
            st.info("사이드바에서 엑셀 파일을 업로드해 주세요.")
            st.stop()
        return get_data_from_upload(uploaded_file)

    if DEFAULT_FILE_PATH.exists():
        return get_data_from_path(str(DEFAULT_FILE_PATH))

    st.error(
        "기본 엑셀 파일을 찾지 못했습니다. "
        "career_jobs.xlsx 파일이 app.py와 같은 폴더에 있는지 확인하거나, "
        "사이드바에서 엑셀 파일을 직접 업로드해 주세요."
    )
    st.stop()


def main():
    df = load_dataframe()

    st.title("직업 정보 검색 데모")
    st.write("희망 직업이나 관심 키워드를 검색하면 관련 직업 정보를 확인할 수 있습니다.")

    search_query = st.text_input(
        "직업명 또는 키워드 검색",
        placeholder="예: 행정학연구원, 심리, 상담, 디자인, 공무원"
    )

    results = search_jobs(df, search_query, top_n=30)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### 검색 결과")

        if results.empty:
            st.warning("검색 결과가 없습니다.")
            return

        st.caption(f"검색 결과 {len(results)}건")

        job_options = results["job"].tolist()

        if "selected_job" not in st.session_state:
            st.session_state.selected_job = job_options[0]

        if st.session_state.selected_job not in job_options:
            st.session_state.selected_job = job_options[0]

        selected_job = st.selectbox(
            "직업 선택",
            options=job_options,
            index=job_options.index(st.session_state.selected_job)
        )
        st.session_state.selected_job = selected_job

    with col2:
        detail = get_job_detail(df, st.session_state.selected_job)
        if detail:
            render_job_detail(detail)
        else:
            st.error("선택한 직업 정보를 찾을 수 없습니다.")


if __name__ == "__main__":
    main()