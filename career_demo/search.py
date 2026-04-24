from __future__ import annotations

from pathlib import Path
import html
import time
import re
import json
import textwrap
from collections import Counter
from difflib import SequenceMatcher
from math import ceil

import numpy as np
import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "career_jobs.xlsx"
EMBEDDING_DIR = BASE_DIR / "embedding_output"
EMBED_META_FILE = EMBEDDING_DIR / "career_jobs_embedding_meta.xlsx"
EMBED_ARRAY_FILE = EMBEDDING_DIR / "career_jobs_embeddings.npy"
EMBED_CONFIG_FILE = EMBEDDING_DIR / "embedding_config.json"
SEMANTIC_THRESHOLD = 0.34

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
    "capacity_1",
    "capacity_all",
]

KOREAN_STOPWORDS = {
    "관련", "직업", "직무", "일", "일을", "하는", "대한", "및", "에서", "으로", "위한", "위해",
    "같은", "있는", "되는", "분야", "업무", "사람", "경우", "통한", "기반", "탐색", "분석",
    "미래", "검색", "관련된", "중심", "한다", "수행", "업무를", "업무에", "직업명", "정보",
    "문장", "처럼", "원하는", "분위기", "직업을", "직업의", "하고", "하면서",
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


def split_job_names(text) -> list[str]:
    if is_missing_like(text):
        return []

    text = normalize_whitespace(str(text))
    if not text:
        return []

    text = re.sub(r"\s*(?:\n|;|/|\||,|，)\s*", "\n", text)
    parts: list[str] = []
    for part in text.split("\n"):
        part = re.sub(r"^\d+[.)]\s*", "", clean_sentence(part))
        if part:
            parts.append(part)
    return unique_keep_order(parts)


def split_sentences(text) -> list[str]:
    if is_missing_like(text):
        return []

    text = normalize_whitespace(str(text))
    if not text:
        return []

    text = re.sub(r"([.!?])\s+", r"\1\n", text)
    text = re.sub(r"(다\.)\s*", r"\1\n", text)
    text = re.sub(r"(요\.)\s*", r"\1\n", text)
    text = re.sub(r"(함\.)\s*", r"\1\n", text)
    text = re.sub(r"(됨\.)\s*", r"\1\n", text)

    sentences: list[str] = []
    for part in re.split(r"\n+", text):
        part = clean_sentence(part)
        if part:
            sentences.append(part)
    return unique_keep_order(sentences)


def summarize_long_text(text, max_points: int = 4, max_chars: int = 118) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        sentences = split_lines(text)

    if not sentences:
        return []

    keywords = ["전망", "증가", "감소", "수요", "시장", "고용", "확대", "축소", "유망", "전환", "성장"]
    scored: list[tuple[float, int, str]] = []
    for idx, sentence in enumerate(sentences):
        score = 0.0
        if idx == 0:
            score += 6.0
        score += sum(keyword in sentence for keyword in keywords) * 1.8
        if 24 <= len(sentence) <= 120:
            score += 1.5
        elif len(sentence) <= 160:
            score += 0.7
        score -= idx * 0.12
        scored.append((score, idx, shorten_text(sentence, max_chars)))

    top = sorted(scored, key=lambda x: (-x[0], x[1]))[:max_points]
    top = sorted(top, key=lambda x: x[1])
    return unique_keep_order([sentence for _, _, sentence in top])


def format_sentences_as_paragraphs(text) -> str:
    sentences = split_sentences(text)
    if not sentences:
        sentences = split_lines(text)
    if not sentences:
        return ""
    return "".join(f"<p>{html.escape(sentence)}</p>" for sentence in sentences)


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


def combine_pcnt_value(integer_part, decimal_part):
    whole = safe_float(integer_part)
    decimal = safe_float(decimal_part)

    if whole is None and decimal is None:
        return None
    if whole is None:
        whole = 0.0
    if decimal is None:
        decimal = 0.0

    if decimal >= 100:
        return whole
    if decimal >= 10:
        digits = len(str(int(decimal)))
        return whole + (decimal / (10 ** digits))
    return whole + (decimal / 10)


def normalize_column_key(col) -> str:
    return re.sub(r"[^a-z0-9가-힣]", "", str(col).strip().lower())


def first_existing_numeric(row: pd.Series, columns: list[str]) -> float | None:
    for col in columns:
        if col in row.index:
            value = safe_float(row.get(col))
            if value is not None:
                return value
    return None


def find_pcnt_part_by_alias(row: pd.Series, aliases: list[str], part_no: int) -> float | None:
    alias_keys = [normalize_column_key(alias) for alias in aliases if alias]
    if not alias_keys:
        return None

    part_patterns = [f"pcnt{part_no}", f"pnt{part_no}", f"percent{part_no}", f"pct{part_no}"]

    for col in row.index:
        key = normalize_column_key(col)
        if not any(alias in key for alias in alias_keys):
            continue
        if not any(pattern in key for pattern in part_patterns):
            # PCNT_남자_1, PNT_남자_2 같은 변형 대응
            if not (("pcnt" in key or "pnt" in key or "percent" in key or "pct" in key) and key.endswith(str(part_no))):
                continue
        value = safe_float(row.get(col))
        if value is not None:
            return value
    return None


def combine_pcnt_columns(
    row: pd.Series,
    integer_columns: list[str],
    decimal_columns: list[str],
    aliases: list[str] | None = None,
) -> float:
    integer_part = first_existing_numeric(row, integer_columns)
    decimal_part = first_existing_numeric(row, decimal_columns)

    if aliases:
        if integer_part is None:
            integer_part = find_pcnt_part_by_alias(row, aliases, 1)
        if decimal_part is None:
            decimal_part = find_pcnt_part_by_alias(row, aliases, 2)

    value = combine_pcnt_value(integer_part, decimal_part)
    return 0.0 if value is None else float(value)


def clamp_percent(value: float) -> float:
    try:
        value = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(100.0, value))


def normalize_search_token(token: str) -> str:
    token = clean_sentence(token).lower()
    token = re.sub(r"[^a-z0-9가-힣]", "", token)
    suffixes = [
        "으로부터", "로부터", "에게서", "에서의", "에서는", "에서", "으로는", "으로", "에게", "와의", "과의",
        "이라면", "라면", "이라고", "라고", "처럼", "까지", "부터", "보다", "마저", "조차", "만의", "만",
        "이나", "나", "들", "적인", "적인데", "적인지", "하는", "하다", "하며", "하고", "하여", "되는",
        "같은", "관련된", "관련", "직무", "직업", "분야", "성격", "분위기", "업무", "정보",
        "와", "과", "은", "는", "이", "가", "을", "를", "의", "도"
    ]
    changed = True
    while changed and len(token) > 1:
        changed = False
        for suffix in sorted(set(suffixes), key=len, reverse=True):
            if len(token) > len(suffix) + 1 and token.endswith(suffix):
                token = token[:-len(suffix)]
                changed = True
                break
    return token.strip()


def mild_query_terms(query: str) -> list[str]:
    raw_tokens = re.findall(r"[A-Za-z가-힣0-9]{2,}", normalize_whitespace(query))
    result = []
    seen = set()
    for token in raw_tokens:
        token_clean = clean_sentence(token).lower()
        if token_clean in KOREAN_STOPWORDS:
            continue
        if token_clean not in seen:
            seen.add(token_clean)
            result.append(token_clean)
    return result


def build_embedding_key(jobdic_seq, job_name: str) -> str:
    if not is_missing_like(jobdic_seq):
        try:
            return f"id::{int(float(jobdic_seq))}"
        except Exception:
            return f"id::{clean_sentence(str(jobdic_seq))}"
    return f"job::{clean_sentence(str(job_name)).lower()}"


def parse_embedded_list(value) -> list[str]:
    if is_missing_like(value):
        return []

    if isinstance(value, list):
        return unique_keep_order([str(x) for x in value if not is_missing_like(x)])

    if isinstance(value, tuple):
        return unique_keep_order([str(x) for x in value if not is_missing_like(x)])

    text = normalize_whitespace(str(value))
    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return unique_keep_order([str(x) for x in parsed if not is_missing_like(x)])
        except Exception:
            pass

    if "|" in text:
        return unique_keep_order([clean_sentence(x) for x in text.split("|") if clean_sentence(x)])

    return unique_keep_order(split_lines(text))


@st.cache_data(show_spinner=False)
def load_embedding_assets(
    meta_path: Path = EMBED_META_FILE,
    array_path: Path = EMBED_ARRAY_FILE,
    config_path: Path = EMBED_CONFIG_FILE,
):
    if not (meta_path.exists() and array_path.exists() and config_path.exists()):
        return None

    meta = pd.read_excel(meta_path)
    embeddings = np.load(array_path)

    if len(meta) != len(embeddings):
        return None

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    for col in ["display_keywords", "display_keywords_text", "display_keywords_json"]:
        if col not in meta.columns:
            meta[col] = ""
    for col in ["llm_keywords", "llm_keywords_text", "llm_keywords_json", "card_keywords", "card_keywords_text", "card_keywords_json"]:
        if col not in meta.columns:
            meta[col] = ""
    for col in ["topic_tags", "topic_tags_text", "topic_tags_json"]:
        if col not in meta.columns:
            meta[col] = ""

    # LLM/ML로 사전 생성한 카드용 키워드가 있으면 최우선으로 사용한다.
    # 없으면 기존 display_keywords를 fallback으로 사용한다.
    meta["llm_keywords_list"] = meta.apply(
        lambda row: parse_embedded_list(
            row.get("llm_keywords_json")
            or row.get("llm_keywords_text")
            or row.get("llm_keywords")
            or row.get("card_keywords_json")
            or row.get("card_keywords_text")
            or row.get("card_keywords")
        ),
        axis=1,
    )
    meta["display_keywords_list"] = meta.apply(
        lambda row: parse_embedded_list(
            row.get("display_keywords_json") or row.get("display_keywords_text") or row.get("display_keywords")
        ),
        axis=1,
    )
    meta["topic_tags_list"] = meta.apply(
        lambda row: parse_embedded_list(
            row.get("topic_tags_json") or row.get("topic_tags_text") or row.get("topic_tags")
        ),
        axis=1,
    )

    keys = [
        build_embedding_key(row.get("jobdicSeq"), row.get("job", ""))
        for _, row in meta.iterrows()
    ]
    key_to_index = {key: idx for idx, key in enumerate(keys)}

    return {
        "meta": meta,
        "embeddings": embeddings.astype(np.float32),
        "key_to_index": key_to_index,
        "model_name": config.get("model_name", "intfloat/multilingual-e5-base"),
        "normalize_embeddings": bool(config.get("normalize_embeddings", True)),
        "config": config,
    }


@st.cache_resource(show_spinner=False)
def load_embedding_model(model_name: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name)


def compute_semantic_scores(df: pd.DataFrame, query: str) -> np.ndarray:
    if df.empty or not query.strip():
        return np.zeros(len(df), dtype=np.float32)

    assets = load_embedding_assets()
    if not assets:
        return np.zeros(len(df), dtype=np.float32)

    try:
        model = load_embedding_model(assets["model_name"])
        query_vec = model.encode(
            [f"query: {normalize_whitespace(query)}"],
            convert_to_numpy=True,
            normalize_embeddings=assets["normalize_embeddings"],
            show_progress_bar=False,
        )[0].astype(np.float32)
    except Exception:
        return np.zeros(len(df), dtype=np.float32)

    positions = []
    embedding_indices = []
    for pos, (_, row) in enumerate(df.iterrows()):
        key = build_embedding_key(row.get("jobdicSeq"), row.get("job", ""))
        idx = assets["key_to_index"].get(key)
        if idx is not None:
            positions.append(pos)
            embedding_indices.append(idx)

    scores = np.zeros(len(df), dtype=np.float32)
    if positions:
        matrix = assets["embeddings"][embedding_indices]
        scores[np.array(positions, dtype=int)] = matrix @ query_vec
    return scores


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
    return split_job_names(row.get("similarJob", ""))


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
    chunks.extend(row.get("display_keywords_list", []))
    chunks.extend(row.get("topic_tags_list", []))
    return " ".join(chunks).lower()


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

    assets = load_embedding_assets()
    if assets:
        meta = assets["meta"].copy()
        meta["embedding_key"] = meta.apply(
            lambda row: build_embedding_key(row.get("jobdicSeq"), row.get("job", "")),
            axis=1,
        )
        meta_cols = [
            "embedding_key",
            "llm_keywords_list",
            "display_keywords_list",
            "topic_tags_list",
            "llm_keywords_text",
            "display_keywords_text",
            "topic_tags_text",
        ]
        df["embedding_key"] = df.apply(
            lambda row: build_embedding_key(row.get("jobdicSeq"), row.get("job", "")),
            axis=1,
        )
        df = df.merge(meta[meta_cols], on="embedding_key", how="left")
        df.drop(columns=["embedding_key"], inplace=True)

    if "llm_keywords_list" not in df.columns:
        df["llm_keywords_list"] = [[] for _ in range(len(df))]
    else:
        df["llm_keywords_list"] = df["llm_keywords_list"].map(parse_embedded_list)

    if "display_keywords_list" not in df.columns:
        df["display_keywords_list"] = [[] for _ in range(len(df))]
    else:
        df["display_keywords_list"] = df["display_keywords_list"].map(parse_embedded_list)

    if "topic_tags_list" not in df.columns:
        df["topic_tags_list"] = [[] for _ in range(len(df))]
    else:
        df["topic_tags_list"] = df["topic_tags_list"].map(parse_embedded_list)

    return df


# -----------------------------
# Search / filter logic
# -----------------------------
def extract_display_keywords(query: str) -> list[str]:
    if not query:
        return []

    raw_tokens = re.findall(r"[A-Za-z가-힣0-9]{2,}", query.lower())
    keywords: list[str] = []
    seen = set()
    for token in raw_tokens:
        token = normalize_search_token(token)
        if not token or token in KOREAN_STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            keywords.append(token)
    return keywords


def extract_search_terms(query: str) -> list[str]:
    base_tokens = extract_display_keywords(query)
    tokens: list[str] = []
    for token in base_tokens:
        tokens.append(token)
        if token in SYNONYM_MAP:
            tokens.extend([item.lower() for item in SYNONYM_MAP[token]])

    unique_tokens: list[str] = []
    seen = set()
    for token in tokens:
        token = normalize_search_token(token)
        if not token or token in KOREAN_STOPWORDS:
            continue
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)
    return unique_tokens


def derive_brief_keywords(query: str, filtered: pd.DataFrame, limit: int = 8) -> list[str]:
    weighted = Counter()

    if not filtered.empty:
        top_n = min(8, len(filtered))
        for rank, (_, row) in enumerate(filtered.head(top_n).iterrows(), start=1):
            weight = max(1.0, 6.5 - rank)
            for keyword in row.get("display_keywords_list", [])[:8]:
                if len(keyword) <= 22:
                    weighted[keyword] += weight

    keywords = [item for item, _ in weighted.most_common(limit)]
    if keywords:
        return keywords[:limit]

    query_tokens = mild_query_terms(query)
    return query_tokens[:limit]


def extract_related_topics(filtered: pd.DataFrame, limit: int = 8) -> list[str]:
    topics = Counter()
    if filtered.empty:
        return []

    top_n = min(10, len(filtered))
    for rank, (_, row) in enumerate(filtered.head(top_n).iterrows(), start=1):
        weight = max(1.0, 7.0 - rank)
        raw_items = []
        raw_items.extend(row.get("topic_tags_list", [])[:6])
        raw_items.extend(row.get("similar_job_list", [])[:3])
        raw_items.extend(row.get("major_list", [])[:2])

        for item in raw_items:
            cleaned = clean_sentence(item)
            if cleaned and len(cleaned) <= 40:
                topics[cleaned] += weight

    return [item for item, _ in topics.most_common(limit)]


def compute_search_score(row: pd.Series, query: str, tokens: list[str]) -> float:
    if not query.strip():
        return 0.0

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
            score += 1.8

    major_joined = " ".join(row.get("major_list", [])).lower()
    for token in tokens:
        if token in major_joined:
            score += 1.8

    return score


def search_jobs(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query.strip():
        return df.iloc[0:0].copy()

    tokens = extract_search_terms(query)
    results = df.copy()
    results["search_score"] = results.apply(lambda row: compute_search_score(row, query, tokens), axis=1)

    semantic_scores = compute_semantic_scores(results, query)
    results["semantic_score"] = semantic_scores
    results["semantic_boost"] = results["semantic_score"].map(
        lambda x: max(0.0, float(x) - SEMANTIC_THRESHOLD) * 35.0
    )
    results["combined_search_score"] = results["search_score"] + results["semantic_boost"]

    results = results[
        (results["search_score"] > 0) |
        (results["semantic_score"] >= SEMANTIC_THRESHOLD)
    ]

    return results.sort_values(
        ["combined_search_score", "search_score", "semantic_score", "job"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


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
# HTML/CSS visualization helpers
# -----------------------------
def _describe_salary_band(amount: int, max_amount: int) -> tuple[str, str]:
    ratio = 0 if max_amount <= 0 else amount / max_amount
    if ratio < 0.34:
        return "진입 구간", "직업군 내 하위권 임금대입니다."
    if ratio < 0.67:
        return "중간 구간", "직업군 내 중간 수준의 임금대입니다."
    return "상위 구간", "직업군 내 비교적 높은 임금대입니다."


def build_salary_gauge(salary_amount) -> str | None:
    if salary_amount is None:
        return None

    try:
        salary_amount = int(round(float(salary_amount)))
    except Exception:
        return None

    if salary_amount <= 0:
        return None

    max_amount = max(5000, int(ceil(salary_amount / 500.0) * 500))
    ratio = clamp_percent((salary_amount / max_amount) * 100)
    band_title, band_desc = _describe_salary_band(salary_amount, max_amount)
    half_amount = max_amount // 2

    return f"""
    <div class="viz-card salary-viz-card">
        <div class="salary-band-chip">{html.escape(band_title)}</div>
        <div class="salary-viz-label">평균 임금 수준</div>
        <div class="salary-viz-value">{salary_amount:,}만원</div>
        <div class="salary-track" aria-label="평균 임금 수준">
            <div class="salary-fill" style="width:{ratio:.2f}%;"></div>
        </div>
        <div class="salary-axis">
            <span>0</span>
            <span>{half_amount:,}</span>
            <span>{max_amount:,}</span>
        </div>
        <div class="chart-note salary-note">{html.escape(band_desc)}</div>
    </div>
    """


def build_gender_chart(detail: pd.Series) -> str | None:
    male = combine_pcnt_columns(
        detail,
        ["PCNT1_남자", "PNT1_남자", "PCNT1 남자", "PNT1 남자", "PCNT1_남성", "PNT1_남성"],
        ["PCNT2_남자", "PNT2_남자", "PCNT2 남자", "PNT2 남자", "PCNT2_남성", "PNT2_남성"],
        aliases=["남자", "남성", "male"],
    )
    female = combine_pcnt_columns(
        detail,
        ["PCNT1_여자", "PNT1_여자", "PCNT1 여자", "PNT1 여자", "PCNT1_여성", "PNT1_여성"],
        ["PCNT2_여자", "PNT2_여자", "PCNT2 여자", "PNT2 여자", "PCNT2_여성", "PNT2_여성"],
        aliases=["여자", "여성", "female"],
    )

    total = male + female
    if total <= 0:
        return None

    male_pct = clamp_percent(male / total * 100)
    female_pct = clamp_percent(female / total * 100)
    male_deg = male_pct * 3.6

    return f"""
    <div class="viz-card gender-viz-card">
        <div class="donut-stage">
            <div class="donut-chart" style="background:conic-gradient(#5446e8 0deg {male_deg:.2f}deg, #2fb7cf {male_deg:.2f}deg 360deg);">
                <div class="donut-hole">
                    <div class="donut-kicker">관심도 합계</div>
                    <div class="donut-value">100%</div>
                </div>
            </div>
        </div>
        <div class="legend-grid">
            <div class="legend-item">
                <span class="legend-dot" style="background:#5446e8;"></span>
                <span class="legend-label">남성</span>
                <strong class="legend-value">{male_pct:.1f}%</strong>
            </div>
            <div class="legend-item">
                <span class="legend-dot" style="background:#2fb7cf;"></span>
                <span class="legend-label">여성</span>
                <strong class="legend-value">{female_pct:.1f}%</strong>
            </div>
        </div>
    </div>
    """


def build_age_chart(detail: pd.Series) -> str | None:
    teen = combine_pcnt_columns(
        detail,
        ["PCNT1_중학생", "PNT1_중학생", "PCNT1 중학생", "PNT1 중학생", "PCNT1_중등", "PNT1_중등"],
        ["PCNT2_중학생", "PNT2_중학생", "PCNT2 중학생", "PNT2 중학생", "PCNT2_중등", "PNT2_중등"],
        aliases=["중학생", "중등", "middle"],
    )
    high = combine_pcnt_columns(
        detail,
        ["PCNT1_고등학생", "PNT1_고등학생", "PCNT1 고등학생", "PNT1 고등학생", "PCNT1_고등", "PNT1_고등"],
        ["PCNT2_고등학생", "PNT2_고등학생", "PCNT2 고등학생", "PNT2 고등학생", "PCNT2_고등", "PNT2_고등"],
        aliases=["고등학생", "고등", "high"],
    )

    total = teen + high
    if total <= 0:
        return None

    teen_pct = clamp_percent(teen / total * 100)
    high_pct = clamp_percent(high / total * 100)

    return f"""
    <div class="viz-card age-viz-card">
        <div class="bar-chart-list">
            <div class="bar-chart-row">
                <div class="bar-chart-head">
                    <span>중학생 <em>14~16세</em></span>
                    <strong>{teen_pct:.1f}%</strong>
                </div>
                <div class="bar-track"><div class="bar-fill middle-fill" style="width:{teen_pct:.2f}%;"></div></div>
            </div>
            <div class="bar-chart-row">
                <div class="bar-chart-head">
                    <span>고등학생 <em>17~19세</em></span>
                    <strong>{high_pct:.1f}%</strong>
                </div>
                <div class="bar-track"><div class="bar-fill high-fill" style="width:{high_pct:.2f}%;"></div></div>
            </div>
        </div>
    </div>
    """


# -----------------------------
# CSS
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
            color-scheme: light !important;
        }

        html, body, [class*="css"], [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main {
            color: var(--text) !important;
            font-family: "Pretendard", "Noto Sans KR", sans-serif;
            background-color: var(--bg) !important;
            color-scheme: light !important;
        }

        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        .stAppToolbar,
        [data-testid="stStatusWidget"],
        [data-testid="stHeaderActionElements"],
        .stDeployButton,
        div[data-testid="stDecoration"]{
            display:none !important;
            visibility:hidden !important;
            height:0 !important;
        }
        #MainMenu,
        footer{
            visibility:hidden !important;
            display:none !important;
        }

        body {
            background:
                radial-gradient(circle at top right, rgba(37,99,235,.08), transparent 20%),
                linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%) !important;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(37,99,235,.08), transparent 20%),
                linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%) !important;
            color: var(--text) !important;
            color-scheme: light !important;
        }

        div[data-baseweb="input"],
        div[data-baseweb="base-input"],
        div[data-baseweb="select"],
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] *,
        input,
        textarea {
            color-scheme: light !important;
        }

        div[data-baseweb="popover"] [role="dialog"],
        div[data-baseweb="popover"] [role="listbox"],
        div[data-baseweb="select"] > div,
        ul[role="listbox"] {
            background: #ffffff !important;
            color: var(--text) !important;
            border: 1px solid var(--line) !important;
            box-shadow: 0 12px 30px rgba(15,23,42,.10) !important;
        }

        div[data-baseweb="popover"] li,
        div[data-baseweb="popover"] [role="option"],
        ul[role="listbox"] li {
            background: #ffffff !important;
            color: var(--text) !important;
        }

        div[data-baseweb="popover"] li:hover,
        div[data-baseweb="popover"] [role="option"]:hover,
        ul[role="listbox"] li:hover {
            background: #eff6ff !important;
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
        .filter-meta{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            margin-top:10px;
        }
        .meta-chip{
            display:inline-flex;
            align-items:center;
            padding:8px 12px;
            border-radius:999px;
            background:#eff6ff;
            border:1px solid #dbeafe;
            color:#1d4ed8;
            font-size:12px;
            font-weight:700;
            line-height:1.5;
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

        .search-idle{
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px dashed #cfe0ff;
            border-radius:22px;
            padding:28px 24px;
            margin-top:16px;
            margin-bottom:12px;
        }
        .search-idle-title{
            font-size:20px;
            line-height:1.4;
            font-weight:800;
            color:#102a43;
            margin-bottom:8px;
        }
        .search-idle-text{
            font-size:14px;
            line-height:1.72;
            color:#64748b;
        }

        .ai-loading-shell{
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid var(--line);
            border-radius:22px;
            padding:22px;
            box-shadow:var(--shadow);
            margin-top:18px;
            margin-bottom:20px;
        }
        .ai-loading-top{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:12px;
            flex-wrap:wrap;
            margin-bottom:12px;
        }
        .ai-loading-title{
            font-size:22px;
            line-height:1.4;
            font-weight:800;
            color:#102a43;
            margin-bottom:6px;
            letter-spacing:-0.02em;
        }
        .ai-loading-sub{
            font-size:14px;
            line-height:1.7;
            color:#64748b;
        }
        .ai-stage-box{
            background:#f8fbff;
            border:1px solid #dce8fb;
            border-radius:18px;
            padding:16px;
            margin-top:14px;
            margin-bottom:14px;
        }
        .ai-stage-label{
            font-size:12px;
            color:#2563eb;
            font-weight:800;
            letter-spacing:.08em;
            text-transform:uppercase;
            margin-bottom:8px;
        }
        .ai-stage-title{
            font-size:18px;
            line-height:1.45;
            font-weight:800;
            color:#0f172a;
            margin-bottom:6px;
        }
        .ai-stage-desc{
            font-size:13px;
            line-height:1.68;
            color:#475467;
        }
        .ai-progress{
            width:100%;
            height:10px;
            background:#e8eef7;
            border-radius:999px;
            overflow:hidden;
            margin-top:14px;
        }
        .ai-progress-bar{
            height:100%;
            border-radius:999px;
            background:linear-gradient(90deg, #173b74 0%, #2563eb 100%);
            transition:width .28s ease;
        }
        .skeleton-grid{
            display:grid;
            grid-template-columns:repeat(3, minmax(0, 1fr));
            gap:16px;
            margin-top:16px;
        }
        .skeleton-card{
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid #e6ebf2;
            border-radius:18px;
            padding:18px;
            min-height:186px;
        }
        .skeleton-line{
            width:100%;
            height:12px;
            border-radius:999px;
            background:linear-gradient(90deg, #eef3fb 25%, #dde7f7 37%, #eef3fb 63%);
            background-size:400% 100%;
            animation:skeletonFlow 1.3s ease-in-out infinite;
            margin-bottom:12px;
        }
        .skeleton-line.short{ width:42%; }
        .skeleton-line.mid{ width:72%; }
        .skeleton-pill-row{
            display:flex;
            gap:8px;
            flex-wrap:wrap;
            margin-top:16px;
        }
        .skeleton-pill{
            width:82px;
            height:28px;
            border-radius:999px;
            background:linear-gradient(90deg, #eef3fb 25%, #dde7f7 37%, #eef3fb 63%);
            background-size:400% 100%;
            animation:skeletonFlow 1.3s ease-in-out infinite;
        }
        @keyframes skeletonFlow{
            0%{ background-position:100% 50%; }
            100%{ background-position:0 50%; }
        }

        .result-card-wrap{
            animation:fadeUpCard .55s ease both;
            margin-bottom:12px;
        }
        @keyframes fadeUpCard{
            0%{ opacity:0; transform:translateY(18px); }
            100%{ opacity:1; transform:translateY(0); }
        }

        .result-card{
            position:relative;
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid var(--line);
            border-radius:20px;
            box-shadow:var(--shadow);
            padding:20px 20px 18px 20px;
            height:440px;
            min-height:440px;
            max-height:440px;
            display:flex;
            flex-direction:column;
            transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;
            overflow:hidden;
            box-sizing:border-box;
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
        .job-title{
            font-size:20px;
            line-height:1.42;
            font-weight:800;
            color:#102a43;
            margin-bottom:10px;
            letter-spacing:-0.02em;
            padding-left:4px;
            min-height:30px;
        }
        .job-summary{
            font-size:14px;
            line-height:1.76;
            color:#475467;
            height:132px;
            min-height:132px;
            max-height:132px;
            overflow:hidden;
            margin-bottom:14px;
            padding-left:4px;
        }
        .tag-row{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            height:104px;
            min-height:104px;
            max-height:104px;
            overflow:hidden;
            margin-bottom:14px;
            padding-left:4px;
        }
        .tag-chip{
            display:inline-flex;
            align-items:center;
            height:32px;
            padding:0 11px;
            border-radius:999px;
            background:#f8fbff;
            border:1px solid #dce8fb;
            color:#2563eb;
            font-size:12px;
            font-weight:700;
            box-sizing:border-box;
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
        .similar-job-grid{
            display:grid;
            grid-template-columns:repeat(2, minmax(0, 1fr));
            gap:10px;
        }
        .similar-job-item{
            display:flex;
            align-items:flex-start;
            gap:8px;
            min-height:54px;
            padding:12px 13px;
            border-radius:14px;
            background:#f8fbff;
            border:1px solid #dce8fb;
            color:#1d4ed8;
            font-size:13px;
            line-height:1.58;
            font-weight:700;
            word-break:keep-all;
        }
        .similar-job-bullet{
            width:8px;
            height:8px;
            border-radius:50%;
            background:#2563eb;
            margin-top:6px;
            flex-shrink:0;
        }
        .outlook-card{
            background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid #e8eef7;
            border-radius:18px;
            padding:18px;
            box-shadow:0 4px 16px rgba(15,23,42,.03);
        }
        .outlook-summary{
            background:#f8fbff;
            border:1px solid #dce8fb;
            border-radius:16px;
            padding:16px;
            margin-bottom:14px;
        }
        .outlook-summary-title{
            font-size:13px;
            color:#1d4ed8;
            font-weight:800;
            margin-bottom:10px;
        }
        .outlook-body{
            font-size:14px;
            line-height:1.82;
            color:#475467;
        }
        .outlook-body p{
            margin:0 0 10px 0;
        }
        .outlook-body p:last-child{
            margin-bottom:0;
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
        .insight-list{
            list-style:none;
            padding-left:0;
            margin:0;
        }
        .insight-list li{
            position:relative;
            padding-left:14px;
            margin-bottom:9px;
            font-size:14px;
            line-height:1.76;
            color:#475467;
            word-break:keep-all;
        }
        .insight-list li:last-child{
            margin-bottom:0;
        }
        .insight-list li::before{
            content:"•";
            position:absolute;
            left:0;
            top:0;
            color:#2563eb;
            font-weight:800;
        }
        .empty-text{
            font-size:14px;
            line-height:1.7;
            color:#98a2b3;
        }

        .viz-card{
            width:100%;
            margin-top:18px;
            padding:20px;
            border:1px solid #e8eef7;
            border-radius:18px;
            background:linear-gradient(180deg,#ffffff 0%,#fbfdff 100%);
            box-shadow:0 4px 16px rgba(15,23,42,.03);
            box-sizing:border-box;
        }
        .donut-stage{
            display:flex;
            align-items:center;
            justify-content:center;
            margin:6px 0 20px 0;
        }
        .donut-chart{
            width:220px;
            height:220px;
            border-radius:50%;
            display:flex;
            align-items:center;
            justify-content:center;
            box-shadow:0 16px 34px rgba(15,23,42,.08);
        }
        .donut-hole{
            width:124px;
            height:124px;
            border-radius:50%;
            background:#ffffff;
            display:flex;
            flex-direction:column;
            align-items:center;
            justify-content:center;
            border:1px solid #eef2ff;
        }
        .donut-kicker{
            color:#64748b;
            font-size:12px;
            font-weight:800;
            margin-bottom:5px;
        }
        .donut-value{
            color:#0f172a;
            font-size:30px;
            font-weight:900;
            letter-spacing:-0.03em;
        }
        .legend-grid{
            display:grid;
            grid-template-columns:repeat(2,minmax(0,1fr));
            gap:10px;
        }
        .legend-item{
            display:flex;
            align-items:center;
            gap:10px;
            padding:12px 14px;
            border-radius:16px;
            background:#f8fbff;
            border:1px solid #e6eefc;
        }
        .legend-dot{
            width:12px;
            height:12px;
            border-radius:50%;
            flex:0 0 12px;
        }
        .legend-label{
            flex:1;
            color:#334155;
            font-size:13px;
            font-weight:800;
        }
        .legend-value{
            color:#0f172a;
            font-size:13px;
            font-weight:900;
        }
        .bar-chart-list{
            display:flex;
            flex-direction:column;
            gap:22px;
            margin-top:6px;
        }
        .bar-chart-head{
            display:flex;
            justify-content:space-between;
            gap:10px;
            margin-bottom:10px;
            color:#334155;
            font-size:13px;
            font-weight:800;
        }
        .bar-chart-head em{
            color:#64748b;
            font-style:normal;
            font-weight:700;
        }
        .bar-chart-head strong{
            color:#0f172a;
            font-weight:900;
        }
        .bar-track{
            width:100%;
            height:30px;
            border-radius:999px;
            background:#e8eef7;
            overflow:hidden;
            border:1px solid #dce8fb;
            box-sizing:border-box;
        }
        .bar-fill{
            height:100%;
            border-radius:999px;
        }
        .middle-fill{
            background:linear-gradient(90deg,#93c5fd 0%,#5b6bff 100%);
        }
        .high-fill{
            background:linear-gradient(90deg,#818cf8 0%,#4338ca 100%);
        }
        .salary-viz-card{
            margin-top:18px;
        }
        .salary-band-chip{
            display:inline-flex;
            align-items:center;
            padding:7px 12px;
            border-radius:999px;
            background:#eef4ff;
            border:1px solid #dbe7ff;
            color:#1d4ed8;
            font-size:12px;
            font-weight:800;
            margin-bottom:16px;
        }
        .salary-viz-label{
            font-size:13px;
            font-weight:800;
            color:#64748b;
            margin-bottom:8px;
        }
        .salary-viz-value{
            font-size:30px;
            font-weight:900;
            color:#0f172a;
            letter-spacing:-0.03em;
            margin-bottom:16px;
        }
        .salary-track{
            width:100%;
            height:34px;
            border-radius:999px;
            background:#dbeafe;
            overflow:hidden;
            border:1px solid #bfdbfe;
            box-sizing:border-box;
        }
        .salary-fill{
            height:100%;
            border-radius:999px;
            background:linear-gradient(90deg,#60a5fa 0%,#2563eb 100%);
        }
        .salary-axis{
            display:flex;
            justify-content:space-between;
            gap:8px;
            margin-top:10px;
            color:#64748b;
            font-size:11px;
            font-weight:700;
        }
        .chart-note{
            margin-top:22px;
            padding:13px 14px;
            border-radius:14px;
            background:#f8fbff;
            border:1px solid #dce8fb;
            color:#475569;
            font-size:13px;
            line-height:1.65;
            font-weight:700;
            text-align:center;
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
            .brief-grid, .similar-job-grid, .skeleton-grid{ grid-template-columns:1fr 1fr; }
            .result-card{ height:430px; min-height:430px; max-height:430px; }
        }
        @media (max-width: 768px){
            .brief-grid, .similar-job-grid, .skeleton-grid, .legend-grid{ grid-template-columns:1fr; }
            .hero{ padding:26px 22px 22px 22px; }
            .result-card{ height:auto; min-height:0; max-height:none; }
            .job-summary, .tag-row{ height:auto; min-height:0; max-height:none; }
        }
        </style>
        """
    )


# -----------------------------
# Page rendering helpers
# -----------------------------
def render_hero(df: pd.DataFrame) -> None:
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
                <span class="glass-chip">AI 키워드 사전 생성 적용</span>
                <span class="glass-chip">NCS·전망·통계 정보 통합</span>
            </div>
        </div>
        """
    )


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
                    <div class="section-sub">직업명, 소개, 적성, 유사 직무, 관련 전공, 사전 생성된 AI 키워드를 함께 반영합니다.</div>
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

    display_keywords = derive_brief_keywords(query, filtered, limit=8)
    token_html = "".join([f'<span class="meta-chip">{html.escape(token)}</span>' for token in display_keywords])

    related_tags = extract_related_topics(filtered, limit=8)
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
                <div class="section-sub">입력한 탐색어와 상위 결과의 의미를 함께 반영해 핵심 키워드와 연관 주제를 요약했습니다.</div>
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


def render_pre_search_state() -> None:
    render_html(
        """
        <div class="search-idle">
            <div class="search-idle-title">AI 탐색어를 입력하면 직업 후보를 정리해 보여드립니다</div>
            <div class="search-idle-text">
                아직 탐색이 시작되지 않아 결과 목록은 표시하지 않고 있습니다. 위 입력창에 관심 있는 직업, 일의 성격, 원하는 분위기를 문장처럼 입력해 보세요.
            </div>
        </div>
        """
    )


def render_ai_search_animation(query: str) -> None:
    stages = [
        ("탐색 의도를 해석하고 있습니다", "입력한 문장을 직업명, 관심사, 업무 성격, 연관 키워드로 분해하고 있습니다."),
        ("임베딩과 직업 데이터를 연결하고 있습니다", "직무 소개, 적성, 유사 직무, 전공 정보와 사전 생성된 의미 벡터를 함께 읽어 관련성이 높은 후보를 좁히고 있습니다."),
        ("결과를 큐레이션하고 있습니다", "가독성이 좋은 순서로 후보를 정렬하고, 바로 읽을 수 있는 탐색 브리핑을 준비하고 있습니다."),
    ]

    placeholder = st.empty()

    for idx, (title, desc) in enumerate(stages, start=1):
        progress = int((idx / len(stages)) * 100)
        placeholder.markdown(
            textwrap.dedent(
                f"""
                <div class="ai-loading-shell">
                    <div class="ai-loading-top">
                        <div>
                            <div class="section-kicker">AI Search Running</div>
                            <div class="ai-loading-title">AI가 탐색을 진행하고 있습니다</div>
                            <div class="ai-loading-sub">탐색어 <strong>{html.escape(query)}</strong> 를 바탕으로 관련 직업을 정교하게 선별하는 중입니다.</div>
                        </div>
                        <div class="ai-badge"><span class="ai-dot"></span>분석 중</div>
                    </div>
                    <div class="ai-stage-box">
                        <div class="ai-stage-label">STEP {idx}</div>
                        <div class="ai-stage-title">{html.escape(title)}</div>
                        <div class="ai-stage-desc">{html.escape(desc)}</div>
                        <div class="ai-progress">
                            <div class="ai-progress-bar" style="width:{progress}%"></div>
                        </div>
                    </div>
                    <div class="skeleton-grid">
                        <div class="skeleton-card">
                            <div class="skeleton-line short"></div>
                            <div class="skeleton-line"></div>
                            <div class="skeleton-line mid"></div>
                            <div class="skeleton-pill-row">
                                <div class="skeleton-pill"></div>
                                <div class="skeleton-pill"></div>
                                <div class="skeleton-pill"></div>
                            </div>
                        </div>
                        <div class="skeleton-card">
                            <div class="skeleton-line short"></div>
                            <div class="skeleton-line"></div>
                            <div class="skeleton-line mid"></div>
                            <div class="skeleton-pill-row">
                                <div class="skeleton-pill"></div>
                                <div class="skeleton-pill"></div>
                            </div>
                        </div>
                        <div class="skeleton-card">
                            <div class="skeleton-line short"></div>
                            <div class="skeleton-line"></div>
                            <div class="skeleton-line mid"></div>
                            <div class="skeleton-pill-row">
                                <div class="skeleton-pill"></div>
                                <div class="skeleton-pill"></div>
                                <div class="skeleton-pill"></div>
                            </div>
                        </div>
                    </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
        time.sleep(0.6 if idx < len(stages) else 0.5)

    placeholder.empty()



# -----------------------------
# Runtime keyword refinement helpers
# -----------------------------
CARD_TRAIT_KEYWORDS = [
    "문제해결능력", "문제 해결 능력", "의사소통능력", "의사소통 능력", "자료분석능력", "자료 분석 능력",
    "수리능력", "수리 능력", "분석적 사고", "논리적 사고", "공간 지각력", "공간지각력",
    "판단력", "분석력", "창의력", "창의성", "응용력", "응용능력", "순발력",
    "협동심", "대인관계", "사교성", "사회성", "정직성", "신뢰성", "책임감",
    "리더십", "집중력", "인내심", "꼼꼼함", "성실성", "도전정신", "성취욕",
    "배려심", "봉사심", "희생정신", "객관성", "외국어 실력", "프로그래밍 능력", "기획력", "기술력", "전문지식",
]
CARD_TRAIT_KEYWORDS = sorted(set(CARD_TRAIT_KEYWORDS), key=len, reverse=True)

CARD_ACTION_WORDS = [
    "보조", "관리", "개발", "분석", "진단", "상담", "자문", "조사", "평가", "측정", "기록",
    "소독", "살균", "설계", "기획", "연구", "검사", "투약", "치료", "수립", "제시", "조율",
    "제작", "운영", "교육", "프로그래밍", "디자인", "모델링", "관찰", "전달", "수납", "접수",
    "회복", "유지", "증진", "상태파악", "수행", "처리", "컨설팅", "지도",
]
CARD_ACTION_WORDS = sorted(set(CARD_ACTION_WORDS), key=len, reverse=True)

CARD_BAD_WORDS = {
    "환자", "해당", "각종", "여러", "다양한", "관련", "대한", "있는", "되는", "하는", "위해",
    "경우", "통해", "중심", "한다", "수행", "업무", "사람", "분야", "직업", "직무", "정보",
    "내용", "방법", "과정", "정도", "자료", "워크넷",
}

CARD_SPECIAL_PATTERNS = [
    (r"의료검사.*투약.*보조", "의료검사·투약 보조"),
    (r"진료.*보조", "진료 보조"),
    (r"간호.*보조", "간호 보조"),
    (r"체온.*맥박.*호흡.*측정|혈압.*체온.*측정|체온.*맥박.*측정", "활력징후 측정"),
    (r"치료내용.*기록|상태.*반응.*관찰.*기록", "환자 상태 기록"),
    (r"의료기구.*소독|의료기구.*살균|물품.*소독|물품.*살균", "의료기구 소독"),
    (r"접수.*수납", "접수·수납 업무"),
    (r"문서.*관리", "문서 관리"),
    (r"3차원.*모델링|3D.*모델링", "3D 모델링"),
    (r"가상.*시스템.*개발|가상현실.*시스템.*개발|가상시스템.*개발", "가상현실 시스템 개발"),
    (r"개발방향.*설정", "개발방향 설정"),
    (r"컴퓨터그래픽.*프로그래밍|프로그래밍", "컴퓨터그래픽 프로그래밍"),
    (r"가상현실.*시스템.*디자인|시스템.*디자인", "가상현실 시스템 디자인"),
    (r"문제점.*분석", "문제점 분석"),
    (r"대책.*연구", "대책 연구"),
    (r"상담.*자문", "상담·자문"),
    (r"진단.*지도", "진단·지도"),
    (r"수출입.*상담|수출입.*자문", "수출입 상담"),
    (r"환경관리.*문제점.*진단|문제점.*진단", "문제점 진단"),
    (r"해결책.*제시", "해결책 제시"),
    (r"영향.*측정.*평가|측정평가", "환경영향 평가"),
    (r"장기계획.*수립", "장기계획 수립"),
    (r"원인.*규명", "원인 규명"),
]


def refine_keyword_phrase(text: str) -> str:
    text = normalize_whitespace(text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = text.replace("ㆍ", "·")
    text = re.sub(
        r"(한다|된다|있다|필요하다|요구된다|유리하다|적합하다|수행한다|돕는다)\.?$",
        "",
        text,
    )
    text = re.sub(r"\s+", " ", text).strip(" .,-;:·")
    text = re.sub(
        r"^(?:[가-힣A-Za-z0-9·]+는|[가-힣A-Za-z0-9·]+은|[가-힣A-Za-z0-9·]+가|[가-힣A-Za-z0-9·]+이)\s+",
        "",
        text,
    )
    protected_suffix = r"(학과|공학과|과학과|디자인학과|소프트웨어과|기계과|전자과|통신과|평가)$"
    if not re.search(protected_suffix, text):
        text = re.sub(r"(을|를|에|의|은|는|이|가)$", "", text).strip()
    return re.sub(r"\s+", " ", text)


def is_good_keyword_phrase(text: str) -> bool:
    text = refine_keyword_phrase(text)
    if not text or len(text) < 2 or len(text) > 26:
        return False
    if re.match(r"^(및|고|여|나|한 후|한|등|또한|그리고|또|와|과|상의)\s+", text):
        return False
    if re.search(
        r"(하면|하며|하고|하여|하므로|되며|되어|있어야|가지고|경우가|사람에게|사람들에게|유리하다|요구된다|필요하다|적합하며|시키며)",
        text,
    ):
        return False
    tokens = [tok for tok in re.split(r"\s+", text) if tok]
    if len(tokens) > 4:
        return False
    if text in CARD_BAD_WORDS:
        return False
    if any(tok in CARD_BAD_WORDS for tok in tokens):
        return False
    if text.endswith(("들", "등")) and len(text) < 6:
        return False
    return True


def unique_refined_keywords(items: list[str]) -> list[str]:
    result: list[str] = []
    seen = set()
    for item in items:
        value = refine_keyword_phrase(item)
        if not is_good_keyword_phrase(value):
            continue
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def extract_trait_keywords_from_row(row: pd.Series) -> list[str]:
    source = f"{row.get('aptitude', '')}\n{row.get('summary', '')}"
    output: list[str] = []

    normalize_map = {
        "문제 해결 능력": "문제해결능력",
        "의사소통 능력": "의사소통능력",
        "자료 분석 능력": "자료분석능력",
        "수리 능력": "수리능력",
        "공간지각력": "공간 지각력",
    }

    for keyword in CARD_TRAIT_KEYWORDS:
        if keyword in source:
            output.append(normalize_map.get(keyword, keyword))

    for line in split_lines(source):
        for part in re.split(r",| 및 |/|·", line):
            part = refine_keyword_phrase(part)
            part = re.sub(r"^(남에 대한 )", "", part)
            part = {
                "정직": "정직성",
                "신뢰": "신뢰성",
                "배려": "배려심",
                "협조": "협조성",
                "혁신": "혁신성",
            }.get(part, part)
            if part in CARD_TRAIT_KEYWORDS or part in {"협조성", "배려심", "봉사심", "희생정신", "혁신성"}:
                output.append(part)

    return unique_refined_keywords(output)


def extract_action_keywords_from_row(row: pd.Series, limit: int = 8) -> list[str]:
    summary = str(row.get("summary", ""))
    output: list[str] = []

    for line in split_lines(summary):
        cleaned = refine_keyword_phrase(line)
        for pattern, keyword in CARD_SPECIAL_PATTERNS:
            if re.search(pattern, cleaned):
                output.append(keyword)

    action_group = "|".join(re.escape(word) for word in CARD_ACTION_WORDS)
    for line in split_lines(summary):
        cleaned = refine_keyword_phrase(line)
        for match in re.finditer(
            rf"([가-힣A-Za-z0-9·/\s]{{2,18}}?)(?:을|를|에|의)?\s*({action_group})(?:하|한|할|하고|하며|한다|함|되|한다)?",
            cleaned,
        ):
            obj = refine_keyword_phrase(match.group(1))
            action = match.group(2)
            obj = re.sub(
                r"^(?:환자의|환자|사용자|기업이나 공공조직|기업|의사나 간호사의 지시에 따라)\s*",
                "",
                obj,
            ).strip()
            obj = re.sub(r"(?:업무|활동)$", "", obj).strip()
            if len(obj) < 2:
                continue
            phrase = f"{obj} {action}".strip()
            if is_good_keyword_phrase(phrase) and not re.match(r"^(의료|각종|관련|여러|다양한)\s", phrase):
                output.append(phrase)

    output = unique_refined_keywords(output)
    special_keywords = [keyword for _, keyword in CARD_SPECIAL_PATTERNS]

    def sort_key(value: str) -> tuple[int, int]:
        score = 0
        if value in special_keywords:
            score += 8
        if "·" in value:
            score += 3
        if any(action in value for action in CARD_ACTION_WORDS):
            score += 2
        if len(value) <= 12:
            score += 1
        return (-score, len(value))

    return sorted(output, key=sort_key)[:limit]


def derive_display_keywords_for_row(row: pd.Series, max_keywords: int = 10) -> list[str]:
    output: list[str] = []

    # 1순위: LLM/ML로 오프라인 생성한 검수형 카드 키워드.
    # 런타임에서 새로 뽑지 않고 메타를 읽기만 하므로 배포 환경 부담이 없다.
    for keyword in row.get("llm_keywords_list", []):
        keyword = refine_keyword_phrase(str(keyword))
        if is_good_keyword_phrase(keyword) and keyword not in output:
            output.append(keyword)
        if len(output) >= max_keywords:
            return output

    # 2순위: 규칙 기반 직무 행위 키워드.
    action_keywords = extract_action_keywords_from_row(row, limit=8)
    trait_keywords = extract_trait_keywords_from_row(row)

    for keyword in action_keywords + trait_keywords:
        if keyword not in output:
            output.append(keyword)
        if len(output) >= max_keywords:
            return output

    # 3순위: 기존 embedding meta 키워드. 문장 조각이 섞일 수 있으므로 필터링한다.
    for keyword in row.get("display_keywords_list", []):
        keyword = refine_keyword_phrase(str(keyword))
        if is_good_keyword_phrase(keyword) and keyword not in output:
            output.append(keyword)
        if len(output) >= max_keywords:
            return output

    # 4순위: 유사직업/전공 fallback.
    for keyword in row.get("similar_job_list", []) + row.get("major_list", []):
        keyword = refine_keyword_phrase(str(keyword))
        if is_good_keyword_phrase(keyword) and keyword not in output:
            output.append(keyword)
        if len(output) >= max_keywords:
            return output

    return output


def select_card_tags(row: pd.Series, limit: int = 3) -> list[str]:
    keywords = derive_display_keywords_for_row(row, max_keywords=limit)
    if len(keywords) >= limit:
        return keywords[:limit]

    for keyword in row.get("similar_job_list", []) + row.get("major_list", []) + row.get("topic_tags_list", []):
        keyword = refine_keyword_phrase(str(keyword))
        if is_good_keyword_phrase(keyword) and keyword not in keywords:
            keywords.append(keyword)
        if len(keywords) >= limit:
            break
    return keywords[:limit]



def render_result_card(row: pd.Series, delay_ms: int = 0) -> None:
    tags = select_card_tags(row, limit=3)
    tags_html = "".join([f'<span class="tag-chip">{html.escape(tag)}</span>' for tag in tags])

    salary_label = "정보 없음"
    if row.get("salary_amount") is not None and not pd.isna(row.get("salary_amount")):
        salary_label = f"{int(row['salary_amount']):,}만원"

    summary = shorten_text(row.get("summary", ""), 130)
    if not summary:
        summary = "직업 요약 정보가 준비되지 않았습니다."

    render_html(
        f"""
        <div class="result-card-wrap" style="animation-delay:{delay_ms}ms;">
            <div class="result-card">
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
        similar_jobs = detail.get("similar_job_list", [])[:8]
        if similar_jobs:
            cards = "".join(
                [
                    f'<div class="similar-job-item"><span class="similar-job-bullet"></span><span>{html.escape(item)}</span></div>'
                    for item in similar_jobs
                ]
            )
            similar_body = f'<div class="similar-job-grid">{cards}</div>'
        else:
            similar_body = '<div class="empty-text">등록된 유사 직업 정보가 없습니다.</div>'

        render_html(
            f"""
            <div class="soft-card">
                <div class="section-title" style="font-size:18px; margin-bottom:10px;">유사 직업</div>
                {similar_body}
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
    aptitude_keywords = derive_display_keywords_for_row(detail, max_keywords=10)
    if not aptitude_keywords:
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
                    <div class="section-sub">사전 생성된 AI 키워드와 직무 원문을 함께 사용해 핵심 적성과 준비 정보를 정리했습니다.</div>
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


def render_outlook_text_panel(title: str, raw_text, empty_message: str) -> None:
    summary_points = summarize_long_text(raw_text, max_points=4, max_chars=118)
    full_html = format_sentences_as_paragraphs(raw_text)

    if not summary_points and not full_html:
        render_html(f"<div class='outlook-card'><div class='empty-text'>{html.escape(empty_message)}</div></div>")
        return

    summary_html = "".join([f"<li>{html.escape(point)}</li>" for point in summary_points]) if summary_points else "<li>요약 가능한 핵심 문장이 충분하지 않습니다.</li>"

    render_html(
        f"""
        <div class="outlook-card">
            <div class="outlook-summary">
                <div class="outlook-summary-title">한눈에 보기</div>
                <ul class="insight-list">{summary_html}</ul>
            </div>
        </div>
        """
    )

    with st.expander(f"{title} 세부 설명 보기", expanded=False):
        if full_html:
            render_html(f"<div class='outlook-body'>{full_html}</div>")
        else:
            st.info(empty_message)


def render_market_section(detail: pd.Series) -> None:
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

        salary_chart_html = build_salary_gauge(salary_amount)
        if salary_chart_html is not None:
            render_html(salary_chart_html)
        else:
            st.info("임금 그래프를 표시할 수 있는 데이터가 없습니다.")

    with col2:
        tab1, tab2 = st.tabs(["고용전망", "발전가능성"])

        with tab1:
            render_outlook_text_panel(
                title="고용전망",
                raw_text=detail.get("employment", ""),
                empty_message="고용전망 설명이 없습니다.",
            )

        with tab2:
            render_outlook_text_panel(
                title="발전가능성",
                raw_text=detail.get("job_possibility", ""),
                empty_message="발전가능성 설명이 없습니다.",
            )


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

    gender_chart_html = build_gender_chart(detail)
    age_chart_html = build_age_chart(detail)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        render_html(
            """
            <div class="soft-card">
                <div class="section-title" style="font-size:18px; margin-bottom:10px;">성별 관심도 비중</div>
            </div>
            """
        )

        if gender_chart_html is not None:
            render_html(gender_chart_html)
        else:
            st.info("성별 PCNT 데이터가 없습니다.")

    with col2:
        render_html(
            """
            <div class="soft-card">
                <div class="section-title" style="font-size:18px; margin-bottom:10px;">연령대별 선호도</div>
            </div>
            """
        )

        if age_chart_html is not None:
            render_html(age_chart_html)
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

    back_col, _ = st.columns([0.18, 0.82])
    with back_col:
        if st.button("← 목록으로", use_container_width=True):
            st.session_state.page = "main"
            rerun_app()

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
    st.session_state.setdefault("page_number", 1)


def render_main_page(df: pd.DataFrame) -> None:
    render_hero(df)

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
                st.session_state.page_number = 1
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
        st.session_state.page_number = 1
        rerun_app()

    if reset_clicked:
        st.session_state.search_input = ""
        st.session_state.committed_query = ""
        st.session_state.trigger_ai_search = False
        st.session_state.page_number = 1
        rerun_app()

    col1, col2, col3 = st.columns([1.6, 0.9, 0.9], gap="medium")
    with col1:
        selected_majors = st.multiselect("전공별 필터", options=major_options, key="major_filter")
    with col2:
        salary_filters = st.multiselect("임금 수준 필터", options=["상", "중", "하", "정보 없음"], key="salary_filter")
    with col3:
        employment_filters = st.multiselect("고용전망 필터", options=["좋음", "보통", "주의"], key="employment_filter")

    search_query = st.session_state.get("committed_query", "").strip()

    if st.session_state.get("trigger_ai_search") and search_query:
        render_ai_search_animation(search_query)
        st.session_state.trigger_ai_search = False

    if not search_query:
        render_ai_search_brief("", df.iloc[0:0], df.iloc[0:0])
        render_pre_search_state()
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

    current_page = int(st.session_state.get("page_number", 1))
    current_page = max(1, min(current_page, page_count))
    st.session_state.page_number = current_page

    start = (current_page - 1) * per_page
    end = start + per_page
    page_df = filtered.iloc[start:end].reset_index(drop=True)

    cols = st.columns(3, gap="large")
    for idx, (_, row) in enumerate(page_df.iterrows()):
        with cols[idx % 3]:
            render_result_card(row, delay_ms=idx * 120)
            if st.button(f"상세 보기 · {row['job']}", key=f"open_{start+idx}", use_container_width=True):
                st.session_state.selected_job = row["job"]
                st.session_state.page = "detail"
                rerun_app()

    render_html(
        """
        <div style="height:8px;"></div>
        """
    )

    page_spacer_l, page_col_prev, page_col_num, page_col_next, page_spacer_r = st.columns(
        [0.36, 0.10, 0.08, 0.10, 0.36],
        gap="small",
    )

    with page_col_prev:
        prev_disabled = current_page <= 1
        if st.button("←", key="page_prev_btn", use_container_width=True, disabled=prev_disabled):
            st.session_state.page_number = max(1, current_page - 1)
            rerun_app()

    with page_col_num:
        render_html(
            f"""
            <div style="
                height:38px;
                display:flex;
                align-items:center;
                justify-content:center;
                border:1px solid #cfd9e8;
                border-radius:12px;
                background:#ffffff;
                color:#0f172a;
                font-size:14px;
                font-weight:800;
                box-shadow:0 4px 12px rgba(15,23,42,.035);
                box-sizing:border-box;
                white-space:nowrap;
            ">
                {current_page} / {page_count}
            </div>
            """
        )

    with page_col_next:
        next_disabled = current_page >= page_count
        if st.button("→", key="page_next_btn", use_container_width=True, disabled=next_disabled):
            st.session_state.page_number = min(page_count, current_page + 1)
            rerun_app()

    render_html('<div style="height:18px;"></div>')


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
