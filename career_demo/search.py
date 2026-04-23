from __future__ import annotations

from pathlib import Path
import html
import json
import re
import time
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# =========================================================
# 기본 설정
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "career_jobs.xlsx"

EMBEDDING_DIR = BASE_DIR / "embedding_output"
EMBED_META_FILE = EMBEDDING_DIR / "career_jobs_embedding_meta.xlsx"
EMBED_ARRAY_FILE = EMBEDDING_DIR / "career_jobs_embeddings.npy"
EMBED_CONFIG_FILE = EMBEDDING_DIR / "embedding_config.json"

SEMANTIC_THRESHOLD = 0.34
MAX_RESULT_COUNT = 12

st.set_page_config(
    page_title="AI 직업 탐색 리포트",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# 공통 유틸
# =========================================================
def is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def safe_text(value: Any, default: str = "") -> str:
    if is_missing(value):
        return default
    return str(value).strip()


def clean_text(value: Any) -> str:
    text = safe_text(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^\w\s가-힣]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def number_from_text(value: Any) -> Optional[float]:
    text = safe_text(value)
    if not text:
        return None

    text = text.replace(",", "")
    found = re.findall(r"-?\d+(?:\.\d+)?", text)
    if not found:
        return None

    try:
        return float(found[0])
    except Exception:
        return None


def escape(value: Any) -> str:
    return html.escape(safe_text(value))


def multiline_to_html(value: Any) -> str:
    text = safe_text(value)
    if not text:
        return ""

    parts = [
        p.strip(" -•·\t")
        for p in re.split(r"\n+|[|]|(?:\s*;\s*)", text)
        if p.strip(" -•·\t")
    ]

    if len(parts) >= 2:
        items = "".join(f"<li>{escape(p)}</li>" for p in parts)
        return f"<ul class='kv-list'>{items}</ul>"

    paragraph = escape(text).replace("\n", "<br>")
    return f"<p class='kv-paragraph'>{paragraph}</p>"


def split_keywords(value: Any) -> list[str]:
    text = safe_text(value)
    if not text:
        return []

    chunks = re.split(r"[,/|;\n]|(?:\s{2,})", text)
    result = []
    seen = set()

    for c in chunks:
        c = c.strip(" -•·\t")
        if not c:
            continue
        if c not in seen:
            seen.add(c)
            result.append(c)

    return result


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = normalize_text(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def find_col(columns: list[str], exact: list[str] | None = None, contains: list[str] | None = None) -> Optional[str]:
    exact = exact or []
    contains = contains or []

    lowered = {c.lower(): c for c in columns}

    for cand in exact:
        if cand.lower() in lowered:
            return lowered[cand.lower()]

    for token in contains:
        token_low = token.lower()
        for col in columns:
            if token_low in col.lower():
                return col

    return None


def get_prefixed_columns(columns: list[str], prefixes: list[str]) -> list[str]:
    result = []
    for col in columns:
        low = col.lower()
        if any(low.startswith(p.lower()) for p in prefixes):
            result.append(col)
    return result


def build_embedding_key(jobdic_seq: Any, job_name: Any) -> str:
    seq = safe_text(jobdic_seq)
    job = normalize_text(job_name)

    if seq:
        return f"id::{seq}"
    return f"job::{job}"


def format_money_like(value: Any) -> str:
    text = safe_text(value)
    if not text:
        return "정보 없음"
    return text


def select_nonempty_fields(row: pd.Series, cols: list[str]) -> list[str]:
    values = []
    for col in cols:
        val = safe_text(row.get(col, ""))
        if val:
            values.append(val)
    return values


# =========================================================
# CSS / UI 고정
# =========================================================
def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root{
            --bg: #f4f7fb;
            --panel: #ffffff;
            --panel-soft: #f8fbff;
            --line: #dbe5f1;
            --line-strong: #bfd0e4;
            --text: #0f172a;
            --muted: #667085;
            --blue: #1d4ed8;
            --blue-2: #2563eb;
            --blue-soft: #eaf2ff;
            --navy: #0b1f44;
            --shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
            --radius-xl: 24px;
            --radius-lg: 18px;
            --radius-md: 14px;
            --container: 1320px;
        }

        html, body, [class*="css"], [data-testid="stAppViewContainer"], [data-testid="stMain"] {
            background: var(--bg) !important;
            color: var(--text) !important;
            color-scheme: light !important;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(37, 99, 235, 0.08), transparent 28%),
                radial-gradient(circle at top left, rgba(14, 165, 233, 0.08), transparent 24%),
                linear-gradient(180deg, #f6f9fd 0%, #f4f7fb 100%) !important;
        }

        [data-testid="stHeader"] {
            background: transparent !important;
        }

        #MainMenu, footer, header {
            visibility: hidden !important;
        }

        [data-testid="collapsedControl"] {
            display: none !important;
        }

        .block-container {
            max-width: var(--container);
            padding-top: 1.6rem !important;
            padding-bottom: 2.8rem !important;
        }

        /* 기본 텍스트 색 고정 */
        p, li, div, span, label, h1, h2, h3, h4, h5, h6 {
            color: var(--text);
        }

        /* 위젯 강제 라이트 */
        .stTextInput > div > div > input,
        .stSelectbox > div > div,
        .stMultiSelect > div > div,
        textarea,
        input {
            background: #ffffff !important;
            color: var(--text) !important;
            border-radius: 14px !important;
        }

        .stTextInput > div > div > input {
            border: 1px solid var(--line-strong) !important;
            height: 52px !important;
            box-shadow: none !important;
        }

        .stButton > button {
            height: 52px;
            border-radius: 14px !important;
            border: 1px solid var(--blue) !important;
            background: linear-gradient(135deg, var(--blue) 0%, var(--blue-2) 100%) !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 10px 24px rgba(37, 99, 235, 0.20);
        }

        .stButton > button:hover {
            border-color: var(--blue) !important;
            background: linear-gradient(135deg, #1e40af 0%, #1d4ed8 100%) !important;
            color: #ffffff !important;
        }

        .hero {
            position: relative;
            overflow: hidden;
            background:
                radial-gradient(circle at 85% 20%, rgba(255,255,255,.25), transparent 18%),
                radial-gradient(circle at 78% 32%, rgba(255,255,255,.18), transparent 12%),
                linear-gradient(135deg, #0b1f44 0%, #14376f 35%, #1d4ed8 100%);
            border-radius: 28px;
            padding: 30px 30px 28px;
            color: #ffffff !important;
            box-shadow: 0 22px 42px rgba(13, 32, 70, 0.20);
            margin-bottom: 20px;
        }

        .hero * {
            color: #ffffff !important;
        }

        .hero-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(255,255,255,.12);
            border: 1px solid rgba(255,255,255,.18);
            font-size: 13px;
            font-weight: 700;
            letter-spacing: .2px;
            margin-bottom: 12px;
        }

        .hero-title {
            font-size: 34px;
            line-height: 1.22;
            font-weight: 900;
            letter-spacing: -0.4px;
            margin: 0 0 10px 0;
        }

        .hero-sub {
            font-size: 16px;
            line-height: 1.75;
            opacity: .95;
            max-width: 760px;
            margin: 0;
        }

        .hero-visual {
            margin-top: 18px;
            display: grid;
            grid-template-columns: 1.4fr 1fr;
            gap: 14px;
        }

        .hero-card {
            background: rgba(255,255,255,.10);
            border: 1px solid rgba(255,255,255,.16);
            backdrop-filter: blur(8px);
            border-radius: 20px;
            padding: 18px;
            min-height: 120px;
        }

        .hero-card-title {
            font-size: 14px;
            font-weight: 800;
            margin-bottom: 8px;
            opacity: .92;
        }

        .hero-card-desc {
            font-size: 14px;
            line-height: 1.7;
            opacity: .93;
        }

        .search-shell {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 18px;
            box-shadow: var(--shadow);
            margin-bottom: 18px;
        }

        .search-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 10px;
        }

        .search-title {
            font-size: 18px;
            font-weight: 800;
            color: var(--text);
            margin: 0;
        }

        .search-help {
            font-size: 13px;
            color: var(--muted);
            margin: 0;
        }

        .panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 18px;
            box-shadow: var(--shadow);
        }

        .panel-title {
            margin: 0 0 14px 0;
            font-size: 18px;
            font-weight: 800;
            letter-spacing: -0.2px;
        }

        .result-item {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 14px 14px 12px;
            margin-bottom: 12px;
            box-shadow: 0 6px 18px rgba(15,23,42,.04);
        }

        .result-rank {
            display: inline-flex;
            min-width: 28px;
            height: 28px;
            padding: 0 8px;
            border-radius: 999px;
            align-items: center;
            justify-content: center;
            background: var(--blue-soft);
            color: var(--blue) !important;
            font-size: 12px;
            font-weight: 900;
            margin-bottom: 8px;
        }

        .result-job {
            font-size: 17px;
            font-weight: 900;
            line-height: 1.35;
            margin-bottom: 6px;
        }

        .result-snippet {
            color: var(--muted);
            font-size: 13px;
            line-height: 1.65;
            margin-bottom: 10px;
        }

        .score-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            height: 28px;
            padding: 0 10px;
            border-radius: 999px;
            background: #eff6ff;
            border: 1px solid #cfe0ff;
            color: #1d4ed8 !important;
            font-size: 12px;
            font-weight: 800;
        }

        .detail-hero {
            background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
            border: 1px solid var(--line);
            border-radius: 24px;
            padding: 22px;
            box-shadow: var(--shadow);
            margin-bottom: 18px;
            animation: fadeUp .45s ease;
        }

        .detail-title {
            font-size: 30px;
            font-weight: 900;
            letter-spacing: -0.3px;
            line-height: 1.2;
            margin: 0 0 8px 0;
        }

        .detail-summary {
            font-size: 15px;
            line-height: 1.8;
            color: var(--muted);
            margin: 0;
        }

        .chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 14px;
        }

        .chip {
            display: inline-flex;
            align-items: center;
            height: 32px;
            padding: 0 12px;
            border-radius: 999px;
            background: #f6f9ff;
            border: 1px solid #d8e4ff;
            color: #2348a6 !important;
            font-size: 12px;
            font-weight: 800;
        }

        .grid-2 {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
            margin-bottom: 18px;
        }

        .info-card {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 18px;
            box-shadow: var(--shadow);
            animation: fadeUp .55s ease;
        }

        .info-title {
            font-size: 16px;
            font-weight: 900;
            line-height: 1.35;
            margin-bottom: 12px;
        }

        .kv-paragraph {
            margin: 0;
            color: var(--text);
            line-height: 1.78;
            font-size: 14px;
        }

        .kv-list {
            margin: 0;
            padding-left: 18px;
        }

        .kv-list li {
            margin: 0 0 6px 0;
            line-height: 1.72;
            font-size: 14px;
            color: var(--text);
        }

        .empty-state {
            min-height: 560px;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: fadeUp .45s ease;
        }

        .empty-shell {
            width: 100%;
            max-width: 760px;
            background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
            border: 1px solid var(--line);
            border-radius: 28px;
            box-shadow: var(--shadow);
            padding: 34px 28px;
            text-align: center;
        }

        .empty-illu {
            width: 180px;
            height: 180px;
            margin: 0 auto 20px;
            border-radius: 50%;
            background:
                radial-gradient(circle at 35% 35%, #8ec5ff 0%, #60a5fa 35%, #1d4ed8 70%, #14376f 100%);
            position: relative;
            box-shadow:
                0 26px 60px rgba(29,78,216,.18),
                inset 0 12px 28px rgba(255,255,255,.16);
        }

        .empty-illu:before,
        .empty-illu:after {
            content: "";
            position: absolute;
            border-radius: 999px;
            background: rgba(255,255,255,.28);
        }

        .empty-illu:before {
            width: 80px;
            height: 12px;
            top: 54px;
            left: 50px;
            box-shadow: 0 24px 0 rgba(255,255,255,.22), 0 48px 0 rgba(255,255,255,.18);
        }

        .empty-illu:after {
            width: 26px;
            height: 26px;
            top: 42px;
            left: 77px;
        }

        .empty-title {
            font-size: 28px;
            font-weight: 900;
            margin-bottom: 10px;
            letter-spacing: -0.3px;
        }

        .empty-desc {
            font-size: 15px;
            line-height: 1.8;
            color: var(--muted);
            margin: 0 auto 14px;
            max-width: 620px;
        }

        .hint-wrap {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 8px;
            margin-top: 10px;
        }

        .hint-chip {
            display: inline-flex;
            align-items: center;
            height: 34px;
            padding: 0 14px;
            border-radius: 999px;
            background: #f6f9ff;
            border: 1px solid #dbeafe;
            color: #1d4ed8 !important;
            font-size: 12px;
            font-weight: 800;
        }

        .loading-wrap {
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            border: 1px solid var(--line);
            border-radius: 22px;
            box-shadow: var(--shadow);
            padding: 24px;
            margin-bottom: 16px;
            animation: fadeUp .3s ease;
        }

        .loading-title {
            font-size: 18px;
            font-weight: 900;
            margin: 0 0 8px 0;
        }

        .loading-desc {
            font-size: 14px;
            color: var(--muted);
            margin: 0 0 16px 0;
        }

        .loading-bar {
            width: 100%;
            height: 10px;
            background: #e8eef8;
            border-radius: 999px;
            overflow: hidden;
            position: relative;
        }

        .loading-bar::after {
            content: "";
            position: absolute;
            left: -25%;
            top: 0;
            width: 25%;
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #60a5fa 0%, #2563eb 100%);
            animation: loadingMove 1.15s infinite ease-in-out;
        }

        @keyframes loadingMove {
            0%   { left: -25%; }
            100% { left: 100%; }
        }

        @keyframes fadeUp {
            from {
                opacity: 0;
                transform: translateY(12px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .plot-shell {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 10px 10px 0 10px;
            box-shadow: var(--shadow);
            animation: fadeUp .55s ease;
        }

        /* 이미지/차트에 환경별 필터가 걸리지 않도록 강제 해제 */
        img, svg, canvas, .js-plotly-plot, .plotly, .main-svg {
            filter: none !important;
            mix-blend-mode: normal !important;
        }

        /* 다크모드 섞임 방지 */
        [data-testid="stMarkdownContainer"] * {
            color: inherit;
        }

        @media (max-width: 980px) {
            .hero-visual {
                grid-template-columns: 1fr;
            }
            .grid-2 {
                grid-template-columns: 1fr;
            }
            .detail-title {
                font-size: 26px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# 데이터 로드
# =========================================================
@st.cache_data(show_spinner=False)
def load_job_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]

    job_col = find_col(df.columns.tolist(), exact=["job", "직업명"], contains=["job", "직업명"])
    seq_col = find_col(df.columns.tolist(), exact=["jobdicSeq", "jobdicseq"], contains=["jobdicseq"])

    if job_col is None:
        raise ValueError("직업명 컬럼(job 또는 직업명)을 찾을 수 없습니다.")

    if seq_col is None:
        df["_embed_key"] = [build_embedding_key("", j) for j in df[job_col]]
    else:
        df["_embed_key"] = [build_embedding_key(s, j) for s, j in zip(df[seq_col], df[job_col])]

    df["_job_col"] = df[job_col].astype(str)
    return df


@st.cache_data(show_spinner=False)
def load_embed_meta(path: str) -> Optional[pd.DataFrame]:
    if not Path(path).exists():
        return None

    meta = pd.read_excel(path)
    meta.columns = [str(c).strip() for c in meta.columns]

    seq_col = find_col(meta.columns.tolist(), exact=["jobdicSeq", "jobdicseq"], contains=["jobdicseq"])
    job_col = find_col(meta.columns.tolist(), exact=["job", "직업명"], contains=["job", "직업명"])

    if job_col is None:
        return None

    if seq_col is None:
        meta["_embed_key"] = [build_embedding_key("", j) for j in meta[job_col]]
    else:
        meta["_embed_key"] = [build_embedding_key(s, j) for s, j in zip(meta[seq_col], meta[job_col])]

    return meta


@st.cache_data(show_spinner=False)
def load_embedding_assets() -> dict[str, Any] | None:
    if not EMBED_META_FILE.exists() or not EMBED_ARRAY_FILE.exists():
        return None

    meta = load_embed_meta(str(EMBED_META_FILE))
    if meta is None:
        return None

    try:
        arr = np.load(EMBED_ARRAY_FILE)
    except Exception:
        return None

    config = {}
    if EMBED_CONFIG_FILE.exists():
        try:
            with open(EMBED_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {}

    if len(meta) != len(arr):
        return None

    return {
        "meta": meta,
        "arr": arr.astype(np.float32),
        "model_name": config.get("model_name", "intfloat/multilingual-e5-base"),
        "normalize_embeddings": bool(config.get("normalize_embeddings", True)),
    }


@st.cache_resource(show_spinner=False)
def load_sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name)
    except Exception:
        return None


# =========================================================
# 검색용 전처리
# =========================================================
def collect_major_columns(columns: list[str]) -> list[str]:
    return [c for c in columns if c.lower().startswith("major_")]


def collect_contact_columns(columns: list[str]) -> list[str]:
    return [c for c in columns if c.lower().startswith("contact_")]


def collect_capacity_columns(columns: list[str]) -> list[str]:
    result = []
    for c in columns:
        low = c.lower()
        if low.startswith("capacity_") or "역량" in c:
            result.append(c)
    return result


def build_search_corpus(row: pd.Series, columns: list[str]) -> str:
    chunks = []

    core_cols = [
        find_col(columns, exact=["job", "직업명"], contains=["job", "직업명"]),
        find_col(columns, exact=["summary", "요약"], contains=["summary", "요약"]),
        find_col(columns, exact=["similarJob"], contains=["similarjob", "유사직업"]),
        find_col(columns, exact=["aptitude"], contains=["aptitude", "적성", "흥미"]),
        find_col(columns, exact=["prepareway"], contains=["prepareway", "준비"]),
        find_col(columns, exact=["training"], contains=["training", "훈련"]),
        find_col(columns, exact=["employment"], contains=["employment", "고용전망", "전망"]),
        find_col(columns, exact=["job_possibility"], contains=["job_possibility", "발전가능성"]),
        find_col(columns, exact=["certification"], contains=["certification", "자격"]),
    ]

    for col in core_cols:
        if col:
            chunks.append(safe_text(row.get(col, "")))

    for col in collect_major_columns(columns):
        chunks.append(safe_text(row.get(col, "")))

    for col in collect_capacity_columns(columns):
        chunks.append(safe_text(row.get(col, "")))

    return normalize_text(" ".join(chunks))


def keyword_score(query: str, corpus: str, job_name: str) -> float:
    query_n = normalize_text(query)
    job_n = normalize_text(job_name)

    if not query_n:
        return 0.0

    tokens = [t for t in query_n.split() if t]
    if not tokens:
        return 0.0

    score = 0.0

    # 직업명 일치 우선
    if query_n == job_n:
        score += 10.0
    elif query_n in job_n:
        score += 7.5
    else:
        ratio = SequenceMatcher(None, query_n, job_n).ratio()
        score += ratio * 4.0

    # 토큰 포함
    for t in tokens:
        if t in corpus:
            score += 1.5
        if t in job_n:
            score += 2.0

    # 전체 코퍼스 유사도
    corpus_ratio = SequenceMatcher(None, query_n, corpus[:500]).ratio()
    score += corpus_ratio * 2.0

    return score


def semantic_search_scores(query: str, df: pd.DataFrame, embed_assets: dict[str, Any] | None) -> dict[str, float]:
    if not query.strip():
        return {}

    if embed_assets is None:
        return {}

    model = load_sentence_transformer(embed_assets["model_name"])
    if model is None:
        return {}

    try:
        prefix_query = f"query: {query}"
        q_vec = model.encode([prefix_query], normalize_embeddings=embed_assets["normalize_embeddings"])[0].astype(np.float32)
    except Exception:
        return {}

    arr = embed_assets["arr"]
    meta = embed_assets["meta"]

    try:
        sims = arr @ q_vec
    except Exception:
        return {}

    result = {}
    for idx, row in meta.iterrows():
        key = row["_embed_key"]
        result[key] = float(sims[idx])

    return result


def search_jobs(df: pd.DataFrame, query: str, embed_assets: dict[str, Any] | None = None) -> pd.DataFrame:
    columns = df.columns.tolist()
    job_col = find_col(columns, exact=["job", "직업명"], contains=["job", "직업명"])
    summary_col = find_col(columns, exact=["summary", "요약"], contains=["summary", "요약"])

    semantic_scores = semantic_search_scores(query, df, embed_assets)

    rows = []
    for _, row in df.iterrows():
        job_name = safe_text(row.get(job_col, "")) if job_col else ""
        summary = safe_text(row.get(summary_col, "")) if summary_col else ""
        corpus = build_search_corpus(row, columns)

        kw = keyword_score(query, corpus, job_name)
        sem = semantic_scores.get(row["_embed_key"], 0.0)

        final_score = kw
        if sem >= SEMANTIC_THRESHOLD:
            final_score += sem * 8.0

        if final_score <= 0:
            continue

        snippet = summary
        if not snippet:
            snippet = safe_text(row.get(find_col(columns, exact=["employment"], contains=["employment", "전망"]), ""))

        rows.append(
            {
                "score": final_score,
                "semantic": sem,
                "job_name": job_name,
                "snippet": snippet,
                "_row": row,
            }
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    result = result.sort_values(["score", "semantic", "job_name"], ascending=[False, False, True]).head(MAX_RESULT_COUNT)
    result = result.reset_index(drop=True)
    return result


# =========================================================
# 분포 데이터 추출
# =========================================================
def extract_percent_distribution(row: pd.Series, label_keywords: list[str]) -> dict[str, float]:
    groups: dict[str, dict[str, float]] = defaultdict(dict)

    for col in row.index:
        value = row[col]
        if is_missing(value):
            continue

        col_s = str(col).strip()
        if not any(k in col_s for k in label_keywords):
            continue

        m = re.match(r"(?i)(p?cnt)(\d+)_(.+)", col_s)
        if m:
            part = m.group(2)
            label = m.group(3).strip()
            num = number_from_text(value)
            if num is not None:
                groups[label][part] = num
            continue

        # 일반 단일 퍼센트 컬럼
        num = number_from_text(value)
        if num is not None:
            groups[col_s][ "single" ] = num

    result = {}
    for label, parts in groups.items():
        if "1" in parts and "2" in parts:
            base = parts["1"]
            frac = parts["2"]
            if 0 <= frac < 100:
                result[label] = float(base) + float(frac) / 100.0
            else:
                result[label] = float(base) + float(frac)
        elif "single" in parts:
            result[label] = float(parts["single"])
        else:
            result[label] = float(sum(parts.values()))

    # 라벨 정리
    cleaned = {}
    for label, val in result.items():
        label2 = re.sub(r"^(PCNT|PNT)\d+_", "", label, flags=re.I).strip()
        label2 = re.sub(r"\s+", " ", label2)
        cleaned[label2] = val

    return cleaned


def extract_gender_distribution(row: pd.Series) -> dict[str, float]:
    raw = extract_percent_distribution(row, ["남자", "여자", "남성", "여성"])

    result = {}
    for k, v in raw.items():
        if "남" in k:
            result["남성"] = v
        elif "여" in k:
            result["여성"] = v

    return result


def extract_age_distribution(row: pd.Series) -> dict[str, float]:
    age_tokens = ["10대", "20대", "30대", "40대", "50대", "60대", "70대", "이하", "이상"]
    raw = extract_percent_distribution(row, age_tokens)

    result = {}
    order = ["10대이하", "10대", "20대", "30대", "40대", "50대", "60대", "70대이상", "70대"]

    for key in raw:
        cleaned = key.replace(" ", "")
        cleaned = cleaned.replace("대이하", "대이하").replace("대이상", "대이상")
        result[cleaned] = raw[key]

    ordered = {}
    for k in order:
        if k in result:
            ordered[k] = result[k]

    for k, v in result.items():
        if k not in ordered:
            ordered[k] = v

    return ordered


# =========================================================
# 차트
# =========================================================
def apply_plotly_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title={
            "text": title,
            "x": 0.02,
            "xanchor": "left",
            "font": {"size": 18, "color": "#0f172a"},
        },
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"family": "Pretendard, Apple SD Gothic Neo, Malgun Gothic, sans-serif", "color": "#0f172a"},
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return fig


def build_gender_chart(data: dict[str, float]) -> Optional[go.Figure]:
    if not data:
        return None

    labels = list(data.keys())
    values = list(data.values())

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.52,
                sort=False,
                marker={"colors": ["#2563eb", "#93c5fd"][: len(labels)], "line": {"color": "#ffffff", "width": 2}},
                textinfo="label+percent",
                textfont={"size": 13, "color": "#0f172a"},
            )
        ]
    )
    fig = apply_plotly_layout(fig, "성별 분포")
    return fig


def build_age_chart(data: dict[str, float]) -> Optional[go.Figure]:
    if not data:
        return None

    labels = list(data.keys())
    values = list(data.values())

    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color="#2563eb",
                text=[f"{v:.1f}%" for v in values],
                textposition="outside",
            )
        ]
    )
    fig.update_xaxes(showgrid=False, tickangle=0, linecolor="#dbe5f1")
    fig.update_yaxes(showgrid=True, gridcolor="#eef3fa", zeroline=False, ticksuffix="%")
    fig = apply_plotly_layout(fig, "연령 분포")
    return fig


# =========================================================
# 렌더링
# =========================================================
def render_hero() -> None:
    st.markdown(
        """
        <section class="hero">
            <div class="hero-badge">🔎 AI 기반 직업 정보 탐색</div>
            <h1 class="hero-title">검색 환경이 달라도 동일하게 보이는<br>안정형 직업 탐색 리포트</h1>
            <p class="hero-sub">
                서버 배포 환경과 로컬 Streamlit 환경에서 색상·배경·차트·비주얼이 달라지는 문제를 줄이기 위해
                전체 UI를 라이트 테마 기준으로 고정하고, 모든 핵심 스타일을 코드에서 직접 지정한 버전입니다.
            </p>

            <div class="hero-visual">
                <div class="hero-card">
                    <div class="hero-card-title">탐색 포인트</div>
                    <div class="hero-card-desc">
                        직업명, 요약, 준비 방법, 관련 전공, 자격, 역량, 고용전망, 유사직업까지 한 번에 정리합니다.
                    </div>
                </div>
                <div class="hero-card">
                    <div class="hero-card-title">표시 안정화</div>
                    <div class="hero-card-desc">
                        Streamlit 기본 테마 의존을 줄이고, Plotly 배경과 글자색도 명시적으로 고정하여 환경 차이를 최소화했습니다.
                    </div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_loading() -> None:
    placeholder = st.empty()
    placeholder.markdown(
        """
        <div class="loading-wrap">
            <div class="loading-title">AI 탐색을 진행하고 있습니다.</div>
            <div class="loading-desc">직업명, 설명, 전공, 역량, 전망 정보를 바탕으로 결과를 정리하는 중입니다.</div>
            <div class="loading-bar"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(0.8)
    placeholder.empty()


def render_search_box() -> tuple[bool, str]:
    st.markdown(
        """
        <div class="search-shell">
            <div class="search-head">
                <div>
                    <h3 class="search-title">직업 검색</h3>
                    <p class="search-help">예: 데이터 분석가, GIS, 심리상담, 반도체, 디자인, 교육기획</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("job_search_form", clear_on_submit=False):
        q_col, b_col = st.columns([5.2, 1.2])
        with q_col:
            query = st.text_input(
                "검색어",
                value=st.session_state.get("active_query", ""),
                placeholder="찾고 싶은 직업명 또는 키워드를 입력하세요.",
                label_visibility="collapsed",
            )
        with b_col:
            submitted = st.form_submit_button("AI 탐색 시작")

    return submitted, query.strip()


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="empty-state">
            <div class="empty-shell">
                <div class="empty-illu"></div>
                <div class="empty-title">직업 탐색을 시작해 주세요.</div>
                <p class="empty-desc">
                    검색어를 입력하면 관련 직업을 우선순위로 정리하고,
                    선택한 직업의 핵심 정보·준비 방법·전망·관련 전공·역량 정보를 오른쪽에 표시합니다.
                </p>
                <div class="hint-wrap">
                    <span class="hint-chip">데이터 분석가</span>
                    <span class="hint-chip">상담심리사</span>
                    <span class="hint-chip">GIS 전문가</span>
                    <span class="hint-chip">UX 디자이너</span>
                    <span class="hint-chip">반도체 공정 엔지니어</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result_list(results: pd.DataFrame) -> None:
    st.markdown("<div class='panel'><h3 class='panel-title'>검색 결과</h3>", unsafe_allow_html=True)

    if results.empty:
        st.info("검색 결과가 없습니다. 다른 키워드로 다시 시도해 주세요.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for i, row in results.iterrows():
        score_label = f"적합도 {row['score']:.2f}"
        job_name = row["job_name"]
        snippet = safe_text(row["snippet"])[:130]
        if len(safe_text(row["snippet"])) > 130:
            snippet += "…"

        st.markdown(
            f"""
            <div class="result-item">
                <div class="result-rank">#{i+1}</div>
                <div class="result-job">{escape(job_name)}</div>
                <div class="result-snippet">{escape(snippet)}</div>
                <span class="score-badge">{escape(score_label)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(f"{job_name} 보기", key=f"pick_job_{i}", use_container_width=True):
            st.session_state["selected_embed_key"] = row["_row"]["_embed_key"]

    st.markdown("</div>", unsafe_allow_html=True)


def info_card(title: str, body_html: str) -> None:
    st.markdown(
        f"""
        <div class="info-card">
            <div class="info-title">{escape(title)}</div>
            {body_html if body_html else "<p class='kv-paragraph'>정보 없음</p>"}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_detail(row: pd.Series, columns: list[str]) -> None:
    job_col = find_col(columns, exact=["job", "직업명"], contains=["job", "직업명"])
    summary_col = find_col(columns, exact=["summary", "요약"], contains=["summary", "요약"])
    similar_col = find_col(columns, exact=["similarJob"], contains=["similarjob", "유사직업"])
    aptitude_col = find_col(columns, exact=["aptitude"], contains=["aptitude", "적성", "흥미"])
    prepare_col = find_col(columns, exact=["prepareway"], contains=["prepareway", "준비"])
    training_col = find_col(columns, exact=["training"], contains=["training", "훈련"])
    salary_col = find_col(columns, exact=["salery", "salary"], contains=["salery", "salary", "임금"])
    employ_col = find_col(columns, exact=["employment"], contains=["employment", "고용전망", "전망"])
    possibility_col = find_col(columns, exact=["job_possibility"], contains=["job_possibility", "발전가능성"])
    empway_col = find_col(columns, exact=["empway"], contains=["empway", "취업", "고용"])
    cert_col = find_col(columns, exact=["certification"], contains=["certification", "자격"])

    major_cols = collect_major_columns(columns)
    contact_cols = collect_contact_columns(columns)
    capacity_cols = collect_capacity_columns(columns)

    title = safe_text(row.get(job_col, "직업 정보")) if job_col else "직업 정보"
    summary = safe_text(row.get(summary_col, "")) if summary_col else ""

    chips = []
    for source in [
        safe_text(row.get(similar_col, "")) if similar_col else "",
        safe_text(row.get(aptitude_col, "")) if aptitude_col else "",
    ]:
        chips.extend(split_keywords(source))

    for val in select_nonempty_fields(row, major_cols[:3]):
        chips.extend(split_keywords(val))

    chips = dedupe_keep_order(chips)[:10]

    st.markdown(
        f"""
        <div class="detail-hero">
            <div class="detail-title">{escape(title)}</div>
            <p class="detail-summary">{escape(summary) if summary else "요약 정보가 없습니다."}</p>
            <div class="chip-row">
                {''.join(f"<span class='chip'>{escape(c)}</span>" for c in chips) if chips else "<span class='chip'>직업 정보</span>"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2열 카드
    st.markdown("<div class='grid-2'>", unsafe_allow_html=True)
    info_card("AI 한 줄 정의", multiline_to_html(summary))
    info_card("유사 직업", multiline_to_html(row.get(similar_col, "")))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='grid-2'>", unsafe_allow_html=True)
    info_card("적성 / 흥미", multiline_to_html(row.get(aptitude_col, "")))
    info_card("준비 방법", multiline_to_html(row.get(prepare_col, "")))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='grid-2'>", unsafe_allow_html=True)
    info_card("훈련 / 교육", multiline_to_html(row.get(training_col, "")))
    info_card("자격 / 인증", multiline_to_html(row.get(cert_col, "")))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='grid-2'>", unsafe_allow_html=True)
    info_card("임금 수준", multiline_to_html(format_money_like(row.get(salary_col, ""))))
    info_card("고용 / 진입 경로", multiline_to_html(row.get(empway_col, "")))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='grid-2'>", unsafe_allow_html=True)
    info_card("고용 전망", multiline_to_html(row.get(employ_col, "")))
    info_card("발전 가능성", multiline_to_html(row.get(possibility_col, "")))
    st.markdown("</div>", unsafe_allow_html=True)

    major_values = dedupe_keep_order(select_nonempty_fields(row, major_cols))
    capacity_values = dedupe_keep_order(select_nonempty_fields(row, capacity_cols))
    contact_values = dedupe_keep_order(select_nonempty_fields(row, contact_cols))

    st.markdown("<div class='grid-2'>", unsafe_allow_html=True)
    info_card("관련 전공", multiline_to_html(" / ".join(major_values[:12])))
    info_card("핵심 역량", multiline_to_html(" / ".join(capacity_values[:12])))
    st.markdown("</div>", unsafe_allow_html=True)

    if contact_values:
        info_card("참고 / 연락 정보", multiline_to_html(" / ".join(contact_values[:15])))

    # 차트
    gender_data = extract_gender_distribution(row)
    age_data = extract_age_distribution(row)

    gender_fig = build_gender_chart(gender_data)
    age_fig = build_age_chart(age_data)

    if gender_fig or age_fig:
        st.markdown("<div class='grid-2'>", unsafe_allow_html=True)
        if gender_fig:
            with st.container():
                st.markdown("<div class='plot-shell'>", unsafe_allow_html=True)
                st.plotly_chart(gender_fig, use_container_width=True, config={"displayModeBar": False})
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.empty()

        if age_fig:
            with st.container():
                st.markdown("<div class='plot-shell'>", unsafe_allow_html=True)
                st.plotly_chart(age_fig, use_container_width=True, config={"displayModeBar": False})
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.empty()
        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# 메인
# =========================================================
def main() -> None:
    inject_css()
    render_hero()

    if not DATA_FILE.exists():
        st.error(f"데이터 파일이 없습니다: {DATA_FILE}")
        return

    try:
        df = load_job_data(str(DATA_FILE))
    except Exception as e:
        st.error(f"직업 데이터 로드 중 오류가 발생했습니다: {e}")
        return

    embed_assets = load_embedding_assets()

    if "active_query" not in st.session_state:
        st.session_state["active_query"] = ""
    if "selected_embed_key" not in st.session_state:
        st.session_state["selected_embed_key"] = None
    if "search_results_cache" not in st.session_state:
        st.session_state["search_results_cache"] = None

    submitted, query = render_search_box()

    if submitted:
        st.session_state["active_query"] = query
        if query:
            render_loading()
            results = search_jobs(df, query, embed_assets)
            st.session_state["search_results_cache"] = results
            if not results.empty:
                st.session_state["selected_embed_key"] = results.iloc[0]["_row"]["_embed_key"]
            else:
                st.session_state["selected_embed_key"] = None
        else:
            st.session_state["search_results_cache"] = None
            st.session_state["selected_embed_key"] = None

    results = st.session_state.get("search_results_cache", None)

    left, right = st.columns([0.95, 1.65], gap="large")

    with left:
        if results is None:
            st.markdown("<div class='panel'><h3 class='panel-title'>검색 결과</h3><p class='kv-paragraph'>아직 검색이 실행되지 않았습니다.</p></div>", unsafe_allow_html=True)
        else:
            render_result_list(results)

    with right:
        if results is None:
            render_empty_state()
        elif results.empty:
            st.markdown(
                """
                <div class="empty-state">
                    <div class="empty-shell">
                        <div class="empty-illu"></div>
                        <div class="empty-title">검색 결과가 없습니다.</div>
                        <p class="empty-desc">
                            다른 표현이나 더 넓은 키워드로 다시 검색해 주세요.
                            예를 들어 직업명 대신 산업, 기술, 역할 키워드로 입력하면 결과가 더 잘 나올 수 있습니다.
                        </p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            selected_key = st.session_state.get("selected_embed_key")

            picked_row = None
            for _, r in results.iterrows():
                if r["_row"]["_embed_key"] == selected_key:
                    picked_row = r["_row"]
                    break

            if picked_row is None:
                picked_row = results.iloc[0]["_row"]

            render_detail(picked_row, df.columns.tolist())


if __name__ == "__main__":
    main()