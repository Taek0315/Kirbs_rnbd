from __future__ import annotations

from pathlib import Path
import re
import json
from typing import Iterable

import numpy as np
import pandas as pd

try:
    from sentence_transformers import SentenceTransformer
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "sentence-transformers가 설치되어 있지 않습니다.\n"
        "conda 환경 또는 Jupyter에서 아래를 먼저 실행해 주세요.\n"
        "pip install -U sentence-transformers openpyxl pandas pyarrow"
    ) from exc


# =========================
# 사용자 설정
# =========================
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "career_jobs.xlsx"
OUTPUT_DIR = BASE_DIR / "embedding_output"

# 한국어 의미 검색용으로 무난한 다국어 임베딩 모델
# 더 높은 성능이 필요하면 아래 후보로 교체 가능
# - intfloat/multilingual-e5-base
# - intfloat/multilingual-e5-large
MODEL_NAME = "intfloat/multilingual-e5-base"

# 메모리가 부족하면 8~16으로 낮추세요.
BATCH_SIZE = 32
NORMALIZE_EMBEDDINGS = True

# 직업 설명을 만들 때 사용할 주요 컬럼
TEXT_COLUMNS = [
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

MAJOR_PREFIX = "major_"
CONTACT_PREFIX = "contact_"


# =========================
# 전처리 유틸
# =========================
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
    text = normalize_whitespace(text)
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

    text = normalize_whitespace(text)
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

    seen = set()
    deduped: list[str] = []
    for part in raw_parts:
        key = part.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(part)
    return deduped



def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen = set()
    result: list[str] = []
    for item in items:
        value = clean_sentence(item)
        if not value:
            continue
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result



def collect_prefixed_values(row: pd.Series, prefix: str) -> list[str]:
    values: list[str] = []
    for col in row.index:
        if str(col).startswith(prefix):
            values.extend(split_lines(row[col]))
    return unique_keep_order(values)


# =========================
# 임베딩용 문서 생성
# =========================
def build_document_text(row: pd.Series) -> str:
    blocks: list[str] = []

    job = clean_sentence(row.get("job", ""))
    if job:
        blocks.append(f"직업명: {job}")

    for col in TEXT_COLUMNS:
        if col == "job":
            continue
        value = row.get(col, "")
        lines = split_lines(value)
        if not lines:
            continue

        if col == "summary":
            label = "직무 요약"
        elif col == "similarJob":
            label = "유사 직업"
        elif col == "aptitude":
            label = "적성"
        elif col == "empway":
            label = "진출 경로"
        elif col == "prepareway":
            label = "준비 방법"
        elif col == "training":
            label = "훈련"
        elif col == "certification":
            label = "자격"
        elif col == "employment":
            label = "고용 전망"
        elif col == "job_possibility":
            label = "발전 가능성"
        elif col == "capacity_1":
            label = "핵심 역량"
        elif col == "capacity_all":
            label = "전체 역량"
        else:
            label = col

        blocks.append(f"{label}: " + " | ".join(lines))

    majors = collect_prefixed_values(row, MAJOR_PREFIX)
    if majors:
        blocks.append("관련 전공: " + " | ".join(majors))

    contacts = collect_prefixed_values(row, CONTACT_PREFIX)
    if contacts:
        blocks.append("추가 정보: " + " | ".join(contacts))

    return "\n".join(blocks).strip()


# =========================
# 저장 및 실행
# =========================
def build_embeddings(
    input_file: Path = INPUT_FILE,
    output_dir: Path = OUTPUT_DIR,
    model_name: str = MODEL_NAME,
    batch_size: int = BATCH_SIZE,
    normalize_embeddings: bool = NORMALIZE_EMBEDDINGS,
) -> tuple[pd.DataFrame, np.ndarray]:
    if not input_file.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_file}")

    output_dir.mkdir(parents=True, exist_ok=True)

    if input_file.suffix.lower() in {".xlsx", ".xls", ".xlsm"}:
        df = pd.read_excel(input_file)
    else:
        df = pd.read_csv(input_file)

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "job" not in df.columns:
        raise ValueError("career_jobs 파일에 'job' 컬럼이 없습니다.")

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda x: normalize_whitespace(x) if not is_missing_like(x) else "")

    df["job"] = df["job"].astype(str).str.strip()
    df = df[df["job"] != ""].reset_index(drop=True)

    df["embedding_text"] = df.apply(build_document_text, axis=1)

    # E5 계열은 문서 인코딩 시 passage: prefix 권장
    input_texts = [f"passage: {text}" for text in df["embedding_text"].tolist()]

    print(f"[1/3] 모델 로드: {model_name}")
    model = SentenceTransformer(model_name)

    print(f"[2/3] 임베딩 생성 시작: {len(input_texts):,}건")
    embeddings = model.encode(
        input_texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=normalize_embeddings,
    )

    if embeddings.dtype != np.float32:
        embeddings = embeddings.astype(np.float32)

    print("[3/3] 파일 저장")
    np.save(output_dir / "career_jobs_embeddings.npy", embeddings)

    meta_cols = [c for c in ["jobdicSeq", "job", "summary", "embedding_text"] if c in df.columns]
    df[meta_cols].to_parquet(output_dir / "career_jobs_embedding_meta.parquet", index=False)
    df[meta_cols].to_excel(output_dir / "career_jobs_embedding_meta.xlsx", index=False)

    config = {
        "input_file": str(input_file),
        "model_name": model_name,
        "row_count": int(len(df)),
        "embedding_dim": int(embeddings.shape[1]),
        "normalize_embeddings": bool(normalize_embeddings),
        "batch_size": int(batch_size),
        "major_prefix": MAJOR_PREFIX,
        "contact_prefix": CONTACT_PREFIX,
        "text_columns": TEXT_COLUMNS,
    }
    with open(output_dir / "embedding_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {output_dir}")
    print(f"임베딩 shape: {embeddings.shape}")
    return df, embeddings


# =========================
# 간단 검색 예시
# =========================
def semantic_search(
    query: str,
    meta_df: pd.DataFrame,
    embeddings: np.ndarray,
    model_name: str = MODEL_NAME,
    top_k: int = 10,
) -> pd.DataFrame:
    if not query.strip():
        return meta_df.iloc[0:0].copy()

    model = SentenceTransformer(model_name)
    query_vec = model.encode(
        [f"query: {query.strip()}"],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0].astype(np.float32)

    scores = embeddings @ query_vec
    order = np.argsort(scores)[::-1][:top_k]

    result = meta_df.iloc[order].copy()
    result["semantic_score"] = scores[order]
    return result.reset_index(drop=True)


if __name__ == "__main__":
    df_meta, emb = build_embeddings()

    print("\n샘플 검색 결과")
    sample_query = "컴퓨터와 관련된 일"
    result = semantic_search(sample_query, df_meta, emb, top_k=5)
    print(result[[c for c in ["job", "semantic_score"] if c in result.columns]])
