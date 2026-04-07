from __future__ import annotations

from pathlib import Path
import html
import time
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
            --line-strong:#d8e2f0;
            --text:#0f172a;
            --muted:#667085;
            --blue:#2563eb;
            --blue-soft:#eff6ff;
            --blue-soft-2:#f6faff;
            --shadow:0 10px 30px rgba(15,23,42,.06);
            --shadow-strong:0 18px 40px rgba(37,99,235,.10);
            --radius:20px;
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
            padding-top:1.05rem;
            padding-bottom:2.4rem;
        }

        .hero{
            background:linear-gradient(135deg, #0f172a 0%, #173b74 56%, #2563eb 100%);
            border-radius:26px;
            padding:32px 32px 28px 32px;
            margin-bottom:22px;
            box-shadow:var(--shadow-strong);
            position:relative;
            overflow:hidden;
        }
        .hero::after{
            content:"";
            position:absolute;
            right:-70px;
            top:-80px;
            width:240px;
            height:240px;
            border-radius:50%;
            background:radial-gradient(circle, rgba(255,255,255,.16) 0%, rgba(255,255,255,0) 68%);
            pointer-events:none;
        }
        .hero-kicker{
            font-size:12px;
            color:#dbeafe;
            font-weight:800;
            letter-spacing:.14em;
            text-transform:uppercase;
            margin-bottom:10px;
        }
        .hero-title{
            font-size:32px;
            line-height:1.22;
            color:#ffffff;
            font-weight:800;
            margin-bottom:12px;
            letter-spacing:-0.02em;
        }
        .hero-sub{
            font-size:15px;
            line-height:1.75;
            color:#dbeafe;
            max-width:860px;
        }
        .glass-row{
            display:flex;
            flex-wrap:wrap;
            gap:10px;
            margin-top:18px;
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
            backdrop-filter:blur(8px);
        }

        .panel{
            background:var(--panel);
            border:1px solid var(--line);
            border-radius:22px;
            box-shadow:var(--shadow);
            padding:24px;
            margin-bottom:22px;
        }
        .panel-head{ margin-bottom:14px; }
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
            margin:0 0 6px 0;
            letter-spacing:-0.02em;
        }
        .section-sub{
            font-size:14px;
            line-height:1.68;
            color:#64748b;
        }

        .stats-row{
            display:grid;
            grid-template-columns:repeat(4, minmax(0, 1fr));
            gap:14px;
            margin-top:16px;
        }
        .stat-card{
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid #dbe7fb;
            border-radius:18px;
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
            line-height:1.2;
            color:#0f172a;
            font-weight:800;
            margin-bottom:5px;
        }
        .stat-sub{
            font-size:13px;
            color:#64748b;
            line-height:1.55;
        }

        .ai-search-shell{
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid var(--line);
            border-radius:22px;
            padding:20px 20px 16px 20px;
            box-shadow:var(--shadow);
            margin-bottom:18px;
        }
        .ai-search-head{
            display:flex;
            align-items:flex-start;
            justify-content:space-between;
            gap:16px;
            margin-bottom:12px;
            flex-wrap:wrap;
        }
        .ai-badge{
            display:inline-flex;
            align-items:center;
            gap:8px;
            padding:8px 12px;
            border-radius:999px;
            background:#eff6ff;
            border:1px solid #dbeafe;
            color:#1d4ed8;
            font-size:12px;
            font-weight:800;
        }
        .ai-dot{
            width:8px;
            height:8px;
            border-radius:50%;
            background:#2563eb;
            box-shadow:0 0 0 0 rgba(37,99,235,.4);
            animation:pulseGlow 1.8s infinite;
        }
        @keyframes pulseGlow{
            0%{ box-shadow:0 0 0 0 rgba(37,99,235,.42); }
            70%{ box-shadow:0 0 0 8px rgba(37,99,235,0); }
            100%{ box-shadow:0 0 0 0 rgba(37,99,235,0); }
        }
        .suggestion-row,
        .filter-meta{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            margin-top:10px;
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
        .search-guide{
            font-size:13px;
            color:#64748b;
            line-height:1.6;
        }
        .brief-grid{
            display:grid;
            grid-template-columns:repeat(3, minmax(0, 1fr));
            gap:14px;
            margin-top:14px;
        }
        .brief-card{
            background:#f8fbff;
            border:1px solid #dce8fb;
            border-radius:18px;
            padding:16px;
            min-height:132px;
        }
        .brief-label{
            font-size:12px;
            color:#667085;
            font-weight:800;
            margin-bottom:10px;
        }
        .brief-value{
            font-size:20px;
            line-height:1.3;
            color:#0f172a;
            font-weight:800;
            margin-bottom:6px;
        }
        .brief-text{
            font-size:13px;
            line-height:1.65;
            color:#475467;
        }

        .result-grid{
            display:grid;
            grid-template-columns:repeat(3, minmax(0, 1fr));
            gap:18px;
        }
        .result-card{
            position:relative;
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid var(--line);
            border-radius:20px;
            box-shadow:var(--shadow);
            padding:20px 20px 18px 20px;
            min-height:286px;
            display:flex;
            flex-direction:column;
            transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;
            overflow:hidden;
            opacity:0;
            transform:translateY(14px);
            animation:cardReveal .55s ease forwards;
            animation-delay:var(--delay, 0s);
        }
        .result-card::before{
            content:"";
            position:absolute;
            inset:0 auto 0 0;
            width:5px;
            background:linear-gradient(180deg, #2563eb 0%, #93c5fd 100%);
            opacity:.92;
        }
        .result-card:hover{
            transform:translateY(-4px);
            box-shadow:0 18px 36px rgba(15,23,42,.10);
            border-color:#cfe0ff;
        }
        @keyframes cardReveal{
            from{ opacity:0; transform:translateY(14px); }
            to{ opacity:1; transform:translateY(0); }
        }
        .job-title{
            font-size:20px;
            line-height:1.42;
            font-weight:800;
            color:#102a43;
            margin-bottom:10px;
            letter-spacing:-0.02em;
            padding-left:4px;
        }
        .job-summary{
            font-size:14px;
            line-height:1.76;
            color:#475467;
            min-height:78px;
            margin-bottom:16px;
            padding-left:4px;
        }
        .tag-row{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            margin-bottom:16px;
            padding-left:4px;
        }
        .tag-chip{
            display:inline-flex;
            align-items:center;
            padding:7px 11px;
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
            margin-top:auto;
            padding-left:4px;
        }
        .mini-metric{
            background:#f8fafc;
            border:1px solid #e8eef7;
            border-radius:15px;
            padding:12px 12px 11px 12px;
        }
        .mini-label{
            font-size:11px;
            color:#667085;
            font-weight:700;
            margin-bottom:5px;
        }
        .mini-value{
            font-size:15px;
            line-height:1.45;
            color:#0f172a;
            font-weight:800;
            letter-spacing:-0.01em;
        }

        .profile-box{
            background:#f8fbff;
            border:1px solid #dce8fb;
            border-radius:18px;
            padding:20px;
        }
        .profile-summary{
            font-size:15px;
            line-height:1.82;
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
            line-height:1.76;
            color:#334155;
            word-break:keep-all;
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
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid #e8eef7;
            border-radius:18px;
            padding:18px;
            height:100%;
            box-shadow:0 4px 16px rgba(15,23,42,.03);
        }
        .timeline-card{
            position:relative;
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid #e8eef7;
            border-radius:18px;
            padding:20px 18px 18px 18px;
            min-height:250px;
            height:100%;
        }
        .timeline-card::before{
            content:"";
            position:absolute;
            left:18px;
            right:18px;
            top:0;
            height:3px;
            border-radius:999px;
            background:linear-gradient(90deg, #2563eb 0%, #bfdbfe 100%);
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
            margin-bottom:14px;
        }
        .timeline-title{
            font-size:16px;
            line-height:1.5;
            font-weight:800;
            color:#102a43;
            margin-bottom:10px;
            letter-spacing:-0.01em;
        }
        .timeline-text{
            font-size:14px;
            line-height:1.76;
            color:#475467;
            white-space:normal;
            word-break:keep-all;
        }
        .timeline-list,
        .insight-list{
            list-style:none;
            padding-left:0;
            margin:0;
        }
        .timeline-list li,
        .insight-list li{
            position:relative;
            padding-left:14px;
            margin-bottom:9px;
            font-size:14px;
            line-height:1.76;
            color:#475467;
            word-break:keep-all;
        }
        .timeline-list li:last-child,
        .insight-list li:last-child{
            margin-bottom:0;
        }
        .timeline-list li::before,
        .insight-list li::before{
            content:"•";
            position:absolute;
            left:0;
            top:0;
            color:#2563eb;
            font-weight:800;
        }
        .insight-box{
            background:#f8fbff;
            border:1px solid #dce8fb;
            border-radius:18px;
            padding:18px;
        }
        .insight-grid-2{
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:16px;
        }
        .detail-note{
            font-size:12px;
            color:#667085;
            margin-top:10px;
        }
        .empty-text{
            font-size:14px;
            line-height:1.7;
            color:#98a2b3;
        }
        .idle-shell{
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid var(--line);
            border-radius:24px;
            box-shadow:var(--shadow);
            padding:32px 28px;
            margin-top:4px;
        }
        .idle-grid{
            display:grid;
            grid-template-columns:1.15fr .85fr;
            gap:18px;
            align-items:stretch;
        }
        .idle-card{
            background:#f8fbff;
            border:1px solid #dce8fb;
            border-radius:18px;
            padding:18px;
        }
        .idle-title{
            font-size:24px;
            line-height:1.42;
            color:#102a43;
            font-weight:800;
            margin-bottom:10px;
            letter-spacing:-0.02em;
        }
        .idle-desc{
            font-size:15px;
            line-height:1.8;
            color:#475467;
        }
        .idle-step{
            display:flex;
            gap:12px;
            align-items:flex-start;
            margin-bottom:14px;
        }
        .idle-step:last-child{ margin-bottom:0; }
        .idle-step-no{
            width:28px;
            height:28px;
            border-radius:50%;
            background:#eff6ff;
            border:1px solid #dbeafe;
            color:#2563eb;
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:12px;
            font-weight:800;
            flex-shrink:0;
            margin-top:2px;
        }
        .idle-step-text{
            font-size:14px;
            line-height:1.72;
            color:#475467;
        }
        .loading-shell{
            background:linear-gradient(135deg, #0f172a 0%, #173b74 54%, #2563eb 100%);
            border-radius:24px;
            padding:28px 28px 24px 28px;
            margin:14px 0 22px 0;
            box-shadow:var(--shadow-strong);
            position:relative;
            overflow:hidden;
        }
        .loading-shell::after{
            content:"";
            position:absolute;
            inset:0;
            background:linear-gradient(100deg, rgba(255,255,255,0) 0%, rgba(255,255,255,.10) 36%, rgba(255,255,255,0) 64%);
            transform:translateX(-100%);
            animation:loadingSweep 2.4s linear infinite;
            pointer-events:none;
        }
        @keyframes loadingSweep{
            to{ transform:translateX(100%); }
        }
        .loading-kicker{
            font-size:12px;
            color:#dbeafe;
            font-weight:800;
            letter-spacing:.12em;
            text-transform:uppercase;
            margin-bottom:8px;
        }
        .loading-title{
            font-size:26px;
            line-height:1.34;
            color:#ffffff;
            font-weight:800;
            margin-bottom:10px;
            letter-spacing:-0.02em;
        }
        .loading-desc{
            font-size:14px;
            line-height:1.78;
            color:#dbeafe;
            max-width:860px;
            margin-bottom:16px;
        }
        .loading-stage{
            display:inline-flex;
            align-items:center;
            gap:8px;
            padding:9px 14px;
            border-radius:999px;
            background:rgba(255,255,255,.12);
            border:1px solid rgba(255,255,255,.18);
            color:#ffffff;
            font-size:13px;
            font-weight:700;
            margin-bottom:18px;
            backdrop-filter:blur(8px);
        }
        .loading-stage-dot{
            width:8px;
            height:8px;
            border-radius:50%;
            background:#bfdbfe;
            box-shadow:0 0 0 0 rgba(191,219,254,.48);
            animation:pulseGlowLight 1.8s infinite;
        }
        @keyframes pulseGlowLight{
            0%{ box-shadow:0 0 0 0 rgba(191,219,254,.45); }
            70%{ box-shadow:0 0 0 8px rgba(191,219,254,0); }
            100%{ box-shadow:0 0 0 0 rgba(191,219,254,0); }
        }
        .loading-steps{
            display:grid;
            grid-template-columns:repeat(4, minmax(0, 1fr));
            gap:12px;
            margin-top:8px;
        }
        .loading-step-card{
            background:rgba(255,255,255,.10);
            border:1px solid rgba(255,255,255,.16);
            border-radius:18px;
            padding:16px 14px;
            min-height:112px;
            backdrop-filter:blur(8px);
        }
        .loading-step-label{
            font-size:12px;
            color:#dbeafe;
            font-weight:800;
            margin-bottom:8px;
        }
        .loading-step-text{
            font-size:13px;
            line-height:1.72;
            color:#ffffff;
        }
        .skeleton-row{
            display:grid;
            grid-template-columns:repeat(3, minmax(0, 1fr));
            gap:16px;
            margin-top:18px;
        }
        .skeleton-card{
            background:#ffffff;
            border:1px solid #e5edf8;
            border-radius:20px;
            padding:20px;
            box-shadow:0 8px 24px rgba(15,23,42,.05);
        }
        .skeleton-line{
            height:12px;
            border-radius:999px;
            margin-bottom:10px;
            background:linear-gradient(90deg, #edf2f7 0%, #f8fbff 50%, #edf2f7 100%);
            background-size:200% 100%;
            animation:skeletonMove 1.35s linear infinite;
        }
        .skeleton-line:last-child{ margin-bottom:0; }
        .w-90{ width:90%; } .w-78{ width:78%; } .w-68{ width:68%; } .w-55{ width:55%; } .w-42{ width:42%; }
        @keyframes skeletonMove{
            0%{ background-position:200% 0; }
            100%{ background-position:-200% 0; }
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div{
            background:#ffffff !important;
            border:1px solid #d0d9e5 !important;
            border-radius:15px !important;
            min-height:50px !important;
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
            min-height:44px !important;
            font-weight:700 !important;
        }
        .stButton > button[kind="primary"]{
            background:linear-gradient(135deg, #173b74 0%, #2563eb 100%) !important;
            color:#ffffff !important;
            border:none !important;
        }
        .stAlert, .stInfo, .stWarning{ border-radius:16px !important; }

        @media (max-width: 1100px){
            .stats-row, .result-grid, .brief-grid{ grid-template-columns:1fr 1fr; }
        }
        @media (max-width: 1100px){
            .loading-steps{ grid-template-columns:1fr 1fr; }
            .idle-grid{ grid-template-columns:1fr; }
        }
        @media (max-width: 768px){
            .stats-row, .result-grid, .insight-grid-2, .brief-grid, .loading-steps, .skeleton-row{ grid-template-columns:1fr; }
            .hero{ padding:26px 22px 22px 22px; }
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
                <span class="glass-chip">연관 전공 정보 제공</span>
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
                    <div class="section-sub">현재 탐색 가능한 직업 데이터의 전체 규모와 정보 범위를 요약했습니다.</div>
                </div>
            </div>
            <div class="stats-row">
                <div class="stat-card">
                    <div class="stat-label">전체 직업 수</div>
                    <div class="stat-value">{len(df):,}</div>
                    <div class="stat-sub">현재 탐색 가능한 전체 직업 수</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">임금 정보 보유</div>
                    <div class="stat-value">{salary_with_value:,}</div>
                    <div class="stat-sub">임금 정보가 제공되는 직업 수</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">전망 좋음 직업</div>
                    <div class="stat-value">{good_outlook:,}</div>
                    <div class="stat-sub">전망이 긍정적으로 읽히는 직업 수</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">연결 전공 / 자격 정보</div>
                    <div class="stat-value">{major_unique:,} / {cert_count:,}</div>
                    <div class="stat-sub">전공 정보와 자격 정보의 누적 연결 수</div>
                </div>
            </div>
        </div>
        """
    )





def render_idle_search_state() -> None:
    render_html(
        """
        <div class="idle-shell">
            <div class="idle-grid">
                <div class="idle-card">
                    <div class="section-kicker">AI Search Guide</div>
                    <div class="idle-title">탐색어를 입력하면 AI가 직업 정보를 정리해 보여드립니다</div>
                    <div class="idle-desc">초기 화면에서는 전체 직업 목록을 바로 펼치지 않습니다. 찾고 싶은 직업명, 관심사, 일의 분위기, 필요한 역량을 자연스럽게 입력한 뒤 <strong>AI 탐색 시작</strong>을 눌러 주세요.</div>
                </div>
                <div class="idle-card">
                    <div class="section-kicker">How It Works</div>
                    <div class="idle-step"><div class="idle-step-no">1</div><div class="idle-step-text">입력한 문장을 바탕으로 탐색 의도와 핵심 키워드를 구조적으로 해석합니다.</div></div>
                    <div class="idle-step"><div class="idle-step-no">2</div><div class="idle-step-text">직무 설명, 유사 직업, 관련 전공, 자격, 시장 지표를 교차 검토합니다.</div></div>
                    <div class="idle-step"><div class="idle-step-no">3</div><div class="idle-step-text">우선순위를 재정렬한 뒤 탐색 브리핑과 결과 카드를 순차적으로 제시합니다.</div></div>
                </div>
            </div>
        </div>
        """
    )


def render_ai_loading_sequence(query: str) -> None:
    stages = [
        (
            "탐색 의도를 정교하게 해석하고 있습니다",
            "입력한 문장에서 관심 분야, 업무 성격, 적합 직무 신호를 분해하고 있습니다.",
            [
                ("의도 해석", "문장 속 핵심 키워드와 암묵적 요구를 정리합니다."),
                ("직무 매칭", "직업명·소개·유사 직무 흐름을 교차 탐색합니다."),
                ("맥락 결합", "전공, 자격, 시장 지표를 함께 결합합니다."),
                ("브리핑 구성", "최종 결과를 읽기 쉬운 탐색 구조로 정리합니다."),
            ],
        ),
        (
            "직무 데이터의 연관 관계를 탐색하고 있습니다",
            f"‘{html.escape(query)}’와 가까운 설명, 유사 직업, 전공 정보를 다층적으로 비교하고 있습니다.",
            [
                ("유사성 분석", "표면 키워드보다 의미상 가까운 직무를 우선 검토합니다."),
                ("전공 매핑", "흩어져 있는 전공 정보를 통합해 연결 패턴을 찾습니다."),
                ("시장 신호", "임금 수준과 고용 전망 텍스트를 함께 점검합니다."),
                ("정렬 최적화", "탐색 흐름에 맞게 결과의 우선순위를 조정합니다."),
            ],
        ),
        (
            "결과를 큐레이션하고 있습니다",
            "단순 일치 결과가 아니라, 바로 읽기 좋은 탐색 브리핑과 카드 구성을 정돈하고 있습니다.",
            [
                ("핵심 요약", "가장 먼저 볼 정보를 상단 브리핑에 압축합니다."),
                ("가독성 조정", "긴 설명은 요약하고 핵심 메트릭은 전면에 배치합니다."),
                ("카드 배열", "결과 카드를 위에서 아래로 순차적으로 제시할 준비를 합니다."),
                ("세부 연결", "상세 페이지에서 이어 볼 정보 흐름을 정리합니다."),
            ],
        ),
    ]

    panel = st.empty()
    progress_slot = st.empty()
    skeleton_slot = st.empty()
    progress = st.progress(0)

    steps_total = len(stages)
    for idx, (title, desc, cards) in enumerate(stages, start=1):
        cards_html = "".join(
            [
                f'<div class="loading-step-card"><div class="loading-step-label">{html.escape(label)}</div><div class="loading-step-text">{html.escape(text_line)}</div></div>'
                for label, text_line in cards
            ]
        )
        panel.markdown(
            textwrap.dedent(
                f"""
                <div class="loading-shell">
                    <div class="loading-kicker">AI Curation Engine</div>
                    <div class="loading-title">{html.escape(title)}</div>
                    <div class="loading-desc">{desc}</div>
                    <div class="loading-stage"><span class="loading-stage-dot"></span>{idx} / {steps_total} 단계 진행 중</div>
                    <div class="loading-steps">{cards_html}</div>
                </div>
                """
            ).strip(),
            unsafe_allow_html=True,
        )
        progress_value = int(idx / steps_total * 100)
        progress.progress(progress_value)
        progress_slot.caption(f"AI가 탐색 결과를 정교하게 정리하고 있습니다 · {progress_value}%")
        skeleton_slot.markdown(
            textwrap.dedent(
                """
                <div class="skeleton-row">
                    <div class="skeleton-card">
                        <div class="skeleton-line w-55"></div>
                        <div class="skeleton-line w-90"></div>
                        <div class="skeleton-line w-78"></div>
                        <div class="skeleton-line w-68"></div>
                        <div class="skeleton-line w-42"></div>
                    </div>
                    <div class="skeleton-card">
                        <div class="skeleton-line w-55"></div>
                        <div class="skeleton-line w-90"></div>
                        <div class="skeleton-line w-78"></div>
                        <div class="skeleton-line w-68"></div>
                        <div class="skeleton-line w-42"></div>
                    </div>
                    <div class="skeleton-card">
                        <div class="skeleton-line w-55"></div>
                        <div class="skeleton-line w-90"></div>
                        <div class="skeleton-line w-78"></div>
                        <div class="skeleton-line w-68"></div>
                        <div class="skeleton-line w-42"></div>
                    </div>
                </div>
                """
            ).strip(),
            unsafe_allow_html=True,
        )
        time.sleep(0.95 if idx == 1 else 1.05)

    panel.empty()
    progress.empty()
    progress_slot.empty()
    skeleton_slot.empty()

def render_search_panel(total_count: int, filtered_count: int, query: str) -> None:
    chips = [
        f"탐색어: {query}" if query.strip() else "탐색어 없음",
        f"현재 결과 {filtered_count:,}건",
        f"전체 데이터 {total_count:,}건",
    ]
    chips_html = "".join([f'<span class="meta-chip">{html.escape(chip)}</span>' for chip in chips])
    render_html(
        f"""
        <div class="ai-search-shell">
            <div class="ai-search-head">
                <div>
                    <div class="section-kicker">AI Search</div>
                    <div class="section-title">검색 조건과 필터를 바탕으로 직업을 탐색했습니다</div>
                    <div class="section-sub">직업명, 소개, 적성, 유사 직무, 관련 전공 정보를 함께 반영합니다.</div>
                </div>
                <div class="ai-badge"><span class="ai-dot"></span>AI 탐색 세션</div>
            </div>
            <div class="filter-meta">{chips_html}</div>
        </div>
        """
    )


def render_ai_search_brief(query: str, searched: pd.DataFrame, filtered: pd.DataFrame) -> None:
    if not query.strip():
        render_html(
            """
            <div class="ai-search-shell">
                <div class="ai-search-head">
                    <div>
                        <div class="section-kicker">AI Search Guide</div>
                        <div class="section-title">어떤 직업을 찾고 있는지 자연스럽게 입력해 보세요</div>
                        <div class="section-sub">직업명뿐 아니라 “컴퓨터와 관련된 일”, “사람을 돕는 직업”, “디자인 감각이 필요한 일”처럼 문장형 탐색도 가능합니다.</div>
                    </div>
                    <div class="ai-badge"><span class="ai-dot"></span>탐색 대기 중</div>
                </div>
                <div class="search-guide">검색어를 입력한 뒤 <strong>AI 탐색 시작</strong>을 누르면 결과를 정리해서 보여줍니다.</div>
            </div>
            """
        )
        return

    tokens = extract_search_terms(query)[:6]
    token_html = "".join([f'<span class="meta-chip">{html.escape(token)}</span>' for token in tokens])

    tag_pool = []
    for _, row in filtered.head(8).iterrows():
        tag_pool.extend(row.get("similar_job_list", [])[:2])
        tag_pool.extend(row.get("major_list", [])[:1])
    related_tags = [item for item, _ in Counter(tag_pool).most_common(5)]
    related_html = "".join([f'<span class="meta-chip">{html.escape(tag)}</span>' for tag in related_tags])

    if filtered.empty:
        result_text = "조건에 맞는 결과를 찾지 못했습니다."
        result_sub = "검색어를 더 넓게 입력하거나 필터를 줄여 보세요."
    else:
        top_job = str(filtered.iloc[0].get("job", ""))
        result_text = f"{len(filtered):,}개 직업을 선별했습니다"
        result_sub = f"현재 탐색어와 가장 가깝게 읽히는 직업은 {top_job}입니다." if top_job else "검색 결과를 정렬했습니다."

    render_html(
        f"""
        <div class="panel">
            <div class="panel-head">
                <div class="section-kicker">AI Exploration Brief</div>
                <div class="section-title">AI 탐색 브리핑</div>
                <div class="section-sub">입력한 탐색어를 기반으로 연관 키워드를 해석하고, 현재 결과를 요약했습니다.</div>
            </div>
            <div class="brief-grid">
                <div class="brief-card">
                    <div class="brief-label">해석된 탐색 키워드</div>
                    <div class="brief-text">{token_html if token_html else '<span class="empty-text">추출된 키워드가 없습니다.</span>'}</div>
                </div>
                <div class="brief-card">
                    <div class="brief-label">탐색 결과</div>
                    <div class="brief-value">{html.escape(result_text)}</div>
                    <div class="brief-text">{html.escape(result_sub)}</div>
                </div>
                <div class="brief-card">
                    <div class="brief-label">연관 주제</div>
                    <div class="brief-text">{related_html if related_html else '상세 결과가 쌓이면 연관 직무·전공 흐름을 함께 보여줍니다.'}</div>
                </div>
            </div>
        </div>
        """
    )


def render_result_card(row: pd.Series, delay: float = 0.0) -> None:
    tags = row.get("similar_job_list", [])[:3]
    if not tags:
        tags = row.get("major_list", [])[:3]
    tags_html = "".join([f'<span class="tag-chip">{html.escape(tag)}</span>' for tag in tags])

    salary_label = "정보 없음"
    if row.get("salary_amount") is not None and not pd.isna(row.get("salary_amount")):
        salary_label = f"{int(row['salary_amount']):,}만원"

    summary = shorten_text(row.get("summary", ""), 92)
    if not summary:
        summary = "직업 요약 정보가 준비되지 않았습니다."

    render_html(
        f"""
        <div class="result-card" style="--delay:{delay:.2f}s;">
            <div class="job-title">{html.escape(str(row.get('job', '')))}</div>
            <div class="job-summary">{html.escape(summary)}</div>
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
                    <div class="section-sub">직업의 핵심 역할과 특징을 문장 단위로 정리했습니다.</div>
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
                    <div class="section-sub">진입부터 실무 적응, 이후 확장까지의 흐름을 단계형으로 정리했습니다.</div>
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


def trim_phrase_edges(phrase: str) -> str:
    phrase = normalize_whitespace(phrase)
    phrase = re.sub(r"^[\-•·▪■]\s*", "", phrase)
    phrase = re.sub(r"^(또|그리고|또한|즉|예를 들어)\s+", "", phrase)
    phrase = re.sub(r"^(?:와|과|및)\s+", "", phrase)
    phrase = re.sub(r"^(이 직업은|해당 직무는|해당 직업은|[가-힣A-Za-z0-9·]+는|[가-힣A-Za-z0-9·]+은|[가-힣A-Za-z0-9·]+이|[가-힣A-Za-z0-9·]+가)\s+", "", phrase)
    phrase = re.sub(r"\s*(이|가|은|는|을|를)\s*(필요하다|필요하며|요구된다|요구되며|있어야 한다|있어야 하며|중요하다|유리하다|적합하다).*$", "", phrase)
    phrase = re.sub(r"\s*(등의|등)\s*$", "", phrase)
    phrase = re.sub(r"\s+", " ", phrase).strip(" ,.;:-")
    return phrase


def extract_keywords_from_text(text: str, limit: int = 14) -> list[str]:
    raw = normalize_whitespace(text)
    if not raw:
        return []

    stopwords = KOREAN_STOPWORDS | {
        "있다", "필요", "요구", "된다", "수준", "능력", "업무", "사람", "위한", "수행", "직업",
        "학생", "교육", "관련", "통해", "평가", "준비", "훈련", "현장", "취득", "과정", "정도",
        "사람들에게", "사람에게", "적합하며", "유리하다", "필요하다", "필요하며", "요구된다", "요구되며",
        "가진", "가지는", "가지고", "있어야", "있으며", "많으므로", "그러므로", "때문에", "전반적인",
    }

    phrase_endings = [
        "의사소통 능력", "글쓰기 능력", "문제 해결 능력", "논리적 사고", "분석적 사고",
        "응용능력", "자료처리능력", "의사소통능력", "언어전달능력", "문제해결능력", "사무능력",
        "활용능력", "사고능력", "통제력", "리더십", "판단력", "분석력", "사고력", "책임감",
        "사명의식", "창의력", "집중력", "인내심", "협동심", "대인관계", "자기통제력", "사회성",
        "정직성", "신뢰성", "꼼꼼함", "윤리의식", "응용력", "열정", "애정", "혁신", "성취",
        "끈기", "체력", "역량", "지식", "능력",
    ]
    phrase_endings = sorted(phrase_endings, key=len, reverse=True)
    phrase_pattern = r"([가-힣A-Za-z·/ ]{1,28}?(?:" + "|".join(re.escape(x) for x in phrase_endings) + r"))"

    candidates = []
    fragments = []
    for line in split_lines(raw):
        parts = re.split(r",|;|/|·", line)
        fragments.extend([normalize_whitespace(part) for part in parts if normalize_whitespace(part)])

    for frag in fragments:
        matches = [m.group(1) for m in re.finditer(phrase_pattern, frag)]
        if matches:
            candidates.extend(matches)
        else:
            frag = trim_phrase_edges(frag)
            if 2 <= len(frag) <= 14 and " " not in frag:
                candidates.append(frag)

    scored = []
    seen = set()
    for phrase in candidates:
        phrase = trim_phrase_edges(phrase)
        if not phrase:
            continue
        if phrase.lower() in stopwords:
            continue
        if len(phrase) < 2 or len(phrase) > 22:
            continue
        if phrase.startswith(("과 ", "와 ", "및 ")):
            continue

        score = 0.0
        if " " in phrase:
            score += 5.0
        if any(phrase.endswith(end) for end in phrase_endings):
            score += 4.0
        if 4 <= len(phrase) <= 14:
            score += 3.0
        elif len(phrase) <= 18:
            score += 1.5
        if any(marker in phrase for marker in ["로서", "때문", "이므로", "많으므로", "사람", "업무"]):
            score -= 3.0
        if phrase in {"교육", "학생", "직무", "사람", "업무"}:
            score -= 5.0

        key = phrase.lower()
        if key in seen:
            continue
        scored.append((score, phrase))
        seen.add(key)

    scored.sort(key=lambda x: (-x[0], len(x[1])))

    selected = []
    for _, phrase in scored:
        if any(phrase != kept and phrase in kept for kept in selected):
            continue
        selected.append(phrase)
        if len(selected) >= limit:
            break

    if not selected:
        tokens = re.findall(r"[A-Za-z가-힣]{2,20}", raw.lower())
        fallback = []
        for token in tokens:
            if token in stopwords:
                continue
            if token not in fallback:
                fallback.append(token)
            if len(fallback) >= limit:
                break
        return fallback

    return selected


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
                    <div class="section-sub">직무에 어울리는 적성과 준비에 도움이 되는 자격 정보를 함께 정리했습니다.</div>
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
                    <div class="section-sub">임금과 전망 정보를 한눈에 읽을 수 있도록 요약했습니다.</div>
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
                    <div class="section-sub">관심도 분포를 성별과 연령대 기준으로 시각화했습니다.</div>
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
    st.session_state.setdefault("search_input", "")
    st.session_state.setdefault("committed_query", "")
    st.session_state.setdefault("trigger_ai_search", False)



def render_main_page(df: pd.DataFrame) -> None:
    suggestion_queries = [
        "컴퓨터와 관련된 일",
        "사람을 돕는 직업",
        "디자인 감각이 필요한 직업",
        "안정적인 사무 직무",
        "환경 문제를 다루는 일",
        "학생을 가르치는 직업",
    ]

    major_options = sorted({major for majors in df["major_list"] for major in majors})

    render_html(
        """
        <div class="ai-search-shell">
            <div class="ai-search-head">
                <div>
                    <div class="section-kicker">AI Search Console</div>
                    <div class="section-title">키워드보다 한 단계 더 자연스럽게 탐색해 보세요</div>
                    <div class="section-sub">직업명, 관심사, 일의 성격, 원하는 분위기를 문장처럼 입력하면 관련 직업을 재정렬합니다.</div>
                </div>
                <div class="ai-badge"><span class="ai-dot"></span>탐색 준비 완료</div>
            </div>
        </div>
        """
    )

    suggestion_cols = st.columns(3, gap="small")
    for idx, suggestion in enumerate(suggestion_queries):
        with suggestion_cols[idx % 3]:
            if st.button(suggestion, key=f"suggestion_{idx}", use_container_width=True):
                st.session_state.search_input = suggestion
                st.session_state.committed_query = suggestion
                st.session_state.trigger_ai_search = True
                rerun_app()

    with st.form("ai_search_form", clear_on_submit=False):
        st.text_input(
            "AI 탐색어 입력",
            placeholder="예: 데이터 분석을 하면서 사람과도 소통하는 직업",
            key="search_input",
        )
        col_submit, col_reset = st.columns([0.82, 0.18], gap="small")
        with col_submit:
            submitted = st.form_submit_button("AI 탐색 시작", use_container_width=True, type="primary")
        with col_reset:
            reset_clicked = st.form_submit_button("초기화", use_container_width=True)

    if submitted:
        st.session_state.committed_query = st.session_state.get("search_input", "").strip()
        st.session_state.trigger_ai_search = True
        rerun_app()

    if reset_clicked:
        st.session_state.search_input = ""
        st.session_state.committed_query = ""
        st.session_state.trigger_ai_search = False
        rerun_app()

    col1, col2, col3 = st.columns([1.6, 0.9, 0.9], gap="medium")
    with col1:
        selected_majors = st.multiselect("전공별 필터", options=major_options, key="major_filter")
    with col2:
        salary_filters = st.multiselect("임금 수준 필터", options=["상", "중", "하", "정보 없음"], key="salary_filter")
    with col3:
        employment_filters = st.multiselect("고용전망 필터", options=["좋음", "보통", "주의"], key="employment_filter")

    search_query = st.session_state.get("committed_query", "")

    if st.session_state.get("trigger_ai_search") and search_query.strip():
        render_ai_loading_sequence(search_query)
        st.session_state.trigger_ai_search = False

    if not search_query.strip():
        render_ai_search_brief(search_query, pd.DataFrame(), pd.DataFrame())
        render_idle_search_state()
        return

    searched = search_jobs(df, search_query)
    filtered = filter_results(searched, selected_majors, salary_filters, employment_filters)

    render_ai_search_brief(search_query, searched, filtered)
    render_search_panel(total_count=len(df), filtered_count=len(filtered), query=search_query)

    if filtered.empty:
        st.warning("조건에 맞는 직업이 없습니다. 탐색어를 조금 넓게 입력하거나 필터를 줄여 주세요.")
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
            render_result_card(row, delay=idx * 0.08)
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
