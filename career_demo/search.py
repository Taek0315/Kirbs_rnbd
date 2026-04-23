from __future__ import annotations

from pathlib import Path
import html
import json
import math
import re
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.colors import LinearSegmentedColormap


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
TOP_N = 12

st.set_page_config(
    page_title="AI 직업 탐색 리포트",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# 테마 / 스타일
# =========================================================
def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #f3f6fb;
            --panel: #ffffff;
            --panel-2: #f8fbff;
            --line: #dde6f2;
            --text: #142033;
            --muted: #5f6f86;
            --blue: #2d6cdf;
            --blue-2: #4f8df5;
            --blue-soft: #eef5ff;
            --navy: #183153;
            --mint: #19b39b;
            --orange: #f59e0b;
            --red: #ef4444;
            --shadow: 0 14px 40px rgba(16, 38, 70, 0.10);
            --radius-xl: 24px;
            --radius-lg: 18px;
            --radius-md: 14px;
            --container: 1360px;
        }

        html, body, [class*="css"], [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {
            color: var(--text) !important;
            background: var(--bg) !important;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(79,141,245,0.08), transparent 28%),
                radial-gradient(circle at top right, rgba(25,179,155,0.06), transparent 20%),
                linear-gradient(180deg, #f7faff 0%, #f3f6fb 100%) !important;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        #MainMenu,
        footer {
            visibility: hidden;
            height: 0;
        }

        .block-container {
            max-width: var(--container);
            padding-top: 1.8rem;
            padding-bottom: 3rem;
        }

        .app-shell {
            display: flex;
            flex-direction: column;
            gap: 22px;
        }

        .hero {
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, #122744 0%, #173a66 42%, #24579c 100%);
            border-radius: 30px;
            padding: 34px 34px 28px 34px;
            box-shadow: 0 18px 40px rgba(18,39,68,0.18);
            color: #ffffff !important;
        }

        .hero:before {
            content: "";
            position: absolute;
            inset: auto -60px -70px auto;
            width: 240px;
            height: 240px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.02) 60%, transparent 72%);
        }

        .hero-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.75fr);
            gap: 18px;
            align-items: stretch;
            position: relative;
            z-index: 1;
        }

        .hero-title {
            font-size: 2.05rem;
            font-weight: 900;
            line-height: 1.18;
            letter-spacing: -0.03em;
            margin: 0 0 10px 0;
            color: #ffffff !important;
        }

        .hero-sub {
            font-size: 1rem;
            line-height: 1.75;
            color: rgba(255,255,255,0.86) !important;
            margin: 0 0 18px 0;
        }

        .hero-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .hero-tag {
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.16);
            color: #ffffff;
            font-size: 0.86rem;
            font-weight: 700;
        }

        .hero-card {
            border-radius: 24px;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.14);
            padding: 22px;
            backdrop-filter: blur(10px);
            min-height: 100%;
        }

        .hero-card-kicker {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 0.78rem;
            font-weight: 800;
            color: #d8e8ff;
            letter-spacing: .06em;
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        .hero-card-title {
            font-size: 1.08rem;
            font-weight: 800;
            margin: 0 0 10px 0;
            color: #ffffff;
        }

        .hero-card-body {
            margin: 0;
            font-size: 0.93rem;
            line-height: 1.72;
            color: rgba(255,255,255,0.86);
        }

        .toolbar-wrap {
            background: rgba(255,255,255,0.76);
            border: 1px solid rgba(255,255,255,0.65);
            box-shadow: var(--shadow);
            border-radius: 22px;
            padding: 16px;
            backdrop-filter: blur(14px);
            position: sticky;
            top: 14px;
            z-index: 20;
        }

        .toolbar-title {
            margin: 0 0 10px 0;
            font-size: 1rem;
            font-weight: 800;
            color: var(--navy);
        }

        .hint-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }

        .hint-chip {
            padding: 8px 12px;
            border-radius: 999px;
            background: var(--blue-soft);
            color: var(--blue);
            font-size: .84rem;
            font-weight: 700;
            border: 1px solid #d7e7ff;
        }

        .section-title {
            font-size: 1.22rem;
            font-weight: 900;
            color: var(--navy);
            margin: 6px 0 12px 0;
            letter-spacing: -0.02em;
        }

        .panel {
            background: var(--panel);
            border-radius: 24px;
            box-shadow: var(--shadow);
            border: 1px solid rgba(223,232,244,0.9);
            padding: 20px 20px 18px 20px;
        }

        .panel-soft {
            background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
        }

        .mini-card {
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            border: 1px solid #e4edf8;
            border-radius: 18px;
            padding: 16px 16px 14px 16px;
            height: 100%;
        }

        .meta-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
        }

        .meta-label {
            font-size: 0.77rem;
            font-weight: 800;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: .05em;
            margin-bottom: 8px;
        }

        .meta-value {
            font-size: 1rem;
            font-weight: 800;
            color: var(--text);
            line-height: 1.45;
        }

        .result-list {
            display: grid;
            gap: 12px;
        }

        .result-card {
            background: #ffffff;
            border: 1px solid #e4edf8;
            border-radius: 20px;
            padding: 14px 14px 12px 14px;
            box-shadow: 0 10px 22px rgba(17, 38, 70, 0.06);
        }

        .result-rank {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: linear-gradient(135deg, #1f5fd0 0%, #4f8df5 100%);
            color: #fff;
            font-size: 0.82rem;
            font-weight: 900;
            margin-right: 8px;
            flex: 0 0 auto;
        }

        .result-title {
            font-size: 1rem;
            font-weight: 900;
            color: var(--navy);
            margin: 0;
            line-height: 1.35;
        }

        .result-desc {
            font-size: 0.91rem;
            color: #4b5b73;
            line-height: 1.7;
            margin: 8px 0 10px 0;
        }

        .score-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }

        .score-track {
            position: relative;
            flex: 1 1 auto;
            height: 8px;
            border-radius: 999px;
            background: #eaf1fb;
            overflow: hidden;
        }

        .score-fill {
            position: absolute;
            inset: 0 auto 0 0;
            background: linear-gradient(90deg, #2d6cdf 0%, #4f8df5 100%);
            border-radius: 999px;
        }

        .score-value {
            font-size: 0.83rem;
            font-weight: 900;
            color: var(--blue);
            white-space: nowrap;
        }

        .chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 7px 10px;
            border-radius: 999px;
            border: 1px solid #dfebfb;
            background: #f7fbff;
            color: #31577f;
            font-size: 0.82rem;
            font-weight: 700;
        }

        .lead-title {
            font-size: 1.68rem;
            font-weight: 900;
            color: var(--navy);
            line-height: 1.25;
            margin: 0 0 8px 0;
            letter-spacing: -0.03em;
        }

        .lead-summary {
            font-size: 1rem;
            color: #465774;
            line-height: 1.82;
            margin: 0;
        }

        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin-top: 14px;
        }

        .kpi-card {
            background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
            border: 1px solid #e2ecf8;
            border-radius: 18px;
            padding: 14px 14px 12px;
        }

        .kpi-label {
            font-size: 0.77rem;
            font-weight: 800;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: .05em;
            margin-bottom: 8px;
        }

        .kpi-value {
            font-size: 1rem;
            line-height: 1.55;
            font-weight: 900;
            color: var(--text);
        }

        .content-list {
            display: grid;
            gap: 10px;
            margin-top: 4px;
        }

        .content-item {
            border-radius: 16px;
            border: 1px solid #e5edf8;
            background: #fbfdff;
            padding: 13px 14px;
            line-height: 1.72;
            color: #344864;
            font-size: 0.95rem;
        }

        .empty-box {
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
            border: 1px dashed #cfe0f6;
            border-radius: 26px;
            padding: 40px 24px;
            text-align: center;
            box-shadow: var(--shadow);
        }

        .empty-emoji {
            font-size: 2.3rem;
            margin-bottom: 10px;
        }

        .empty-title {
            font-size: 1.3rem;
            font-weight: 900;
            color: var(--navy);
            margin: 0 0 8px 0;
        }

        .empty-sub {
            font-size: 0.98rem;
            color: #53657f;
            line-height: 1.8;
            max-width: 760px;
            margin: 0 auto;
        }

        .loading-wrap {
            display: grid;
            place-items: center;
            padding: 28px 10px 10px 10px;
        }

        .loading-card {
            width: min(720px, 100%);
            border-radius: 24px;
            padding: 26px 24px;
            background: linear-gradient(135deg, #ffffff 0%, #f5f9ff 100%);
            border: 1px solid #dfebfb;
            box-shadow: var(--shadow);
        }

        .loading-head {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 1.05rem;
            font-weight: 900;
            color: var(--navy);
            margin-bottom: 10px;
        }

        .loading-dot {
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: linear-gradient(135deg, #2d6cdf, #19b39b);
            box-shadow: 0 0 0 8px rgba(45,108,223,0.10);
            animation: pulse 1.25s infinite;
        }

        .loading-bar {
            position: relative;
            height: 10px;
            background: #eaf1fb;
            border-radius: 999px;
            overflow: hidden;
            margin: 12px 0 14px 0;
        }

        .loading-fill {
            position: absolute;
            inset: 0;
            width: 42%;
            border-radius: 999px;
            background: linear-gradient(90deg, #2d6cdf 0%, #19b39b 100%);
            animation: loadingMove 1.35s ease-in-out infinite;
        }

        .foot-note {
            font-size: .86rem;
            color: var(--muted);
            line-height: 1.7;
        }

        @keyframes pulse {
            0% { transform: scale(0.92); opacity: .78; }
            50% { transform: scale(1.08); opacity: 1; }
            100% { transform: scale(0.92); opacity: .78; }
        }

        @keyframes loadingMove {
            0% { transform: translateX(-115%); }
            50% { transform: translateX(130%); }
            100% { transform: translateX(260%); }
        }

        div[data-testid="stTextInput"] input {
            border-radius: 14px !important;
            border: 1px solid #dce8f6 !important;
            background: #ffffff !important;
            min-height: 46px;
            color: #15243a !important;
            box-shadow: none !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: #77a7ff !important;
            box-shadow: 0 0 0 4px rgba(45,108,223,0.10) !important;
        }

        div[data-testid="stButton"] > button {
            min-height: 46px;
            border-radius: 14px !important;
            border: 0 !important;
            background: linear-gradient(135deg, #1f5fd0 0%, #4f8df5 100%) !important;
            color: #ffffff !important;
            font-weight: 800 !important;
            padding: 0 18px !important;
            box-shadow: 0 12px 22px rgba(45,108,223,0.22) !important;
        }

        div[data-testid="stButton"] > button:hover {
            filter: brightness(1.03);
            transform: translateY(-1px);
        }

        div[data-testid="stSelectbox"] > div,
        div[data-testid="stMultiSelect"] > div,
        div[data-testid="stPopover"] > div {
            border-radius: 14px !important;
        }

        @media (max-width: 1100px) {
            .hero-grid,
            .meta-grid,
            .kpi-grid {
                grid-template-columns: 1fr 1fr;
            }
        }

        @media (max-width: 768px) {
            .hero-grid,
            .meta-grid,
            .kpi-grid {
                grid-template-columns: 1fr;
            }
            .hero {
                padding: 26px 22px 22px 22px;
            }
            .lead-title {
                font-size: 1.38rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# 유틸
# =========================================================
def normalize_text(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, float) and np.isnan(text):
        return ""
    text = str(text)
    text = html.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>|</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()


def normalize_key(text: Any) -> str:
    text = normalize_text(text).lower()
    text = re.sub(r"[^0-9a-zA-Z가-힣]+", "", text)
    return text


def clean_name(text: Any) -> str:
    text = normalize_text(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_lines(value: Any, max_items: int = 999) -> List[str]:
    text = normalize_text(value)
    if not text:
        return []

    raw_parts = re.split(r"\n+|[•·▪●◦]|\s*[-–—]\s+|\s{2,}|(?<=[.!?])\s+(?=[A-Z가-힣])|;", text)
    parts: List[str] = []
    seen = set()
    for part in raw_parts:
        item = re.sub(r"^\d+[.)]\s*", "", part).strip(" -\t")
        item = re.sub(r"\s+", " ", item).strip()
        if len(item) < 2:
            continue
        key = normalize_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        parts.append(item)
        if len(parts) >= max_items:
            break
    return parts


def short_text(value: Any, limit: int = 160) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        if pd.isna(value):
            return None
        return float(value)

    text = normalize_text(value).replace(",", "")
    if not text:
        return None
    nums = re.findall(r"-?\d+(?:\.\d+)?", text)
    if not nums:
        return None

    val = float(nums[0])
    if "천" in text and "만원" in text:
        val *= 1000
    elif "억" in text and "원" in text:
        val *= 10000
    return val


def format_money_krw_manwon(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "정보 없음"
    if value >= 10000:
        eok = int(value // 10000)
        rest = int(round(value % 10000))
        return f"약 {eok}억 {rest:,}만원" if rest else f"약 {eok}억원"
    return f"약 {int(round(value)):,}만원"


def ratio_to_percent(value: Any) -> Optional[float]:
    num = parse_numeric(value)
    if num is None:
        return None
    if 0 <= num <= 1:
        num *= 100
    return max(0.0, min(100.0, num))


def safe_get(row: pd.Series, col: Optional[str], default: Any = "") -> Any:
    if not col or col not in row.index:
        return default
    value = row[col]
    if pd.isna(value):
        return default
    return value


def pick_column(columns: List[str], aliases: List[str], contains: Optional[List[str]] = None) -> Optional[str]:
    normalized = {col: normalize_key(col) for col in columns}
    alias_keys = [normalize_key(a) for a in aliases]
    contains_keys = [normalize_key(a) for a in (contains or [])]

    for alias in alias_keys:
        for col, key in normalized.items():
            if key == alias:
                return col
    for alias in alias_keys:
        for col, key in normalized.items():
            if alias and alias in key:
                return col
    if contains_keys:
        for col, key in normalized.items():
            if all(token in key for token in contains_keys if token):
                return col
    return None


def collect_prefixed_columns(columns: List[str], prefixes: List[str]) -> List[str]:
    out: List[str] = []
    prefix_keys = [normalize_key(p) for p in prefixes]
    for col in columns:
        key = normalize_key(col)
        if any(key.startswith(p) for p in prefix_keys):
            out.append(col)
    return out


def build_embedding_key(jobdic_seq: Any, job: Any) -> str:
    seq = normalize_text(jobdic_seq)
    if seq:
        return f"id::{seq}"
    return f"job::{normalize_key(job)}"


def cosine_similarity_matrix(vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    denom = np.linalg.norm(vector)
    if denom == 0:
        return np.zeros(matrix.shape[0], dtype=float)
    matrix_norm = np.linalg.norm(matrix, axis=1)
    matrix_norm = np.where(matrix_norm == 0, 1e-12, matrix_norm)
    return np.dot(matrix, vector) / (matrix_norm * denom)


# =========================================================
# 데이터 로드
# =========================================================
@st.cache_data(show_spinner=False)
def load_dataframe(data_path: Path) -> pd.DataFrame:
    if not data_path.exists():
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {data_path}")
    df = pd.read_excel(data_path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_resource(show_spinner=False)
def load_embedding_assets() -> Dict[str, Any]:
    assets: Dict[str, Any] = {
        "enabled": False,
        "meta": None,
        "matrix": None,
        "config": {},
        "error": None,
        "encoder": None,
    }

    if not (EMBED_META_FILE.exists() and EMBED_ARRAY_FILE.exists()):
        return assets

    try:
        meta = pd.read_excel(EMBED_META_FILE)
        matrix = np.load(EMBED_ARRAY_FILE)
        config = {}
        if EMBED_CONFIG_FILE.exists():
            config = json.loads(EMBED_CONFIG_FILE.read_text(encoding="utf-8"))

        assets["meta"] = meta
        assets["matrix"] = matrix.astype(float)
        assets["config"] = config
        assets["enabled"] = True

        try:
            from sentence_transformers import SentenceTransformer

            model_name = config.get("model_name", "intfloat/multilingual-e5-base")
            assets["encoder"] = SentenceTransformer(model_name)
        except Exception as exc:  # noqa: BLE001
            assets["error"] = f"임베딩 인코더 로드 실패: {exc}"
        return assets
    except Exception as exc:  # noqa: BLE001
        assets["error"] = str(exc)
        assets["enabled"] = False
        return assets


def build_column_map(df: pd.DataFrame) -> Dict[str, Any]:
    cols = list(df.columns)
    job_col = pick_column(cols, ["job", "직업", "직업명", "occupation", "name"])
    summary_col = pick_column(cols, ["summary", "요약", "한줄정의", "설명", "description"])
    similar_col = pick_column(cols, ["similarJob", "similar_job", "유사직업"])
    aptitude_col = pick_column(cols, ["aptitude", "흥미", "적성", "흥미적성"])
    prepare_col = pick_column(cols, ["prepareway", "준비방법", "준비방안", "진입방법"])
    training_col = pick_column(cols, ["training", "훈련", "교육훈련", "교육"])
    salary_col = pick_column(cols, ["salery", "salary", "임금", "임금수준", "연봉"])
    employment_col = pick_column(cols, ["employment", "고용전망", "전망", "취업전망"])
    growth_col = pick_column(cols, ["job_possibility", "발전가능성", "발전전망", "경력전망"])
    route_col = pick_column(cols, ["empway", "고용", "취업경로", "진출분야"])
    cert_col = pick_column(cols, ["certification", "자격", "자격증"])
    capacity_col = pick_column(cols, ["capacity_all", "capacity", "역량", "필요역량"])
    task_col = pick_column(cols, ["capacity_1", "직무", "업무", "주요업무", "수행업무"])
    jobdic_seq_col = pick_column(cols, ["jobdicSeq", "jobdicseq", "직업사전일련번호"])

    male_cols = [c for c in cols if "남" in c or normalize_key(c).startswith("pcnt1") and "male" in normalize_key(c)]
    female_cols = [c for c in cols if "여" in c or normalize_key(c).startswith("pcnt1") and "female" in normalize_key(c)]
    age_cols = [c for c in cols if re.search(r"(10|20|30|40|50|60)대", str(c)) or re.search(r"age|연령", str(c), re.I)]

    return {
        "job": job_col,
        "summary": summary_col,
        "similar": similar_col,
        "aptitude": aptitude_col,
        "prepare": prepare_col,
        "training": training_col,
        "salary": salary_col,
        "employment": employment_col,
        "growth": growth_col,
        "route": route_col,
        "cert": cert_col,
        "capacity": capacity_col,
        "task": task_col,
        "jobdic_seq": jobdic_seq_col,
        "major_cols": collect_prefixed_columns(cols, ["major_"])
        or [c for c in cols if "전공" in str(c)],
        "contact_cols": collect_prefixed_columns(cols, ["contact_"])
        or [c for c in cols if "기관" in str(c) or "출처" in str(c)],
        "keyword_cols": collect_prefixed_columns(cols, ["keyword", "tag", "topic"]),
        "male_cols": male_cols,
        "female_cols": female_cols,
        "age_cols": age_cols,
    }


def prepare_dataframe(df: pd.DataFrame, cmap: Dict[str, Any], embed_assets: Dict[str, Any]) -> pd.DataFrame:
    out = df.copy()

    job_col = cmap["job"]
    summary_col = cmap["summary"]
    jobdic_seq_col = cmap["jobdic_seq"]

    out["_job"] = out[job_col].map(clean_name) if job_col else ""
    out["_summary"] = out[summary_col].map(normalize_text) if summary_col else ""
    out["_search_blob"] = out.apply(lambda row: build_search_blob(row, cmap), axis=1)
    out["_embedding_key"] = out.apply(
        lambda row: build_embedding_key(safe_get(row, jobdic_seq_col), safe_get(row, job_col)),
        axis=1,
    )

    meta = embed_assets.get("meta")
    if meta is not None and not meta.empty:
        meta = meta.copy()
        if "embedding_key" not in meta.columns:
            seq_col = pick_column(list(meta.columns), ["jobdicSeq", "jobdicseq", "id"])
            job_meta_col = pick_column(list(meta.columns), ["job", "직업", "name"])
            meta["embedding_key"] = meta.apply(
                lambda row: build_embedding_key(
                    safe_get(row, seq_col),
                    safe_get(row, job_meta_col),
                ),
                axis=1,
            )
        keep_cols = [c for c in meta.columns if c not in out.columns or c == "embedding_key"]
        out = out.merge(meta[keep_cols], how="left", left_on="_embedding_key", right_on="embedding_key")

    return out


def build_search_blob(row: pd.Series, cmap: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in [
        "job",
        "summary",
        "similar",
        "aptitude",
        "prepare",
        "training",
        "salary",
        "employment",
        "growth",
        "route",
        "cert",
        "capacity",
        "task",
    ]:
        parts.append(normalize_text(safe_get(row, cmap.get(key))))

    for col in cmap.get("major_cols", []) + cmap.get("contact_cols", []) + cmap.get("keyword_cols", []):
        parts.append(normalize_text(safe_get(row, col)))

    return "\n".join([p for p in parts if p]).strip()


# =========================================================
# 검색 로직
# =========================================================
STOPWORDS = {
    "직업",
    "관련",
    "하는",
    "하는일",
    "업무",
    "분야",
    "정보",
    "탐색",
    "추천",
    "알려줘",
    "찾아줘",
    "싶어",
    "되는",
    "되는법",
    "직무",
    "대한",
    "에서",
    "그리고",
}


def tokenize_query(query: str) -> List[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", query.lower())
    tokens = [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]
    return tokens


def fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


@st.cache_data(show_spinner=False)
def search_jobs_cached(
    query: str,
    df: pd.DataFrame,
    cmap: Dict[str, Any],
    semantic_scores: Optional[np.ndarray],
    top_n: int = TOP_N,
) -> pd.DataFrame:
    q = normalize_text(query)
    q_norm = q.lower()
    q_key = normalize_key(q)
    tokens = tokenize_query(q)

    if not q_key:
        return df.iloc[0:0].copy()

    records: List[Dict[str, Any]] = []
    for idx, row in df.iterrows():
        job = clean_name(row.get("_job", ""))
        summary = normalize_text(row.get("_summary", ""))
        blob = normalize_text(row.get("_search_blob", ""))
        blob_lower = blob.lower()
        job_key = normalize_key(job)

        exact = 1.0 if q_key == job_key else 0.0
        contains = 1.0 if q_norm in job.lower() else 0.0
        fuzzy_name = fuzzy_ratio(q_norm, job.lower())
        fuzzy_blob = fuzzy_ratio(q_norm, blob_lower[:600]) if blob_lower else 0.0

        token_hits = sum(1 for token in tokens if token in blob_lower)
        token_ratio = token_hits / max(len(tokens), 1)

        prefix_bonus = 0.0
        if tokens and job:
            joined = " ".join(tokens)
            if job.lower().startswith(joined):
                prefix_bonus = 0.15
            elif any(job.lower().startswith(t) for t in tokens):
                prefix_bonus = 0.08

        semantic = float(semantic_scores[idx]) if semantic_scores is not None and idx < len(semantic_scores) else 0.0
        semantic_adj = max(0.0, semantic - SEMANTIC_THRESHOLD)

        score = (
            exact * 2.8
            + contains * 1.6
            + fuzzy_name * 1.4
            + fuzzy_blob * 0.35
            + token_ratio * 2.2
            + prefix_bonus
            + semantic_adj * 2.0
        )

        if score < 0.28 and token_hits == 0 and fuzzy_name < 0.45 and semantic < SEMANTIC_THRESHOLD:
            continue

        matched_terms = [token for token in tokens if token in blob_lower]
        records.append(
            {
                "_idx": idx,
                "_score": score,
                "_semantic": semantic,
                "_token_hits": token_hits,
                "_matched_terms": matched_terms,
            }
        )

    if not records:
        return df.iloc[0:0].copy()

    score_df = pd.DataFrame(records).sort_values(["_score", "_semantic", "_token_hits"], ascending=False)
    top = score_df.head(top_n)
    merged = df.loc[top["_idx"].tolist()].copy()
    merged = merged.merge(top, left_index=True, right_on="_idx", how="left")
    merged = merged.sort_values(["_score", "_semantic", "_token_hits"], ascending=False).reset_index(drop=True)
    return merged


def compute_semantic_scores(query: str, df: pd.DataFrame, embed_assets: Dict[str, Any]) -> Optional[np.ndarray]:
    if not embed_assets.get("enabled"):
        return None
    encoder = embed_assets.get("encoder")
    matrix = embed_assets.get("matrix")
    if encoder is None or matrix is None:
        return None

    try:
        query_vector = encoder.encode([query], normalize_embeddings=bool(embed_assets.get("config", {}).get("normalize_embeddings", True)))[0]
        meta = embed_assets.get("meta")
        if meta is None or meta.empty:
            return None

        sims_meta = cosine_similarity_matrix(np.asarray(query_vector, dtype=float), np.asarray(matrix, dtype=float))
        sim_map = dict(zip(meta["embedding_key"].astype(str), sims_meta)) if "embedding_key" in meta.columns else {}
        scores = df["_embedding_key"].map(lambda x: float(sim_map.get(str(x), 0.0))).to_numpy(dtype=float)
        return scores
    except Exception:
        return None


# =========================================================
# 차트
# =========================================================
def style_matplotlib() -> None:
    plt.rcParams["font.family"] = [
        "Malgun Gothic",
        "AppleGothic",
        "NanumGothic",
        "Noto Sans CJK KR",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"


style_matplotlib()


def get_salary_distribution(df: pd.DataFrame, cmap: Dict[str, Any]) -> List[float]:
    salary_col = cmap.get("salary")
    if not salary_col:
        return []
    vals = df[salary_col].map(parse_numeric).dropna().astype(float).tolist()
    return vals


@st.cache_data(show_spinner=False)
def salary_quantiles(vals: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if not vals:
        return None, None, None
    arr = np.array(vals, dtype=float)
    return float(np.quantile(arr, 0.33)), float(np.quantile(arr, 0.66)), float(np.quantile(arr, 0.95))


def fig_gender_profile(male_pct: Optional[float], female_pct: Optional[float]):
    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=170)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.5, 0.9)
    ax.axis("off")

    ax.text(0, 0.72, "성별 분포", fontsize=14, fontweight="bold", color="#173a66")
    ax.text(0, 0.54, "해당 직업 종사자 비중", fontsize=10, color="#5f6f86")

    bg = patches.FancyBboxPatch((0, -0.02), 100, 0.24, boxstyle="round,pad=0.01,rounding_size=0.12", linewidth=0, facecolor="#edf3fb")
    ax.add_patch(bg)

    male = 0 if male_pct is None else max(0, min(100, male_pct))
    female = 100 - male if female_pct is None else max(0, min(100, female_pct))
    total = male + female
    if total > 0 and abs(total - 100) > 1:
        male = male / total * 100
        female = female / total * 100

    left_seg = patches.FancyBboxPatch((0, -0.02), male, 0.24, boxstyle="round,pad=0.01,rounding_size=0.12", linewidth=0, facecolor="#2d6cdf")
    ax.add_patch(left_seg)
    ax.add_patch(patches.Rectangle((male, -0.02), female, 0.24, linewidth=0, facecolor="#9cc4ff"))
    if female > 0:
        right_round = patches.FancyBboxPatch((100 - female, -0.02), female, 0.24, boxstyle="round,pad=0.01,rounding_size=0.12", linewidth=0, facecolor="#9cc4ff")
        ax.add_patch(right_round)

    ax.text(max(male * 0.5, 5), 0.10, f"남성 {male:.1f}%", ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    ax.text(min(male + female * 0.5, 95), 0.10, f"여성 {female:.1f}%", ha="center", va="center", color="#173a66", fontsize=10, fontweight="bold")
    return fig



def extract_age_distribution(row: pd.Series, cmap: Dict[str, Any]) -> Dict[str, float]:
    pairs: Dict[str, float] = {}
    for col in cmap.get("age_cols", []):
        label = str(col)
        val = ratio_to_percent(row.get(col))
        if val is None:
            continue

        match = re.search(r"(10|20|30|40|50|60)대", label)
        if match:
            pairs[match.group(1) + "대"] = val
            continue
        num = re.search(r"(10|20|30|40|50|60)", label)
        if num:
            pairs[num.group(1) + "대"] = val
    return dict(sorted(pairs.items(), key=lambda x: int(re.findall(r"\d+", x[0])[0])))



def fig_age_profile(age_dist: Dict[str, float]):
    if not age_dist:
        age_dist = {"정보 없음": 0}
    labels = list(age_dist.keys())
    values = list(age_dist.values())

    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=170)
    ax.set_facecolor("white")
    y = np.arange(len(labels))
    ax.barh(y, values, color="#dbeafe", height=0.5)
    ax.barh(y, values, color="#4f8df5", height=0.5, alpha=0.95)

    ax.set_title("연령대 분포", loc="left", fontsize=14, fontweight="bold", color="#173a66", pad=14)
    ax.text(0.0, 1.02, "주요 종사 연령 구간", transform=ax.transAxes, fontsize=10, color="#5f6f86")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10, color="#31445f")
    ax.set_xlim(0, max(max(values) * 1.18 if values else 10, 10))
    ax.grid(axis="x", color="#e8eef7", linewidth=1)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="x", colors="#6b7c94")
    for yi, val in zip(y, values):
        ax.text(val + max(ax.get_xlim()[1] * 0.015, 0.3), yi, f"{val:.1f}%", va="center", fontsize=10, color="#173a66", fontweight="bold")
    return fig



def fig_salary_gauge(current_value: Optional[float], q1: Optional[float], q2: Optional[float], q3: Optional[float]):
    fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=170)
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)

    ax.text(0, 0.86, "임금 수준", fontsize=14, fontweight="bold", color="#173a66")
    ax.text(0, 0.68, "전체 직업 분포 대비 대략적 위치", fontsize=10, color="#5f6f86")

    bands = [
        (0, 33.3, "하위권", "#dbeafe"),
        (33.3, 66.6, "중간권", "#93c5fd"),
        (66.6, 100, "상위권", "#2d6cdf"),
    ]
    for x0, x1, label, color in bands:
        rect = patches.FancyBboxPatch((x0, 0.22), x1 - x0, 0.18, boxstyle="round,pad=0.01,rounding_size=0.1", linewidth=0, facecolor=color)
        ax.add_patch(rect)
        ax.text((x0 + x1) / 2, 0.31, label, ha="center", va="center", fontsize=10, fontweight="bold", color="#173a66" if x1 < 100 else "white")

    if current_value is not None and all(v is not None for v in [q1, q2, q3]):
        if current_value <= q1:
            pos = (current_value / max(q1, 1e-9)) * 33.3
        elif current_value <= q2:
            pos = 33.3 + ((current_value - q1) / max(q2 - q1, 1e-9)) * 33.3
        elif current_value <= q3:
            pos = 66.6 + ((current_value - q2) / max(q3 - q2, 1e-9)) * 33.4
        else:
            pos = min(100, 90 + min((current_value - q3) / max(q3, 1e-9), 1) * 10)

        triangle = patches.RegularPolygon((pos, 0.51), 3, radius=2.4, orientation=math.pi, color="#173a66")
        ax.add_patch(triangle)
        ax.text(pos, 0.60, format_money_krw_manwon(current_value), ha="center", va="bottom", fontsize=10, fontweight="bold", color="#173a66")
    else:
        ax.text(0, 0.52, "임금 정보가 충분하지 않아 상대 위치를 계산하지 못했습니다.", fontsize=10.2, color="#5f6f86")

    return fig


# =========================================================
# UI 컴포넌트
# =========================================================
def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="hero-grid">
            <div>
              <h1 class="hero-title">AI 직업 탐색 리포트</h1>
              <p class="hero-sub">
                사용자가 입력한 직업명, 관심 키워드, 전공/역량 단서를 바탕으로 유사 직업을 탐색하고,
                직무 요약·준비 방법·자격·고용 전망까지 한 화면에서 정리해주는 탐색형 리포트입니다.
              </p>
              <div class="hero-tags">
                <span class="hero-tag">직업명 직접 검색</span>
                <span class="hero-tag">유사 직업 추천</span>
                <span class="hero-tag">전공/역량 단서 매칭</span>
                <span class="hero-tag">준비 경로 요약</span>
              </div>
            </div>
            <div class="hero-card">
              <div class="hero-card-kicker">AI Search Navigator</div>
              <h3 class="hero-card-title">이렇게 입력하면 잘 찾습니다</h3>
              <p class="hero-card-body">
                예시: <b>데이터 분석가</b>, <b>GIS 전문가</b>, <b>공간정보</b>, <b>연구직</b>, <b>환경 + 데이터</b><br/>
                직업명이 정확하지 않아도 관련 핵심어, 수행 업무, 전공 단서를 함께 입력하면 탐색 품질이 좋아집니다.
              </p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_loading() -> None:
    st.markdown(
        """
        <div class="loading-wrap">
          <div class="loading-card">
            <div class="loading-head">
              <span class="loading-dot"></span>
              <span>AI가 직업 데이터와 유사도를 종합 분석하고 있습니다.</span>
            </div>
            <div class="loading-bar"><div class="loading-fill"></div></div>
            <div class="foot-note">직업명, 설명, 전공, 역량, 준비 경로, 임베딩 유사도를 함께 반영해 결과를 구성합니다.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_empty_state() -> None:
    st.markdown(
        """
        <div class="empty-box">
          <div class="empty-emoji">🧭</div>
          <h3 class="empty-title">탐색할 직업 또는 관심 키워드를 입력해 주세요</h3>
          <p class="empty-sub">
            좌측 상단 검색창에 직업명, 관심 분야, 전공, 기술 키워드를 입력한 뒤 <b>AI 탐색 시작</b>을 누르면
            유사 직업 후보와 함께 상세 리포트가 순차적으로 나타납니다.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_result_list(results: pd.DataFrame, cmap: Dict[str, Any]) -> None:
    st.markdown('<div class="section-title">추천 직업 후보</div>', unsafe_allow_html=True)
    rows = []
    for i, (_, row) in enumerate(results.iterrows(), start=1):
        score_pct = min(98, max(18, int(round(float(row.get("_score", 0)) * 22))))
        title = clean_name(row.get("_job", "")) or "직업명 없음"
        desc = short_text(row.get("_summary", "정보가 없습니다."), 120)
        match_terms = row.get("_matched_terms", []) or []
        chips = "".join(f'<span class="chip">#{html.escape(str(t))}</span>' for t in match_terms[:4])
        rows.append(
            f"""
            <div class="result-card">
              <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                <span class="result-rank">{i}</span>
                <p class="result-title">{html.escape(title)}</p>
              </div>
              <div class="score-row">
                <div class="score-track"><div class="score-fill" style="width:{score_pct}%"></div></div>
                <div class="score-value">적합도 {score_pct}</div>
              </div>
              <p class="result-desc">{html.escape(desc)}</p>
              <div class="chip-row">{chips}</div>
            </div>
            """
        )
    st.markdown('<div class="result-list">' + "".join(rows) + "</div>", unsafe_allow_html=True)



def render_content_block(title: str, items: List[str], empty_text: str = "정보가 없습니다.") -> None:
    st.markdown(f'<div class="section-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    if not items:
        st.markdown(f'<div class="content-item">{html.escape(empty_text)}</div>', unsafe_allow_html=True)
        return
    html_items = "".join(f'<div class="content-item">{html.escape(item)}</div>' for item in items)
    st.markdown(f'<div class="content-list">{html_items}</div>', unsafe_allow_html=True)



def collect_job_keywords(row: pd.Series, cmap: Dict[str, Any], limit: int = 8) -> List[str]:
    chips: List[str] = []
    for source in [cmap.get("similar"), cmap.get("aptitude"), cmap.get("capacity"), cmap.get("task")]:
        chips.extend(split_lines(safe_get(row, source), max_items=4))
    for col in cmap.get("keyword_cols", [])[:5]:
        chips.extend(split_lines(safe_get(row, col), max_items=3))

    uniq: List[str] = []
    seen = set()
    for chip in chips:
        cleaned = re.sub(r"\s+", " ", chip).strip()
        key = normalize_key(cleaned)
        if len(cleaned) < 2 or key in seen:
            continue
        seen.add(key)
        uniq.append(cleaned)
        if len(uniq) >= limit:
            break
    return uniq



def render_job_overview(row: pd.Series, full_df: pd.DataFrame, cmap: Dict[str, Any]) -> None:
    title = clean_name(row.get("_job", "")) or "직업명 없음"
    summary = normalize_text(row.get("_summary", "")) or "직업 요약 정보가 없습니다."
    salary_value = parse_numeric(safe_get(row, cmap.get("salary")))
    growth_text = short_text(safe_get(row, cmap.get("growth"), "정보 없음"), 60)
    route_text = short_text(safe_get(row, cmap.get("route"), "정보 없음"), 60)
    cert_text = short_text(safe_get(row, cmap.get("cert"), "정보 없음"), 60)

    st.markdown(
        f"""
        <div class="panel panel-soft">
          <div class="lead-title">{html.escape(title)}</div>
          <p class="lead-summary">{html.escape(summary)}</p>
          <div class="kpi-grid">
            <div class="kpi-card">
              <div class="kpi-label">임금 수준</div>
              <div class="kpi-value">{html.escape(format_money_krw_manwon(salary_value))}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">발전 가능성</div>
              <div class="kpi-value">{html.escape(growth_text)}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">주요 진출 경로</div>
              <div class="kpi-value">{html.escape(route_text)}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">관련 자격</div>
              <div class="kpi-value">{html.escape(cert_text)}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chips = collect_job_keywords(row, cmap)
    if chips:
        html_chips = "".join(f'<span class="chip">#{html.escape(c)}</span>' for c in chips)
        st.markdown(
            f'<div class="panel" style="padding:16px 18px 14px 18px;"><div class="section-title" style="margin-top:0;">핵심 키워드</div><div class="chip-row">{html_chips}</div></div>',
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2, gap="large")

    male_pct = None
    female_pct = None
    for col in cmap.get("male_cols", []):
        male_pct = ratio_to_percent(row.get(col))
        if male_pct is not None:
            break
    for col in cmap.get("female_cols", []):
        female_pct = ratio_to_percent(row.get(col))
        if female_pct is not None:
            break

    with col1:
        st.pyplot(fig_gender_profile(male_pct, female_pct), use_container_width=True)

    age_dist = extract_age_distribution(row, cmap)
    with col2:
        st.pyplot(fig_age_profile(age_dist), use_container_width=True)

    salary_vals = get_salary_distribution(full_df, cmap)
    q1, q2, q3 = salary_quantiles(salary_vals)
    st.pyplot(fig_salary_gauge(salary_value, q1, q2, q3), use_container_width=True)



def render_detail_sections(row: pd.Series, cmap: Dict[str, Any]) -> None:
    task_items = split_lines(safe_get(row, cmap.get("task")), max_items=6)
    capacity_items = split_lines(safe_get(row, cmap.get("capacity")), max_items=8)
    aptitude_items = split_lines(safe_get(row, cmap.get("aptitude")), max_items=8)
    prepare_items = split_lines(safe_get(row, cmap.get("prepare")), max_items=8)
    training_items = split_lines(safe_get(row, cmap.get("training")), max_items=8)
    cert_items = split_lines(safe_get(row, cmap.get("cert")), max_items=8)
    route_items = split_lines(safe_get(row, cmap.get("route")), max_items=8)
    employment_items = split_lines(safe_get(row, cmap.get("employment")), max_items=8)
    growth_items = split_lines(safe_get(row, cmap.get("growth")), max_items=6)

    major_items: List[str] = []
    for col in cmap.get("major_cols", []):
        major_items.extend(split_lines(safe_get(row, col), max_items=2))
    major_items = list(dict.fromkeys(major_items))[:10]

    contact_items: List[str] = []
    for col in cmap.get("contact_cols", []):
        contact_items.extend(split_lines(safe_get(row, col), max_items=2))
    contact_items = list(dict.fromkeys(contact_items))[:10]

    left_panel_html = "".join([
        build_content_block_html("주요 수행 업무", task_items, "주요 수행 업무 정보가 없습니다."),
        build_content_block_html("필요 역량", capacity_items, "필요 역량 정보가 없습니다."),
        build_content_block_html("적성 · 흥미", aptitude_items, "적성/흥미 정보가 없습니다."),
    ])
    right_panel_html = "".join([
        build_content_block_html("준비 방법", prepare_items, "준비 방법 정보가 없습니다."),
        build_content_block_html("교육 · 훈련", training_items, "교육/훈련 정보가 없습니다."),
        build_content_block_html("관련 자격", cert_items, "관련 자격 정보가 없습니다."),
    ])
    bottom_left_html = "".join([
        build_content_block_html("진출 경로", route_items, "진출 경로 정보가 없습니다."),
        build_content_block_html("고용 전망", employment_items, "고용 전망 정보가 없습니다."),
        build_content_block_html("발전 가능성", growth_items, "발전 가능성 정보가 없습니다."),
    ])
    bottom_right_html = "".join([
        build_content_block_html("관련 전공", major_items, "관련 전공 정보가 없습니다."),
        build_content_block_html("참고 기관 · 출처", contact_items, "참고 기관/출처 정보가 없습니다."),
    ])

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(f'<div class="panel">{left_panel_html}</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="panel">{right_panel_html}</div>', unsafe_allow_html=True)

    c3, c4 = st.columns(2, gap="large")
    with c3:
        st.markdown(f'<div class="panel">{bottom_left_html}</div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="panel">{bottom_right_html}</div>', unsafe_allow_html=True)


# =========================================================
# 메인
# =========================================================
def main() -> None:
    inject_css()
    render_hero()

    try:
        raw_df = load_dataframe(DATA_FILE)
    except Exception as exc:  # noqa: BLE001
        st.error(f"데이터를 불러오지 못했습니다. {exc}")
        st.stop()

    embed_assets = load_embedding_assets()
    cmap = build_column_map(raw_df)
    df = prepare_dataframe(raw_df, cmap, embed_assets)

    if not cmap.get("job"):
        st.error("직업명 컬럼을 식별하지 못했습니다. 데이터 컬럼명을 확인해 주세요.")
        st.stop()

    with st.container():
        st.markdown('<div class="toolbar-title">탐색 입력</div>', unsafe_allow_html=True)
        search_col, btn_col = st.columns([6.5, 1.5], gap="small")
        with search_col:
            query = st.text_input(
                "직업명 또는 관심 키워드",
                value=st.session_state.get("query", ""),
                placeholder="예: GIS 전문가, 데이터 분석가, 환경 + 연구, 상담, 디자인",
                label_visibility="collapsed",
            )
        with btn_col:
            do_search = st.button("AI 탐색 시작", use_container_width=True)

        st.markdown(
            """
            <div class="hint-row">
                <span class="hint-chip">예시: 데이터 분석가</span>
                <span class="hint-chip">예시: 공간정보</span>
                <span class="hint-chip">예시: 연구직</span>
                <span class="hint-chip">예시: 환경 + 데이터</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if do_search:
        st.session_state["query"] = query
        st.session_state["searched"] = True
        st.session_state["just_searched"] = True

    searched = st.session_state.get("searched", False)
    current_query = st.session_state.get("query", query).strip()

    if not searched or not current_query:
        render_empty_state()
        return

    if st.session_state.get("just_searched", False):
        render_loading()
        time.sleep(0.8)
        st.session_state["just_searched"] = False

    semantic_scores = compute_semantic_scores(current_query, df, embed_assets)
    results = search_jobs_cached(current_query, df, cmap, semantic_scores, TOP_N)

    if results.empty:
        st.markdown(
            """
            <div class="empty-box">
              <div class="empty-emoji">🔎</div>
              <h3 class="empty-title">일치하는 직업을 찾지 못했습니다</h3>
              <p class="empty-sub">
                직업명 전체를 쓰지 않아도 됩니다. 전공, 수행 업무, 도메인 키워드처럼 더 넓은 단서로 다시 검색해 보세요.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    left, right = st.columns([0.94, 1.66], gap="large")
    options = results["_job"].fillna("").astype(str).tolist()
    if st.session_state.get("selected_job_name") not in options:
        st.session_state["selected_job_name"] = options[0]

    with left:
        st.markdown(
            f"""
            <div class="meta-grid">
              <div class="mini-card">
                <div class="meta-label">검색어</div>
                <div class="meta-value">{html.escape(current_query)}</div>
              </div>
              <div class="mini-card">
                <div class="meta-label">추천 결과</div>
                <div class="meta-value">{len(results)}건</div>
              </div>
              <div class="mini-card">
                <div class="meta-label">임베딩 검색</div>
                <div class="meta-value">{'활성' if embed_assets.get('encoder') is not None else '텍스트 기반'}</div>
              </div>
              <div class="mini-card">
                <div class="meta-label">데이터 수</div>
                <div class="meta-value">{len(df):,}건</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        selected_job_name = st.selectbox(
            "상세 보기 직업",
            options=options,
            index=options.index(st.session_state.get("selected_job_name", options[0])),
        )
        st.session_state["selected_job_name"] = selected_job_name
        render_result_list(results, cmap)

    selected_rows = results[results["_job"].astype(str) == st.session_state["selected_job_name"]]
    selected = selected_rows.iloc[0] if not selected_rows.empty else results.iloc[0]
    with right:
        render_job_overview(selected, df, cmap)
        render_detail_sections(selected, cmap)


if __name__ == "__main__":
    main()
