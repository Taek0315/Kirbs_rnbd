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
        "pip install -U sentence-transformers openpyxl pandas pyarrow kiwipiepy"
    ) from exc

try:
    from kiwipiepy import Kiwi
except ImportError:  # pragma: no cover
    Kiwi = None


# =========================
# 사용자 설정
# =========================
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "career_jobs.xlsx"
OUTPUT_DIR = BASE_DIR / "embedding_output"

MODEL_NAME = "intfloat/multilingual-e5-base"
BATCH_SIZE = 32
NORMALIZE_EMBEDDINGS = True

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

KEYWORD_SOURCE_COLUMNS = [
    "capacity_1",
    "capacity_all",
    "aptitude",
    "summary",
]

MAJOR_PREFIX = "major_"
CONTACT_PREFIX = "contact_"
MAX_DISPLAY_KEYWORDS = 10
MAX_TOPIC_TAGS = 12

PREFERRED_KEYWORD_ENDINGS = [
    "문제 해결 능력", "문제해결능력", "의사소통 능력", "의사소통능력", "자료 분석 능력",
    "자료분석능력", "분석 능력", "분석능력", "프로그래밍 능력", "기획 능력", "기획력",
    "사고 능력", "사고능력", "사고력", "분석력", "판단력", "통제력", "리더십",
    "책임감", "창의력", "창의성", "혁신성", "집중력", "인내심", "협동심", "대인관계",
    "대인관계능력", "자기통제력", "사회성", "정직성", "신뢰성", "응용력", "응용능력",
    "활용능력", "기술력", "지식", "전문지식", "성취욕", "도전정신", "꼼꼼함", "성실성",
]
PREFERRED_KEYWORD_ENDINGS = sorted(set(PREFERRED_KEYWORD_ENDINGS), key=len, reverse=True)

KEYWORD_STOPWORDS = {
    "관련", "직업", "직무", "일", "일을", "하는", "대한", "및", "에서", "으로", "위한", "위해",
    "같은", "있는", "되는", "분야", "업무", "사람", "경우", "통한", "기반", "탐색", "분석",
    "미래", "검색", "관련된", "중심", "한다", "수행", "업무를", "업무에", "직업명", "정보",
    "수", "것", "등", "필요", "요구", "평가", "준비", "훈련", "현장", "과정", "정도",
    "있다", "된다", "있으며", "통해", "전반적", "전반적인", "직업정보", "워크넷", "자료",
    "능력", "지식", "역량", "문장", "설명", "내용", "자격", "조건", "방법",
}

BAD_PHRASE_TOKENS = {
    "수", "있는", "있는", "되는", "하는", "하게", "하므로", "하고", "하며", "하여", "대한",
    "관련", "관련된", "관한", "자주", "또는", "그리고", "또", "이", "그", "저", "및", "등",
    "문제", "사람", "업무", "직업", "분야",
}

PROTECTED_SINGLE_KEYWORDS = {
    "끈기", "책임감", "리더십", "창의력", "창의성", "혁신성", "집중력", "인내심", "협동심",
    "정직성", "신뢰성", "성취욕", "도전정신", "사회성", "분석력", "판단력", "기획력", "꼼꼼함",
}

NOUN_TAGS = {"NNG", "NNP", "SL", "SN", "XR", "XPN"}


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
    return text.strip(" ,;:-")



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



def normalize_keyword_candidate(text: str) -> str:
    text = normalize_whitespace(text)
    text = text.replace("/", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"[\"'“”‘’]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;:-")

    replacements = [
        (r"\s*에 대한\s*", " "),
        (r"\s*에 관한\s*", " "),
        (r"\s*관련\s*", " "),
        (r"\s*관련된\s*", " "),
        (r"\s*및\s*", " "),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)

    text = re.sub(r"\s+", " ", text).strip(" ,;:-")
    return text



def is_valid_keyword_candidate(candidate: str) -> bool:
    candidate = normalize_keyword_candidate(candidate)
    if not candidate:
        return False

    if len(candidate) < 2 or len(candidate) > 24:
        return False

    lowered = candidate.lower()
    if lowered in KEYWORD_STOPWORDS:
        return False

    tokens = [tok for tok in candidate.split() if tok]
    if len(tokens) > 4:
        return False

    if any(tok.lower() in KEYWORD_STOPWORDS for tok in tokens):
        return False
    if any(tok in BAD_PHRASE_TOKENS for tok in tokens):
        return False

    # 조사/어미가 붙은 문장 조각 제거
    bad_suffix = re.compile(r"(하는|하며|하고|하여|하므로|되는|있는|있는|대한|관련된|같은|수있는|수 있는)$")
    if bad_suffix.search(candidate):
        return False

    # 동사/절 구조가 섞인 긴 구절 제거
    if re.search(r"(할 수|낼 수|될 수|하므로|하기 때문에|할수)", candidate):
        return False

    if re.search(r"[가-힣]{2,}(를|을|은|는|이|가|에|의)$", candidate):
        return False

    return True



def extract_keyword_candidates_regex(text: str) -> list[str]:
    raw = normalize_whitespace(text)
    if not raw:
        return []

    candidates: list[str] = []

    ending_group = "|".join(re.escape(item) for item in PREFERRED_KEYWORD_ENDINGS)
    phrase_pattern = re.compile(
        rf"(?:[가-힣A-Za-z0-9]+\s+){{0,2}}(?:{ending_group})"
    )
    for match in phrase_pattern.finditer(raw):
        phrase = normalize_keyword_candidate(match.group(0))
        if is_valid_keyword_candidate(phrase):
            candidates.append(phrase)

    for single in PROTECTED_SINGLE_KEYWORDS:
        if single in raw:
            candidates.append(single)

    return unique_keep_order(candidates)



def extract_keyword_candidates_kiwi(text: str, kiwi: Kiwi | None) -> list[str]:
    if kiwi is None:
        return []

    raw = normalize_whitespace(text)
    if not raw:
        return []

    candidates: list[str] = []
    for sentence in re.split(r"\n+", raw):
        sentence = sentence.strip()
        if not sentence:
            continue

        try:
            tokens = kiwi.tokenize(sentence)
        except Exception:
            continue

        buffer: list[str] = []
        for tok in tokens:
            form = tok.form.strip()
            tag = tok.tag
            if tag in NOUN_TAGS and len(form) >= 1:
                if form.lower() not in KEYWORD_STOPWORDS:
                    buffer.append(form)
            else:
                if buffer:
                    for n in range(1, min(4, len(buffer)) + 1):
                        for start in range(0, len(buffer) - n + 1):
                            phrase = " ".join(buffer[start:start + n])
                            phrase = normalize_keyword_candidate(phrase)
                            if is_valid_keyword_candidate(phrase):
                                candidates.append(phrase)
                    buffer = []
        if buffer:
            for n in range(1, min(4, len(buffer)) + 1):
                for start in range(0, len(buffer) - n + 1):
                    phrase = " ".join(buffer[start:start + n])
                    phrase = normalize_keyword_candidate(phrase)
                    if is_valid_keyword_candidate(phrase):
                        candidates.append(phrase)

    return unique_keep_order(candidates)



def score_keyword_candidate(candidate: str, source_text: str) -> float:
    score = 0.0
    if candidate in PROTECTED_SINGLE_KEYWORDS:
        score += 5.0
    if any(candidate.endswith(end) for end in PREFERRED_KEYWORD_ENDINGS):
        score += 6.0
    if 2 <= len(candidate) <= 10:
        score += 2.4
    elif len(candidate) <= 16:
        score += 1.2
    if " " in candidate:
        score += 1.0
    if candidate in source_text:
        score += 2.0
    if re.search(r"[A-Za-z]", candidate):
        score += 0.5
    return score



def rank_keyword_candidates(
    candidates: list[str],
    document_embedding: np.ndarray,
    model: SentenceTransformer,
    source_text: str,
    max_keywords: int = MAX_DISPLAY_KEYWORDS,
) -> list[str]:
    clean_candidates = []
    seen = set()
    for cand in candidates:
        cand = normalize_keyword_candidate(cand)
        if not is_valid_keyword_candidate(cand):
            continue
        key = cand.lower()
        if key in seen:
            continue
        seen.add(key)
        clean_candidates.append(cand)

    if not clean_candidates:
        return []

    candidate_inputs = [f"query: {cand}" for cand in clean_candidates]
    cand_emb = model.encode(
        candidate_inputs,
        batch_size=min(len(candidate_inputs), 32),
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)

    semantic_scores = cand_emb @ document_embedding

    scored: list[tuple[float, str]] = []
    for cand, sem in zip(clean_candidates, semantic_scores):
        score = float(sem) * 10.0 + score_keyword_candidate(cand, source_text)
        scored.append((score, cand))

    scored.sort(key=lambda x: (-x[0], len(x[1])))

    selected: list[str] = []
    for _, cand in scored:
        if any(cand != kept and (cand in kept or kept in cand) for kept in selected):
            continue
        selected.append(cand)
        if len(selected) >= max_keywords:
            break
    return selected



def build_display_keywords(
    row: pd.Series,
    document_embedding: np.ndarray,
    model: SentenceTransformer,
    kiwi: Kiwi | None,
    max_keywords: int = MAX_DISPLAY_KEYWORDS,
) -> list[str]:
    source_parts: list[str] = []
    for col in KEYWORD_SOURCE_COLUMNS:
        value = row.get(col, "")
        if not is_missing_like(value):
            source_parts.append(str(value))
    source_text = "\n".join(source_parts)

    if not clean_sentence(source_text):
        return []

    candidates: list[str] = []

    # capacity 계열은 이미 의미 단위가 깔끔한 경우가 많으므로 우선 반영
    for col in ["capacity_1", "capacity_all"]:
        for line in split_lines(row.get(col, "")):
            norm = normalize_keyword_candidate(line)
            if is_valid_keyword_candidate(norm):
                candidates.append(norm)

    candidates.extend(extract_keyword_candidates_regex(source_text))
    candidates.extend(extract_keyword_candidates_kiwi(source_text, kiwi))

    # fallback: 적성/요약 라인에서 너무 긴 문장 제외 후 짧은 명사구만 추가
    for col in ["aptitude", "summary"]:
        for line in split_lines(row.get(col, "")):
            line = normalize_keyword_candidate(line)
            if 2 <= len(line) <= 16 and is_valid_keyword_candidate(line):
                candidates.append(line)

    return rank_keyword_candidates(
        candidates=unique_keep_order(candidates),
        document_embedding=document_embedding,
        model=model,
        source_text=source_text,
        max_keywords=max_keywords,
    )



def build_topic_tags(row: pd.Series, max_tags: int = MAX_TOPIC_TAGS) -> list[str]:
    tags: list[str] = []
    tags.extend(split_job_names(row.get("similarJob", "")))
    tags.extend(collect_prefixed_values(row, MAJOR_PREFIX))
    tags.extend(get_simple_topic_tokens(row.get("summary", "")))

    clean_tags: list[str] = []
    for tag in tags:
        tag = normalize_keyword_candidate(tag)
        if not tag:
            continue
        if len(tag) > 28:
            continue
        if tag.lower() in KEYWORD_STOPWORDS:
            continue
        clean_tags.append(tag)

    clean_tags = unique_keep_order(clean_tags)
    return clean_tags[:max_tags]



def get_simple_topic_tokens(text) -> list[str]:
    result: list[str] = []
    for line in split_lines(text):
        for part in re.split(r"[,/|·]", line):
            part = normalize_keyword_candidate(part)
            if 2 <= len(part) <= 16 and is_valid_keyword_candidate(part):
                result.append(part)
    return unique_keep_order(result)


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

    input_texts = [f"passage: {text}" for text in df["embedding_text"].tolist()]

    print(f"[1/4] 모델 로드: {model_name}")
    model = SentenceTransformer(model_name)

    kiwi = None
    if Kiwi is not None:
        try:
            print("[1-1/4] Kiwi 로드")
            kiwi = Kiwi()
        except Exception:
            kiwi = None
    else:
        print("[안내] kiwipiepy가 설치되어 있지 않아 형태소 분석 없이 키워드 보강을 진행합니다.")

    print(f"[2/4] 임베딩 생성 시작: {len(input_texts):,}건")
    embeddings = model.encode(
        input_texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=normalize_embeddings,
    )

    if embeddings.dtype != np.float32:
        embeddings = embeddings.astype(np.float32)

    print("[3/4] 키워드/주제 태그 생성")
    display_keywords_list: list[list[str]] = []
    topic_tags_list: list[list[str]] = []
    for idx, row in df.iterrows():
        doc_emb = embeddings[idx]
        display_keywords = build_display_keywords(row, doc_emb, model, kiwi, max_keywords=MAX_DISPLAY_KEYWORDS)
        topic_tags = build_topic_tags(row, max_tags=MAX_TOPIC_TAGS)
        display_keywords_list.append(display_keywords)
        topic_tags_list.append(topic_tags)

    df["display_keywords"] = display_keywords_list
    df["display_keywords_text"] = df["display_keywords"].map(lambda x: " | ".join(x))
    df["display_keywords_json"] = df["display_keywords"].map(json.dumps)
    df["topic_tags"] = topic_tags_list
    df["topic_tags_text"] = df["topic_tags"].map(lambda x: " | ".join(x))
    df["topic_tags_json"] = df["topic_tags"].map(json.dumps)

    print("[4/4] 파일 저장")
    np.save(output_dir / "career_jobs_embeddings.npy", embeddings)

    meta_priority_cols = [
        "jobdicSeq",
        "job",
        "summary",
        "display_keywords",
        "display_keywords_text",
        "display_keywords_json",
        "topic_tags",
        "topic_tags_text",
        "topic_tags_json",
        "embedding_text",
    ]
    meta_cols = [c for c in meta_priority_cols if c in df.columns]

    df[meta_cols].to_parquet(output_dir / "career_jobs_embedding_meta.parquet", index=False)

    excel_df = df[meta_cols].copy()
    # Excel에는 리스트 직접 저장이 불편하므로 문자열 컬럼 중심으로 보조 저장
    for list_col in ["display_keywords", "topic_tags"]:
        if list_col in excel_df.columns:
            excel_df[list_col] = excel_df[list_col].map(lambda x: " | ".join(x))
    excel_df.to_excel(output_dir / "career_jobs_embedding_meta.xlsx", index=False)

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
        "keyword_source_columns": KEYWORD_SOURCE_COLUMNS,
        "has_kiwi": bool(kiwi is not None),
        "max_display_keywords": MAX_DISPLAY_KEYWORDS,
        "max_topic_tags": MAX_TOPIC_TAGS,
    }
    with open(output_dir / "embedding_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {output_dir}")
    print(f"임베딩 shape: {embeddings.shape}")
    print("예시 키워드:")
    preview_cols = [c for c in ["job", "display_keywords_text", "topic_tags_text"] if c in df.columns]
    print(df[preview_cols].head(5).to_string(index=False))
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
    print(result[[c for c in ["job", "display_keywords_text", "semantic_score"] if c in result.columns]])
