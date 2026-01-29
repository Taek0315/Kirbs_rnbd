from __future__ import annotations

from typing import Iterable

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


def _get_header_row(worksheet: gspread.Worksheet) -> list[str]:
    header = worksheet.row_values(1)
    return [col.strip() for col in header if col is not None]


def _ensure_header(
    worksheet: gspread.Worksheet,
    desired_header: Iterable[str],
) -> list[str]:
    desired = list(desired_header)
    header = _get_header_row(worksheet)

    if not header:
        worksheet.update("A1", [desired])
        return desired

    missing = [col for col in desired if col not in header]
    if missing:
        header = header + missing
        worksheet.update("A1", [header])

    return header


def append_one_row_to_sheet(wide_row: dict) -> None:
    service_account_info = st.secrets["gcp_service_account"]
    sheet_id = st.secrets["survey"]["sheet_id"]

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
    )
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.get_worksheet(0)
    if worksheet is None:
        raise ValueError("No worksheet found in the spreadsheet.")

    header = _ensure_header(worksheet, wide_row.keys())
    values = [wide_row.get(col, "") for col in header]
    worksheet.append_row(values, value_input_option="RAW")
