
from pathlib import Path
import html
import math
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
    page_title="Job-Explorer AI",
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
    "관련", "직업", "일", "일을", "하는", "대한", "및", "에서", "으로", "위한", "위해",
    "같은", "있는", "되는", "분야", "업무", "직무", "사람", "경우", "통한", "기반", "직업명",
    "탐색", "분석", "미래", "검색", "관련된", "중심", "하는일", "하거나", "하고", "또는"
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

def render_html(markup: str):
    st.markdown(textwrap.dedent(markup).strip(), unsafe_allow_html=True)

def rerun_app():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

def inject_css():
    render_html(
        """
        <style>
        :root{
            --bg:#f5f7fb;
            --panel:#ffffff;
            --line:#e5eaf3;
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
                radial-gradient(circle at top right, rgba(37,99,235,.10), transparent 22%),
                linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
        }

        .block-container{
            max-width:var(--container);
            padding-top:1.2rem;
            padding-bottom:2.5rem;
        }

        h1,h2,h3,h4,h5{
            color:#102a43 !important;
            letter-spacing:-0.02em;
        }

        p, li, label, span, div{
            color:#334155;
        }

        .hero{
            background:linear-gradient(135deg, #0f172a 0%, #173b74 55%, #2563eb 100%);
            border-radius:24px;
            padding:30px 30px 26px 30px;
            box-shadow:var(--shadow);
            color:#fff;
            margin-bottom:20px;
        }

        .hero-kicker{
            font-size:12px;
            letter-spacing:.12em;
            text-transform:uppercase;
            font-weight:800;
            opacity:.9;
            color:#dbeafe;
            margin-bottom:10px;
        }

        .hero-title{
            font-size:32px;
            line-height:1.3;
            font-weight:800;
            color:#ffffff;
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
            gap:8px;
            background:rgba(255,255,255,.10);
            border:1px solid rgba(255,255,255,.18);
            border-radius:999px;
            padding:9px 14px;
            font-size:13px;
            color:#f8fbff;
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

        .panel-head{
            display:flex;
            align-items:flex-end;
            justify-content:space-between;
            gap:16px;
            flex-wrap:wrap;
            margin-bottom:16px;
        }

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
            line-height:1.6;
            color:#64748b;
        }

        .stats-row{
            display:grid;
            grid-template-columns:repeat(4, minmax(0,1fr));
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
            line-height:1.5;
            color:#667085;
            font-weight:700;
            margin-bottom:8px;
        }

        .stat-value{
            font-size:24px;
            line-height:1.3;
            font-weight:800;
            color:#0f172a;
            letter-spacing:-0.02em;
            margin-bottom:4px;
        }

        .stat-sub{
            font-size:13px;
            line-height:1.5;
            color:#64748b;
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
            color:#1d4ed8;
            border:1px solid #dbeafe;
            font-size:12px;
            font-weight:700;
        }

        .result-count{
            font-size:14px;
            line-height:1.6;
            color:#475467;
            font-weight:700;
        }

        .card-shell{
            background:#ffffff;
            border:1px solid var(--line);
            border-radius:18px;
            box-shadow:var(--shadow);
            padding:18px;
            min-height:300px;
            display:flex;
            flex-direction:column;
            justify-content:space-between;
        }

        .job-title{
            font-size:20px;
            line-height:1.45;
            font-weight:800;
            color:#102a43;
            margin-bottom:10px;
        }

        .job-summary{
            font-size:14px;
            line-height:1.7;
            color:#475467;
            min-height:76px;
            margin-bottom:14px;
        }

        .tag-row{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            margin-bottom:14px;
        }

        .tag{
            display:inline-flex;
            align-items:center;
            padding:7px 11px;
            border-radius:999px;
            background:#f8fafc;
            border:1px solid #e2e8f0;
            color:#334155;
            font-size:12px;
            font-weight:700;
        }

        .tag.blue{
            background:#eff6ff;
            border-color:#dbeafe;
            color:#1d4ed8;
        }

        .tag.green{
            background:#ecfdf3;
            border-color:#d1fadf;
            color:#027a48;
        }

        .tag.red{
            background:#fef3f2;
            border-color:#fecdca;
            color:#b42318;
        }

        .detail-hero{
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid var(--line);
            border-radius:22px;
            box-shadow:var(--shadow);
            padding:26px 24px;
            margin-bottom:18px;
        }

        .detail-topline{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:12px;
            flex-wrap:wrap;
            margin-bottom:12px;
        }

        .breadcrumb{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            align-items:center;
            font-size:12px;
            color:#667085;
        }

        .detail-title{
            font-size:30px;
            line-height:1.35;
            font-weight:800;
            color:#102a43;
            margin-bottom:10px;
        }

        .detail-summary{
            font-size:15px;
            line-height:1.8;
            color:#475467;
            margin-bottom:18px;
        }

        .detail-grid{
            display:grid;
            grid-template-columns:1.15fr .85fr;
            gap:18px;
        }

        .mini-card{
            background:#ffffff;
            border:1px solid var(--line);
            border-radius:18px;
            padding:18px;
            height:100%;
        }

        .mini-title{
            font-size:16px;
            line-height:1.5;
            font-weight:800;
            color:#102a43;
            margin-bottom:10px;
        }

        .mini-text{
            font-size:14px;
            line-height:1.7;
            color:#475467;
        }

        .timeline{
            display:grid;
            grid-template-columns:repeat(4, minmax(0,1fr));
            gap:16px;
        }

        .timeline-item{
            background:#fbfdff;
            border:1px solid #e6ebf3;
            border-radius:18px;
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
            margin-bottom:14px;
        }

        .timeline-title{
            font-size:15px;
            line-height:1.5;
            font-weight:800;
            color:#102a43;
            margin-bottom:8px;
        }

        .timeline-text{
            font-size:14px;
            line-height:1.75;
            color:#475467;
            word-break:keep-all;
        }

        .keyword-cloud{
            display:flex;
            flex-wrap:wrap;
            gap:10px;
        }

        .keyword-pill{
            display:inline-flex;
            align-items:center;
            border-radius:999px;
            padding:10px 15px;
            background:#ffffff;
            border:1px solid #e6ebf3;
            box-shadow:0 2px 8px rgba(15,23,42,.03);
            font-weight:800;
            color:#1f2937;
        }

        .two-col{
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:18px;
        }

        .clean-list{
            list-style:none;
            padding:0;
            margin:0;
        }

        .clean-list li{
            padding:10px 0;
            border-bottom:1px solid #eef2f6;
            font-size:14px;
            line-height:1.7;
            color:#475467;
            word-break:keep-all;
        }

        .clean-list li:last-child{
            border-bottom:none;
            padding-bottom:0;
        }

        .insight-grid{
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:18px;
        }

        .empty-note{
            font-size:14px;
            line-height:1.6;
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

        .stTextInput label,
        .stSelectbox label,
        .stMultiSelect label,
        .stRadio label{
            color:#334155 !important;
            font-weight:700 !important;
        }

        .stButton > button{
            width:100%;
            border-radius:14px;
            border:1px solid #cdd8ea;
            background:#ffffff;
            color:#102a43;
            font-weight:800;
            padding:.7rem 1rem;
        }

        .stButton > button:hover{
            border-color:#2563eb;
            color:#2563eb;
            background:#eff6ff;
        }

        @media (max-width: 1100px){
            .stats-row,
            .timeline,
            .detail-grid,
            .two-col,
            .insight-grid{
                grid-template-columns:1fr;
            }
        }
        </style>
        """
    )

def is_missing(value):
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return stripped == "" or stripped.lower() == "nan"
    try:
        result = pd.isna(value)
        if isinstance(result, bool):
            return result
    except Exception:
        pass
    return False

def clean_text(value):
    if is_missing(value):
        return ""
    text = str(value).replace("\r", "\n").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def split_items(value):
    if is_missing(value):
        return []
    text = str(value).replace("\r", "\n")
    raw_parts = []
    for part in re.split(r"\n|;|\|", text):
        part = part.strip()
        if not part:
            continue
        if "," in part and len(part) < 150:
            raw_parts.extend([p.strip() for p in part.split(",") if p.strip()])
        else:
            raw_parts.append(part)
    items = []
    for part in raw_parts:
        part = re.sub(r"^[\-•·]+\s*", "", part).strip()
        if part and part.lower() != "nan":
            items.append(part)
    return unique_keep_order(items)

def unique_keep_order(items):
    seen = set()
    result = []
    for item in items:
        key = str(item).strip()
        if not key or key.lower() == "nan":
            continue
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result

def shorten(text, width=42):
    text = clean_text(text)
    if len(text) <= width:
        return text
    return text[:width].rstrip() + "…"

def tokenize(text):
    text = clean_text(text).lower()
    tokens = re.findall(r"[a-z0-9가-힣]{2,20}", text)
    return [t for t in tokens if t not in KOREAN_STOPWORDS]

def expand_tokens(tokens):
    expanded = set(tokens)
    for token in list(tokens):
        for key, values in SYNONYM_MAP.items():
            if token == key or key in token or token in key:
                expanded.add(key)
                expanded.update(values)
    return list(expanded)

def parse_salary_metrics(text):
    text = clean_text(text).replace(",", "")
    if not text:
        return {}

    label_map = {"하위": "하위 25%", "평균": "평균", "상위": "상위 25%"}
    patterns = [
        r"(하위|평균|상위)\s*\(?\d+%\)?\s*([0-9]+(?:\.[0-9]+)?)\s*만원",
        r"(하위|평균|상위)[^\d]{0,18}([0-9]+(?:\.[0-9]+)?)\s*만원",
    ]
    metrics = {}
    for pattern in patterns:
        for key, value in re.findall(pattern, text):
            metrics[label_map[key]] = float(value)
        if metrics:
            break
    return metrics

def classify_outlook(text):
    raw = clean_text(text)
    if any(word in raw for word in ["감소", "줄어", "축소", "약화", "낮아질", "어려울"]):
        return "낮음"
    if any(word in raw for word in ["증가", "성장", "확대", "유망", "밝", "좋"]):
        return "높음"
    return "보통"

def extract_major_list(row):
    majors = []
    for col in [c for c in row.index if str(c).startswith("major_")]:
        value = row[col]
        if not is_missing(value):
            majors.append(str(value).strip())
    return unique_keep_order(majors)

def extract_contact_list(row):
    contacts = []
    for col in [c for c in row.index if str(c).startswith("contact_")]:
        value = row[col]
        if not is_missing(value):
            contacts.append(str(value).strip())
    return unique_keep_order(contacts)

def extract_keyword_cloud(row, limit=14):
    source_text = " ".join(
        [
            clean_text(row.get("job")),
            clean_text(row.get("summary")),
            clean_text(row.get("aptitude")),
            clean_text(row.get("prepareway")),
            clean_text(row.get("training")),
            clean_text(row.get("capacity_1")),
            clean_text(row.get("capacity_all")),
        ]
    )
    candidates = re.findall(r"[A-Za-z가-힣]{2,20}", source_text)
    stopwords = KOREAN_STOPWORDS | {
        "직업", "직무", "업무", "사람", "능력", "정보", "수행", "요구", "필요", "관련",
        "기본", "전반", "통해", "분야", "현재", "자료", "워크넷", "직업인", "자신", "등의",
        "정도", "가능성", "직장", "고객", "활용", "전반적", "전반적인"
    }

    weighted = []
    preferred = ["시스템", "데이터", "분석", "설계", "기획", "문제해결", "의사소통", "기술", "관리", "정확", "서비스", "연구"]
    for token in candidates:
        token = token.strip()
        token = re.sub(r"[^A-Za-z가-힣]", "", token)
        if len(token) < 2:
            continue
        if token.lower() in {"nan"} or token in stopwords:
            continue
        weighted.append(token)

    counts = Counter(weighted)
    ordered = []
    for pref in preferred:
        for word, _ in counts.most_common(limit * 3):
            if pref in word and word not in ordered:
                ordered.append(word)
                break
    for word, _ in counts.most_common(limit * 3):
        if word not in ordered:
            ordered.append(word)
        if len(ordered) >= limit:
            break
    return ordered[:limit]

def build_timeline(row):
    summary_lines = split_items(row.get("summary"))
    prepare_lines = split_items(row.get("prepareway"))
    training_lines = split_items(row.get("training"))
    empway_lines = split_items(row.get("empway"))
    cert_lines = split_items(row.get("certification"))

    sources = [
        ("직무 이해", summary_lines[0] if summary_lines else ""),
        ("진입 준비", prepare_lines[0] if prepare_lines else ""),
        ("훈련·실무", training_lines[0] if training_lines else ""),
        ("확장 경로", empway_lines[0] if empway_lines else (cert_lines[0] if cert_lines else "")),
    ]

    fallback = [
        "직무의 핵심 역할과 업무 맥락을 파악합니다.",
        "학력·전공·기초 준비 요소를 확인합니다.",
        "현장 훈련 또는 실무 적응 과정을 거칩니다.",
        "자격과 경험을 넓혀 전문성을 확장합니다.",
    ]

    items = []
    for idx, (title, text) in enumerate(sources):
        items.append(
            {
                "title": title,
                "text": clean_text(text) or fallback[idx],
            }
        )
    return items

def render_empty_list(items):
    if not items:
        return '<div class="empty-note">등록된 정보가 없습니다.</div>'
    return "<ul class='clean-list'>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in items) + "</ul>"

def make_search_score(row, query, base_tokens, expanded_tokens):
    if not query:
        return 0.0
    job_text = row["job_norm"]
    full_text = row["search_blob_norm"]
    score = 0.0

    if query in job_text:
        score += 120
    if query in full_text:
        score += 35

    for token in base_tokens:
        if token in job_text:
            score += 28
        elif token in full_text:
            score += 10

    for token in expanded_tokens:
        if token in full_text:
            score += 4

    ratio = SequenceMatcher(None, query, job_text).ratio()
    if ratio >= 0.45:
        score += ratio * 24

    return score

@st.cache_data
def load_and_prepare_data(file_path: str):
    df = pd.read_excel(file_path)
    df = df.copy()

    unnamed_cols = [c for c in df.columns if str(c).startswith("Unnamed")]
    if unnamed_cols:
        df = df.drop(columns=unnamed_cols)

    major_cols = [c for c in df.columns if str(c).startswith("major_")]
    contact_cols = [c for c in df.columns if str(c).startswith("contact_")]

    df["job"] = df["job"].astype(str).str.strip()
    df["summary"] = df["summary"].fillna("")
    df["similarJob"] = df["similarJob"].fillna("")
    df["major_list"] = df.apply(extract_major_list, axis=1)
    df["contact_list"] = df.apply(extract_contact_list, axis=1)
    df["similar_list"] = df["similarJob"].apply(split_items)
    df["certification_list"] = df["certification"].apply(split_items)
    df["aptitude_list"] = df["aptitude"].apply(split_items)
    df["salary_metrics"] = df["salery"].apply(parse_salary_metrics)
    df["salary_avg_value"] = df["salary_metrics"].apply(lambda x: x.get("평균") if x else None)

    salary_series = pd.to_numeric(df["salary_avg_value"], errors="coerce")
    q1 = float(salary_series.quantile(0.33)) if salary_series.notna().any() else None
    q2 = float(salary_series.quantile(0.66)) if salary_series.notna().any() else None

    def salary_band(value):
        if pd.isna(value) or value is None:
            return "미상"
        if value <= q1:
            return "하"
        if value <= q2:
            return "중"
        return "상"

    df["salary_band"] = df["salary_avg_value"].apply(salary_band)
    df["outlook_label"] = (df["employment"].fillna("") + " " + df["job_possibility"].fillna("")).apply(classify_outlook)
    df["summary_short"] = df["summary"].apply(lambda x: shorten(split_items(x)[0] if split_items(x) else x, 42))
    df["search_blob"] = df.apply(
        lambda row: " ".join([clean_text(row.get(col, "")) for col in SEARCH_COLUMNS] + row["major_list"] + row["contact_list"]),
        axis=1,
    )
    df["job_norm"] = df["job"].fillna("").astype(str).str.lower()
    df["search_blob_norm"] = df["search_blob"].fillna("").astype(str).str.lower()

    all_majors = sorted({major for majors in df["major_list"] for major in majors})
    return df, all_majors

def search_and_filter(df, query="", majors=None, salary_bands=None, outlooks=None, sort_by="관련도"):
    work = df.copy()
    majors = majors or []
    salary_bands = salary_bands or []
    outlooks = outlooks or []

    query_clean = clean_text(query).lower()
    base_tokens = tokenize(query_clean)
    expanded_tokens = expand_tokens(base_tokens)

    work["search_score"] = work.apply(
        lambda row: make_search_score(row, query_clean, base_tokens, expanded_tokens), axis=1
    )

    if query_clean:
        work = work[(work["search_score"] > 0) | (work["job_norm"].str.contains(query_clean, na=False))]

    if majors:
        work = work[work["major_list"].apply(lambda items: any(m in items for m in majors))]

    if salary_bands:
        work = work[work["salary_band"].isin(salary_bands)]

    if outlooks:
        work = work[work["outlook_label"].isin(outlooks)]

    if sort_by == "가나다순":
        work = work.sort_values(["job"], ascending=[True])
    elif sort_by == "평균임금 높은순":
        work = work.sort_values(["salary_avg_value", "job"], ascending=[False, True], na_position="last")
    else:
        work = work.sort_values(["search_score", "salary_avg_value"], ascending=[False, False], na_position="last")

    return work.reset_index(drop=True)

def outlook_badge(label):
    if label == "높음":
        return "tag green"
    if label == "낮음":
        return "tag red"
    return "tag"

def salary_badge(label):
    if label == "상":
        return "tag blue"
    if label == "하":
        return "tag red"
    return "tag"

def render_main_header(df):
    total_jobs = len(df)
    major_count = len({major for items in df["major_list"] for major in items})
    avg_salary = pd.to_numeric(df["salary_avg_value"], errors="coerce").dropna()
    avg_salary_text = f"{avg_salary.mean():.0f}만원" if not avg_salary.empty else "미제공"

    render_html(
        f"""
        <div class="hero">
            <div class="hero-kicker">Job-Explorer AI</div>
            <div class="hero-title">미래의 직업을 검색하세요</div>
            <div class="hero-sub">
                직업명, 요약, 유사직업, 적성, 전공 데이터를 함께 탐색하는 AI 기반 직업 데이터 큐레이션 웹페이지입니다.
                검색 → 필터 → 카드 탐색 → 상세 분석 순서로 바로 확인할 수 있도록 구성했습니다.
            </div>
            <div class="stats-row">
                <div class="stat-card">
                    <div class="stat-label">직업 데이터</div>
                    <div class="stat-value">{total_jobs}</div>
                    <div class="stat-sub">career_jobs.xlsx 기준 직업 수</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">관련 전공</div>
                    <div class="stat-value">{major_count}</div>
                    <div class="stat-sub">major_1~21 통합 기준</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">평균 임금 표기</div>
                    <div class="stat-value">{avg_salary_text}</div>
                    <div class="stat-sub">텍스트에서 평균값 파싱 기준</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">검색 방식</div>
                    <div class="stat-value">키워드+유사어</div>
                    <div class="stat-sub">job·summary·major 동시 탐색</div>
                </div>
            </div>
        </div>
        """
    )

def render_search_filters(all_majors):
    render_html(
        """
        <div class="search-banner">
            <div class="section-kicker">Search & Filter</div>
            <div class="section-title">검색 및 필터링</div>
            <div class="section-sub">job과 summary를 중심으로 유사 키워드까지 함께 탐색합니다.</div>
        </div>
        """
    )

    col1, col2 = st.columns([1.55, 1], gap="large")
    with col1:
        query = st.text_input(
            "직업명 또는 키워드",
            value=st.session_state.get("query_text", ""),
            placeholder="예: 컴퓨터와 관련된 일, 상담, 디자인, 환경, 기획",
        )
    with col2:
        sort_by = st.selectbox(
            "정렬",
            options=["관련도", "가나다순", "평균임금 높은순"],
            index=["관련도", "가나다순", "평균임금 높은순"].index(st.session_state.get("sort_by", "관련도")),
        )

    col3, col4, col5 = st.columns([1.45, .8, .8], gap="large")
    with col3:
        majors = st.multiselect(
            "전공별 필터",
            options=all_majors,
            default=st.session_state.get("major_filter", []),
            placeholder="관련 전공을 선택하세요",
        )
    with col4:
        salary_bands = st.multiselect(
            "임금 수준",
            options=["상", "중", "하"],
            default=st.session_state.get("salary_filter", []),
            placeholder="상/중/하",
        )
    with col5:
        outlooks = st.multiselect(
            "고용 전망",
            options=["높음", "보통", "낮음"],
            default=st.session_state.get("outlook_filter", []),
            placeholder="전망 선택",
        )

    st.session_state["query_text"] = query
    st.session_state["sort_by"] = sort_by
    st.session_state["major_filter"] = majors
    st.session_state["salary_filter"] = salary_bands
    st.session_state["outlook_filter"] = outlooks

    return query, majors, salary_bands, outlooks, sort_by

def render_result_cards(results, query, majors, salary_bands, outlooks):
    active_filters = []
    if query:
        active_filters.append(f"검색어: {query}")
    if majors:
        active_filters.append(f"전공 {len(majors)}개")
    if salary_bands:
        active_filters.append("임금 " + "/".join(salary_bands))
    if outlooks:
        active_filters.append("전망 " + "/".join(outlooks))

    render_html(
        f"""
        <div class="panel">
            <div class="panel-head">
                <div>
                    <div class="section-kicker">Result Grid</div>
                    <div class="section-title">검색 결과 카드</div>
                    <div class="section-sub">직업명, 요약, 유사 직업, 임금/전망을 빠르게 비교할 수 있습니다.</div>
                </div>
                <div class="result-count">총 {len(results)}개 직업</div>
            </div>
            <div class="filter-meta">
                {''.join(f'<span class="meta-chip">{html.escape(item)}</span>' for item in active_filters) if active_filters else '<span class="meta-chip">전체 직업 보기</span>'}
            </div>
        </div>
        """
    )

    if results.empty:
        st.info("조건에 맞는 직업이 없습니다. 검색어 또는 필터를 바꿔서 다시 확인해 주세요.")
        return

    max_cards = min(len(results), 24)
    if len(results) > max_cards:
        st.caption(f"결과가 많아 상위 {max_cards}개만 먼저 표시합니다. 검색어·필터를 더 구체화하면 범위를 좁힐 수 있습니다.")

    cols = st.columns(3, gap="large")
    for idx, (_, row) in enumerate(results.head(max_cards).iterrows()):
        with cols[idx % 3]:
            similar_tags = row["similar_list"][:3]
            salary_value = f"평균 {row['salary_avg_value']:.0f}만원" if pd.notna(row["salary_avg_value"]) else "임금 정보 미상"
            render_html(
                f"""
                <div class="card-shell">
                    <div>
                        <div class="job-title">{html.escape(row['job'])}</div>
                        <div class="job-summary">{html.escape(row['summary_short'] or '요약 정보가 없습니다.')}</div>
                        <div class="tag-row">
                            <span class="{salary_badge(row['salary_band'])}">임금 {html.escape(str(row['salary_band']))}</span>
                            <span class="{outlook_badge(row['outlook_label'])}">전망 {html.escape(row['outlook_label'])}</span>
                        </div>
                        <div class="tag-row">
                            {''.join(f'<span class="tag">{html.escape(tag)}</span>' for tag in similar_tags) if similar_tags else '<span class="tag">유사 직업 정보 없음</span>'}
                        </div>
                        <div class="mini-text">{html.escape(salary_value)}</div>
                    </div>
                </div>
                """
            )
            if st.button("상세 분석 보기", key=f"detail_{idx}_{row['job']}"):
                st.session_state["selected_job"] = row["job"]
                st.session_state["view_mode"] = "detail"
                rerun_app()

def render_detail_header(row):
    salary_metrics = row["salary_metrics"] or {}
    avg_salary = f"{salary_metrics['평균']:.0f}만원" if "평균" in salary_metrics else "미제공"
    majors = row["major_list"][:4]
    similar_tags = row["similar_list"][:4]

    render_html(
        f"""
        <div class="detail-hero">
            <div class="detail-topline">
                <div class="breadcrumb">
                    <span>직업 탐색</span><span>›</span><span>상세 분석</span><span>›</span><span>{html.escape(row['job'])}</span>
                </div>
            </div>
            <div class="detail-title">{html.escape(row['job'])}</div>
            <div class="detail-summary">{html.escape(clean_text(row['summary']) or '직업 요약 정보가 없습니다.')}</div>
            <div class="glass-row">
                <span class="meta-chip">평균 임금 {html.escape(avg_salary)}</span>
                <span class="meta-chip">고용 전망 {html.escape(row['outlook_label'])}</span>
                <span class="meta-chip">관련 전공 {len(row['major_list'])}개</span>
                <span class="meta-chip">자격 정보 {len(row['certification_list'])}개</span>
            </div>
        </div>
        """
    )

    col1, col2 = st.columns([1.1, .9], gap="large")
    with col1:
        render_html(
            f"""
            <div class="mini-card">
                <div class="mini-title">유사 직업</div>
                <div class="tag-row">
                    {''.join(f'<span class="tag">{html.escape(tag)}</span>' for tag in similar_tags) if similar_tags else '<span class="tag">등록된 유사 직업 없음</span>'}
                </div>
                <div class="mini-title" style="margin-top:10px;">관련 전공 미리보기</div>
                <div class="tag-row">
                    {''.join(f'<span class="tag blue">{html.escape(tag)}</span>' for tag in majors) if majors else '<span class="tag">등록된 전공 없음</span>'}
                </div>
            </div>
            """
        )
    with col2:
        render_html(
            f"""
            <div class="mini-card">
                <div class="mini-title">직무 핵심 포인트</div>
                <div class="mini-text">
                    적성, 준비방법, 훈련, 자격 정보를 하나의 직무 프로필로 묶어 보았습니다.
                    아래 섹션에서 진입 로드맵, 역량 키워드, 자격 정보, 관심도 데이터를 순서대로 확인할 수 있습니다.
                </div>
            </div>
            """
        )

def render_roadmap_section(row):
    steps = build_timeline(row)
    cards = []
    for idx, item in enumerate(steps, start=1):
        cards.append(
            f"""
            <div class="timeline-item">
                <div class="timeline-no">{idx}</div>
                <div class="timeline-title">{html.escape(item['title'])}</div>
                <div class="timeline-text">{html.escape(item['text'])}</div>
            </div>
            """
        )

    render_html(
        f"""
        <div class="panel">
            <div class="section-kicker">How to be</div>
            <div class="section-title">로드맵</div>
            <div class="section-sub">prepareway와 training, empway를 묶어 단계형 타임라인으로 재구성했습니다.</div>
            <div style="height:14px;"></div>
            <div class="timeline">{''.join(cards)}</div>
        </div>
        """
    )

def render_capability_section(row):
    keywords = extract_keyword_cloud(row)
    certs = row["certification_list"]
    majors = row["major_list"]
    aptitude_lines = row["aptitude_list"]

    render_html(
        f"""
        <div class="panel">
            <div class="section-kicker">Capability & Qualification</div>
            <div class="section-title">역량 및 자격</div>
            <div class="section-sub">aptitude의 핵심 어휘를 키워드 클라우드처럼 정리하고, 자격·전공을 별도로 묶었습니다.</div>
            <div style="height:16px;"></div>
            <div class="keyword-cloud">
                {''.join(f'<span class="keyword-pill">{html.escape(word)}</span>' for word in keywords) if keywords else '<div class="empty-note">추출 가능한 키워드가 없습니다.</div>'}
            </div>
            <div style="height:18px;"></div>
            <div class="two-col">
                <div class="mini-card">
                    <div class="mini-title">자격증 / 자격 요건</div>
                    {render_empty_list(certs)}
                </div>
                <div class="mini-card">
                    <div class="mini-title">관련 전공</div>
                    {render_empty_list(majors)}
                </div>
            </div>
        </div>
        """
    )

    with st.expander("적성 원문 보기", expanded=False):
        if aptitude_lines:
            for line in aptitude_lines:
                st.write(f"- {line}")
        else:
            st.caption("등록된 적성 정보가 없습니다.")

def build_gender_chart(row, metric="PCNT1"):
    col_male = f"{metric}_남자"
    col_female = f"{metric}_여자"
    values = [
        pd.to_numeric(row.get(col_male), errors="coerce"),
        pd.to_numeric(row.get(col_female), errors="coerce"),
    ]
    if pd.isna(values).all():
        return None

    chart_df = pd.DataFrame({"성별": ["남성", "여성"], "관심도": [0 if pd.isna(v) else float(v) for v in values]})
    fig = px.pie(chart_df, names="성별", values="관심도", hole=0.55)
    fig.update_traces(textinfo="label+percent", hovertemplate="%{label}: %{value}<extra></extra>")
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend_title_text="",
        height=320,
    )
    return fig

def build_age_chart(row):
    age_df = pd.DataFrame(
        {
            "연령대": ["중학생(14~16세)", "고등학생(17~19세)"],
            "PCNT1": [
                pd.to_numeric(row.get("PCNT1_중학생(14~16세 청소년)"), errors="coerce"),
                pd.to_numeric(row.get("PCNT1_고등학생(17~19세 청소년)"), errors="coerce"),
            ],
            "PCNT2": [
                pd.to_numeric(row.get("PCNT2_중학생(14~16세 청소년)"), errors="coerce"),
                pd.to_numeric(row.get("PCNT2_고등학생(17~19세 청소년)"), errors="coerce"),
            ],
        }
    )
    age_df = age_df.fillna(0)
    melted = age_df.melt(id_vars="연령대", var_name="지표", value_name="관심도")
    fig = px.bar(melted, x="연령대", y="관심도", color="지표", barmode="group")
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320, legend_title_text="")
    fig.update_traces(hovertemplate="%{x} · %{fullData.name}: %{y}<extra></extra>")
    return fig

def render_insight_section(row):
    salary_metrics = row["salary_metrics"] or {}
    salary_cards = []
    for label in ["하위 25%", "평균", "상위 25%"]:
        if label in salary_metrics:
            salary_cards.append(
                f"""
                <div class="stat-card">
                    <div class="stat-label">{html.escape(label)}</div>
                    <div class="stat-value">{salary_metrics[label]:.0f}만원</div>
                    <div class="stat-sub">salery 텍스트 파싱 기준</div>
                </div>
                """
            )
    if not salary_cards:
        salary_cards.append(
            """
            <div class="stat-card">
                <div class="stat-label">임금 정보</div>
                <div class="stat-value">미제공</div>
                <div class="stat-sub">원본 텍스트 확인 필요</div>
            </div>
            """
        )

    employment_text = clean_text(row.get("employment"))
    possibility_text = clean_text(row.get("job_possibility"))

    render_html(
        f"""
        <div class="panel">
            <div class="section-kicker">Data Insight</div>
            <div class="section-title">시장 지표 및 통계 시각화</div>
            <div class="section-sub">salery, employment, job_possibility, PCNT 데이터를 읽기 쉬운 인사이트 형태로 재구성했습니다.</div>
            <div style="height:16px;"></div>
            <div class="insight-grid">
                <div class="mini-card">
                    <div class="mini-title">시장 지표 인포그래픽</div>
                    <div class="stats-row" style="grid-template-columns:repeat(3, minmax(0,1fr)); margin-top:0;">
                        {''.join(salary_cards)}
                    </div>
                    <div style="height:14px;"></div>
                    <div class="mini-title">고용 전망</div>
                    <div class="mini-text">{html.escape(shorten(employment_text, 220) or '고용 전망 정보가 없습니다.')}</div>
                    <div style="height:12px;"></div>
                    <div class="mini-title">발전 가능성</div>
                    <div class="mini-text">{html.escape(shorten(possibility_text, 220) or '발전 가능성 정보가 없습니다.')}</div>
                </div>
                <div class="mini-card">
                    <div class="mini-title">통계 차트</div>
                    <div class="mini-text">성별 비중은 도넛 차트, 연령대 선호도는 막대 차트로 제공합니다.</div>
                </div>
            </div>
        </div>
        """
    )

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**성별 관심도 비중**")
        tab1, tab2 = st.tabs(["PCNT1", "PCNT2"])
        with tab1:
            fig = build_gender_chart(row, "PCNT1")
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.caption("PCNT1 성별 데이터가 없습니다.")
        with tab2:
            fig = build_gender_chart(row, "PCNT2")
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.caption("PCNT2 성별 데이터가 없습니다.")
    with right:
        st.markdown("**연령대별 선호도**")
        age_fig = build_age_chart(row)
        st.plotly_chart(age_fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("PCNT1/PCNT2는 원본 엑셀 컬럼명을 그대로 반영한 관심도 지표입니다.")

    with st.expander("원문 텍스트 전체 보기", expanded=False):
        st.markdown("**고용전망**")
        st.write(employment_text or "등록된 내용이 없습니다.")
        st.markdown("**발전가능성**")
        st.write(possibility_text or "등록된 내용이 없습니다.")
        st.markdown("**준비방법**")
        st.write(clean_text(row.get("prepareway")) or "등록된 내용이 없습니다.")
        st.markdown("**훈련**")
        st.write(clean_text(row.get("training")) or "등록된 내용이 없습니다.")

def render_detail_page(df):
    selected_job = st.session_state.get("selected_job")
    if not selected_job:
        st.session_state["view_mode"] = "search"
        rerun_app()

    row_df = df[df["job"] == selected_job]
    if row_df.empty:
        st.error("선택한 직업 정보를 찾을 수 없습니다.")
        return

    row = row_df.iloc[0]

    top_left, top_right = st.columns([.22, .78], gap="large")
    with top_left:
        if st.button("← 검색 결과로 돌아가기"):
            st.session_state["view_mode"] = "search"
            rerun_app()
    with top_right:
        options = df["job"].dropna().astype(str).tolist()
        current_idx = options.index(selected_job) if selected_job in options else 0
        jump_job = st.selectbox("다른 직업으로 바로 이동", options=options, index=current_idx)
        if jump_job != selected_job:
            st.session_state["selected_job"] = jump_job
            rerun_app()

    render_detail_header(row)
    render_roadmap_section(row)
    render_capability_section(row)
    render_insight_section(row)

def main():
    inject_css()

    if not DATA_FILE.exists():
        st.error(
            f"데이터 파일을 찾을 수 없습니다: {DATA_FILE.name}\n"
            "app.py와 같은 폴더에 career_jobs.xlsx를 두고 실행해 주세요."
        )
        st.stop()

    df, all_majors = load_and_prepare_data(str(DATA_FILE))

    if "view_mode" not in st.session_state:
        st.session_state["view_mode"] = "search"

    if st.session_state["view_mode"] == "detail":
        render_detail_page(df)
        return

    render_main_header(df)
    query, majors, salary_bands, outlooks, sort_by = render_search_filters(all_majors)
    results = search_and_filter(
        df,
        query=query,
        majors=majors,
        salary_bands=salary_bands,
        outlooks=outlooks,
        sort_by=sort_by,
    )
    render_result_cards(results, query, majors, salary_bands, outlooks)

if __name__ == "__main__":
    main()
