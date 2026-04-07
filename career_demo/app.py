from __future__ import annotations

from pathlib import Path
import html
import re
import textwrap
from collections import Counter
from difflib import SequenceMatcher

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "career_jobs.xlsx"

st.set_page_config(
    page_title="AI 직업 탐색 리포트",
    page_icon="🔎",
    layout="wide",
)

SEARCH_COLUMNS = [
    "job",
    "summary",
    "similarJob",
    "aptitude",
    "empway",
    "prepareway",
    "training",
    "certification",
    "employment",
    "job_possibility",
]

KOREAN_STOPWORDS = {
    "관련", "직업", "직무", "일", "일을", "하는", "대한", "및", "에서", "으로", "위한", "위해",
    "같은", "있는", "되는", "분야", "업무", "사람", "경우", "통한", "기반", "탐색", "분석",
    "미래", "검색", "관련된", "중심", "한다", "수행", "업무를", "업무에", "직업명", "정보",
}

SYNONYM_MAP = {
    "컴퓨터": ["it", "정보", "소프트웨어", "프로그래밍", "시스템", "개발", "데이터", "네트워크", "전산", "ai", "인공지능"],
    "it": ["컴퓨터", "정보", "소프트웨어", "시스템", "개발", "데이터", "네트워크", "전산", "ai", "인공지능"],
    "인공지능": ["ai", "데이터", "소프트웨어", "시스템", "개발", "컴퓨터"],
    "상담": ["심리", "치료", "코칭", "의사소통", "상담사"],
    "디자인": ["그래픽", "시각", "콘텐츠", "광고", "영상", "편집"],
    "행정": ["사무", "총무", "기획", "관리", "행정사무"],
    "환경": ["기후", "생태", "에너지", "자원", "환경공학"],
    "의료": ["보건", "병원", "간호", "임상", "건강"],
    "교육": ["교사", "교수", "강사", "훈련", "학습"],
    "연구": ["실험", "분석", "조사", "개발", "연구원"],
    "기계": ["설비", "장비", "제조", "기술", "공학"],
    "법": ["법률", "판사", "변호", "행정", "규정"],
    "예술": ["음악", "미술", "공연", "디자인", "창작"],
}


# -----------------------------
# Basic helpers
# -----------------------------
def render_html(markup: str) -> None:
    st.markdown(textwrap.dedent(markup).strip(), unsafe_allow_html=True)


def rerun_app() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def is_missing_like(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return stripped == "" or stripped.lower() == "nan"
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def normalize_whitespace(text: str) -> str:
    text = str(text)
    text = text.replace("_x000D_", " ")
    text = text.replace("\\r", "\n").replace("\\n", "\n")
    text = text.replace("\r", "\n")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\u00a0", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def clean_sentence(text: str) -> str:
    if is_missing_like(text):
        return ""
    text = normalize_whitespace(str(text))
    text = re.sub(r"^[\-•·▪■]\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,;-")


def split_lines(text) -> list[str]:
    if is_missing_like(text):
        return []

    if isinstance(text, (list, tuple, set)):
        lines: list[str] = []
        for item in text:
            lines.extend(split_lines(item))
        return lines

    text = normalize_whitespace(str(text))
    if not text:
        return []

    text = re.sub(r"\n\s*[-•·▪■]\s*", "\n", text)
    text = re.sub(r"^\s*[-•·▪■]\s*", "", text)

    raw_parts: list[str] = []
    for part in re.split(r"\n|;", text):
        part = clean_sentence(part)
        if not part:
            continue
        if "," in part and len(part) < 90:
            raw_parts.extend([clean_sentence(p) for p in part.split(",") if clean_sentence(p)])
        else:
            raw_parts.append(part)

    deduped: list[str] = []
    seen = set()
    for part in raw_parts:
        key = part.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(part)
    return deduped


def unique_keep_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        value = clean_sentence(item)
        if not value:
            continue
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def shorten_text(text: str, limit: int = 60) -> str:
    text = clean_sentence(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def safe_float(value):
    try:
        if is_missing_like(value):
            return None
        return float(value)
    except Exception:
        return None


# -----------------------------
# Data loading and preparation
# -----------------------------
@st.cache_data(show_spinner=False)
def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda x: normalize_whitespace(x) if not is_missing_like(x) else "")

    if "job" not in df.columns:
        raise ValueError("career_jobs.xlsx에 'job' 컬럼이 없습니다.")

    if "summary" not in df.columns:
        df["summary"] = ""

    df["job"] = df["job"].astype(str).str.strip()
    df = df[df["job"] != ""].reset_index(drop=True)

    salary_values = df.get("salery", pd.Series([""] * len(df))).map(extract_salary_amount)
    valid_salary = salary_values.dropna()
    if valid_salary.empty:
        low_cut = None
        high_cut = None
    else:
        low_cut = float(valid_salary.quantile(0.33))
        high_cut = float(valid_salary.quantile(0.66))

    df["salary_amount"] = salary_values
    df["salary_bucket"] = df["salary_amount"].map(lambda x: classify_salary_bucket(x, low_cut, high_cut))
    df["employment_status"] = df.apply(classify_employment_status, axis=1)
    df["major_list"] = df.apply(get_major_list, axis=1)
    df["similar_job_list"] = df.apply(get_similar_jobs, axis=1)
    df["certification_list"] = df.apply(get_certifications, axis=1)
    df["contact_list_all"] = df.apply(get_contacts, axis=1)
    df["search_blob"] = df.apply(build_search_blob, axis=1)
    return df


# -----------------------------
# Row-level extractors
# -----------------------------
def extract_salary_amount(text) -> float | None:
    if is_missing_like(text):
        return None

    cleaned = str(text).replace(",", "")
    patterns = [
        r"평균연봉\(중위값\)은\s*([0-9]+(?:\.[0-9]+)?)\s*만원",
        r"중위값\)?은\s*([0-9]+(?:\.[0-9]+)?)\s*만원",
        r"평균연봉은\s*([0-9]+(?:\.[0-9]+)?)\s*만원",
        r"([0-9]+(?:\.[0-9]+)?)\s*만원",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                continue
    return None


def classify_salary_bucket(amount: float | None, low_cut: float | None, high_cut: float | None) -> str:
    if amount is None:
        return "정보 없음"
    if low_cut is None or high_cut is None:
        return "정보 있음"
    if amount < low_cut:
        return "하"
    if amount < high_cut:
        return "중"
    return "상"


def classify_employment_status(row: pd.Series) -> str:
    text = f"{row.get('employment', '')} {row.get('job_possibility', '')}".lower()
    if any(word in text for word in ["증가", "성장", "확대", "유망", "밝", "좋"]):
        return "좋음"
    if any(word in text for word in ["감소", "축소", "줄어", "낮아질", "어려울", "감소할"]):
        return "주의"
    return "보통"


def get_prefixed_values(row: pd.Series, prefix: str) -> list[str]:
    items: list[str] = []
    for col in row.index:
        if str(col).startswith(prefix):
            items.extend(split_lines(row[col]))
    return unique_keep_order(items)


def get_major_list(row: pd.Series) -> list[str]:
    return get_prefixed_values(row, "major_")


def get_similar_jobs(row: pd.Series) -> list[str]:
    return unique_keep_order(split_lines(row.get("similarJob", "")))


def get_certifications(row: pd.Series) -> list[str]:
    return unique_keep_order(split_lines(row.get("certification", "")))


def get_contacts(row: pd.Series) -> list[str]:
    return unique_keep_order(get_prefixed_values(row, "contact_"))


def build_search_blob(row: pd.Series) -> str:
    chunks = []
    for col in SEARCH_COLUMNS:
        if col in row.index:
            chunks.append(str(row.get(col, "")))
    chunks.extend(row.get("major_list", []))
    return " ".join(chunks).lower()


# -----------------------------
# Search / filter logic
# -----------------------------
def extract_search_terms(query: str) -> list[str]:
    if not query:
        return []

    raw_tokens = re.findall(r"[A-Za-z가-힣0-9]{2,}", query.lower())
    tokens: list[str] = []
    for token in raw_tokens:
        if token in KOREAN_STOPWORDS:
            continue
        tokens.append(token)
        if token in SYNONYM_MAP:
            tokens.extend([item.lower() for item in SYNONYM_MAP[token]])

    unique_tokens: list[str] = []
    seen = set()
    for token in tokens:
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)
    return unique_tokens


def compute_search_score(row: pd.Series, query: str, tokens: list[str]) -> float:
    if not query.strip():
        return 1.0

    job_text = str(row.get("job", "")).lower()
    summary_text = str(row.get("summary", "")).lower()
    full_text = str(row.get("search_blob", "")).lower()

    score = 0.0
    query_lower = query.lower().strip()

    if query_lower in job_text:
        score += 12.0
    if query_lower in summary_text:
        score += 8.0
    if query_lower in full_text:
        score += 5.0

    ratio = SequenceMatcher(None, query_lower, job_text).ratio()
    if ratio >= 0.45:
        score += ratio * 7

    for token in tokens:
        if token in job_text:
            score += 6.0
        elif token in summary_text:
            score += 3.2
        elif token in full_text:
            score += 1.6

    major_joined = " ".join(row.get("major_list", [])).lower()
    for token in tokens:
        if token in major_joined:
            score += 1.8

    return score


def search_jobs(df: pd.DataFrame, query: str) -> pd.DataFrame:
    tokens = extract_search_terms(query)
    results = df.copy()
    results["search_score"] = results.apply(lambda row: compute_search_score(row, query, tokens), axis=1)
    if query.strip():
        results = results[results["search_score"] > 0]
    return results.sort_values(["search_score", "job"], ascending=[False, True]).reset_index(drop=True)


def filter_results(
    df: pd.DataFrame,
    selected_majors: list[str],
    salary_filters: list[str],
    employment_filters: list[str],
) -> pd.DataFrame:
    filtered = df.copy()

    if selected_majors:
        selected_set = {item.lower() for item in selected_majors}
        filtered = filtered[
            filtered["major_list"].map(
                lambda majors: bool({m.lower() for m in majors} & selected_set)
            )
        ]

    if salary_filters:
        filtered = filtered[filtered["salary_bucket"].isin(salary_filters)]

    if employment_filters:
        filtered = filtered[filtered["employment_status"].isin(employment_filters)]

    return filtered.reset_index(drop=True)


# -----------------------------
# Visualization helpers
# -----------------------------
def build_gender_chart(detail: pd.Series):
    gender_cols = [
        ("남성", safe_float(detail.get("PCNT1_남자"))),
        ("여성", safe_float(detail.get("PCNT1_여자"))),
    ]
    chart_df = pd.DataFrame(gender_cols, columns=["구분", "값"])
    chart_df = chart_df.dropna()
    if chart_df.empty or chart_df["값"].sum() == 0:
        return None

    fig = px.pie(chart_df, values="값", names="구분", hole=0.45)
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend_title_text="",
        height=320,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


def build_age_chart(detail: pd.Series):
    age_rows = []
    for label in ["중학생(14~16세 청소년)", "고등학생(17~19세 청소년)"]:
        pcnt1 = safe_float(detail.get(f"PCNT1_{label}"))
        pcnt2 = safe_float(detail.get(f"PCNT2_{label}"))
        if pcnt1 is not None:
            age_rows.append({"연령대": label, "지표": "PCNT1", "값": pcnt1})
        if pcnt2 is not None:
            age_rows.append({"연령대": label, "지표": "PCNT2", "값": pcnt2})

    chart_df = pd.DataFrame(age_rows)
    if chart_df.empty:
        return None

    fig = px.bar(chart_df, x="연령대", y="값", color="지표", barmode="group")
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend_title_text="",
        xaxis_title="",
        yaxis_title="지표값",
        height=320,
    )
    return fig


def build_salary_gauge(amount: float | None):
    if amount is None:
        return None

    max_value = max(5000, amount * 1.35)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=amount,
            number={"suffix": "만원"},
            gauge={
                "axis": {"range": [0, max_value]},
                "bar": {"thickness": 0.45},
                "steps": [
                    {"range": [0, max_value * 0.33], "color": "#dbeafe"},
                    {"range": [max_value * 0.33, max_value * 0.66], "color": "#bfdbfe"},
                    {"range": [max_value * 0.66, max_value], "color": "#93c5fd"},
                ],
            },
            title={"text": "평균 임금 수준"},
        )
    )
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10))
    return fig


# -----------------------------
# UI styling
# -----------------------------
def inject_css() -> None:
    render_html(
        """
        <style>
        :root{
            --bg:#f5f7fb;
            --panel:#ffffff;
            --line:#e6ebf2;
            --text:#0f172a;
            --muted:#667085;
            --blue:#2563eb;
            --blue-soft:#eff6ff;
            --shadow:0 8px 28px rgba(15,23,42,.06);
            --radius:18px;
            --container:1280px;
        }

        html, body, [class*="css"] { color: var(--text); }
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(37,99,235,.08), transparent 20%),
                linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
        }

        .block-container{
            max-width:var(--container);
            padding-top:1.15rem;
            padding-bottom:2.2rem;
        }

        .hero{
            background:linear-gradient(135deg, #0f172a 0%, #173b74 55%, #2563eb 100%);
            border-radius:24px;
            padding:30px;
            margin-bottom:20px;
            box-shadow:var(--shadow);
        }
        .hero-kicker{
            font-size:12px;
            color:#dbeafe;
            font-weight:800;
            letter-spacing:.12em;
            text-transform:uppercase;
            margin-bottom:10px;
        }
        .hero-title{
            font-size:32px;
            line-height:1.25;
            color:#ffffff;
            font-weight:800;
            margin-bottom:10px;
        }
        .hero-sub{
            font-size:15px;
            line-height:1.7;
            color:#dbeafe;
            max-width:860px;
        }
        .glass-row{
            display:flex;
            flex-wrap:wrap;
            gap:10px;
            margin-top:16px;
        }
        .glass-chip{
            display:inline-flex;
            align-items:center;
            background:rgba(255,255,255,.10);
            border:1px solid rgba(255,255,255,.18);
            border-radius:999px;
            padding:9px 14px;
            color:#ffffff;
            font-size:13px;
            font-weight:700;
        }

        .panel{
            background:var(--panel);
            border:1px solid var(--line);
            border-radius:20px;
            box-shadow:var(--shadow);
            padding:22px;
            margin-bottom:20px;
        }
        .panel-head{ margin-bottom:16px; }
        .section-kicker{
            font-size:12px;
            font-weight:800;
            letter-spacing:.08em;
            text-transform:uppercase;
            color:#2563eb;
            margin-bottom:6px;
        }
        .section-title{
            font-size:22px;
            line-height:1.4;
            font-weight:800;
            color:#102a43;
            margin:0 0 4px 0;
        }
        .section-sub{
            font-size:14px;
            line-height:1.65;
            color:#64748b;
        }

        .stats-row{
            display:grid;
            grid-template-columns:repeat(4, minmax(0, 1fr));
            gap:14px;
            margin-top:18px;
        }
        .stat-card{
            background:#ffffff;
            border:1px solid #dbe7fb;
            border-radius:16px;
            padding:18px 16px;
        }
        .stat-label{
            font-size:12px;
            color:#667085;
            font-weight:700;
            margin-bottom:8px;
        }
        .stat-value{
            font-size:24px;
            line-height:1.25;
            color:#0f172a;
            font-weight:800;
            margin-bottom:4px;
        }
        .stat-sub{
            font-size:13px;
            color:#64748b;
            line-height:1.5;
        }

        .search-banner{
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid var(--line);
            border-radius:20px;
            padding:18px 18px 8px 18px;
            box-shadow:var(--shadow);
            margin-bottom:18px;
        }
        .filter-meta{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            margin-top:8px;
        }
        .meta-chip{
            display:inline-flex;
            align-items:center;
            padding:7px 12px;
            border-radius:999px;
            background:#eff6ff;
            border:1px solid #dbeafe;
            color:#1d4ed8;
            font-size:12px;
            font-weight:700;
        }

        .result-grid{
            display:grid;
            grid-template-columns:repeat(3, minmax(0, 1fr));
            gap:16px;
        }
        .result-card{
            background:#ffffff;
            border:1px solid var(--line);
            border-radius:18px;
            box-shadow:var(--shadow);
            padding:18px;
            min-height:245px;
        }
        .job-title{
            font-size:20px;
            line-height:1.4;
            font-weight:800;
            color:#102a43;
            margin-bottom:8px;
        }
        .job-summary{
            font-size:14px;
            line-height:1.7;
            color:#475467;
            min-height:70px;
            margin-bottom:14px;
        }
        .tag-row{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            margin-bottom:14px;
        }
        .tag-chip{
            display:inline-flex;
            align-items:center;
            padding:6px 10px;
            border-radius:999px;
            background:#f8fbff;
            border:1px solid #dce8fb;
            color:#2563eb;
            font-size:12px;
            font-weight:700;
        }
        .metric-row{
            display:grid;
            grid-template-columns:repeat(2, minmax(0, 1fr));
            gap:10px;
            margin-top:6px;
        }
        .mini-metric{
            background:#f8fafc;
            border:1px solid #e8eef7;
            border-radius:14px;
            padding:10px 12px;
        }
        .mini-label{
            font-size:11px;
            color:#667085;
            font-weight:700;
            margin-bottom:5px;
        }
        .mini-value{
            font-size:15px;
            color:#0f172a;
            font-weight:800;
        }

        .profile-box{
            background:#f8fbff;
            border:1px solid #dce8fb;
            border-radius:18px;
            padding:18px;
        }
        .profile-summary{
            font-size:15px;
            line-height:1.8;
            color:#334155;
        }
        .bullet-list{
            list-style:none;
            padding-left:0;
            margin:0;
        }
        .bullet-list li{
            padding:10px 0;
            border-bottom:1px solid #edf2f7;
            font-size:14px;
            line-height:1.75;
            color:#334155;
        }
        .bullet-list li:last-child{ border-bottom:none; }

        .pill-wrap{
            display:flex;
            flex-wrap:wrap;
            gap:10px;
        }
        .pill{
            display:inline-flex;
            align-items:center;
            padding:9px 13px;
            border-radius:999px;
            background:#eff6ff;
            border:1px solid #dbeafe;
            color:#1d4ed8;
            font-size:13px;
            font-weight:700;
        }
        .soft-card{
            background:#fbfdff;
            border:1px solid #e8eef7;
            border-radius:16px;
            padding:16px;
            height:100%;
        }
        .timeline-card{
            background:#fbfdff;
            border:1px solid #e8eef7;
            border-radius:16px;
            padding:18px 16px;
            min-height:220px;
        }
        .timeline-no{
            width:34px;
            height:34px;
            border-radius:50%;
            background:#eff6ff;
            border:1px solid #dbeafe;
            color:#2563eb;
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:13px;
            font-weight:800;
            margin-bottom:12px;
        }
        .timeline-title{
            font-size:16px;
            line-height:1.5;
            font-weight:800;
            color:#102a43;
            margin-bottom:8px;
        }
        .timeline-text{
            font-size:14px;
            line-height:1.75;
            color:#475467;
            white-space:normal;
            word-break:keep-all;
        }
        .empty-text{
            font-size:14px;
            line-height:1.7;
            color:#98a2b3;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div{
            background:#ffffff !important;
            border:1px solid #d0d9e5 !important;
            border-radius:14px !important;
            min-height:48px !important;
            box-shadow:none !important;
            color:#111827 !important;
        }
        input{ color:#111827 !important; }
        input::placeholder{ color:#94a3b8 !important; }
        .stTextInput label, .stSelectbox label, .stMultiSelect label{
            color:#334155 !important;
            font-weight:700 !important;
            font-size:14px !important;
        }
        .stButton > button{
            border-radius:14px !important;
            border:1px solid #d0d9e5 !important;
            min-height:42px !important;
            font-weight:700 !important;
        }
        .stAlert, .stInfo, .stWarning{ border-radius:16px !important; }

        @media (max-width: 1100px){
            .stats-row, .result-grid{ grid-template-columns:1fr 1fr; }
        }
        @media (max-width: 768px){
            .stats-row, .result-grid{ grid-template-columns:1fr; }
        }
        </style>
        """
    )


# -----------------------------
# Page rendering helpers
# -----------------------------
def render_hero(df: pd.DataFrame) -> None:
    major_count = sum(1 for col in df.columns if col.startswith("major_"))
    render_html(
        f"""
        <div class="hero">
            <div class="hero-kicker">Job-Explorer AI</div>
            <div class="hero-title">미래의 직업을 검색하세요</div>
            <div class="hero-sub">
                키워드 기반 검색, 직무 요약, 준비 경로, 전공·자격 정보, 통계 차트를 한 화면에서 탐색할 수 있도록 구성한 AI 기반 직업 데이터 큐레이션 플랫폼입니다.
            </div>
            <div class="glass-row">
                <span class="glass-chip">직업 데이터 {len(df):,}건</span>
                <span class="glass-chip">전공 컬럼 {major_count}개 연동</span>
                <span class="glass-chip">NCS·전망·통계 정보 통합</span>
            </div>
        </div>
        """
    )


def render_top_stats(df: pd.DataFrame) -> None:
    salary_with_value = int(df["salary_amount"].notna().sum())
    good_outlook = int((df["employment_status"] == "좋음").sum())
    major_unique = len(sorted({major for majors in df["major_list"] for major in majors}))
    cert_count = int(df["certification_list"].map(len).sum())

    render_html(
        f"""
        <div class="panel">
            <div class="panel-head">
                <div>
                    <div class="section-kicker">Data Snapshot</div>
                    <div class="section-title">직업 데이터 현황</div>
                    <div class="section-sub">업로드된 career_jobs.xlsx 기준으로 탐색 가능한 전체 범위를 요약했습니다.</div>
                </div>
            </div>
            <div class="stats-row">
                <div class="stat-card">
                    <div class="stat-label">전체 직업 수</div>
                    <div class="stat-value">{len(df):,}</div>
                    <div class="stat-sub">job 컬럼 기준 유효 직업 수</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">임금 정보 보유</div>
                    <div class="stat-value">{salary_with_value:,}</div>
                    <div class="stat-sub">salery 컬럼에서 수치 추출 가능</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">전망 좋음 직업</div>
                    <div class="stat-value">{good_outlook:,}</div>
                    <div class="stat-sub">employment·job_possibility 기반</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">연결 전공 / 자격 정보</div>
                    <div class="stat-value">{major_unique:,} / {cert_count:,}</div>
                    <div class="stat-sub">major_1~21, certification 기준</div>
                </div>
            </div>
        </div>
        """
    )


def render_search_panel(total_count: int, filtered_count: int, query: str) -> None:
    chips = [
        f"검색어: {query}" if query.strip() else "검색어 없음",
        f"필터 적용 결과 {filtered_count:,}건",
        f"전체 데이터 {total_count:,}건",
    ]
    chips_html = "".join([f'<span class="meta-chip">{html.escape(chip)}</span>' for chip in chips])
    render_html(
        f"""
        <div class="search-banner">
            <div class="section-kicker">Search & Filter</div>
            <div class="section-title">키워드와 조건으로 직업을 좁혀보세요</div>
            <div class="section-sub">job, summary, similarJob, aptitude, major 정보를 함께 반영하여 검색합니다.</div>
            <div class="filter-meta">{chips_html}</div>
        </div>
        """
    )


def render_result_card(row: pd.Series) -> None:
    tags = row.get("similar_job_list", [])[:3]
    if not tags:
        tags = row.get("major_list", [])[:3]
    tags_html = "".join([f'<span class="tag-chip">{html.escape(tag)}</span>' for tag in tags])

    salary_label = "정보 없음"
    if row.get("salary_amount") is not None and not pd.isna(row.get("salary_amount")):
        salary_label = f"{int(row['salary_amount']):,}만원"

    render_html(
        f"""
        <div class="result-card">
            <div class="job-title">{html.escape(str(row.get('job', '')))}</div>
            <div class="job-summary">{html.escape(shorten_text(row.get('summary', ''), 88))}</div>
            <div class="tag-row">{tags_html if tags_html else '<span class="tag-chip">연관 태그 없음</span>'}</div>
            <div class="metric-row">
                <div class="mini-metric">
                    <div class="mini-label">임금 수준</div>
                    <div class="mini-value">{html.escape(salary_label)} · {html.escape(str(row.get('salary_bucket', '정보 없음')))}</div>
                </div>
                <div class="mini-metric">
                    <div class="mini-label">고용 전망</div>
                    <div class="mini-value">{html.escape(str(row.get('employment_status', '보통')))}</div>
                </div>
            </div>
        </div>
        """
    )


def render_profile_section(detail: pd.Series) -> None:
    summary_lines = split_lines(detail.get("summary", ""))
    if not summary_lines:
        summary_lines = [clean_sentence(detail.get("summary", ""))]
    summary_html = "<ul class='bullet-list'>" + "".join([
        f"<li>{html.escape(line)}</li>" for line in summary_lines if line
    ]) + "</ul>"

    render_html(
        """
        <div class="panel">
            <div class="panel-head">
                <div>
                    <div class="section-kicker">Job Profile</div>
                    <div class="section-title">직무 프로필</div>
                    <div class="section-sub">직업명과 summary 전문을 읽기 쉬운 문장 단위로 구조화했습니다.</div>
                </div>
            </div>
        </div>
        """
    )
    col1, col2 = st.columns([1.2, 0.8], gap="large")
    with col1:
        render_html(
            f"""
            <div class="profile-box">
                <div class="section-title" style="font-size:26px; margin-bottom:12px;">{html.escape(str(detail.get('job', '')))}</div>
                <div class="profile-summary">{summary_html}</div>
            </div>
            """
        )
    with col2:
        similar_jobs = detail.get("similar_job_list", [])[:6]
        if similar_jobs:
            pills = "".join([f'<span class="pill">{html.escape(item)}</span>' for item in similar_jobs])
        else:
            pills = '<div class="empty-text">등록된 유사 직업 정보가 없습니다.</div>'
        render_html(
            f"""
            <div class="soft-card">
                <div class="section-title" style="font-size:18px; margin-bottom:10px;">유사 직업</div>
                <div class="pill-wrap">{pills}</div>
            </div>
            """
        )
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        majors = detail.get("major_list", [])[:8]
        major_html = "".join([f'<span class="pill">{html.escape(item)}</span>' for item in majors]) if majors else '<div class="empty-text">등록된 관련 전공 정보가 없습니다.</div>'
        render_html(
            f"""
            <div class="soft-card">
                <div class="section-title" style="font-size:18px; margin-bottom:10px;">관련 전공</div>
                <div class="pill-wrap">{major_html}</div>
            </div>
            """
        )


def get_roadmap_steps(detail: pd.Series) -> list[dict[str, str]]:
    summary_lines = split_lines(detail.get("summary", ""))
    prepare_lines = split_lines(detail.get("prepareway", ""))
    training_lines = split_lines(detail.get("training", ""))
    empway_lines = split_lines(detail.get("empway", ""))

    fallback_text = {
        "직무 이해": summary_lines[0] if summary_lines else "직무 개요와 핵심 역할을 먼저 이해합니다.",
        "진입 준비": prepare_lines[0] if prepare_lines else "진입을 위한 학력, 교과 이수, 자격 요건을 확인합니다.",
        "훈련·실무": training_lines[0] if training_lines else "현장 훈련 또는 실무 적응 과정을 거칩니다.",
        "확장 경로": empway_lines[0] if empway_lines else "채용·배치·경력 확장 경로를 점검합니다.",
    }

    return [
        {"no": "1", "title": "직무 이해", "text": fallback_text["직무 이해"]},
        {"no": "2", "title": "진입 준비", "text": fallback_text["진입 준비"]},
        {"no": "3", "title": "훈련·실무", "text": fallback_text["훈련·실무"]},
        {"no": "4", "title": "확장 경로", "text": fallback_text["확장 경로"]},
    ]


def render_roadmap_section(detail: pd.Series) -> None:
    render_html(
        """
        <div class="panel">
            <div class="panel-head">
                <div>
                    <div class="section-kicker">How To Be</div>
                    <div class="section-title">로드맵</div>
                    <div class="section-sub">prepareway, training, empway를 바탕으로 단계형 로드맵으로 재구성했습니다.</div>
                </div>
            </div>
        </div>
        """
    )

    steps = get_roadmap_steps(detail)
    cols = st.columns(4, gap="medium")
    for col, step in zip(cols, steps):
        with col:
            render_html(
                f"""
                <div class="timeline-card">
                    <div class="timeline-no">{html.escape(step['no'])}</div>
                    <div class="timeline-title">{html.escape(step['title'])}</div>
                    <div class="timeline-text">{html.escape(clean_sentence(step['text']))}</div>
                </div>
                """
            )


def extract_keywords_from_text(text: str, limit: int = 14) -> list[str]:
    text = normalize_whitespace(text).lower()
    tokens = re.findall(r"[A-Za-z가-힣]{2,20}", text)
    stopwords = KOREAN_STOPWORDS | {
        "있다", "필요", "요구", "된다", "수준", "능력", "업무", "사람", "위한", "수행", "직업",
        "학생", "교육", "관련", "통해", "평가", "준비", "훈련", "현장", "취득", "과정", "정도",
    }
    cleaned = [token for token in tokens if token not in stopwords]
    counts = Counter(cleaned)
    return [word for word, _ in counts.most_common(limit)]


def render_capability_section(detail: pd.Series) -> None:
    aptitude_keywords = extract_keywords_from_text(str(detail.get("aptitude", "")), limit=12)
    if not aptitude_keywords:
        aptitude_keywords = extract_keywords_from_text(str(detail.get("summary", "")), limit=12)

    keyword_html = "".join([f'<span class="pill">#{html.escape(word)}</span>' for word in aptitude_keywords])
    certs = detail.get("certification_list", [])
    cert_html = "<ul class='bullet-list'>" + "".join([f"<li>{html.escape(item)}</li>" for item in certs]) + "</ul>" if certs else "<div class='empty-text'>등록된 자격 정보가 없습니다.</div>"

    render_html(
        """
        <div class="panel">
            <div class="panel-head">
                <div>
                    <div class="section-kicker">Competency & Qualification</div>
                    <div class="section-title">역량 및 자격</div>
                    <div class="section-sub">aptitude 텍스트에서 핵심 키워드를 추출하고 certification 정보를 리스트화했습니다.</div>
                </div>
            </div>
        </div>
        """
    )
    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        render_html(
            f"""
            <div class="soft-card">
                <div class="section-title" style="font-size:18px; margin-bottom:10px;">핵심 적성 키워드</div>
                <div class="pill-wrap">{keyword_html if keyword_html else '<div class="empty-text">추출 가능한 키워드가 없습니다.</div>'}</div>
            </div>
            """
        )
        aptitude_lines = split_lines(detail.get("aptitude", ""))
        if aptitude_lines:
            render_html(
                f"""
                <div class="soft-card" style="margin-top:16px;">
                    <div class="section-title" style="font-size:18px; margin-bottom:10px;">적성 상세</div>
                    <ul class="bullet-list">{''.join([f'<li>{html.escape(line)}</li>' for line in aptitude_lines])}</ul>
                </div>
                """
            )
    with col2:
        render_html(
            f"""
            <div class="soft-card">
                <div class="section-title" style="font-size:18px; margin-bottom:10px;">관련 자격</div>
                {cert_html}
            </div>
            """
        )
        contacts = detail.get("contact_list_all", [])
        contact_html = "<ul class='bullet-list'>" + "".join([f"<li>{html.escape(item)}</li>" for item in contacts]) + "</ul>" if contacts else "<div class='empty-text'>추가 링크/연락처 정보가 없습니다.</div>"
        render_html(
            f"""
            <div class="soft-card" style="margin-top:16px;">
                <div class="section-title" style="font-size:18px; margin-bottom:10px;">추가 정보</div>
                {contact_html}
            </div>
            """
        )


def render_market_section(detail: pd.Series) -> None:
    employment_text = split_lines(detail.get("employment", ""))
    possibility_text = split_lines(detail.get("job_possibility", ""))
    salary_amount = extract_salary_amount(detail.get("salery", ""))
    salary_bucket = detail.get("salary_bucket", "정보 없음")
    employment_status = detail.get("employment_status", "보통")

    render_html(
        """
        <div class="panel">
            <div class="panel-head">
                <div>
                    <div class="section-kicker">Market Insight</div>
                    <div class="section-title">시장 지표</div>
                    <div class="section-sub">salery, employment, job_possibility를 읽기 쉬운 요약 카드와 차트로 재구성했습니다.</div>
                </div>
            </div>
        </div>
        """
    )

    col1, col2 = st.columns([0.9, 1.1], gap="large")
    with col1:
        render_html(
            f"""
            <div class="soft-card">
                <div class="section-title" style="font-size:18px; margin-bottom:12px;">핵심 지표 요약</div>
                <div class="metric-row" style="grid-template-columns:1fr; gap:12px;">
                    <div class="mini-metric">
                        <div class="mini-label">임금 수준</div>
                        <div class="mini-value">{html.escape(f'{int(salary_amount):,}만원' if salary_amount is not None else '정보 없음')}</div>
                    </div>
                    <div class="mini-metric">
                        <div class="mini-label">임금 필터 구간</div>
                        <div class="mini-value">{html.escape(str(salary_bucket))}</div>
                    </div>
                    <div class="mini-metric">
                        <div class="mini-label">고용 전망</div>
                        <div class="mini-value">{html.escape(str(employment_status))}</div>
                    </div>
                </div>
            </div>
            """
        )
        gauge = build_salary_gauge(salary_amount)
        if gauge is not None:
            st.plotly_chart(gauge, use_container_width=True, key=f"salary_gauge_{detail.get('jobdicSeq', detail.name)}")
    with col2:
        tab1, tab2 = st.tabs(["고용전망", "발전가능성"])
        with tab1:
            if employment_text:
                render_html(
                    f"""
                    <div class="soft-card">
                        <ul class="bullet-list">{''.join([f'<li>{html.escape(line)}</li>' for line in employment_text])}</ul>
                    </div>
                    """
                )
            else:
                render_html("<div class='soft-card'><div class='empty-text'>고용전망 설명이 없습니다.</div></div>")
        with tab2:
            if possibility_text:
                render_html(
                    f"""
                    <div class="soft-card">
                        <ul class="bullet-list">{''.join([f'<li>{html.escape(line)}</li>' for line in possibility_text])}</ul>
                    </div>
                    """
                )
            else:
                render_html("<div class='soft-card'><div class='empty-text'>발전가능성 설명이 없습니다.</div></div>")


def render_chart_section(detail: pd.Series) -> None:
    render_html(
        """
        <div class="panel">
            <div class="panel-head">
                <div>
                    <div class="section-kicker">PCNT Analytics</div>
                    <div class="section-title">데이터 인사이트</div>
                    <div class="section-sub">PCNT 컬럼을 이용해 성별 관심도와 연령대별 지표를 시각화했습니다.</div>
                </div>
            </div>
        </div>
        """
    )

    gender_fig = build_gender_chart(detail)
    age_fig = build_age_chart(detail)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        render_html("<div class='soft-card'><div class='section-title' style='font-size:18px; margin-bottom:10px;'>성별 관심도 비중</div></div>")
        if gender_fig is not None:
            st.plotly_chart(gender_fig, use_container_width=True, key=f"gender_chart_{detail.get('jobdicSeq', detail.name)}")
        else:
            st.info("성별 PCNT 데이터가 없습니다.")
    with col2:
        render_html("<div class='soft-card'><div class='section-title' style='font-size:18px; margin-bottom:10px;'>연령대별 선호도</div></div>")
        if age_fig is not None:
            st.plotly_chart(age_fig, use_container_width=True, key=f"age_chart_{detail.get('jobdicSeq', detail.name)}")
        else:
            st.info("연령대 PCNT 데이터가 없습니다.")


def render_detail_page(detail: pd.Series) -> None:
    job_name = str(detail.get("job", ""))
    render_html(
        f"""
        <div class="hero" style="margin-bottom:18px;">
            <div class="hero-kicker">Detail Page</div>
            <div class="hero-title">{html.escape(job_name)}</div>
            <div class="hero-sub">직무 프로필, 로드맵, 역량 및 자격, 시장 지표, PCNT 차트를 한 화면에서 확인할 수 있습니다.</div>
        </div>
        """
    )

    top_col1, top_col2 = st.columns([0.18, 0.82])
    with top_col1:
        if st.button("← 목록으로", use_container_width=True):
            st.session_state.page = "main"
            rerun_app()
    with top_col2:
        st.caption("상세 분석 페이지")

    render_profile_section(detail)
    render_roadmap_section(detail)
    render_capability_section(detail)
    render_market_section(detail)
    render_chart_section(detail)


# -----------------------------
# Main page
# -----------------------------
def ensure_session_defaults() -> None:
    st.session_state.setdefault("page", "main")
    st.session_state.setdefault("selected_job", None)


def render_main_page(df: pd.DataFrame) -> None:
    render_hero(df)
    render_top_stats(df)

    major_options = sorted({major for majors in df["major_list"] for major in majors})

    search_query = st.text_input(
        "직업명이나 키워드를 입력하세요",
        placeholder="예: 컴퓨터와 관련된 일, 상담, 디자인, 교사, 환경",
        key="search_query",
    )

    col1, col2, col3 = st.columns([1.6, 0.9, 0.9], gap="medium")
    with col1:
        selected_majors = st.multiselect("전공별 필터", options=major_options, key="major_filter")
    with col2:
        salary_filters = st.multiselect("임금 수준 필터", options=["상", "중", "하", "정보 없음"], key="salary_filter")
    with col3:
        employment_filters = st.multiselect("고용전망 필터", options=["좋음", "보통", "주의"], key="employment_filter")

    searched = search_jobs(df, search_query)
    filtered = filter_results(searched, selected_majors, salary_filters, employment_filters)

    render_search_panel(total_count=len(df), filtered_count=len(filtered), query=search_query)

    if filtered.empty:
        st.warning("조건에 맞는 직업이 없습니다. 검색어나 필터를 조정해 주세요.")
        return

    per_page = 12
    page_count = max(1, (len(filtered) - 1) // per_page + 1)
    current_page = st.number_input("페이지", min_value=1, max_value=page_count, value=1, step=1)
    start = (current_page - 1) * per_page
    end = start + per_page
    page_df = filtered.iloc[start:end].reset_index(drop=True)

    cols = st.columns(3, gap="large")
    for idx, (_, row) in enumerate(page_df.iterrows()):
        with cols[idx % 3]:
            render_result_card(row)
            if st.button(f"상세 보기 · {row['job']}", key=f"open_{start+idx}", use_container_width=True):
                st.session_state.selected_job = row["job"]
                st.session_state.page = "detail"
                rerun_app()


# -----------------------------
# Entrypoint
# -----------------------------
def main() -> None:
    inject_css()
    ensure_session_defaults()

    if not DATA_FILE.exists():
        st.error(f"기본 데이터 파일을 찾지 못했습니다: {DATA_FILE.name}")
        st.stop()

    try:
        df = load_data(DATA_FILE)
    except Exception as exc:
        st.error(f"데이터 로드 중 오류가 발생했습니다: {exc}")
        st.stop()

    if st.session_state.page == "detail" and st.session_state.selected_job:
        matched = df[df["job"] == st.session_state.selected_job]
        if matched.empty:
            st.warning("선택한 직업 정보를 찾을 수 없어 목록 화면으로 이동합니다.")
            st.session_state.page = "main"
            st.session_state.selected_job = None
            rerun_app()
            return
        render_detail_page(matched.iloc[0])
    else:
        render_main_page(df)


if __name__ == "__main__":
    main()
