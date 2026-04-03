import re
import pandas as pd

BASE_COLUMNS = [
    "job",
    "summary",
    "similarJob",
    "aptitude",
    "empway",
    "employment",
    "salery",
    "prepareway",
    "training",
    "certification",
    "job_possibility",
]

CONTACT_COLUMNS = [f"contact_{i}" for i in range(1, 8)]
MAJOR_COLUMNS = [f"major_{i}" for i in range(1, 22)]


def clean_text(value):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def collect_nonempty_values(row, columns):
    values = []
    for col in columns:
        if col in row:
            value = clean_text(row[col])
            if value:
                values.append(value)
    return values


def load_job_data(file_source):
    df = pd.read_excel(file_source)

    for col in BASE_COLUMNS + CONTACT_COLUMNS + MAJOR_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    for col in BASE_COLUMNS + CONTACT_COLUMNS + MAJOR_COLUMNS:
        df[col] = df[col].apply(clean_text)

    df["contact_list"] = df.apply(lambda row: collect_nonempty_values(row, CONTACT_COLUMNS), axis=1)
    df["major_list"] = df.apply(lambda row: collect_nonempty_values(row, MAJOR_COLUMNS), axis=1)

    df["search_text"] = (
        df["job"].fillna("") + " " +
        df["summary"].fillna("") + " " +
        df["similarJob"].fillna("") + " " +
        df["prepareway"].fillna("") + " " +
        df["empway"].fillna("") + " " +
        df["job_possibility"].fillna("") + " " +
        df["aptitude"].fillna("")
    ).str.lower()

    df = df.drop_duplicates(subset=["job"]).reset_index(drop=True)
    return df


def score_job(row, query: str) -> int:
    q = query.strip().lower()
    if not q:
        return 0

    job = row["job"].lower()
    search_text = row["search_text"]

    score = 0
    if job == q:
        score += 100
    if q in job:
        score += 50
    if q in search_text:
        score += 20

    tokens = [token for token in q.split() if token]
    for token in tokens:
        if token == job:
            score += 30
        elif token in job:
            score += 15
        elif token in search_text:
            score += 5

    return score


def search_jobs(df: pd.DataFrame, query: str, top_n: int = 30) -> pd.DataFrame:
    q = query.strip()

    if not q:
        return df[["job"]].sort_values("job").head(top_n)

    result = df.copy()
    result["score"] = result.apply(lambda row: score_job(row, q), axis=1)
    result = result[result["score"] > 0].sort_values(["score", "job"], ascending=[False, True])

    return result.head(top_n)


def get_job_detail(df: pd.DataFrame, job_name: str):
    matched = df[df["job"] == job_name]
    if matched.empty:
        return None
    return matched.iloc[0].to_dict()