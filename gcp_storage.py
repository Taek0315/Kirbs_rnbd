from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


def save_to_gcp(df: pd.DataFrame) -> None:
    """Save survey responses to a future GCP backend.

    TODO:
    - Google Sheets via gspread + service account JSON in Streamlit secrets
    - BigQuery insert
    - GCS upload
    """

    gcp_env_vars = [
        "GCP_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GCP_SERVICE_ACCOUNT_JSON",
    ]
    has_gcp_config = any(os.getenv(key) for key in gcp_env_vars)

    if not has_gcp_config:
        output_path = Path("usability_survey_responses_local.csv")
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return

    raise NotImplementedError("GCP 저장 백엔드가 아직 구성되지 않았습니다.")
