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
    spreadsheet_id = st.secrets["sheets"]["spreadsheet_id"]
    worksheet_name = st.secrets["sheets"]["worksheet_name"]

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
    )
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(spreadsheet_id)
    worksheet = sheet.worksheet(worksheet_name)

    header = _ensure_header(worksheet, wide_row.keys())
    values = [wide_row.get(col, "") for col in header]
    worksheet.append_row(values, value_input_option="RAW")
