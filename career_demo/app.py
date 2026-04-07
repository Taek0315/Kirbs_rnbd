from pathlib import Path
import re
import html
from collections import Counter

import pandas as pd
import streamlit as st
from data_loader import load_job_data, search_jobs, get_job_detail

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "career_jobs.xlsx"

st.set_page_config(
    page_title="AI 직업 탐색 리포트",
    page_icon="🔎",
    layout="wide",
)


def inject_css():
    st.markdown(
        """
        <style>
        :root{
            --bg:#f5f7fb;
            --panel:#ffffff;
            --line:#e6ebf2;
            --line-strong:#d9e2ee;
            --text:#0f172a;
            --muted:#667085;
            --blue:#2563eb;
            --blue-soft:#eff6ff;
            --shadow:0 4px 20px rgba(15,23,42,.05);
            --radius:16px;
            --container:1200px;
        }

        html, body, [class*="css"] {
            color: var(--text);
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(59,130,246,.10), transparent 24%),
                linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
        }

        .block-container {
            max-width: var(--container);
            padding-top: 1.2rem;
            padding-bottom: 2.5rem;
        }

        h1,h2,h3,h4 {
            color: #102a43 !important;
            letter-spacing: -0.01em;
        }

        p, li, label, span, div {
            color: #334155;
        }

        .nav-shell {
            background: rgba(255,255,255,.92);
            border: 1px solid var(--line);
            border-radius: 20px;
            box-shadow: var(--shadow);
            padding: 18px 20px 14px 20px;
            margin-bottom: 24px;
            backdrop-filter: blur(10px);
        }

        .nav-breadcrumb {
            display:flex;
            align-items:center;
            gap:8px;
            font-size:12px;
            line-height:1.5;
            color:#64748b;
            margin-bottom:10px;
            flex-wrap:wrap;
        }

        .crumb-current{
            color:#0f172a;
            font-weight:700;
        }

        .nav-title{
            font-size:24px;
            line-height:1.4;
            font-weight:800;
            color:#102a43;
            margin-bottom:8px;
        }

        .nav-sub{
            font-size:14px;
            line-height:1.6;
            color:#64748b;
            margin-bottom:14px;
        }

        .context-shell{
            background:#f8fbff;
            border:1px solid #dbe7fb;
            border-radius:16px;
            padding:14px 16px;
            margin-bottom:18px;
        }

        .context-line{
            font-size:14px;
            line-height:1.6;
            color:#334155;
        }

        .filter-chip-row{
            display:flex;
            flex-wrap:wrap;
            gap:8px;
            margin-top:10px;
        }

        .filter-chip{
            display:inline-flex;
            align-items:center;
            padding:7px 12px;
            border-radius:999px;
            background:#eff6ff;
            border:1px solid #dbeafe;
            color:#1d4ed8;
            font-size:12px;
            font-weight:700;
        }

        .brief-shell{
            background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border:1px solid var(--line);
            border-radius:20px;
            box-shadow: var(--shadow);
            padding:24px;
            margin-bottom:24px;
            position:relative;
            overflow:hidden;
        }

        .brief-shell::before{
            content:"";
            position:absolute;
            inset:0;
            background:linear-gradient(
                110deg,
                rgba(255,255,255,0) 0%,
                rgba(59,130,246,.05) 35%,
                rgba(255,255,255,0) 65%
            );
            transform:translateX(-100%);
            animation:scan 2.8s linear infinite;
            pointer-events:none;
        }

        @keyframes scan {
            to { transform: translateX(100%); }
        }

        .brief-kicker{
            font-size:12px;
            line-height:1.5;
            color:#2563eb;
            font-weight:800;
            letter-spacing:.08em;
            text-transform:uppercase;
            margin-bottom:10px;
        }

        .brief-title{
            font-size:24px;
            line-height:1.4;
            font-weight:800;
            color:#102a43;
            margin-bottom:8px;
        }

        .brief-desc{
            font-size:14px;
            line-height:1.6;
            letter-spacing:-0.2px;
            color:#475467;
            margin-bottom:18px;
        }

        .summary-one-line{
            background:#f8fbff;
            border:1px solid #dce8fb;
            border-radius:16px;
            padding:18px;
            margin-bottom:18px;
        }

        .summary-label{
            font-size:12px;
            line-height:1.5;
            color:#2563eb;
            font-weight:800;
            margin-bottom:8px;
        }

        .summary-text{
            font-size:18px;
            line-height:1.5;
            font-weight:700;
            color:#0f172a;
            letter-spacing:-0.3px;
        }

        .keyword-wrap{
            display:flex;
            flex-wrap:wrap;
            gap:10px;
            margin-top:2px;
        }

        .keyword-chip{
            display:inline-flex;
            align-items:center;
            padding:10px 14px;
            border-radius:999px;
            background:#ffffff;
            border:1px solid #e6eef8;
            box-shadow: 0 2px 10px rgba(15,23,42,.03);
            font-size:13px;
            font-weight:700;
            color:#334155;
        }

        .insight-grid{
            display:grid;
            grid-template-columns: 1.2fr .8fr;
            gap:24px;
            align-items:stretch;
        }

        .mini-panel{
            background:#fff;
            border:1px solid var(--line);
            border-radius:16px;
            padding:18px;
            height:100%;
        }

        .mini-panel-title{
            font-size:18px;
            line-height:1.5;
            font-weight:700;
            color:#102a43;
            margin-bottom:10px;
        }

        .mini-panel-body{
            font-size:14px;
            line-height:1.6;
            letter-spacing:-0.2px;
            color:#475467;
        }

        .meter-label{
            font-size:12px;
            line-height:1.5;
            color:#667085;
            font-weight:700;
            margin-bottom:10px;
        }

        .meter-shell{
            width:100%;
            height:12px;
            background:#edf2f7;
            border-radius:999px;
            overflow:hidden;
            margin-bottom:10px;
        }

        .meter-fill{
            height:100%;
            border-radius:999px;
            background:linear-gradient(90deg, #60a5fa 0%, #2563eb 100%);
        }

        .meter-score{
            font-size:28px;
            line-height:1.3;
            font-weight:800;
            color:#0f172a;
            margin-bottom:4px;
        }

        .section-shell{
            background:transparent;
            margin-bottom:28px;
        }

        .section-head{
            margin-bottom:14px;
        }

        .section-kicker{
            font-size:12px;
            line-height:1.5;
            color:#2563eb;
            font-weight:800;
            letter-spacing:.08em;
            text-transform:uppercase;
            margin-bottom:6px;
        }

        .section-title{
            font-size:18px;
            line-height:1.5;
            font-weight:700;
            color:#102a43;
            margin-bottom:4px;
        }

        .section-sub{
            font-size:14px;
            line-height:1.6;
            color:#667085;
            letter-spacing:-0.2px;
        }

        .card{
            background:#ffffff;
            border:1px solid var(--line);
            border-radius:16px;
            box-shadow: var(--shadow);
            padding:20px;
        }

        .grid-2{
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:24px;
        }

        .grid-3{
            display:grid;
            grid-template-columns:repeat(3, 1fr);
            gap:16px;
        }

        .timeline{
            display:grid;
            grid-template-columns:repeat(4, 1fr);
            gap:16px;
        }

        .timeline-item{
            position:relative;
            background:#fbfdff;
            border:1px solid #e8eef7;
            border-radius:16px;
            padding:18px 16px;
            min-height:170px;
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

        .timeline-icon{
            font-size:22px;
            line-height:1;
            margin-bottom:12px;
        }

        .timeline-title{
            font-size:15px;
            line-height:1.5;
            font-weight:700;
            color:#0f172a;
            margin-bottom:8px;
        }

        .timeline-text{
            font-size:14px;
            line-height:1.6;
            color:#64748b;
            letter-spacing:-0.2px;
        }

        .radar-shell{
            display:flex;
            gap:24px;
            align-items:center;
            justify-content:space-between;
            flex-wrap:wrap;
        }

        .legend-list{
            min-width:240px;
            flex:1 1 240px;
        }

        .legend-item{
            margin-bottom:12px;
        }

        .legend-top{
            display:flex;
            justify-content:space-between;
            gap:10px;
            margin-bottom:6px;
        }

        .legend-name{
            font-size:13px;
            font-weight:700;
            color:#334155;
        }

        .legend-value{
            font-size:13px;
            font-weight:800;
            color:#0f172a;
        }

        .legend-bar{
            width:100%;
            height:8px;
            background:#edf2f7;
            border-radius:999px;
            overflow:hidden;
        }

        .legend-bar > span{
            display:block;
            height:100%;
            border-radius:999px;
            background:linear-gradient(90deg, #93c5fd 0%, #2563eb 100%);
        }

        .ai-comment{
            margin-top:16px;
            background:#f8fbff;
            border:1px solid #dbeafe;
            border-radius:14px;
            padding:14px 16px;
            font-size:14px;
            line-height:1.6;
            color:#1e3a8a;
        }

        .metric-card{
            background:#fbfdff;
            border:1px solid #e8eef7;
            border-radius:14px;
            padding:16px;
        }

        .metric-label{
            font-size:12px;
            line-height:1.5;
            color:#667085;
            font-weight:700;
            margin-bottom:8px;
        }

        .metric-value{
            font-size:22px;
            line-height:1.35;
            font-weight:800;
            color:#0f172a;
            letter-spacing:-0.3px;
            margin-bottom:4px;
        }

        .metric-sub{
            font-size:13px;
            line-height:1.6;
            color:#667085;
        }

        .status-pill{
            display:inline-flex;
            align-items:center;
            gap:8px;
            padding:10px 12px;
            border-radius:999px;
            font-size:13px;
            font-weight:800;
            margin-bottom:12px;
        }

        .status-up{
            background:#ecfdf3;
            border:1px solid #d1fadf;
            color:#027a48;
        }

        .status-mid{
            background:#f8fafc;
            border:1px solid #e2e8f0;
            color:#475467;
        }

        .status-down{
            background:#fef3f2;
            border:1px solid #fecdca;
            color:#b42318;
        }

        .stress-shell{
            margin-top:16px;
        }

        .stress-bar{
            width:100%;
            height:12px;
            background:linear-gradient(90deg, #d1fae5 0%, #fde68a 50%, #fecaca 100%);
            border-radius:999px;
            position:relative;
            overflow:hidden;
        }

        .stress-marker{
            position:absolute;
            top:-3px;
            width:18px;
            height:18px;
            border-radius:50%;
            background:#0f172a;
            border:3px solid #fff;
            box-shadow:0 2px 8px rgba(15,23,42,.18);
            transform:translateX(-50%);
        }

        .stress-scale{
            display:flex;
            justify-content:space-between;
            font-size:12px;
            color:#667085;
            margin-top:8px;
        }

        .clean-list{
            list-style:none;
            padding-left:0;
            margin:0;
        }

        .clean-list li{
            padding:12px 0;
            border-bottom:1px solid #eef2f6;
            font-size:14px;
            line-height:1.6;
            color:#334155;
        }

        .clean-list li:last-child{
            border-bottom:none;
            padding-bottom:0;
        }

        .empty-state{
            color:#98a2b3;
            font-size:14px;
            line-height:1.6;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div{
            background:#ffffff !important;
            border:1px solid #d0d9e5 !important;
            border-radius:14px !important;
            min-height:48px !important;
            box-shadow:none !important;
            color:#111827 !important;
        }

        input{
            color:#111827 !important;
        }

        input::placeholder{
            color:#94a3b8 !important;
        }

        .stTextInput label,
        .stSelectbox label,
        .stMultiSelect label{
            color:#334155 !important;
            font-weight:700 !important;
            font-size:14px !important;
        }

        .stAlert, .stInfo, .stWarning{
            border-radius:16px !important;
        }

        @media (max-width: 1024px){
            .insight-grid,
            .grid-2,
            .timeline,
            .grid-3{
                grid-template-columns:1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def get_data():
    return load_job_data(DATA_FILE)


def split_lines(text: str):
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return []
    text = str(text).replace("\r", "\n").strip()
    if not text:
        return []

    raw_parts = []
    for part in re.split(r"\n|;", text):
        part = part.strip()
        if not part:
            continue
        if "," in part and len(part) < 120:
            raw_parts.extend([p.strip() for p in part.split(",") if p.strip()])
        else:
            raw_parts.append(part)

    lines = []
    for line in raw_parts:
        line = re.sub(r"^[\\-•·]\s*", "", line).strip()
        if line:
            lines.append(line)
    return lines


def collect_prefixed_values(detail: dict, prefix: str):
    items = []
    for key, value in detail.items():
        if key.startswith(prefix) and value is not None and not pd.isna(value):
            value = str(value).strip()
            if value and value.lower() != "nan":
                items.append(value)
    return items


def unique_keep_order(items):
    seen = set()
    result = []
    for item in items:
        norm = str(item).strip()
        if not norm or norm.lower() == "nan":
            continue
        if norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def get_similar_jobs(detail: dict):
    return unique_keep_order(split_lines(detail.get("similarJob", "")))


def get_major_list(detail: dict):
    return unique_keep_order(collect_prefixed_values(detail, "major_"))


def get_contact_list(detail: dict):
    contacts = []
    if isinstance(detail.get("contact_list"), list):
        contacts.extend(detail.get("contact_list"))
    contacts.extend(collect_prefixed_values(detail, "contact_"))
    return unique_keep_order(contacts)


def clean_sentence(text: str):
    if not text:
        return ""
    text = re.sub(r"^[\\-•·]\s*", "", str(text)).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def infer_domain(job_name: str, search_query: str, detail: dict):
    text = f"{job_name} {search_query} {detail.get('summary','')} {detail.get('aptitude','')}".lower()
    mapping = [
        ("IT 분야", ["it", "정보", "컴퓨터", "시스템", "소프트웨어", "네트워크", "데이터"]),
        ("보건·의료 분야", ["간호", "의료", "병원", "보건", "약", "임상", "치과"]),
        ("교육 분야", ["교사", "교육", "교수", "강사", "훈련"]),
        ("상담·심리 분야", ["상담", "심리", "치료", "정서"]),
        ("디자인·콘텐츠 분야", ["디자인", "영상", "콘텐츠", "그래픽", "광고", "편집"]),
        ("경영·사무 분야", ["경영", "회계", "사무", "행정", "인사", "총무", "기획"]),
        ("공학·기술 분야", ["기계", "전기", "가스", "환경", "설비", "공학", "기술"]),
        ("서비스 분야", ["서비스", "고객", "판매", "영업", "안내", "호텔", "관광"]),
        ("연구 분야", ["연구", "분석", "실험"]),
    ]
    for label, keywords in mapping:
        if any(keyword in text for keyword in keywords):
            return label
    return "직업 탐색"


def build_breadcrumb(job_name: str, search_query: str, detail: dict):
    domain = infer_domain(job_name, search_query, detail)
    return ["직업 탐색", domain, job_name]


def extract_keywords(detail: dict, limit: int = 8):
    text = " ".join(
        [
            str(detail.get("job", "")),
            str(detail.get("summary", "")),
            str(detail.get("aptitude", "")),
            str(detail.get("empway", "")),
        ]
    )
    candidates = re.findall(r"[A-Za-z가-힣·ㆍ]{2,20}", text)
    stopwords = {
        "그리고","관련","직업","위해","통해","되는","한다","있다","있으며","것으로","정도",
        "업무","필요","요구","사람","사람에게","유리하다","적합","직업인","경우","향후",
        "자료","워크넷","정보","수준","능력","역할","기업","고객","기본적","기본적인","가능성",
        "직장","고용","임금","평균","하위","상위","된다","하는","업무를","직업은","직업이",
        "관련된","등의","등을","대한","자신의","자신이","수행","준비","교육"
    }
    weighted = []
    preferred = ["전략", "시스템", "분석", "기획", "설계", "커뮤니케이션", "문제해결", "책임감", "데이터", "고객", "운용", "진단", "컨설팅"]
    for token in candidates:
        token = token.strip("·ㆍ")
        if len(token) < 2 or token in stopwords:
            continue
        weighted.append(token)

    counts = Counter(weighted)
    top = [word for word, _ in counts.most_common(limit * 2)]

    ordered = []
    for pref in preferred:
        if any(pref in word for word in top):
            matched = next(word for word in top if pref in word)
            if matched not in ordered:
                ordered.append(matched)

    for token in top:
        if token not in ordered:
            ordered.append(token)
        if len(ordered) >= limit:
            break

    return [f"#{token}" for token in ordered[:limit]]


def derive_competency_scores(detail: dict):
    text = " ".join(
        [
            str(detail.get("summary", "")),
            str(detail.get("aptitude", "")),
            str(detail.get("empway", "")),
            str(detail.get("training", "")),
        ]
    )

    score_map = {
        "논리적 사고": {"base": 58, "keywords": ["분석", "논리", "기획", "판단", "진단", "전략", "문제해결"]},
        "커뮤니케이션": {"base": 55, "keywords": ["고객", "의사소통", "설명", "협업", "조정", "서비스", "상담"]},
        "문제 해결": {"base": 57, "keywords": ["해결", "개선", "대응", "최적", "점검", "감리"]},
        "기술 이해": {"base": 54, "keywords": ["시스템", "컴퓨터", "정보", "기계", "설비", "기술", "전산"]},
        "책임감": {"base": 56, "keywords": ["성실", "책임", "정확", "도덕성", "통제", "안전"]},
        "분석력": {"base": 58, "keywords": ["자료", "수집", "조사", "평가", "검토", "통계", "분석"]},
    }

    scores = {}
    for label, info in score_map.items():
        score = info["base"]
        for keyword in info["keywords"]:
            if keyword in text:
                score += 6
        scores[label] = max(35, min(score, 95))
    return scores


def render_radar_svg(scores: dict):
    labels = list(scores.keys())
    values = list(scores.values())
    size = 320
    center = size / 2
    radius = 110

    def point(angle_deg, r):
        import math
        rad = math.radians(angle_deg - 90)
        x = center + r * math.cos(rad)
        y = center + r * math.sin(rad)
        return x, y

    angles = [i * 360 / len(labels) for i in range(len(labels))]

    grid_polys = []
    for level in [25, 50, 75, 100]:
        pts = []
        for angle in angles:
            x, y = point(angle, radius * level / 100)
            pts.append(f"{x:.1f},{y:.1f}")
        grid_polys.append(
            f'<polygon points="{" ".join(pts)}" fill="none" stroke="#E5E7EB" stroke-width="1"/>'
        )

    axes = []
    label_nodes = []
    for label, angle in zip(labels, angles):
        x, y = point(angle, radius)
        axes.append(f'<line x1="{center}" y1="{center}" x2="{x:.1f}" y2="{y:.1f}" stroke="#E5E7EB" stroke-width="1"/>')
        lx, ly = point(angle, radius + 26)
        label_nodes.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#64748B" font-size="12" font-weight="700" text-anchor="middle">{html.escape(label)}</text>'
        )

    poly_pts = []
    for value, angle in zip(values, angles):
        x, y = point(angle, radius * value / 100)
        poly_pts.append(f"{x:.1f},{y:.1f}")

    points_html = []
    for value, angle in zip(values, angles):
        x, y = point(angle, radius * value / 100)
        points_html.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#2563EB" stroke="#FFFFFF" stroke-width="2"/>')

    return f"""
    <svg width="340" height="340" viewBox="0 0 320 320" xmlns="http://www.w3.org/2000/svg" aria-label="역량 레이더 차트">
        <circle cx="{center}" cy="{center}" r="3" fill="#CBD5E1"/>
        {''.join(grid_polys)}
        {''.join(axes)}
        <polygon points="{' '.join(poly_pts)}" fill="rgba(37,99,235,.18)" stroke="#2563EB" stroke-width="2.5"/>
        {''.join(points_html)}
        {''.join(label_nodes)}
    </svg>
    """


def parse_salary_metrics(text: str):
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return {}

    raw = str(text).strip()
    if not raw:
        return {}

    label_map = {"하위": "하위 25%", "평균": "중앙값/평균", "상위": "상위 25%"}
    cleaned = raw.replace(",", "")

    try:
        patterns = [
            r"(하위|평균|상위)\s*(?:\(?\d+%\)?)?\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)\s*만원",
            r"(하위|평균|상위)[^\d]{0,20}([0-9]+(?:\.[0-9]+)?)\s*만원",
        ]
        matches = []
        for pattern in patterns:
            found = re.findall(pattern, cleaned)
            if found:
                matches = found
                break
    except re.error:
        return {}

    if not matches:
        return {}

    metrics = {}
    for key, value in matches:
        label = label_map.get(key, key)
        metrics[label] = f"{value}만원"
    return metrics


def classify_outlook(text: str):
    text = str(text)
    if any(word in text for word in ["증가", "성장", "확대", "밝", "좋", "유망"]):
        return "상승", "매우 밝거나 확장 가능성이 있는 편입니다.", "status-up", "↗"
    if any(word in text for word in ["감소", "줄어", "축소", "낮아질", "어려울"]):
        return "하락", "감소 또는 축소 압력이 있는 편입니다.", "status-down", "↘"
    return "유지", "현 수준 유지 또는 완만한 변화 가능성이 큽니다.", "status-mid", "→"


def infer_stress_signal(detail: dict):
    text = f"{detail.get('job_possibility','')} {detail.get('summary','')} {detail.get('aptitude','')}"
    score = 45
    if "정신적 스트레스는 심하지 않은" in text or "스트레스는 심하지 않은" in text:
        score -= 18
    if "정신적 스트레스" in text and any(k in text for k in ["높", "많", "심한", "큰"]):
        score += 20
    for k, w in {
        "고객": 8, "감리": 8, "안전": 6, "책임": 8, "분석": 5,
        "점검": 5, "정확": 5, "상담": 10, "영업": 8, "위험": 8
    }.items():
        if k in text:
            score += w
    return max(15, min(score, 90))


def make_one_line_definition(detail: dict):
    summary_lines = split_lines(detail.get("summary", ""))
    if summary_lines:
        return clean_sentence(summary_lines[0])
    return f"{detail.get('job','이 직업')}는 필요한 정보를 수집하고 정리하여 현장에서 필요한 역할을 수행하는 직업입니다."


def get_role_steps(detail: dict):
    steps = []
    summary_lines = split_lines(detail.get("summary", ""))
    emp_lines = split_lines(detail.get("empway", ""))
    training_lines = split_lines(detail.get("training", ""))

    merged = [clean_sentence(x) for x in (summary_lines + emp_lines + training_lines) if clean_sentence(x)]

    default_titles = ["업무 맥락 파악", "핵심 역할 수행", "현장 대응 및 실행", "숙련도 강화"]
    icons = ["🔍", "🧩", "🛠️", "📈"]

    for idx in range(min(4, len(merged))):
        steps.append({"title": default_titles[idx], "text": merged[idx], "icon": icons[idx]})

    while len(steps) < 4:
        fallback = [
            "직무 정보를 이해하고",
            "핵심 업무를 수행하며",
            "현장에서 필요한 대응을 익히고",
            "경험을 통해 숙련도를 높입니다.",
        ]
        idx = len(steps)
        steps.append({"title": default_titles[idx], "text": fallback[idx], "icon": icons[idx]})

    return steps


def render_html_card(title: str, body_html: str):
    st.markdown(
        f'''
        <div class="card">
            <div class="mini-panel-title">{html.escape(title)}</div>
            <div class="mini-panel-body">{body_html}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


def render_navigator(job_options, selected_job, focus_items, search_query, detail):
    breadcrumb = build_breadcrumb(selected_job, search_query, detail)

    crumb_html = []
    for idx, item in enumerate(breadcrumb):
        cls = "crumb-current" if idx == len(breadcrumb) - 1 else ""
        crumb_html.append(f'<span class="{cls}">{html.escape(item)}</span>')
        if idx < len(breadcrumb) - 1:
            crumb_html.append("<span>›</span>")

    st.markdown(
        f'''
        <div class="nav-shell">
            <div class="nav-breadcrumb">{''.join(crumb_html)}</div>
            <div class="nav-title">{html.escape(selected_job)} 탐색 리포트</div>
            <div class="nav-sub">
                상단에서 직업과 보고 싶은 정보 범위를 정하면, 아래에서 AI가 핵심 정의와 세부 인사이트를 구조적으로 정리합니다.
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.25, 1.75], gap="medium")
    with col1:
        selected = st.selectbox(
            "어떤 직업을 중심으로 볼까요?",
            options=job_options,
            index=job_options.index(selected_job),
        )
    with col2:
        selected_focus = st.multiselect(
            "어떤 정보를 우선해서 볼까요?",
            options=["직무소개", "핵심 역량", "전망/연봉", "연관 직업", "준비 방법", "관련 학과", "추가 정보"],
            default=focus_items,
        )

    focus_text = " · ".join(selected_focus) if selected_focus else "전체 정보"
    chips = "".join([f'<span class="filter-chip">{html.escape(item)}</span>' for item in selected_focus]) or '<span class="filter-chip">전체 보기</span>'

    st.markdown(
        f'''
        <div class="context-shell">
            <div class="context-line">
                <strong>{html.escape(selected)}</strong>에 대해 <strong>{html.escape(focus_text)}</strong> 정보를 중심으로 보여주고 있습니다.
            </div>
            <div class="filter-chip-row">{chips}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    return selected, selected_focus


def render_brief_dashboard(detail: dict):
    one_line = make_one_line_definition(detail)
    keywords = extract_keywords(detail)
    keyword_html = "".join([f'<span class="keyword-chip">{html.escape(k)}</span>' for k in keywords])
    provided_scope = []
    for label, key in [
        ("직무 소개", "summary"),
        ("준비 방법", "prepareway"),
        ("훈련/교육", "training"),
        ("전망", "job_possibility"),
        ("연관 직업", "similarJob"),
    ]:
        if split_lines(detail.get(key, "")):
            provided_scope.append(label)
    if get_major_list(detail):
        provided_scope.append("관련 학과")
    scope_text = " · ".join(unique_keep_order(provided_scope)) if provided_scope else "직무 소개 중심 정보"

    st.markdown(
        f'''
        <div class="brief-shell">
            <div class="brief-kicker">The Insight</div>
            <div class="brief-title">AI 브리핑 대시보드</div>
            <div class="brief-desc">
                직업 설명, 적성, 준비 경로, 전망 문구를 종합해 핵심 정의와 탐색 키워드를 먼저 제시합니다.
            </div>

            <div class="summary-one-line">
                <div class="summary-label">AI 한 줄 정의</div>
                <div class="summary-text">{html.escape(one_line)}</div>
            </div>

            <div class="insight-grid">
                <div class="mini-panel">
                    <div class="mini-panel-title">핵심 키워드</div>
                    <div class="mini-panel-body">
                        <div class="keyword-wrap">{keyword_html or '<span class="empty-state">추출 가능한 키워드가 없습니다.</span>'}</div>
                    </div>
                </div>
                <div class="mini-panel">
                    <div class="mini-panel-title">현재 제공 범위</div>
                    <div class="mini-panel-body" style="margin-bottom:8px;">
                        {html.escape(scope_text)}
                    </div>
                    <div class="mini-panel-body">
                        현재 리포트는 사용자 응답 데이터를 활용하지 않고, 직업 설명·준비 경로·전망 문구를 구조화하여 보여줍니다.
                    </div>
                </div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


def render_role_section(detail: dict):
    steps = get_role_steps(detail)
    cards = []
    for idx, step in enumerate(steps, start=1):
        cards.append(
            f'''
            <div class="timeline-item">
                <div class="timeline-no">{idx}</div>
                <div class="timeline-icon">{step["icon"]}</div>
                <div class="timeline-title">{html.escape(step["title"])}</div>
                <div class="timeline-text">{html.escape(step["text"])}</div>
            </div>
            '''
        )

    st.markdown(
        '''
        <div class="section-shell">
            <div class="section-head">
                <div class="section-kicker">Role & Task</div>
                <div class="section-title">이 직업은 어떤 일을 하나요?</div>
                <div class="section-sub">긴 설명문 대신, 실제 업무 흐름처럼 읽히도록 단계형 구조로 정리했습니다.</div>
            </div>
            <div class="timeline">
        ''',
        unsafe_allow_html=True,
    )
    st.markdown("".join(cards), unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_capability_section(detail: dict):
    scores = derive_competency_scores(detail)
    radar_svg = render_radar_svg(scores)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_name, top_value = sorted_scores[0]

    legends = []
    for name, value in scores.items():
        legends.append(
            f'''
            <div class="legend-item">
                <div class="legend-top">
                    <div class="legend-name">{html.escape(name)}</div>
                    <div class="legend-value">{value}</div>
                </div>
                <div class="legend-bar"><span style="width:{value}%"></span></div>
            </div>
            '''
        )

    st.markdown(
        f'''
        <div class="section-shell">
            <div class="section-head">
                <div class="section-kicker">Capability Profile</div>
                <div class="section-title">이 직업에 요구되는 핵심 역량은 무엇인가요?</div>
                <div class="section-sub">직업 설명문과 적성 문구를 바탕으로 직무에서 상대적으로 강조되는 역량을 시각화했습니다.</div>
            </div>

            <div class="card">
                <div class="radar-shell">
                    <div>{radar_svg}</div>
                    <div class="legend-list">
                        {''.join(legends)}
                    </div>
                </div>
                <div class="ai-comment">
                    이 직업은 <strong>{html.escape(top_name)}</strong> 역량의 비중이 특히 크게 읽힙니다.
                    설명문 기준으로 보면 핵심 역량 강도는 <strong>{top_value}점</strong> 수준입니다.
                </div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


def render_outlook_section(detail: dict):
    status, desc, status_class, arrow = classify_outlook(detail.get("employment", ""))
    salary = parse_salary_metrics(detail.get("salery", ""))
    stress = infer_stress_signal(detail)
    possibility_lines = split_lines(detail.get("job_possibility", ""))
    job_pos_summary = possibility_lines[0] if possibility_lines else "전반적 직업 조건 설명이 제공됩니다."

    salary_cards = []
    if salary:
        for label in ["하위 25%", "중앙값/평균", "상위 25%"]:
            if label in salary:
                salary_cards.append(
                    f'''
                    <div class="metric-card">
                        <div class="metric-label">{html.escape(label)}</div>
                        <div class="metric-value">{html.escape(salary[label])}</div>
                        <div class="metric-sub">제공된 임금 정보 기준</div>
                    </div>
                    '''
                )
    else:
        salary_cards.append(
            '''
            <div class="metric-card">
                <div class="metric-label">임금 정보</div>
                <div class="metric-value">별도 수치 없음</div>
                <div class="metric-sub">원문 설명을 확인해 주세요.</div>
            </div>
            '''
        )

    st.markdown(
        f'''
        <div class="section-shell">
            <div class="section-head">
                <div class="section-kicker">Outlook & Value</div>
                <div class="section-title">미래 가치와 현실적 조건</div>
                <div class="section-sub">전망, 연봉, 업무 밀도 시그널을 분리해 읽기 쉽게 구성했습니다.</div>
            </div>

            <div class="grid-2">
                <div class="card">
                    <div class="status-pill {status_class}">{arrow} {html.escape(status)}</div>
                    <div class="mini-panel-title">고용 전망</div>
                    <div class="mini-panel-body" style="margin-bottom:14px;">{html.escape(desc)}</div>
                    <div class="mini-panel-body">{html.escape(clean_sentence(job_pos_summary))}</div>

                    <div class="stress-shell">
                        <div class="metric-label">업무 밀도 시그널</div>
                        <div class="stress-bar">
                            <div class="stress-marker" style="left:{stress}%"></div>
                        </div>
                        <div class="stress-scale">
                            <span>낮음</span><span>보통</span><span>높음</span>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="mini-panel-title">연봉 및 조건 포인트</div>
                    <div class="grid-3">
                        {''.join(salary_cards)}
                    </div>
                </div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


def render_extension_section(detail: dict):
    similar_jobs = get_similar_jobs(detail)
    majors = get_major_list(detail)
    contacts = get_contact_list(detail)

    def render_list(items):
        if not items:
            return '<div class="empty-state">등록된 내용이 없습니다.</div>'
        return "<ul class='clean-list'>" + "".join([f"<li>{html.escape(x)}</li>" for x in items]) + "</ul>"

    prepare_parts = []
    for title, key in [("진입 경로", "empway"), ("준비 방법", "prepareway"), ("훈련 및 교육", "training"), ("자격/면허", "certification")]:
        lines = split_lines(detail.get(key, ""))
        if lines:
            prepare_parts.extend([f"{title}: {x}" for x in lines])

    st.markdown(
        '''
        <div class="section-shell">
            <div class="section-head">
                <div class="section-kicker">Extension</div>
                <div class="section-title">다음 단계로 탐색을 확장해 보세요</div>
                <div class="section-sub">연관 직업, 준비 방법, 관련 학과를 별도 모듈로 분리했습니다.</div>
            </div>
        ''',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        render_html_card("연관 직업", render_list(similar_jobs))
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        render_html_card("준비 방법", render_list(prepare_parts))
    with col2:
        render_html_card("관련 학과", render_list(majors))
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        render_html_card("추가 정보", render_list(contacts))

    st.markdown("</div>", unsafe_allow_html=True)


def render_detail_sections(detail: dict, focus_items: list):
    focus = set(focus_items)

    if "직무소개" in focus or not focus:
        render_role_section(detail)
    if "핵심 역량" in focus or not focus:
        render_capability_section(detail)
    if "전망/연봉" in focus or not focus:
        render_outlook_section(detail)
    if {"연관 직업", "준비 방법", "관련 학과", "추가 정보"} & focus or not focus:
        render_extension_section(detail)


def main():
    inject_css()

    if not DATA_FILE.exists():
        st.error(
            f"기본 데이터 파일을 찾지 못했습니다: {DATA_FILE.name}\\n\\n"
            "app.py와 같은 폴더에 career_jobs.xlsx가 있는지 확인해 주세요."
        )
        st.stop()

    df = get_data()

    search_query = st.text_input(
        "직업명 또는 키워드 검색",
        placeholder="예: IT컨설턴트, 상담, 디자인, 행정, 환경",
    )
    results = search_jobs(df, search_query, top_n=30)

    if results.empty:
        st.markdown(
            '''
            <div class="nav-shell">
                <div class="nav-title">직업 탐색 리포트</div>
                <div class="nav-sub">검색 결과가 없습니다. 다른 직업명이나 키워드로 다시 입력해 주세요.</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
        st.warning("검색 결과가 없습니다.")
        st.stop()

    job_options = results["job"].dropna().astype(str).tolist()

    if "selected_job" not in st.session_state or st.session_state.selected_job not in job_options:
        st.session_state.selected_job = job_options[0]

    if "focus_items" not in st.session_state:
        st.session_state.focus_items = ["직무소개", "핵심 역량", "전망/연봉"]

    initial_detail = get_job_detail(df, st.session_state.selected_job)
    selected_job, selected_focus = render_navigator(
        job_options=job_options,
        selected_job=st.session_state.selected_job,
        focus_items=st.session_state.focus_items,
        search_query=search_query,
        detail=initial_detail if initial_detail else {"job": st.session_state.selected_job},
    )

    st.session_state.selected_job = selected_job
    st.session_state.focus_items = selected_focus if selected_focus else []

    detail = get_job_detail(df, st.session_state.selected_job)
    if not detail:
        st.error("선택한 직업 정보를 찾을 수 없습니다.")
        st.stop()

    render_brief_dashboard(detail)
    render_detail_sections(detail, st.session_state.focus_items)


if __name__ == "__main__":
    main()
