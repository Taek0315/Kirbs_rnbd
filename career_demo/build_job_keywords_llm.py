from __future__ import annotations

"""
LLM/ML 기반 직업 카드 키워드 생성기

목적:
- Streamlit 앱 런타임에서 키워드를 즉석 추출하지 않고,
  career_jobs.xlsx 기준으로 카드 표시용 키워드를 사전 생성한다.
- 생성 결과는 embedding_output/career_jobs_embedding_meta.xlsx에 저장되며,
  search_fixed_complete_v7.py가 llm_keywords_json/list를 최우선으로 읽는다.

권장 실행:
1) LLM 서버 또는 OpenAI-compatible endpoint가 있는 경우
   python build_job_keywords_llm.py --mode llm --input career_jobs.xlsx --output-dir embedding_output

   환경변수:
   - LLM_BASE_URL   예: http://localhost:11434/v1 또는 사내 LLM gateway URL
   - LLM_MODEL      예: 사내 배포 모델명
   - LLM_API_KEY    필요한 경우만 설정

2) LLM endpoint가 없는 경우 fallback 생성
   python build_job_keywords_llm.py --mode fallback --input career_jobs.xlsx --output-dir embedding_output

주의:
- 운영/배포 서버에서 LLM을 호출하지 않는다.
- 키워드 생성은 데이터 갱신 시 연구/개발 PC에서 1회 실행한다.
"""

from pathlib import Path
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Iterable

import pandas as pd


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

DEFAULT_MAX_KEYWORDS = 8

BAD_KEYWORD_PARTS = {
    "이에 포함된",
    "이를 포함한",
    "환자가",
    "환자의",
    "사용자가",
    "사용자의",
    "업무를",
    "업무에",
    "관련된",
    "관련한",
    "다양한",
    "여러",
    "각종",
    "정보",
    "자료",
    "내용",
    "설명",
}

BAD_EXACT = {
    "직업", "직무", "업무", "분야", "관련", "정보", "자료", "내용", "능력", "역량",
    "환자", "사용자", "기업", "학생", "교육", "시스템", "프로그램",
}

ACTION_NOUNS = [
    "기획", "설계", "개발", "운영", "관리", "분석", "평가", "상담", "지도", "교육",
    "훈련", "조사", "연구", "진단", "검사", "측정", "보조", "지원", "제작", "편집",
    "감독", "점검", "정비", "시공", "품질관리", "마케팅", "영업", "컨설팅",
]

COMMON_DOMAIN_PATTERNS = [
    (r"온라인|사이버|원격|이러닝|e-?learning", "온라인 교육"),
    (r"교육과정|교육 과정|교수", "교육과정"),
    (r"콘텐츠|컨텐츠", "콘텐츠"),
    (r"프로그램", "프로그램"),
    (r"환경", "환경"),
    (r"의료|병원|환자|진료|간호", "의료"),
    (r"데이터|자료|통계|분석", "데이터"),
    (r"소프트웨어|프로그램|시스템|컴퓨터|프로그래밍", "소프트웨어"),
    (r"디자인|시각|그래픽", "디자인"),
    (r"상담|심리|치료", "상담"),
    (r"경영|기업|조직|사업", "경영"),
    (r"기계|장비|설비", "기계"),
    (r"전기|전자|회로", "전기·전자"),
    (r"건축|건설|시공", "건설"),
]


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
    return text.strip(" ,.;:-")


def split_lines(text) -> list[str]:
    if is_missing_like(text):
        return []
    text = normalize_whitespace(str(text))
    if not text:
        return []
    text = re.sub(r"\n\s*[-•·▪■]\s*", "\n", text)
    text = re.sub(r"^\s*[-•·▪■]\s*", "", text)
    out: list[str] = []
    for part in re.split(r"\n|;", text):
        part = clean_sentence(part)
        if not part:
            continue
        if "," in part and len(part) < 100:
            out.extend([clean_sentence(p) for p in part.split(",") if clean_sentence(p)])
        else:
            out.append(part)
    return unique_keep_order(out)


def split_job_names(text) -> list[str]:
    if is_missing_like(text):
        return []
    text = normalize_whitespace(str(text))
    text = re.sub(r"\s*(?:\n|;|/|\||,|，)\s*", "\n", text)
    return unique_keep_order([
        re.sub(r"^\d+[.)]\s*", "", clean_sentence(x))
        for x in text.split("\n")
        if clean_sentence(x)
    ])


def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        value = clean_sentence(str(item))
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def collect_prefixed_values(row: pd.Series, prefix: str) -> list[str]:
    values: list[str] = []
    for col in row.index:
        if str(col).startswith(prefix):
            values.extend(split_lines(row.get(col, "")))
    return unique_keep_order(values)


def build_context(row: pd.Series, max_chars: int = 2400) -> str:
    labels = {
        "job": "직업명",
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
    blocks = []
    for col in TEXT_COLUMNS:
        if col not in row.index:
            continue
        lines = split_lines(row.get(col, ""))
        if lines:
            blocks.append(f"{labels.get(col, col)}: " + " / ".join(lines[:5]))
    majors = collect_prefixed_values(row, MAJOR_PREFIX)
    if majors:
        blocks.append("관련 전공: " + " / ".join(majors[:12]))
    text = "\n".join(blocks)
    return text[:max_chars]


def normalize_keyword(keyword: str) -> str:
    keyword = clean_sentence(keyword)
    keyword = re.sub(r"^[#ㆍ·•\-\s]+", "", keyword)
    keyword = re.sub(r"\([^)]*\)", "", keyword)
    keyword = re.sub(r"\[[^\]]*\]", "", keyword)
    keyword = re.sub(r"\s+", " ", keyword).strip(" ,.;:-")
    keyword = keyword.replace(" ,", ",")
    keyword = re.sub(r"^(?:환자의|환자|사용자의|사용자|기업의|기업|학생의|학생)\s+", "", keyword)
    keyword = re.sub(r"\s*(?:업무|활동|작업)$", "", keyword).strip()
    return keyword


def is_valid_keyword(keyword: str) -> bool:
    keyword = normalize_keyword(keyword)
    if not keyword:
        return False
    if keyword in BAD_EXACT:
        return False
    if len(keyword) < 2 or len(keyword) > 22:
        return False
    if any(part in keyword for part in BAD_KEYWORD_PARTS):
        return False
    if re.search(r"(하는|하며|하고|하여|되는|있는|같은|위한|대한|관련된|관련한)$", keyword):
        return False
    if re.search(r"(은|는|이|가|을|를|의|에|에서|으로|로)$", keyword):
        return False
    if len(keyword.split()) > 4:
        return False
    return True


def validate_keywords(keywords: Iterable[str], max_keywords: int = DEFAULT_MAX_KEYWORDS) -> list[str]:
    out: list[str] = []
    for kw in keywords:
        kw = normalize_keyword(str(kw))
        if not is_valid_keyword(kw):
            continue
        if any(kw != kept and (kw in kept or kept in kw) for kept in out):
            continue
        out.append(kw)
        if len(out) >= max_keywords:
            break
    return out


def fallback_keywords(row: pd.Series, max_keywords: int = DEFAULT_MAX_KEYWORDS) -> list[str]:
    """
    LLM endpoint가 없을 때 사용하는 보조 생성기.
    완전한 LLM 품질은 아니지만 문장 조각을 최대한 피하고
    '도메인 + 행위' 형태를 우선한다.
    """
    text = build_context(row, max_chars=4000)
    job = clean_sentence(row.get("job", ""))
    candidates: list[str] = []

    # 1) 유사 직업은 대체로 카드 태그로 안전하다.
    candidates.extend(split_job_names(row.get("similarJob", ""))[:3])

    # 2) 도메인 + 행위 조합 생성
    domains = []
    for pattern, label in COMMON_DOMAIN_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            domains.append(label)
    domains = unique_keep_order(domains)[:4]

    for domain in domains:
        for action in ACTION_NOUNS:
            if action in text:
                if domain == action:
                    candidates.append(domain)
                else:
                    candidates.append(f"{domain} {action}")

    # 3) 자주 등장하는 목적어 + 행위 패턴
    compact = re.sub(r"\s+", " ", text)
    for obj, action in re.findall(r"([가-힣A-Za-z0-9· ]{2,18})(?:을|를|의)?\s*(기획|설계|개발|운영|관리|분석|평가|상담|지도|교육|조사|연구|보조|지원|제작|편집|점검|정비|시공)", compact):
        obj = normalize_keyword(obj)
        obj = re.sub(r"^(?:각종|다양한|여러|관련|이에 포함된)\s*", "", obj)
        if 2 <= len(obj) <= 14:
            candidates.append(f"{obj} {action}")

    # 4) 관련 전공은 후순위 fallback
    candidates.extend(collect_prefixed_values(row, MAJOR_PREFIX)[:4])

    return validate_keywords(candidates, max_keywords=max_keywords)


def extract_json_object(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError(f"JSON 객체를 찾지 못했습니다: {text[:200]}")
    return json.loads(match.group(0))


def call_openai_compatible_chat(
    base_url: str,
    model: str,
    api_key: str,
    messages: list[dict],
    timeout: int = 60,
    temperature: float = 0.1,
) -> str:
    base_url = base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw)
    return parsed["choices"][0]["message"]["content"]


def llm_keywords_for_row(
    row: pd.Series,
    base_url: str,
    model: str,
    api_key: str = "",
    max_keywords: int = DEFAULT_MAX_KEYWORDS,
    retries: int = 2,
    sleep_sec: float = 0.7,
) -> list[str]:
    context = build_context(row)
    job = clean_sentence(row.get("job", ""))

    system_prompt = (
        "너는 한국어 직업정보 서비스의 카드 태그를 만드는 편집자다. "
        "직무 설명을 읽고 사용자가 직업의 핵심 업무를 바로 이해할 수 있는 짧은 한국어 키워드를 만든다. "
        "반드시 JSON만 출력한다."
    )
    user_prompt = f"""
직업명: {job}

직업 정보:
{context}

요구사항:
- keywords 배열에 {max_keywords}개 이내로 작성
- 각 키워드는 2~18자 내외의 명사구 또는 '대상+행위' 구문
- 좋은 예: "교육과정 기획", "온라인 교육 운영", "학습 콘텐츠 개발", "진료 보조", "데이터 분석"
- 나쁜 예: "이에 포함된 콘텐츠 개발", "환자의 체온", "사용자가 원하는", "관련 업무", "다양한 시스템"
- 조사로 끝나는 표현 금지: 은/는/이/가/을/를/의/에/으로
- 직업명 자체만 반복하지 말 것
- 원문에 없는 과장된 기술명이나 허위 키워드 생성 금지

출력 형식:
{{"keywords":["키워드1","키워드2"]}}
""".strip()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    for attempt in range(retries + 1):
        try:
            content = call_openai_compatible_chat(
                base_url=base_url,
                model=model,
                api_key=api_key,
                messages=messages,
            )
            obj = extract_json_object(content)
            keywords = obj.get("keywords", [])
            if not isinstance(keywords, list):
                raise ValueError("keywords가 배열이 아닙니다.")
            validated = validate_keywords(keywords, max_keywords=max_keywords)
            if validated:
                return validated
            raise ValueError(f"유효 키워드 없음: {keywords}")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(sleep_sec * (attempt + 1))

    print(f"[LLM 실패] {job}: {last_error}")
    return fallback_keywords(row, max_keywords=max_keywords)


def build_keyword_meta(
    input_file: Path,
    output_dir: Path,
    mode: str = "auto",
    max_keywords: int = DEFAULT_MAX_KEYWORDS,
    checkpoint_every: int = 25,
    force: bool = False,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(input_file) if input_file.suffix.lower() in {".xlsx", ".xls", ".xlsm"} else pd.read_csv(input_file)
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "job" not in df.columns:
        raise ValueError("입력 파일에 'job' 컬럼이 없습니다.")

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda x: normalize_whitespace(x) if not is_missing_like(x) else "")

    df["job"] = df["job"].astype(str).str.strip()
    df = df[df["job"] != ""].reset_index(drop=True)

    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()

    use_llm = mode == "llm" or (mode == "auto" and base_url and model)
    if mode == "llm" and not (base_url and model):
        raise RuntimeError("LLM 모드에는 LLM_BASE_URL과 LLM_MODEL 환경변수가 필요합니다.")

    if use_llm:
        print(f"[모드] LLM keyword extraction: base={base_url}, model={model}")
    else:
        print("[모드] fallback keyword extraction: LLM endpoint 미사용")

    llm_keywords_list = []
    for idx, row in df.iterrows():
        job = clean_sentence(row.get("job", ""))
        if use_llm:
            keywords = llm_keywords_for_row(
                row=row,
                base_url=base_url,
                model=model,
                api_key=api_key,
                max_keywords=max_keywords,
            )
        else:
            keywords = fallback_keywords(row, max_keywords=max_keywords)

        llm_keywords_list.append(keywords)
        print(f"[{idx+1:03d}/{len(df):03d}] {job}: {' | '.join(keywords)}")

        if checkpoint_every and (idx + 1) % checkpoint_every == 0:
            tmp = df.iloc[: idx + 1].copy()
            tmp["llm_keywords"] = llm_keywords_list
            tmp["llm_keywords_text"] = tmp["llm_keywords"].map(lambda x: " | ".join(x))
            tmp["llm_keywords_json"] = tmp["llm_keywords"].map(lambda x: json.dumps(x, ensure_ascii=False))
            tmp.to_excel(output_dir / "_keyword_generation_checkpoint.xlsx", index=False)

    df["llm_keywords"] = llm_keywords_list
    df["llm_keywords_text"] = df["llm_keywords"].map(lambda x: " | ".join(x))
    df["llm_keywords_json"] = df["llm_keywords"].map(lambda x: json.dumps(x, ensure_ascii=False))

    # search.py 기존 로더와 호환되도록 display_keywords에도 동일하게 기록한다.
    df["display_keywords"] = df["llm_keywords_text"]
    df["display_keywords_text"] = df["llm_keywords_text"]
    df["display_keywords_json"] = df["llm_keywords_json"]

    topic_tags = []
    for _, row in df.iterrows():
        tags = []
        tags.extend(split_job_names(row.get("similarJob", "")))
        tags.extend(collect_prefixed_values(row, MAJOR_PREFIX))
        topic_tags.append(validate_keywords(tags, max_keywords=12))

    df["topic_tags"] = topic_tags
    df["topic_tags_text"] = df["topic_tags"].map(lambda x: " | ".join(x))
    df["topic_tags_json"] = df["topic_tags"].map(lambda x: json.dumps(x, ensure_ascii=False))

    meta_cols = [
        "jobdicSeq",
        "job",
        "summary",
        "llm_keywords",
        "llm_keywords_text",
        "llm_keywords_json",
        "display_keywords",
        "display_keywords_text",
        "display_keywords_json",
        "topic_tags",
        "topic_tags_text",
        "topic_tags_json",
    ]
    meta_cols = [c for c in meta_cols if c in df.columns]
    meta = df[meta_cols].copy()

    for list_col in ["llm_keywords", "topic_tags"]:
        if list_col in meta.columns:
            meta[list_col] = meta[list_col].map(lambda x: " | ".join(x) if isinstance(x, list) else str(x))

    out_xlsx = output_dir / "career_jobs_embedding_meta.xlsx"
    out_csv = output_dir / "career_jobs_embedding_meta.csv"
    meta.to_excel(out_xlsx, index=False)
    meta.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print(f"\n저장 완료: {out_xlsx}")
    print(f"보조 CSV: {out_csv}")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("career_jobs.xlsx"))
    parser.add_argument("--output-dir", type=Path, default=Path("embedding_output"))
    parser.add_argument("--mode", choices=["auto", "llm", "fallback"], default="auto")
    parser.add_argument("--max-keywords", type=int, default=DEFAULT_MAX_KEYWORDS)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    build_keyword_meta(
        input_file=args.input,
        output_dir=args.output_dir,
        mode=args.mode,
        max_keywords=args.max_keywords,
        checkpoint_every=args.checkpoint_every,
        force=args.force,
    )


if __name__ == "__main__":
    main()
