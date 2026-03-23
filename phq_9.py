# -*- coding: utf-8 -*-
import os
import uuid
from datetime import datetime, timezone, timedelta
from textwrap import dedent
from typing import Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components


# ──────────────────────────────────────────────────────────────────────────────
# 앱 상태 초기화
# ──────────────────────────────────────────────────────────────────────────────
def _reset_to_survey() -> None:
    """앱 상태 초기화 후 인트로로 이동"""
    st.session_state.page = "intro"
    st.session_state.consent = False
    st.session_state.consent_ts = None
    st.session_state.answers = {}
    st.session_state.functional = None
    st.session_state.summary = None
    st.session_state.db_insert_done = False
    st.session_state.examinee = {
        "user_id": str(uuid.uuid4()),
        "name": "",
        "gender": "",
        "age": "",
        "region": "",
        "email": "",
        "phone": "",
    }
    for i in range(1, 10):
        st.session_state.pop(f"q{i}", None)
    st.session_state.pop("functional-impact", None)
    st.session_state.pop("consent_checkbox", None)


# ──────────────────────────────────────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="PHQ-9 자기보고 검사", page_icon="📝", layout="centered")


# 색상 토큰
INK = "#0F172A"
SUBTLE = "#475569"
CARD_BG = "#FFFFFF"
APP_BG = "#F6F8FB"
BORDER = "#E2E8F0"
BRAND = "#2563EB"
ACCENT = "#DC2626"


# ──────────────────────────────────────────────────────────────────────────────
# 전역 스타일
# ──────────────────────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

:root {
  --bg: #F6F8FB;
  --surface: #FFFFFF;
  --surface-2: #F8FAFC;
  --surface-3: #F1F5F9;
  --ink: #0F172A;
  --muted: #475569;
  --muted-2: #64748B;
  --border: #DCE4EE;
  --border-strong: #CBD5E1;
  --shadow-sm: 0 4px 12px rgba(15, 23, 42, 0.04);
  --shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
  --radius-xl: 24px;
  --radius-lg: 18px;
  --radius-md: 14px;
  --control-height: 48px;
  --brand: #2563EB;
  --brand-600: #1D4ED8;
  --brand-50: rgba(37, 99, 235, 0.10);
  --danger: #DC2626;
  --danger-soft: #FFF7ED;
  --danger-border: #FDBA74;

  /* input/select 라이트 톤 */
  --field-bg: #F8FAFC;
  --field-bg-hover: #F1F5F9;
  --field-border: #D7E0EA;
  --field-text: #0F172A;
  --field-placeholder: transparent;
}

* { box-sizing: border-box; }

html, body {
  color-scheme: light !important;
  background: var(--bg);
  color: var(--ink);
  font-family: "Inter", "Noto Sans KR", system-ui, -apple-system, Segoe UI, Roboto, Apple SD Gothic Neo, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

body, p, div, span, li, button, label, input, textarea {
  font-family: "Inter", "Noto Sans KR", system-ui, -apple-system, Segoe UI, Roboto, Apple SD Gothic Neo, Helvetica, Arial, sans-serif !important;
}

[data-testid="stAppViewContainer"] { background: var(--bg) !important; }
[data-testid="block-container"] { max-width: 100%; padding: 0; margin: 0; }
[data-testid="stToolbar"], #MainMenu, header, footer { display: none !important; }

.app-wrap {
  max-width: 960px;
  margin: 0 auto;
  padding: 18px 24px 56px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.examinee-layout {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  align-items: center;
  margin-top: 6px;
}
.actions .stButton { margin: 0 !important; }
.actions-row { display: flex; gap: 12px; }

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow);
  padding: 28px;
}

.card.compact {
  padding: 20px;
  border-radius: var(--radius-lg);
}

.form-card {
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.card-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.badge {
  display: inline-flex;
  padding: 4px 12px;
  border-radius: 999px;
  background: var(--brand-50);
  color: var(--brand);
  font-weight: 800;
  font-size: 12px;
  border: 1px solid rgba(37, 99, 235, 0.25);
  width: fit-content;
}

.title-xl {
  font-size: 1.6rem;
  font-weight: 900;
  letter-spacing: -0.4px;
  color: var(--ink);
}
.title-lg {
  font-size: 1.15rem;
  font-weight: 850;
  color: var(--ink);
}
.section-title {
  font-size: 0.98rem;
  font-weight: 800;
  color: var(--ink);
}
.text {
  color: var(--muted);
  line-height: 1.7;
  font-size: 0.98rem;
}
.card p, .card li { line-height: 1.75 !important; }
.footer-note {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
  text-align: center;
}

.instruction-list {
  margin: 12px 0 0;
  padding-left: 18px;
  line-height: 1.7;
  color: var(--ink);
  font-size: 0.98rem;
}
.instruction-list li { margin-bottom: 8px; }
.question-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.question-text {
  font-weight: 700;
  font-size: 1rem;
  line-height: 1.6;
  color: var(--ink);
}
.question-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px !important;
}
.section-card { margin-bottom: 32px !important; }
.section-to-question { margin-bottom: 40px !important; }
.result-card { margin-bottom: 28px !important; }
.result-danger { margin-top: 36px !important; }
.result-actions { margin-top: 32px !important; }

.summary-layout {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
  margin-top: 18px;
}
.gauge-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 28px 22px 32px;
  text-align: center;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.gauge-circle {
  width: 210px;
  height: 210px;
  border-radius: 50%;
  margin: 0 auto 10px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.06);
}
.gauge-circle::after {
  content: "";
  position: absolute;
  inset: 24px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.06);
}
.gauge-inner {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.gauge-number {
  font-size: 3rem;
  font-weight: 900;
  line-height: 1;
  color: var(--ink);
}
.gauge-denom {
  font-size: 1rem;
  font-weight: 700;
  color: var(--muted);
}
.gauge-severity {
  display: inline-flex;
  padding: 6px 18px;
  border-radius: 999px;
  font-weight: 800;
  border: 1.5px solid currentColor;
  font-size: 1rem;
}
.narrative-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 26px 28px;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.narrative-title { font-weight: 800; font-size: 1rem; }
.functional-highlight {
  border-top: 1px solid var(--border);
  padding-top: 14px;
}
.functional-title {
  font-size: 0.9rem;
  color: var(--muted-2);
  font-weight: 700;
  margin-bottom: 6px;
}
.functional-value { font-size: 1.05rem; }
.domain-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 22px 24px;
  background: var(--surface-2);
  box-shadow: var(--shadow);
}
.domain-profile {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.domain-note {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
  color: var(--muted);
  line-height: 1.5;
}
.domain-row {
  display: grid;
  grid-template-columns: 1.4fr 2.2fr 0.6fr;
  gap: 16px;
  align-items: center;
}
.domain-title { font-weight: 700; font-size: 1rem; }
.domain-desc {
  font-size: 0.85rem;
  color: var(--muted);
  margin-top: 4px;
}
.domain-bar {
  position: relative;
  height: 14px;
  background: rgba(226, 232, 240, 0.9);
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid rgba(203, 213, 225, 0.9);
}
.domain-fill {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: var(--brand);
}
.domain-score { justify-self: end; font-weight: 700; }

.respondent-card-marker {
  width: 0;
  height: 0;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
  margin: 0;
  padding: 0;
  display: block;
}

/* only the bordered container wrapper */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 24px !important;
  box-shadow: var(--shadow) !important;
  padding: 28px 30px !important;
  overflow: hidden !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) > div {
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
}

.respondent-form-shell,
.respondent-form-header {
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.respondent-form-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 18px;
}

.respondent-form-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.respondent-form-title {
  font-size: 1.15rem;
  font-weight: 850;
  color: var(--ink);
  line-height: 1.4;
  width: 100%;
  max-width: 100%;
}

.respondent-form-desc {
  display: block;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  color: var(--muted);
  font-size: 0.98rem;
  line-height: 1.72;
  white-space: normal !important;
  word-break: keep-all !important;
  overflow-wrap: anywhere !important;
  line-break: auto;
}

.respondent-form-divider {
  width: 100%;
  max-width: 100%;
  height: 1px;
  background: var(--border);
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stHorizontalBlock"] {
  gap: 18px;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="column"] {
  padding: 0 !important;
  min-width: 0 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stTextInput"],
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stSelectbox"] {
  width: 100% !important;
  max-width: 100% !important;
  min-width: 0 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stTextInput"] > div,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stSelectbox"] > div {
  width: 100% !important;
  max-width: 100% !important;
  min-width: 0 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="base-input"],
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="select"] {
  width: 100% !important;
  max-width: 100% !important;
  min-width: 0 !important;
  min-height: var(--control-height) !important;
  border-radius: var(--radius-md) !important;
  background: var(--field-bg) !important;
  border: 1px solid var(--field-border) !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease !important;
  overflow: hidden !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="base-input"] > div,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="select"] > div,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="select"] > div > div {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  min-height: calc(var(--control-height) - 2px) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stWidgetLabel"],
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stWidgetLabel"] *,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) label[data-testid="stWidgetLabel"] p,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) label[data-testid="stWidgetLabel"] span,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stTextInput"] label,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stSelectbox"] label,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stTextInput"] p,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stSelectbox"] p,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stMarkdownContainer"] label,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stMarkdownContainer"] p {
  color: var(--ink) !important;
  font-weight: 700 !important;
  font-size: 0.96rem !important;
  line-height: 1.5 !important;
  opacity: 1 !important;
  white-space: normal !important;
  overflow-wrap: anywhere !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stWidgetLabel"] {
  margin-bottom: 8px !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) input,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) textarea,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="select"] input,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="base-input"] input {
  color: var(--field-text) !important;
  -webkit-text-fill-color: var(--field-text) !important;
  caret-color: var(--field-text) !important;
  background: transparent !important;
  width: 100% !important;
  min-width: 0 !important;
  opacity: 1 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) input::placeholder,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) textarea::placeholder {
  color: transparent !important;
  opacity: 0 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="base-input"]:hover,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="select"]:hover {
  background: var(--field-bg-hover) !important;
  border-color: #C5D0DD !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="base-input"]:focus-within,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="select"]:focus-within {
  border-color: var(--brand) !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
  background: #FFFFFF !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) input:focus,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) input:focus-visible,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) textarea:focus,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) textarea:focus-visible {
  outline: none !important;
  box-shadow: none !important;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="select"] span,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="select"] input,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="select"] svg,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="base-input"] span,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-baseweb="base-input"] input {
  color: var(--field-text) !important;
  fill: var(--field-text) !important;
  stroke: var(--field-text) !important;
  opacity: 1 !important;
  -webkit-text-fill-color: var(--field-text) !important;
}

.examinee-warning-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 4px;
  width: 100%;
  max-width: 100%;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) [data-testid="stAlert"] {
  width: 100% !important;
  max-width: 100% !important;
  overflow: hidden !important;
}

.examinee-actions {
  padding-top: 8px;
  width: 100%;
  max-width: 100%;
}

.warn {
  background: var(--danger-soft);
  border: 1px solid var(--danger-border);
  color: #7C2D12;
  border-radius: var(--radius-md);
  padding: 14px 18px;
  font-weight: 600;
}
[data-testid="stAlert"] {
  border-radius: var(--radius-md) !important;
  border: 1px solid var(--danger-border) !important;
  background: var(--danger-soft) !important;
  box-shadow: var(--shadow-sm) !important;
}
[data-testid="stAlert"] * {
  color: var(--ink) !important;
  opacity: 1 !important;
}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
  font-weight: 600 !important;
  line-height: 1.6 !important;
}

.safety-card {
  background: rgba(220, 38, 38, 0.10);
  border: 1px solid var(--danger);
  color: var(--ink);
  border-radius: var(--radius-xl);
  padding: 22px 24px;
  box-shadow: var(--shadow);
}
.safety-card .title-lg { color: var(--danger); }

.stButton { width: 100%; }
.stButton > button {
  width: 100% !important;
  min-height: var(--control-height) !important;
  height: var(--control-height) !important;
  border-radius: var(--radius-md) !important;
  border: 1px solid transparent !important;
  padding: 0 20px !important;
  font-size: 0.97rem !important;
  font-weight: 800 !important;
  white-space: nowrap !important;
  word-break: keep-all !important;
  box-shadow: none !important;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease !important;
}
.stButton > button:focus-visible {
  outline: none !important;
  box-shadow: 0 0 0 3px var(--brand-50) !important;
}
.stButton > button[kind="primary"] {
  background: var(--brand) !important;
  border-color: var(--brand) !important;
  color: #FFFFFF !important;
}
.stButton > button[kind="primary"] * {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--brand-600) !important;
  border-color: var(--brand-600) !important;
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22) !important;
}
.stButton > button:not([kind="primary"]) {
  background: var(--surface) !important;
  color: var(--brand) !important;
  border-color: var(--border-strong) !important;
}
.stButton > button:not([kind="primary"]) * {
  color: var(--brand) !important;
  -webkit-text-fill-color: var(--brand) !important;
}
.stButton > button:not([kind="primary"]):hover {
  border-color: var(--brand) !important;
  background: var(--surface-2) !important;
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08) !important;
}
.stButton > button:disabled {
  background: var(--surface-3) !important;
  color: var(--muted-2) !important;
  border-color: var(--border) !important;
  cursor: not-allowed !important;
  box-shadow: none !important;
}

[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] p,
[data-testid="stCheckbox"] span {
  color: var(--ink) !important;
  opacity: 1 !important;
  font-weight: 700 !important;
}
[data-testid="stCheckbox"] svg { color: var(--brand) !important; }
[data-testid="stCheckbox"] input:focus-visible + div {
  outline: none !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18) !important;
  border-radius: 6px;
}

[data-testid="stRadio"] { margin-top: 6px; }
[data-testid="stRadio"] > div[role="radiogroup"] {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 10px !important;
  align-items: center !important;
}
[data-testid="stRadio"] [role="radio"] {
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
  padding: 10px 16px !important;
  border-radius: 999px !important;
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  color: var(--ink) !important;
  font-weight: 700 !important;
  white-space: nowrap !important;
}
[data-testid="stRadio"] [role="radio"][aria-checked="true"] {
  background: var(--brand-50) !important;
  border-color: var(--brand) !important;
}
[data-testid="stRadio"] label,
[data-testid="stRadio"] label span {
  color: var(--ink) !important;
  opacity: 1 !important;
  white-space: nowrap !important;
}
[data-testid="stRadio"] label span {
  font-weight: 600 !important;
}
[data-testid="stRadio"] input:checked + div {
  outline: 2px solid rgba(37, 99, 235, 0.35) !important;
  border-radius: 999px !important;
}
[data-testid="stRadio"] div { color: var(--ink) !important; }
[data-testid="stRadio"] label:focus-within {
  border-color: var(--brand) !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18) !important;
}

@media (max-width: 768px) {
  .form-grid,
  .optional-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .app-wrap { padding: 0 18px 40px; }
  .card, .form-card { padding: 22px; }
  .section-panel { padding: 18px; }
  .gauge-circle { width: 180px; height: 180px; }
  .domain-row { grid-template-columns: 1fr; }
  .domain-score { justify-self: start; }

  div[data-testid="stVerticalBlockBorderWrapper"]:has(.respondent-card-marker) {
    padding: 22px 18px !important;
    border-radius: 20px !important;
  }

  .respondent-form-desc {
    font-size: 0.94rem;
    line-height: 1.68;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 상태 관리
# ──────────────────────────────────────────────────────────────────────────────
def init_state() -> None:
    if "page" not in st.session_state:
        st.session_state.page = "intro"
    if "consent" not in st.session_state:
        st.session_state.consent = False
    if "consent_ts" not in st.session_state:
        st.session_state.consent_ts = None
    if "answers" not in st.session_state:
        st.session_state.answers = {}
    if "functional" not in st.session_state:
        st.session_state.functional = None
    if "summary" not in st.session_state:
        st.session_state.summary = None
    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False
    if "examinee" not in st.session_state:
        st.session_state.examinee = {
            "user_id": str(uuid.uuid4()),
            "name": "",
            "gender": "",
            "age": "",
            "region": "",
            "email": "",
            "phone": "",
        }


# ──────────────────────────────────────────────────────────────────────────────
# 문항/선택지
# ──────────────────────────────────────────────────────────────────────────────
REGION_OPTIONS = [
    "수도권",
    "충청권",
    "강원권",
    "전라권",
    "경상권",
    "제주도",
]

GENDER_OPTIONS = [
    "남성",
    "여성",
    "기타",
    "응답하지 않음",
]

QUESTIONS = [
    {"no": 1, "ko": "일상적인 활동(예: 취미나 일상 일과 등)에 흥미나 즐거움을 거의 느끼지 못한다.", "domain": "흥미/즐거움 상실"},
    {"no": 2, "ko": "기분이 가라앉거나, 우울하거나, 희망이 없다고 느낀다.", "domain": "우울한 기분"},
    {"no": 3, "ko": "잠들기 어렵거나 자주 깨는 등 수면에 문제가 있었거나, 반대로 너무 많이 잠을 잔다.", "domain": "수면 문제"},
    {"no": 4, "ko": "평소보다 피곤함을 더 자주 느꼈거나, 기운이 거의 없다.", "domain": "피로/에너지 부족"},
    {"no": 5, "ko": "식욕이 줄었거나 반대로 평소보다 더 많이 먹는다.", "domain": "식욕 변화"},
    {"no": 6, "ko": "자신을 부정적으로 느끼거나, 스스로 실패자라고 생각한다.", "domain": "죄책감/무가치감"},
    {"no": 7, "ko": "일상생활 및 같은 일에 집중하는 것이 어렵다.", "domain": "집중력 저하"},
    {"no": 8, "ko": "다른 사람들이 눈치챌 정도로 매우 느리게 말하고 움직이거나, 반대로 평소보다 초조하고 안절부절 못한다.", "domain": "느려짐/초조함"},
    {"no": 9, "ko": "죽는 게 낫겠다는 생각하거나, 어떤 식으로든 자신을 해치고 싶은 생각이 든다.", "domain": "자살/자해 생각"},
]
LABELS = ["전혀 아님 (0)", "며칠 동안 (1)", "절반 이상 (2)", "거의 매일 (3)"]
LABEL2SCORE = {LABELS[0]: 0, LABELS[1]: 1, LABELS[2]: 2, LABELS[3]: 3}

COG_AFF = [1, 2, 6, 7, 9]
SOMATIC = [3, 4, 5, 8]

SEVERITY_PILL = {
    "정상": ("#DBEAFE", "#1E3A8A"),
    "경미": ("#FEF3C7", "#92400E"),
    "중등도": ("#FFE4E6", "#9F1239"),
    "중증": ("#FED7AA", "#9A3412"),
    "심각": ("#FECACA", "#7F1D1D"),
}

SEVERITY_ARC_COLOR = {
    "정상": "#16a34a",
    "경미": "#f59e0b",
    "중등도": "#f97316",
    "중증": "#f43f5e",
    "심각": "#b91c1c",
}

SEVERITY_GUIDANCE = {
    "정상": "현재 보고된 주관적 우울 증상은 정상 범위에 해당하며, 기본적인 자기 관리와 모니터링을 이어가시면 됩니다.",
    "경미": "경미 수준의 우울감이 보고되었습니다. 생활리듬 조정과 상담 자원 안내 등 예방적 개입을 고려할 수 있습니다.",
    "중등도": "임상적으로 의미 있는 중등도 수준으로, 정신건강 전문인의 평가와 치료적 개입을 권장합니다.",
    "중증": "중증 수준의 우울 증상이 보고되어, 신속한 전문 평가와 적극적인 치료 계획 수립이 필요합니다.",
    "심각": "심각 수준의 우울 증상이 보고되었습니다. 안전 평가를 포함한 즉각적인 전문 개입이 권고됩니다.",
}

DOMAIN_META = [
    {
        "name": "신체/생리 증상",
        "desc": "(수면, 피곤함, 식욕, 정신운동 문제)",
        "items": SOMATIC,
        "max": 12,
    },
    {
        "name": "인지/정서 증상",
        "desc": "(흥미저하, 우울감, 죄책감, 집중력, 자살사고)",
        "items": COG_AFF,
        "max": 15,
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────────────────────
def _sanitize_csv_value(v) -> str:
    if v is None:
        return ""
    s = str(v)
    s = s.replace("\n", " ").replace("\r", " ")
    s = s.replace(",", " ")
    return s.strip()


def dict_to_kv_csv(d: dict) -> str:
    if not isinstance(d, dict):
        return ""
    parts = []
    for k, v in d.items():
        parts.append(f"{_sanitize_csv_value(k)}={_sanitize_csv_value(v)}")
    return ",".join(parts)


def validate_name(name: str) -> Optional[str]:
    if not name.strip():
        return "이름을 입력해 주세요."
    return None


def validate_gender(gender: str) -> Optional[str]:
    if not gender.strip():
        return "성별을 선택해 주세요."
    if gender not in GENDER_OPTIONS:
        return "성별을 다시 선택해 주세요."
    return None


def validate_age(age: str) -> Optional[str]:
    value = age.strip()
    if not value:
        return "연령을 입력해 주세요."
    if not value.isdigit():
        return "연령은 숫자만 입력해 주세요."
    age_num = int(value)
    if not 1 <= age_num <= 120:
        return "연령은 1세부터 120세 사이로 입력해 주세요."
    return None


def validate_region(region: str) -> Optional[str]:
    if not region.strip():
        return "거주지역을 선택해 주세요."
    if region not in REGION_OPTIONS:
        return "거주지역을 다시 선택해 주세요."
    return None


def validate_phone(phone: str) -> Optional[str]:
    value = phone.strip()
    if not value:
        return None
    if not all(ch.isdigit() or ch == "-" for ch in value):
        return "연락처는 숫자와 하이픈(-)만 입력해 주세요."
    return None


def validate_email(email: str) -> Optional[str]:
    value = email.strip()
    if not value:
        return None
    if "@" not in value or "." not in value:
        return "이메일 형식이 올바르지 않습니다. (@와 . 포함)"
    return None


def normalize_phone(phone: str) -> str:
    value = phone.strip().replace(" ", "")
    cleaned = []
    last_dash = False
    for ch in value:
        if ch.isdigit():
            cleaned.append(ch)
            last_dash = False
        elif ch == "-" and not last_dash:
            cleaned.append(ch)
            last_dash = True
    return "".join(cleaned).strip("-")


def build_exam_data_phq9(payload: dict) -> dict:
    exam_name = (payload.get("exam", {}) or {}).get("title", "PHQ_9")

    meta = payload.get("meta", {}) or {}
    examinee = payload.get("examinee", {}) or {}
    consent_meta = {
        "consent": meta.get("consent"),
        "consent_ts": meta.get("consent_ts"),
        "started_ts": meta.get("started_ts") or meta.get("consent_ts") or "",
        "submitted_ts": meta.get("submitted_ts"),
        "version": (payload.get("exam", {}) or {}).get("version"),
        "respondent_id": examinee.get("user_id"),
    }

    answers = payload.get("answers", {}) or {}
    result = payload.get("result", {}) or {}

    domain_scores = result.get("domain_scores", {}) or {}
    result_flat = dict(result)
    if isinstance(domain_scores, dict):
        ds = "|".join([f"{_sanitize_csv_value(k)}:{_sanitize_csv_value(v)}" for k, v in domain_scores.items()])
        result_flat["domain_scores"] = ds

    return {
        "exam_name": _sanitize_csv_value(exam_name),
        "consent_col": dict_to_kv_csv(consent_meta),
        "examinee_col": dict_to_kv_csv(examinee),
        "answers_col": dict_to_kv_csv(answers),
        "result_col": dict_to_kv_csv(result_flat),
    }


def phq_severity(total: int) -> str:
    return (
        "정상" if total <= 4 else
        "경미" if total <= 9 else
        "중등도" if total <= 14 else
        "중증" if total <= 19 else
        "심각"
    )


def build_domain_profile_html(scores: List[int]) -> str:
    if len(scores) < 9:
        scores = (scores + [0] * 9)[:9]

    rows: List[str] = []
    for meta in DOMAIN_META:
        score = sum(scores[i - 1] for i in meta["items"])
        ratio = (score / meta["max"]) if meta["max"] else 0
        rows.append(
            dedent(
                f"""
                <div class="domain-row">
                  <div>
                    <div class="domain-title">{meta['name']}</div>
                    <div class="domain-desc">{meta['desc']}</div>
                  </div>
                  <div class="domain-bar">
                    <div class="domain-fill" style="width:{ratio*100:.1f}%"></div>
                  </div>
                  <div class="domain-score">{score} / {meta['max']}</div>
                </div>
                """
            ).strip()
        )
    rows_html = "\n".join(rows)
    note_html = '<div class="domain-note">※ 각 영역의 점수는 높을수록 해당 영역의 우울 관련 증상이 더 많이 보고되었음을 의미합니다.</div>'
    return (
        '<div class="domain-panel">\n'
        '  <div class="domain-profile">\n'
        f'{rows_html}\n'
        '  </div>\n'
        f'{note_html}\n'
        '</div>'
    )


def compose_narrative(total: int, severity: str, functional: Optional[str], item9: int) -> str:
    base = f"총점 {total}점(27점 만점)으로, [{severity}] 수준의 우울 증상이 보고되었습니다. {SEVERITY_GUIDANCE[severity]}"
    functional_text = (
        f" 응답자 보고에 따르면, 이러한 증상으로 인한 일·집안일·대인관계의 어려움은 ‘{functional}’ 수준입니다."
        if functional else ""
    )
    safety_text = (
        " 특히, 자해/자살 관련 사고(9번 문항)가 보고되어 이에 대한 즉각적인 관심과 평가가 매우 중요합니다."
        if item9 > 0 else ""
    )
    return base + functional_text + safety_text


def kst_iso_now() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).isoformat(timespec="seconds")


def get_dev_mode() -> bool:
    try:
        params = st.query_params
        return str(params.get("dev", "0")) == "1"
    except Exception:
        try:
            params = st.experimental_get_query_params()
            values = params.get("dev", ["0"])
            return str(values[0]) == "1"
        except Exception:
            return False


# ──────────────────────────────────────────────────────────────────────────────
# UI 헬퍼
# ──────────────────────────────────────────────────────────────────────────────
def render_question_item(question: Dict[str, object]) -> None:
    with st.container():
        st.markdown(
            dedent(
                f"""
                <div class="card compact question-card">
                  <div class="question-header">
                    <div class="badge">문항 {question['no']}</div>
                    <div class="question-text">{question['ko']}</div>
                  </div>
                """
            ),
            unsafe_allow_html=True,
        )
        st.session_state.answers[question["no"]] = st.radio(
            label=f"문항 {question['no']}",
            options=LABELS,
            index=None,
            horizontal=True,
            label_visibility="collapsed",
            key=f"q{question['no']}",
        )
        st.markdown("</div>", unsafe_allow_html=True)


def render_functional_block() -> None:
    with st.container():
        st.markdown(
            dedent(
                """
                <div class="card compact question-card">
                  <div class="question-header">
                    <div class="badge">기능 손상</div>
                    <div class="question-text">이 문제들 때문에 일·집안일·대인관계에 얼마나 어려움이 있었습니까?</div>
                    <div class="text" style="margin-top:4px;">가장 가까운 수준을 선택해 주세요.</div>
                  </div>
                """
            ),
            unsafe_allow_html=True,
        )
        st.session_state.functional = st.radio(
            "기능 손상",
            options=["전혀 어렵지 않음", "어렵지 않음", "어려움", "매우 어려움"],
            index=None,
            horizontal=True,
            label_visibility="collapsed",
            key="functional-impact",
        )
        st.markdown("</div>", unsafe_allow_html=True)


def render_intro_page() -> None:
    with st.container():
        st.markdown('<div class="app-wrap"><div class="stack">', unsafe_allow_html=True)

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="badge">PHQ-9</div>
                    <div class="title-xl">우울 증상 자기보고 검사</div>
                    <div class="text">지난 2주 동안 경험한 증상 빈도를 0~3점 척도로 기록하는 표준화된 자기보고 도구입니다.</div>
                  </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="title-lg">PHQ-9 검사 안내</div>
                  </div>
                  <ul class="instruction-list">
                    <li>목적: 최근 2주간 우울 관련 증상의 빈도를 자가 보고하여 현재 상태를 점검합니다.</li>
                    <li>대상: 만 12세 이상 누구나 스스로 응답할 수 있습니다.</li>
                    <li>응답 방식: 각 문항은 <b>전혀 아님(0)</b>부터 <b>거의 매일(3)</b>까지의 0~3점 척도로 응답합니다.</li>
                  </ul>
                  <div class="text" style="margin-top:10px;">※ 결과 해석은 참고용이며, 의학적 진단을 대신하지 않습니다.</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="title-lg">개인정보 수집·이용 동의</div>
                  </div>
                  <ul class="instruction-list">
                    <li>검사 진행을 위해 이름, 성별, 연령, 거주지역 등 기본 정보를 입력받습니다. 휴대폰 번호와 이메일은 선택 입력 항목입니다.</li>
                    <li>입력된 개인정보는 KIRBS+의 개인정보 관련 약관에 적용되며 약관에 따라 저장 및 활용될 수 있습니다.</li>
                    <li>동의 후 검사 시작 시점과 동의 시점 정보가 기록되며, 이후 응답 내용은 결과 산출에 사용됩니다.</li>
                  </ul>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        consent_checked = st.checkbox(
            "개인정보 수집 및 이용에 동의합니다. (필수)",
            key="consent_checkbox",
            value=st.session_state.consent,
        )
        if consent_checked != st.session_state.consent:
            st.session_state.consent = consent_checked
            if not consent_checked:
                st.session_state.consent_ts = None
        st.markdown("</div>", unsafe_allow_html=True)

        actions = st.columns([1, 1], gap="medium")
        with actions[0]:
            st.empty()
        with actions[1]:
            next_clicked = st.button("다음", type="primary", use_container_width=True)
            if next_clicked:
                if not st.session_state.consent:
                    st.warning("동의가 필요합니다.", icon="⚠️")
                else:
                    if not st.session_state.consent_ts:
                        st.session_state.consent_ts = kst_iso_now()
                    st.session_state.page = "examinee"
                    st.rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)


def render_examinee_page() -> None:
    with st.container():
        st.markdown('<div class="app-wrap"><div class="stack examinee-layout">', unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown('<div class="respondent-card-marker"></div>', unsafe_allow_html=True)

            st.markdown(
                dedent(
                    """
                    <div class="respondent-form-shell">
                      <div class="respondent-form-header">
                        <div class="respondent-form-title">응답자 정보</div>
                        <div class="respondent-form-desc">검사 진행과 결과 확인을 위해 필요한 정보를 입력해 주세요. 이름, 성별, 연령, 거주지역은 필수이며 휴대폰번호와 이메일은 선택 입력입니다.</div>
                      </div>
                      <div class="respondent-form-divider"></div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

            identity_col, gender_col = st.columns(2, gap="medium")
            with identity_col:
                name = st.text_input(
                    "이름",
                    value=st.session_state.examinee.get("name", ""),
                )
            with gender_col:
                gender = st.selectbox(
                    "성별",
                    options=[""] + GENDER_OPTIONS,
                    index=([""] + GENDER_OPTIONS).index(st.session_state.examinee.get("gender", ""))
                    if st.session_state.examinee.get("gender", "") in GENDER_OPTIONS
                    else 0,
                )

            age_col, region_col = st.columns(2, gap="medium")
            with age_col:
                age = st.text_input(
                    "연령",
                    value=st.session_state.examinee.get("age", ""),
                )
            with region_col:
                region = st.selectbox(
                    "거주지역",
                    options=[""] + REGION_OPTIONS,
                    index=([""] + REGION_OPTIONS).index(st.session_state.examinee.get("region", ""))
                    if st.session_state.examinee.get("region", "") in REGION_OPTIONS
                    else 0,
                )

            phone = st.text_input(
                "휴대폰번호 (선택)",
                value=st.session_state.examinee.get("phone", ""),
            )
            email = st.text_input(
                "이메일 (선택)",
                value=st.session_state.examinee.get("email", ""),
            )

            normalized_phone = normalize_phone(phone)
            st.session_state.examinee.update({
                "name": name.strip(),
                "gender": gender,
                "age": age.strip(),
                "region": region,
                "phone": normalized_phone,
                "email": email.strip(),
            })

            name_error = validate_name(name)
            gender_error = validate_gender(gender)
            age_error = validate_age(age)
            region_error = validate_region(region)
            phone_error = validate_phone(normalized_phone)
            email_error = validate_email(email)

            missing_fields = []
            if not name.strip():
                missing_fields.append("이름")
            if not gender.strip():
                missing_fields.append("성별")
            if not age.strip():
                missing_fields.append("연령")
            if not region.strip():
                missing_fields.append("거주지역")

            required_errors = []
            if name_error and name.strip():
                required_errors.append(name_error)
            if gender_error and gender.strip():
                required_errors.append(gender_error)
            if age_error and age.strip():
                required_errors.append(age_error)
            if region_error and region.strip():
                required_errors.append(region_error)

            if missing_fields or required_errors or phone_error or email_error:
                st.markdown('<div class="examinee-warning-area">', unsafe_allow_html=True)
                if missing_fields:
                    st.warning(f"{', '.join(missing_fields)}을 입력해주세요.", icon="⚠️")
                for error in required_errors:
                    st.warning(error, icon="⚠️")
                if phone_error:
                    st.warning(phone_error, icon="⚠️")
                if email_error:
                    st.warning(email_error, icon="⚠️")
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="examinee-actions">', unsafe_allow_html=True)
            actions = st.columns([1, 1], gap="medium")
            all_valid = not any([name_error, gender_error, age_error, region_error, phone_error, email_error])
            with actions[0]:
                if st.button("이전", use_container_width=True):
                    st.session_state.page = "intro"
                    st.rerun()
            with actions[1]:
                if st.button("다음", type="primary", use_container_width=True, disabled=not all_valid):
                    st.session_state.page = "survey"
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div></div>', unsafe_allow_html=True)


def render_survey_page() -> None:
    with st.container():
        st.markdown('<div class="app-wrap"><div class="stack">', unsafe_allow_html=True)

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="title-lg">지시문</div>
                  </div>
                  <ul class="instruction-list">
                    <li>각 문항에 대해 지난 2주 동안의 빈도를 <b>전혀 아님(0)</b> · <b>며칠 동안(1)</b> · <b>절반 이상(2)</b> · <b>거의 매일(3)</b> 가운데 가장 가까운 값으로 선택합니다.</li>
                    <li>모든 문항과 기능 손상 질문을 완료한 뒤 ‘결과 보기’를 누르면 총점, 중증도, 영역별 분석을 바로 확인할 수 있습니다.</li>
                  </ul>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            dedent(
                """
                <div class="card section-card">
                  <div class="card-header">
                    <div class="title-lg">질문지 (지난 2주)</div>
                    <div class="text">표준 PHQ-9 · 모든 문항은 동일한 0–3점 척도를 사용합니다.</div>
                  </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-to-question"></div>', unsafe_allow_html=True)

        for q in QUESTIONS:
            render_question_item(q)

        render_functional_block()

        actions = st.columns([1, 1], gap="medium")
        with actions[0]:
            if st.button("이전", use_container_width=True):
                st.session_state.page = "examinee"
                st.rerun()
        with actions[1]:
            if st.button("결과 보기", type="primary", use_container_width=True):
                scores, unanswered = [], 0
                for i in range(1, 10):
                    lab = st.session_state.answers.get(i)
                    if lab is None:
                        unanswered += 1
                        scores.append(0)
                    else:
                        scores.append(LABEL2SCORE[lab])
                total = sum(scores)
                sev = phq_severity(total)
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.session_state.summary = (total, sev, st.session_state.functional, scores, ts, unanswered)
                st.session_state.page = "result"
                st.rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)


def render_result_page(dev_mode: bool = False) -> None:
    if not st.session_state.summary:
        st.warning("먼저 설문을 완료해 주세요.")
        st.stop()

    total, sev, functional, scores, ts, unanswered = st.session_state.summary
    item9_score = scores[8] if len(scores) >= 9 else 0

    narrative = compose_narrative(total, sev, functional, item9_score)
    arc_color = SEVERITY_ARC_COLOR.get(sev, BRAND)
    gauge_percent = (max(0, min(total, 27)) / 27) * 100
    functional_value = functional if functional else "미응답"

    st.markdown('<div class="app-wrap"><div class="stack">', unsafe_allow_html=True)

    name_value = st.session_state.examinee.get("name", "").strip()
    name_text = name_value if name_value else "(미입력)"

    st.markdown(
        dedent(
            f"""
            <div class="card result-card">
              <div class="card-header">
                <div class="title-lg">I. 종합 소견</div>
                <div class="text">검사 일시: {ts}</div>
                <div class="text">응답자: {name_text}</div>
              </div>
              <div class="summary-layout">
                <div class="gauge-card">
                  <div class="badge" style="margin: 0 auto;">총점</div>
                  <div class="gauge-circle" style="background: conic-gradient({arc_color} {gauge_percent:.2f}%, rgba(226,232,240,0.9) {gauge_percent:.2f}%, rgba(226,232,240,0.9) 100%);">
                    <div class="gauge-inner">
                      <div class="gauge-number">{total}</div>
                      <div class="gauge-denom">/ 27</div>
                    </div>
                  </div>
                  <div class="gauge-severity" style="color:{arc_color};">{sev}</div>
                </div>
                <div class="narrative-card">
                  <div class="narrative-title">주요 소견</div>
                  <div class="text">{narrative}</div>
                  <div class="functional-highlight">
                    <div class="functional-title">일상 기능 손상 (10번 문항)</div>
                    <div class="functional-value"><strong>{functional_value}</strong></div>
                  </div>
                </div>
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if unanswered > 0:
        st.markdown(
            f'<div class="warn">⚠️ 미응답 {unanswered}개 문항은 0점으로 계산되었습니다.</div>',
            unsafe_allow_html=True,
        )

    domain_html = build_domain_profile_html(scores)
    domain_section_html = dedent(
        """
        <div class="card result-card">
          <div class="card-header">
            <div class="title-lg">II. 증상 영역별 프로파일</div>
            <div class="text">각 영역별 보고된 증상 강도를 확인할 수 있습니다.</div>
          </div>
          {domain_panel}
        </div>
        """
    ).strip().format(domain_panel=domain_html)
    st.markdown(domain_section_html, unsafe_allow_html=True)

    if item9_score > 0:
        st.markdown(
            dedent(
                """
                <div class="card safety-card result-card result-danger">
                  <div class="card-header">
                    <div class="title-lg">안전 안내 (문항 9 관련)</div>
                    <div class="text">자살·자해 생각이 있을 때 즉시 도움 받기</div>
                  </div>
                  <div>한국: <b>1393 자살예방상담(24시간)</b>, <b>정신건강상담 1577-0199</b> · 긴급 시 <b>112/119</b>.</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="result-actions">', unsafe_allow_html=True)
    actions = st.columns([1, 1], gap="medium")
    with actions[0]:
        if st.button("닫기", use_container_width=True):
            components.html("<script>window.close();</script>", height=0)
            st.info("창이 닫히지 않으면 브라우저 탭을 직접 닫거나 ‘새 검사 시작’을 눌러 주세요.", icon="ℹ️")
    with actions[1]:
        if st.button("새 검사 시작", type="primary", use_container_width=True):
            _reset_to_survey()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        dedent(
            """
            <div class="card compact result-card">
              <div class="footer-note">
                PHQ-9는 공공 도메인(Pfizer 별도 허가 불필요).<br>
                Kroenke, Spitzer, & Williams (2001) JGIM · Spitzer, Kroenke, & Williams (1999) JAMA.
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    def build_phq9_payload() -> dict:
        total_, sev_, functional_, scores_, ts_, unanswered_ = st.session_state.summary

        somatic_score = sum(scores_[i - 1] for i in SOMATIC)
        cog_aff_score = sum(scores_[i - 1] for i in COG_AFF)

        submitted_ts = kst_iso_now()

        exam_data = {
            "exam": {"title": "PHQ_9", "version": "v1"},
            "examinee": dict(st.session_state.examinee),
            "answers": {
                **{f"q{i}": scores_[i - 1] for i in range(1, 10)},
                "functional_impact": functional_ if functional_ else None,
            },
            "result": {
                "total": total_,
                "severity": sev_,
                "domain_scores": {
                    "somatic": somatic_score,
                    "cog_aff": cog_aff_score,
                },
                "unanswered": unanswered_,
            },
            "meta": {
                "started_ts": st.session_state.consent_ts or "",
                "submitted_ts": submitted_ts,
                "consent": st.session_state.consent,
                "consent_ts": st.session_state.consent_ts,
            },
        }
        return exam_data

    with st.container():
        internal_payload = build_phq9_payload()
        exam_data = build_exam_data_phq9(internal_payload)
        auto_db_insert(exam_data)

        if dev_mode:
            required_keys = ["exam_name", "consent_col", "examinee_col", "answers_col", "result_col"]
            st.caption("dev=1 sanity check · standardized exam_data")
            st.json(exam_data, expanded=False)
            st.code(
                f"exam_data_has_exact_5_keys={list(exam_data.keys()) == required_keys} keys={list(exam_data.keys())}",
                language="text",
            )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# 데이터 저장 분기 + DB 연동 전용 블록
# ──────────────────────────────────────────────────────────────────────────────
def _is_db_insert_enabled() -> bool:
    raw = os.getenv("ENABLE_DB_INSERT", "false")
    return str(raw).strip().lower() == "true"


ENABLE_DB_INSERT = _is_db_insert_enabled()

if ENABLE_DB_INSERT:
    from utils.database import Database


def safe_db_insert(exam_data: dict) -> bool:
    """
    dev PC: ENABLE_DB_INSERT=false → 저장 호출 안 함
    운영/병합: ENABLE_DB_INSERT=true → Database().insert(exam_data) 수행
    """
    if not ENABLE_DB_INSERT:
        return False

    try:
        db = Database()
        db.insert(exam_data)
        return True
    except Exception as e:
        print(f"[DB INSERT ERROR] {e}")
        return False


def auto_db_insert(exam_data: dict) -> None:
    """
    결과 저장 자동 호출
    - 개발 환경(ENABLE_DB_INSERT=false): DB insert 미실행 + exam_data expander로 노출
    - 활성 환경: 이름 검증 후 DB 저장 1회 시도 (성공 시 중복 방지 플래그 ON)
    """
    if "db_insert_done" not in st.session_state:
        st.session_state.db_insert_done = False
    if st.session_state.db_insert_done:
        return

    if not ENABLE_DB_INSERT:
        with st.expander("DB disabled debug payload", expanded=False):
            st.json(exam_data)
        st.caption("DB disabled (ENABLE_DB_INSERT=false)")
        return

    if not st.session_state.examinee.get("name"):
        st.error("이름을 입력해 주세요.")
        return

    ok = safe_db_insert(exam_data)
    if ok:
        st.session_state.db_insert_done = True
        st.success("검사 완료")
    else:
        st.warning("DB 저장이 수행되지 않았습니다. 환경/모듈 상태를 확인해 주세요.")


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    inject_css()
    init_state()
    dev_mode = get_dev_mode()

    if st.session_state.page == "intro":
        render_intro_page()
    elif st.session_state.page == "examinee":
        if not st.session_state.consent:
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            st.rerun()
        render_examinee_page()
    elif st.session_state.page == "survey":
        if not st.session_state.consent:
            st.warning("동의 확인 후 검사를 시작해 주세요.")
            st.session_state.page = "intro"
            st.rerun()
        if not st.session_state.examinee.get("name", "").strip():
            st.session_state.page = "examinee"
            st.rerun()
        render_survey_page()
    elif st.session_state.page == "result":
        render_result_page(dev_mode=dev_mode)
    else:
        st.session_state.page = "intro"
        st.rerun()


if __name__ == "__main__":
    main()
