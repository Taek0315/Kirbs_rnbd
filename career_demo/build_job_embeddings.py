from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Iterable

import numpy as np
import pandas as pd

try:
    from sentence_transformers import SentenceTransformer
except ImportError as exc:
    raise SystemExit(
        "sentence-transformers가 설치되어 있지 않습니다.\n"
        "아래 패키지를 먼저 설치해 주세요.\n"
        "pip install -U sentence-transformers openpyxl pandas numpy"
    ) from exc


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

MAJOR_PREFIX = "major_"
CONTACT_PREFIX = "contact_"
MAX_DISPLAY_KEYWORDS = 10
MAX_TOPIC_TAGS = 12


# =========================
# 키워드 추출 사전
# =========================
TRAIT_KEYWORDS = [
    "문제해결능력", "문제 해결 능력", "의사소통능력", "의사소통 능력", "자료분석능력", "자료 분석 능력",
    "수리능력", "수리 능력", "분석적 사고", "논리적 사고", "공간 지각력", "공간지각력",
    "판단력", "분석력", "창의력", "창의성", "응용력", "응용능력", "순발력",
    "협동심", "대인관계", "사교성", "사회성", "정직성", "신뢰성", "책임감",
    "리더십", "집중력", "인내심", "꼼꼼함", "성실성", "도전정신", "성취욕",
    "배려심", "봉사심", "희생정신", "객관성", "외국어 실력", "프로그래밍 능력", "기획력", "기술력", "전문지식",
]
TRAIT_KEYWORDS = sorted(set(TRAIT_KEYWORDS), key=len, reverse=True)

ACTION_WORDS = [
    "보조", "관리", "개발", "분석", "진단", "상담", "자문", "조사", "평가", "측정", "기록",
    "소독", "살균", "설계", "기획", "연구", "검사", "투약", "치료", "수립", "제시", "조율",
    "제작", "운영", "교육", "프로그래밍", "디자인", "모델링", "관찰", "전달", "수납", "접수",
    "회복", "유지", "증진", "상태파악", "수행", "처리", "컨설팅", "지도",
]
ACTION_WORDS = sorted(set(ACTION_WORDS), key=len, reverse=True)

BAD_WORDS = {
    "환자", "해당", "각종", "여러", "다양한", "관련", "대한", "있는", "되는", "하는", "위해",
    "경우", "통해", "중심", "한다", "수행", "업무", "사람", "분야", "직업", "직무", "정보",
    "내용", "방법", "과정", "정도", "자료", "워크넷",
}

SPECIAL_PATTERNS = [
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


# =========================
# 전처리
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
    text = text.replace("_x000D_", "\n")
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
    return text.strip(" ,;:-")


def split_lines(text) -> list[str]:
    if is_missing_like(text):
        return []
    text = normalize_whitespace(str(text))
    if not text:
        return []
    text = re.sub(r"\n\s*[-•·▪■]\s*", "\n", text)
    text = re.sub(r"^\s*[-•·▪■]\s*", "", text)

    parts: list[str] = []
    for part in re.split(r"\n|;", text):
        part = clean_sentence(part)
        if part:
            parts.append(part)
    return unique_keep_order(parts)


def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen = set()
    result: list[str] = []
    for item in items:
        value = clean_sentence(str(item))
        if not value:
            continue
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def refine_keyword_phrase(text: str) -> str:
    text = normalize_whitespace(str(text))
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
    if text in BAD_WORDS:
        return False
    if any(tok in BAD_WORDS for tok in tokens):
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


def split_job_names(text) -> list[str]:
    if is_missing_like(text):
        return []
    return unique_refined_keywords([part for part in re.split(r",|/|;|\n|\|", str(text)) if refine_keyword_phrase(part)])


def collect_prefixed_values(row: pd.Series, prefix: str) -> list[str]:
    values: list[str] = []
    for col in row.index:
        if str(col).startswith(prefix):
            value = row.get(col)
            if not is_missing_like(value):
                values.extend([part for part in re.split(r",|/|;|\n", str(value)) if refine_keyword_phrase(part)])
    return unique_refined_keywords(values)


# =========================
# 키워드 생성
# =========================
def extract_trait_keywords(row: pd.Series) -> list[str]:
    source = f"{row.get('aptitude', '')}\n{row.get('summary', '')}"
    output: list[str] = []

    normalize_map = {
        "문제 해결 능력": "문제해결능력",
        "의사소통 능력": "의사소통능력",
        "자료 분석 능력": "자료분석능력",
        "수리 능력": "수리능력",
        "공간지각력": "공간 지각력",
    }

    for keyword in TRAIT_KEYWORDS:
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
            if part in TRAIT_KEYWORDS or part in {"협조성", "배려심", "봉사심", "희생정신", "혁신성"}:
                output.append(part)

    return unique_refined_keywords(output)


def extract_action_keywords(row: pd.Series, limit: int = 8) -> list[str]:
    summary = str(row.get("summary", ""))
    output: list[str] = []

    for line in split_lines(summary):
        cleaned = refine_keyword_phrase(line)
        for pattern, keyword in SPECIAL_PATTERNS:
            if re.search(pattern, cleaned):
                output.append(keyword)

    action_group = "|".join(re.escape(word) for word in ACTION_WORDS)
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
    special_keywords = [keyword for _, keyword in SPECIAL_PATTERNS]

    def sort_key(value: str) -> tuple[int, int]:
        score = 0
        if value in special_keywords:
            score += 8
        if "·" in value:
            score += 3
        if any(action in value for action in ACTION_WORDS):
            score += 2
        if len(value) <= 12:
            score += 1
        return (-score, len(value))

    return sorted(output, key=sort_key)[:limit]


def build_display_keywords(row: pd.Series, max_keywords: int = MAX_DISPLAY_KEYWORDS) -> list[str]:
    action_keywords = extract_action_keywords(row, limit=8)
    trait_keywords = extract_trait_keywords(row)

    output: list[str] = []
    for keyword in action_keywords + trait_keywords:
        if keyword not in output:
            output.append(keyword)
        if len(output) >= max_keywords:
            return output

    for keyword in split_job_names(row.get("similarJob", "")) + collect_prefixed_values(row, MAJOR_PREFIX):
        if keyword not in output:
            output.append(keyword)
        if len(output) >= max_keywords:
            return output

    return output


def build_topic_tags(row: pd.Series, max_tags: int = MAX_TOPIC_TAGS) -> list[str]:
    return (split_job_names(row.get("similarJob", "")) + collect_prefixed_values(row, MAJOR_PREFIX))[:max_tags]


# =========================
# 임베딩 문서 생성
# =========================
def build_document_text(row: pd.Series) -> str:
    labels = {
        "summary": "직무 요약",
        "similarJob": "유사 직업",
        "aptitude": "적성",
        "empway": "진출 경로",
        "prepareway": "준비 방법",
        "training": "훈련",
        "certification": "자격",
        "employment": "고용 전망",
        "job_possibility": "발전 가능성",
        "capacity_1": "핵심 역량",
        "capacity_all": "전체 역량",
    }

    blocks: list[str] = []
    job = clean_sentence(row.get("job", ""))
    if job:
        blocks.append(f"직업명: {job}")

    for col in TEXT_COLUMNS:
        if col == "job":
            continue
        lines = split_lines(row.get(col, ""))
        if not lines:
            continue
        label = labels.get(col, col)
        blocks.append(f"{label}: " + " | ".join(lines))

    majors = collect_prefixed_values(row, MAJOR_PREFIX)
    if majors:
        blocks.append("관련 전공: " + " | ".join(majors))

    contacts = collect_prefixed_values(row, CONTACT_PREFIX)
    if contacts:
        blocks.append("추가 정보: " + " | ".join(contacts))

    return "\n".join(blocks).strip()


# =========================
# 실행
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

    print(f"[2/4] 임베딩 생성 시작: {len(input_texts):,}건")
    embeddings = model.encode(
        input_texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=normalize_embeddings,
    ).astype(np.float32)

    print("[3/4] 키워드/주제 태그 생성")
    df["display_keywords"] = df.apply(build_display_keywords, axis=1)
    df["display_keywords_text"] = df["display_keywords"].map(lambda x: " | ".join(x))
    df["display_keywords_json"] = df["display_keywords"].map(lambda x: json.dumps(x, ensure_ascii=False))

    df["topic_tags"] = df.apply(build_topic_tags, axis=1)
    df["topic_tags_text"] = df["topic_tags"].map(lambda x: " | ".join(x))
    df["topic_tags_json"] = df["topic_tags"].map(lambda x: json.dumps(x, ensure_ascii=False))

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

    excel_df = df[meta_cols].copy()
    for list_col in ["display_keywords", "topic_tags"]:
        if list_col in excel_df.columns:
            excel_df[list_col] = excel_df[list_col].map(lambda x: " | ".join(x))

    excel_df.to_excel(output_dir / "career_jobs_embedding_meta.xlsx", index=False)

    try:
        df[meta_cols].to_parquet(output_dir / "career_jobs_embedding_meta.parquet", index=False)
    except Exception:
        print("[안내] pyarrow 또는 fastparquet이 없어 parquet 저장은 건너뛰었습니다. xlsx 메타 파일은 정상 저장되었습니다.")

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
        "keyword_source_columns": ["summary", "aptitude", "similarJob"] + [MAJOR_PREFIX + "*"],
        "keyword_method": "rule_based_action_trait_v2",
        "max_display_keywords": MAX_DISPLAY_KEYWORDS,
        "max_topic_tags": MAX_TOPIC_TAGS,
    }
    with open(output_dir / "embedding_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {output_dir}")
    print(f"임베딩 shape: {embeddings.shape}")
    preview_cols = [c for c in ["job", "display_keywords_text", "topic_tags_text"] if c in excel_df.columns]
    print(excel_df[preview_cols].head(10).to_string(index=False))
    return df, embeddings


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
    cols = [c for c in ["job", "display_keywords_text", "semantic_score"] if c in result.columns]
    print(result[cols].to_string(index=False))
