"""
app.py - SmartCampus 360 — Main Streamlit Application

Entry point: streamlit run app.py
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pymongo.errors import DuplicateKeyError

import config
import analytics as an
import operations as ops
from database import ping, get_database, get_complaints_collection, get_students_collection, collection_stats
from models import initialize_database, COMPLAINT_JSON_SCHEMA, STUDENT_JSON_SCHEMA
from sample_data import insert_sample_data
from validators import ValidationError

# ─── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION & GLOBAL STYLES
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="SmartCampus 360",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Premium CSS ──────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 14px;
}

/* ── Background ── */
.stApp {
    background: #080E1D;
    color: #E2E8F0;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1525 0%, #0B1120 100%);
    border-right: 1px solid rgba(99,102,241,0.18);
}
[data-testid="stSidebar"] .stMarkdown p {
    color: #94A3B8;
    font-size: 0.78rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-weight: 600;
}

/* ── Main content area ── */
[data-testid="stAppViewContainer"] > .main {
    background: #080E1D;
}

.block-container {
    padding: 1.5rem 2rem 4rem !important;
    max-width: 1400px;
}

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, #0F1A2E 0%, #111827 100%);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(99,102,241,0.18);
}
div[data-testid="metric-container"] label {
    color: #94A3B8 !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #F1F5F9 !important;
    font-size: 2.1rem !important;
    font-weight: 800 !important;
    line-height: 1.1 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 0.78rem !important;
}

/* ── Section headings ── */
h1 { color: #F8FAFC !important; font-weight: 800 !important; letter-spacing: -0.02em; }
h2 { color: #E2E8F0 !important; font-weight: 700 !important; }
h3 { color: #CBD5E1 !important; font-weight: 600 !important; }

/* ── Dividers ── */
hr { border-color: rgba(99,102,241,0.15) !important; margin: 1.2rem 0 !important; }

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%);
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 0.5rem 1.2rem;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(99,102,241,0.3);
}
.stButton > button:hover {
    background: linear-gradient(135deg, #7C3AED 0%, #6366F1 100%);
    box-shadow: 0 4px 16px rgba(99,102,241,0.45);
    transform: translateY(-1px);
}
.stButton > button:active {
    transform: translateY(0);
}

/* ── Forms ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: #111827 !important;
    border: 1px solid rgba(99,102,241,0.25) !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: rgba(99,102,241,0.6) !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
}
.stSelectbox > div > div > div { color: #E2E8F0 !important; }

/* ── Date input ── */
.stDateInput > div > div > input {
    background: #111827 !important;
    border: 1px solid rgba(99,102,241,0.25) !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
}

/* ── DataFrame / Table ── */
.stDataFrame, [data-testid="stTable"] {
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: #0F1A2E !important;
    border: 1px solid rgba(99,102,241,0.18) !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
    font-weight: 600 !important;
}
.streamlit-expanderContent {
    background: #0D1525 !important;
    border: 1px solid rgba(99,102,241,0.12) !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
}

/* ── Alerts & messages ── */
.stAlert { border-radius: 10px !important; border: none !important; }
.stSuccess { background: rgba(16,185,129,0.12) !important; color: #34D399 !important; }
.stError   { background: rgba(239,68,68,0.12)  !important; color: #F87171 !important; }
.stWarning { background: rgba(245,158,11,0.12) !important; color: #FBBF24 !important; }
.stInfo    { background: rgba(99,102,241,0.12)  !important; color: #818CF8 !important; }

/* ── Tabs ── */
[data-testid="stTabBar"] { background: transparent !important; }
button[data-baseweb="tab"] {
    background: transparent !important;
    color: #94A3B8 !important;
    border-bottom: 2px solid transparent !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #818CF8 !important;
    border-bottom-color: #6366F1 !important;
    font-weight: 600 !important;
}
button[data-baseweb="tab"]:hover { color: #CBD5E1 !important; }

/* ── Sidebar nav items ── */
.nav-item {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.55rem 0.9rem;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
    margin-bottom: 0.2rem;
    color: #94A3B8;
    font-size: 0.88rem;
    font-weight: 500;
    text-decoration: none;
}
.nav-item:hover { background: rgba(99,102,241,0.12); color: #C7D2FE; }
.nav-item.active {
    background: rgba(99,102,241,0.2);
    color: #A5B4FC;
    font-weight: 600;
    border-left: 3px solid #6366F1;
}

/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.badge-pending    { background: rgba(245,158,11,0.15); color: #FBBF24; border: 1px solid rgba(245,158,11,0.3); }
.badge-progress   { background: rgba(99,102,241,0.15); color: #818CF8; border: 1px solid rgba(99,102,241,0.3); }
.badge-resolved   { background: rgba(16,185,129,0.15); color: #34D399; border: 1px solid rgba(16,185,129,0.3); }
.badge-high       { background: rgba(239,68,68,0.15);  color: #F87171; border: 1px solid rgba(239,68,68,0.3); }
.badge-medium     { background: rgba(245,158,11,0.12); color: #FBBF24; border: 1px solid rgba(245,158,11,0.25);}
.badge-low        { background: rgba(16,185,129,0.12); color: #6EE7B7; border: 1px solid rgba(16,185,129,0.25);}

/* ── KPI card custom ── */
.kpi-card {
    background: linear-gradient(135deg, #0F1A2E 0%, #111827 100%);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35);
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; right: 0;
    width: 80px; height: 80px;
    border-radius: 50%;
    filter: blur(30px);
    opacity: 0.25;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(99,102,241,0.2);
}
.kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #64748B;
    margin-bottom: 0.5rem;
}
.kpi-value {
    font-size: 2.4rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.03em;
    margin-bottom: 0.3rem;
}
.kpi-sub {
    font-size: 0.75rem;
    color: #475569;
    font-weight: 500;
}

/* ── Page header ── */
.page-header {
    background: linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(79,70,229,0.04) 100%);
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 14px;
    padding: 1.4rem 1.8rem;
    margin-bottom: 1.5rem;
}
.page-header h1 { margin: 0 !important; font-size: 1.6rem !important; }
.page-header p  { color: #64748B; margin: 0.3rem 0 0; font-size: 0.85rem; }

/* ── Complaint card ── */
.complaint-card {
    background: #0D1525;
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
    transition: border-color 0.2s;
}
.complaint-card:hover { border-color: rgba(99,102,241,0.4); }

/* ── Connection indicator ── */
.conn-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
}
.conn-ok    { background: #10B981; box-shadow: 0 0 6px #10B981; animation: pulse-green 2s infinite; }
.conn-fail  { background: #EF4444; box-shadow: 0 0 6px #EF4444; }

@keyframes pulse-green {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.5; }
}

/* ── Chart containers ── */
.chart-card {
    background: #0D1525;
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 14px;
    padding: 1.2rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.25);
}

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 3rem 2rem;
    color: #475569;
}
.empty-state h3 { color: #64748B !important; margin-bottom: 0.5rem; }
.empty-state p  { font-size: 0.9rem; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #080E1D; }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.4); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,0.7); }
</style>
""",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════════
# CHART HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

_DARK_TEMPLATE = "plotly_dark"
_CHART_BG = "rgba(13,21,37,0)"
_PAPER_BG = "rgba(0,0,0,0)"

_COLOR_SCALE = [
    "#6366F1", "#8B5CF6", "#EC4899", "#F59E0B",
    "#10B981", "#06B6D4", "#F43F5E", "#84CC16",
]

_STATUS_COLORS = {
    "Pending": "#F59E0B",
    "In Progress": "#6366F1",
    "Resolved": "#10B981",
}
_PRIORITY_COLORS = {
    "High": "#EF4444",
    "Medium": "#F59E0B",
    "Low": "#10B981",
}


def _chart_layout(fig, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor=_PAPER_BG,
        plot_bgcolor=_CHART_BG,
        font=dict(family="Inter, sans-serif", color="#94A3B8", size=12),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            bgcolor="rgba(13,21,37,0.8)",
            bordercolor="rgba(99,102,241,0.2)",
            borderwidth=1,
            font=dict(size=11),
        ),
        xaxis=dict(
            gridcolor="rgba(99,102,241,0.08)",
            zerolinecolor="rgba(99,102,241,0.15)",
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            gridcolor="rgba(99,102,241,0.08)",
            zerolinecolor="rgba(99,102,241,0.15)",
            tickfont=dict(size=11),
        ),
    )
    return fig


def _donut_chart(labels, values, title="", colors=None) -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.6,
            marker=dict(colors=colors or _COLOR_SCALE, line=dict(color="#080E1D", width=2)),
            textinfo="label+percent",
            hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#E2E8F0")),
        showlegend=True,
        paper_bgcolor=_PAPER_BG,
        plot_bgcolor=_CHART_BG,
        font=dict(family="Inter", color="#94A3B8"),
        margin=dict(l=10, r=10, t=40, b=10),
        height=340,
        legend=dict(bgcolor="rgba(13,21,37,0.8)", bordercolor="rgba(99,102,241,0.2)", borderwidth=1),
    )
    return fig


def _bar_chart(x, y, title="", color="#6366F1", orientation="v") -> go.Figure:
    if orientation == "h":
        fig = go.Figure(
            go.Bar(
                x=y, y=x, orientation="h",
                marker=dict(color=color, line=dict(color="rgba(0,0,0,0)")),
                hovertemplate="%{y}: %{x}<extra></extra>",
            )
        )
    else:
        fig = go.Figure(
            go.Bar(
                x=x, y=y,
                marker=dict(color=color, line=dict(color="rgba(0,0,0,0)")),
                hovertemplate="%{x}: %{y}<extra></extra>",
            )
        )
    fig.update_layout(title=dict(text=title, font=dict(size=14, color="#E2E8F0")))
    return _chart_layout(fig)


def _area_chart(dates, counts, title="") -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=dates, y=counts,
            mode="lines+markers",
            fill="tozeroy",
            line=dict(color="#6366F1", width=2.5),
            fillcolor="rgba(99,102,241,0.12)",
            marker=dict(size=5, color="#818CF8"),
            hovertemplate="%{x}: %{y} complaints<extra></extra>",
        )
    )
    fig.update_layout(title=dict(text=title, font=dict(size=14, color="#E2E8F0")))
    return _chart_layout(fig, height=300)


# ═══════════════════════════════════════════════════════════════════════════════
# CONNECTION & DB INIT (cached)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(ttl=60)
def _db_ping() -> dict:
    return ping()


@st.cache_resource
def _ensure_db_initialized():
    """Initialize DB schema once per session."""
    try:
        return initialize_database()
    except Exception as exc:
        return {"error": str(exc)}


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

PAGES = [
    ("🏠", "Overview",          "Executive dashboard with live KPIs"),
    ("📋", "Complaints",        "Browse, filter & manage complaints"),
    ("➕", "Create Complaint",  "Submit a new campus complaint"),
    ("📊", "Analytics",         "Aggregation pipelines & charts"),
    ("🎓", "Students",          "Student directory management"),
    ("🔍", "Database Explorer", "Live MongoDB schema & query explorer"),
    ("⚙️", "Settings",          "Configuration & project info"),
]

with st.sidebar:
    # ── Brand ──────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="padding:1.2rem 0.5rem 1rem; border-bottom:1px solid rgba(99,102,241,0.2);">
          <div style="font-size:1.4rem; font-weight:800; color:#F8FAFC; letter-spacing:-0.02em;">
            🎓 SmartCampus
            <span style="color:#6366F1;">360</span>
          </div>
          <div style="font-size:0.7rem; color:#475569; margin-top:0.2rem; font-weight:500;
                      letter-spacing:0.05em; text-transform:uppercase;">
            Intelligent Campus Analytics
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)

    # ── Navigation ─────────────────────────────────────────────────────────────
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Overview"

    for icon, name, _ in PAGES:
        is_active = st.session_state.current_page == name
        active_cls = "active" if is_active else ""
        if st.button(
            f"{icon}  {name}",
            key=f"nav_{name}",
            use_container_width=True,
        ):
            st.session_state.current_page = name
            st.rerun()

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.divider()

    # ── DB Connection Status ───────────────────────────────────────────────────
    _status = _db_ping()
    if _status["connected"]:
        st.markdown(
            f"""<div style="font-size:0.75rem; color:#475569; padding:0.6rem 0.2rem;">
              <span class="conn-dot conn-ok"></span>
              <span style="color:#34D399; font-weight:600;">Connected</span><br/>
              <span style="color:#334155; margin-left:14px;">{_status['database']}</span>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""<div style="font-size:0.75rem; color:#475569; padding:0.6rem 0.2rem;">
              <span class="conn-dot conn-fail"></span>
              <span style="color:#F87171; font-weight:600;">Disconnected</span><br/>
              <span style="color:#7F1D1D; margin-left:14px; font-size:0.7rem;">
                {_status.get('error','')[:60]}
              </span>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Date ──────────────────────────────────────────────────────────────────
    now_local = datetime.now()
    st.markdown(
        f"""<div style="font-size:0.72rem; color:#334155; padding:0.3rem 0.2rem;">
          📅 {now_local.strftime('%d %b %Y • %H:%M')}
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Refresh ───────────────────────────────────────────────────────────────
    if st.button("🔄 Refresh Data", use_container_width=True, key="global_refresh"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    st.markdown(
        """<div style="font-size:0.65rem; color:#1E293B; padding:0.5rem 0.2rem; margin-top:0.5rem;">
          CSE494 • Intelligent NoSQL Databases
        </div>""",
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _require_db():
    """Display a friendly error if DB is not connected and stop page rendering."""
    if not _db_ping()["connected"]:
        st.error(
            "⚠️ MongoDB is not reachable. Please check your connection and try again.",
            icon="🔌",
        )
        with st.expander("Connection details"):
            status = _db_ping()
            st.json(status)
        st.stop()


def _page_header(title: str, subtitle: str):
    st.markdown(
        f"""<div class="page-header">
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>""",
        unsafe_allow_html=True,
    )


def _status_badge(status: str) -> str:
    cls = {"Pending": "badge-pending", "In Progress": "badge-progress", "Resolved": "badge-resolved"}.get(status, "badge-pending")
    return f'<span class="badge {cls}">{status}</span>'


def _priority_badge(priority: str) -> str:
    cls = {"High": "badge-high", "Medium": "badge-medium", "Low": "badge-low"}.get(priority, "badge-low")
    return f'<span class="badge {cls}">{priority}</span>'


def _df_from_complaints(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ["created_at", "updated_at", "resolved_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
    if "_id" in df.columns:
        df.drop(columns=["_id"], inplace=True)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

def page_overview():
    _require_db()
    _page_header(
        "🏠 Executive Overview",
        "Live dashboard powered by MongoDB aggregation pipelines",
    )

    # ── KPI Summary ────────────────────────────────────────────────────────────
    with st.spinner("Loading metrics…"):
        summary = an.get_dashboard_summary()

    total = summary.get("total", 0)
    resolved = summary.get("resolved", 0)
    pending = summary.get("pending", 0)
    in_prog = summary.get("in_progress", 0)
    high_unresolved = summary.get("high_priority_unresolved", 0)
    rate = summary.get("resolution_rate", 0.0)
    avg_hours = summary.get("avg_resolution_hours")

    if total == 0:
        st.markdown(
            """<div class="empty-state">
              <h3>📭 No Complaints Yet</h3>
              <p>The database is empty. Go to <strong>Settings</strong> to load sample data,
              or <strong>Create Complaint</strong> to add your first record.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📌 Total Complaints", total)
    with col2:
        st.metric("🟡 Open (Pending)", pending, delta=f"{in_prog} In Progress", delta_color="normal")
    with col3:
        st.metric("🔴 High-Priority Open", high_unresolved)
    with col4:
        st.metric("✅ Resolution Rate", f"{rate}%",
                  delta=f"~{avg_hours}h avg" if avg_hours else "—",
                  delta_color="normal")

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # Second KPI row
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("🔵 In Progress", in_prog)
    with col6:
        st.metric("🟢 Resolved", resolved)
    with col7:
        unresolved = pending + in_prog
        st.metric("⏳ Unresolved", unresolved)
    with col8:
        avg_display = f"{avg_hours}h" if avg_hours else "N/A"
        st.metric("⏱ Avg Resolution Time", avg_display)

    st.divider()

    # ── Charts Row 1 ───────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        cat_data = an.complaints_by_category()
        if cat_data:
            labels = [d["category"] for d in cat_data]
            values = [d["count"] for d in cat_data]
            fig = _donut_chart(labels, values, "Complaints by Category")
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        status_data = an.complaints_by_status()
        if status_data:
            labels = [d["status"] for d in status_data]
            values = [d["count"] for d in status_data]
            colors = [_STATUS_COLORS.get(s, "#6366F1") for s in labels]
            fig = _donut_chart(labels, values, "Status Distribution", colors)
            st.plotly_chart(fig, use_container_width=True)

    # ── Trend Chart ────────────────────────────────────────────────────────────
    trend_data = an.complaint_trends_daily(days=60)
    if trend_data:
        dates = [d["date"] for d in trend_data]
        counts = [d["count"] for d in trend_data]
        fig = _area_chart(dates, counts, "Complaint Volume — Last 60 Days")
        st.plotly_chart(fig, use_container_width=True)

    # ── Charts Row 2 ───────────────────────────────────────────────────────────
    c3, c4 = st.columns(2)

    with c3:
        pri_data = an.complaints_by_priority()
        if pri_data:
            labels = [d["priority"] for d in pri_data]
            values = [d["count"] for d in pri_data]
            colors = [_PRIORITY_COLORS.get(p, "#6366F1") for p in labels]
            fig = _donut_chart(labels, values, "Priority Distribution", colors)
            st.plotly_chart(fig, use_container_width=True)

    with c4:
        dept_data = an.department_workload()
        if dept_data:
            depts = [d["department"][:20] for d in dept_data[:8]]
            totals = [d["total"] for d in dept_data[:8]]
            fig = _bar_chart(totals, depts, "Department Workload", "#6366F1", orientation="h")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Recent Complaints Table ────────────────────────────────────────────────
    st.markdown("### 📋 Recent Complaints")
    recent = ops.get_complaints(limit=10)
    if recent:
        df = _df_from_complaints(recent)
        display_cols = ["complaint_id", "student_id", "category", "priority", "status", "location", "created_at"]
        display_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No recent complaints found.")

    st.divider()

    # ── Quick Actions ──────────────────────────────────────────────────────────
    st.markdown("### ⚡ Quick Actions")
    qa1, qa2, qa3 = st.columns(3)
    with qa1:
        if st.button("➕ Register New Complaint", use_container_width=True):
            st.session_state.current_page = "Create Complaint"
            st.rerun()
    with qa2:
        if st.button("📋 View All Open Issues", use_container_width=True):
            st.session_state.current_page = "Complaints"
            st.rerun()
    with qa3:
        if st.button("📊 Open Analytics", use_container_width=True):
            st.session_state.current_page = "Analytics"
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: COMPLAINTS
# ═══════════════════════════════════════════════════════════════════════════════

def page_complaints():
    _require_db()
    _page_header(
        "📋 Complaint Management",
        "Search, filter, update, and resolve campus complaints",
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    with st.expander("🔍 Search & Filters", expanded=True):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            search = st.text_input("Search (ID / Student / Description)", placeholder="e.g. CMP1001 or WiFi…")
        with fc2:
            filter_status = st.selectbox("Status", ["All"] + config.STATUSES)
            filter_category = st.selectbox("Category", ["All"] + config.CATEGORIES)
        with fc3:
            filter_priority = st.selectbox("Priority", ["All"] + config.PRIORITIES)
            filter_dept = st.selectbox("Department", ["All"] + config.DEPARTMENTS)

        dc1, dc2 = st.columns(2)
        with dc1:
            date_from = st.date_input("Date From", value=None)
        with dc2:
            date_to = st.date_input("Date To", value=None)

    # Build filter args
    filter_kwargs = dict(
        search_text=search or None,
        status=None if filter_status == "All" else filter_status,
        category=None if filter_category == "All" else filter_category,
        priority=None if filter_priority == "All" else filter_priority,
        department=None if filter_dept == "All" else filter_dept,
        date_from=(
            datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
            if date_from else None
        ),
        date_to=(
            datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc)
            if date_to else None
        ),
    )

    total_filtered = ops.count_complaints(**filter_kwargs)
    complaints = ops.get_complaints(**filter_kwargs, limit=50)

    # ── Action bar ────────────────────────────────────────────────────────────
    ab1, ab2, ab3 = st.columns([4, 2, 2])
    with ab1:
        st.markdown(
            f"<p style='color:#64748B; font-size:0.85rem; margin:0.5rem 0;'>"
            f"Showing <strong style='color:#E2E8F0'>{len(complaints)}</strong> of "
            f"<strong style='color:#E2E8F0'>{total_filtered}</strong> results</p>",
            unsafe_allow_html=True,
        )
    with ab2:
        if complaints:
            df_export = _df_from_complaints(complaints)
            csv = df_export.to_csv(index=False)
            st.download_button(
                "⬇ Export CSV",
                data=csv,
                file_name=f"complaints_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with ab3:
        if st.button("➕ New Complaint", use_container_width=True):
            st.session_state.current_page = "Create Complaint"
            st.rerun()

    if not complaints:
        st.markdown(
            """<div class="empty-state">
              <h3>🔎 No Results Found</h3>
              <p>Adjust your filters or create a new complaint.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # ── Complaint Table ────────────────────────────────────────────────────────
    df = _df_from_complaints(complaints)
    display_cols = ["complaint_id", "student_id", "category", "priority",
                    "status", "department", "location", "created_at"]
    display_cols = [c for c in display_cols if c in df.columns]

    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

    st.divider()

    # ── Detail / Edit Panel ───────────────────────────────────────────────────
    st.markdown("### 🔧 View / Edit Complaint")

    complaint_ids = [c["complaint_id"] for c in complaints]
    selected_id = st.selectbox("Select Complaint ID", complaint_ids, key="sel_complaint")

    if selected_id:
        doc = ops.get_complaint(selected_id)
        if not doc:
            st.error(f"Complaint '{selected_id}' not found.")
            return

        # Display detail
        with st.expander(f"📄 Detail: {selected_id}", expanded=True):
            d1, d2, d3 = st.columns(3)
            with d1:
                st.markdown(f"**Student ID:** {doc['student_id']}")
                st.markdown(f"**Category:** {doc['category']}")
                st.markdown(f"**Location:** {doc['location']}")
            with d2:
                st.markdown(
                    f"**Status:** {_status_badge(doc['status'])}",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"**Priority:** {_priority_badge(doc['priority'])}",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Department:** {doc['department']}")
            with d3:
                st.markdown(f"**Created:** {doc['created_at']}")
                st.markdown(f"**Updated:** {doc['updated_at']}")
                if doc.get("resolved_at"):
                    st.markdown(f"**Resolved:** {doc['resolved_at']}")

            st.markdown(f"**Description:**  \n{doc['description']}")
            if doc.get("resolution_notes"):
                st.markdown(f"**Resolution Notes:**  \n{doc['resolution_notes']}")

        # ── Edit Form ──────────────────────────────────────────────────────────
        with st.expander("✏️ Edit Complaint", expanded=False):
            with st.form(f"edit_form_{selected_id}"):
                ef1, ef2 = st.columns(2)
                with ef1:
                    new_status = st.selectbox(
                        "Status",
                        config.STATUSES,
                        index=config.STATUSES.index(doc["status"]),
                    )
                    new_priority = st.selectbox(
                        "Priority",
                        config.PRIORITIES,
                        index=config.PRIORITIES.index(doc["priority"]),
                    )
                with ef2:
                    new_dept = st.selectbox(
                        "Department",
                        config.DEPARTMENTS,
                        index=(config.DEPARTMENTS.index(doc["department"])
                               if doc["department"] in config.DEPARTMENTS else 0),
                    )
                    new_location = st.text_input("Location", value=doc["location"])

                new_desc = st.text_area("Description", value=doc["description"], height=100)
                new_notes = st.text_area(
                    "Resolution Notes (required if resolving)",
                    value=doc.get("resolution_notes") or "",
                    height=80,
                )

                submitted = st.form_submit_button("💾 Save Changes", use_container_width=True)
                if submitted:
                    updates: dict = {
                        "status": new_status,
                        "priority": new_priority,
                        "department": new_dept,
                        "location": new_location.strip(),
                        "description": new_desc.strip(),
                    }
                    if new_notes.strip():
                        updates["resolution_notes"] = new_notes.strip()
                    try:
                        modified = ops.update_complaint(selected_id, updates)
                        if modified:
                            st.success(f"✅ Complaint {selected_id} updated successfully.")
                        else:
                            st.info("No changes were made.")
                        st.rerun()
                    except (ValidationError, KeyError) as exc:
                        st.error(f"Update failed: {exc}")

        # ── Quick Resolve ─────────────────────────────────────────────────────
        if doc["status"] != "Resolved":
            with st.expander("✅ Quick Resolve", expanded=False):
                with st.form(f"resolve_form_{selected_id}"):
                    r_notes = st.text_area("Resolution Notes", height=80)
                    r_submit = st.form_submit_button("✅ Mark as Resolved", use_container_width=True)
                    if r_submit:
                        try:
                            ops.resolve_complaint(selected_id, r_notes.strip() or None)
                            st.success(f"✅ Complaint {selected_id} resolved.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Error: {exc}")

        # ── Delete ────────────────────────────────────────────────────────────
        with st.expander("🗑️ Delete Complaint", expanded=False):
            st.warning(
                "⚠️ Deletion is permanent and cannot be undone. "
                "Type the complaint ID below to confirm."
            )
            with st.form(f"delete_form_{selected_id}"):
                confirm_id = st.text_input("Confirm Complaint ID")
                del_submit = st.form_submit_button("🗑️ Delete", use_container_width=True)
                if del_submit:
                    if confirm_id.strip() == selected_id:
                        try:
                            deleted = ops.delete_complaint(selected_id)
                            if deleted:
                                st.success(f"Complaint {selected_id} has been deleted.")
                                st.rerun()
                            else:
                                st.error("Complaint not found.")
                        except Exception as exc:
                            st.error(f"Error: {exc}")
                    else:
                        st.error("IDs do not match. Deletion cancelled.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: CREATE COMPLAINT
# ═══════════════════════════════════════════════════════════════════════════════

def page_create_complaint():
    _require_db()
    _page_header(
        "➕ Create Complaint",
        "Submit a new campus complaint — all fields are stored in MongoDB",
    )

    # Prevent duplicate submission via session flag
    if st.session_state.get("complaint_just_created"):
        cid = st.session_state.pop("complaint_just_created")
        st.success(f"🎉 Complaint **{cid}** submitted successfully!")
        st.balloons()
        if st.button("➕ Submit Another"):
            st.rerun()
        return

    # Pre-generate a complaint ID suggestion
    try:
        suggested_id = ops.generate_complaint_id()
    except Exception:
        suggested_id = "CMP1001"

    # Fetch student IDs for helper dropdown
    try:
        student_ids = ops.get_all_student_ids()
    except Exception:
        student_ids = []

    with st.form("create_complaint_form", clear_on_submit=False):
        st.markdown("#### 🧾 Complaint Details")
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            complaint_id = st.text_input(
                "Complaint ID *",
                value=suggested_id,
                help="Auto-generated. Edit only if needed.",
            )
        with r1c2:
            if student_ids:
                student_id = st.selectbox("Student ID *", student_ids)
            else:
                student_id = st.text_input(
                    "Student ID *",
                    placeholder="e.g. STU101",
                    help="Format: STU followed by number",
                )

        r2c1, r2c2 = st.columns(2)
        with r2c1:
            category = st.selectbox("Category *", config.CATEGORIES)
        with r2c2:
            default_dept = config.CATEGORY_DEPARTMENT_MAP.get(category, config.DEPARTMENTS[0])
            department = st.selectbox(
                "Department *",
                config.DEPARTMENTS,
                index=config.DEPARTMENTS.index(default_dept),
            )

        r3c1, r3c2 = st.columns(2)
        with r3c1:
            priority = st.selectbox("Priority *", config.PRIORITIES, index=1)
        with r3c2:
            location = st.text_input("Building / Location *", placeholder="e.g. Block A, Room 204")

        description = st.text_area(
            "Description * (min 10 characters)",
            placeholder="Describe the issue in detail…",
            height=130,
        )
        additional_details = st.text_area(
            "Additional Details (optional)",
            placeholder="Any extra context, photos description, or reference details…",
            height=80,
        )

        st.markdown(
            "<p style='color:#475569; font-size:0.78rem; margin:0.3rem 0;'>"
            "* Required fields. Initial status is automatically set to <strong>Pending</strong>.</p>",
            unsafe_allow_html=True,
        )

        submitted = st.form_submit_button(
            "🚀 Submit Complaint", use_container_width=True
        )

        if submitted:
            # Client-side quick checks before hitting DB
            errors = []
            if not complaint_id.strip():
                errors.append("Complaint ID is required.")
            if not student_id or (isinstance(student_id, str) and not student_id.strip()):
                errors.append("Student ID is required.")
            if not location.strip():
                errors.append("Location is required.")
            if len(description.strip()) < config.MIN_DESCRIPTION_LENGTH:
                errors.append(
                    f"Description must be at least {config.MIN_DESCRIPTION_LENGTH} characters."
                )
            if errors:
                for e in errors:
                    st.error(e)
            else:
                with st.spinner("Saving complaint to MongoDB…"):
                    try:
                        ops.create_complaint(
                            complaint_id=complaint_id.strip(),
                            student_id=student_id.strip() if isinstance(student_id, str) else student_id,
                            category=category,
                            description=description.strip(),
                            location=location.strip(),
                            priority=priority,
                            department=department,
                            additional_details=additional_details.strip() or None,
                        )
                        st.session_state["complaint_just_created"] = complaint_id.strip()
                        st.rerun()
                    except DuplicateKeyError:
                        st.error(
                            f"⚠️ Complaint ID **{complaint_id.strip()}** already exists. "
                            f"Try **{ops.generate_complaint_id()}** instead."
                        )
                    except (ValidationError, Exception) as exc:
                        st.error(f"❌ Submission failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

def page_analytics():
    _require_db()
    _page_header(
        "📊 Analytics & Insights",
        "MongoDB aggregation pipelines powering interactive visualizations",
    )

    total = an.resolved_vs_unresolved().get("total", 0)
    if total == 0:
        st.markdown(
            """<div class="empty-state">
              <h3>📭 No Data Available</h3>
              <p>Initialize sample data in <strong>Settings</strong> to explore analytics.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # ── Date Range Filter ──────────────────────────────────────────────────────
    with st.expander("📅 Global Date Range Filter", expanded=False):
        af1, af2 = st.columns(2)
        with af1:
            a_date_from = st.date_input("From", value=None, key="a_from")
        with af2:
            a_date_to = st.date_input("To", value=None, key="a_to")

    tabs = st.tabs([
        "📂 Category", "🔄 Status", "⚡ Priority",
        "📈 Trends", "⏱ Resolution Time", "🏢 Departments",
        "🚨 High Priority", "📊 Summary",
    ])

    # ─ Tab 1: Category ─────────────────────────────────────────────────────────
    with tabs[0]:
        data = an.complaints_by_category()
        if data:
            labels = [d["category"] for d in data]
            values = [d["count"] for d in data]
            c1, c2 = st.columns(2)
            with c1:
                fig = _donut_chart(labels, values, "Category Distribution")
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig2 = _bar_chart(labels, values, "Complaints per Category", "#6366F1")
                st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    # ─ Tab 2: Status ───────────────────────────────────────────────────────────
    with tabs[1]:
        data = an.complaints_by_status()
        if data:
            labels = [d["status"] for d in data]
            values = [d["count"] for d in data]
            colors = [_STATUS_COLORS.get(s, "#6366F1") for s in labels]
            c1, c2 = st.columns(2)
            with c1:
                fig = _donut_chart(labels, values, "Status Distribution", colors)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig2 = _bar_chart(
                    values, labels, "Count by Status", colors, orientation="h"
                )
                st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    # ─ Tab 3: Priority ─────────────────────────────────────────────────────────
    with tabs[2]:
        data = an.complaints_by_priority()
        if data:
            labels = [d["priority"] for d in data]
            values = [d["count"] for d in data]
            colors = [_PRIORITY_COLORS.get(p, "#6366F1") for p in labels]
            c1, c2 = st.columns(2)
            with c1:
                fig = _donut_chart(labels, values, "Priority Distribution", colors)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig2 = go.Figure(go.Bar(
                    x=labels, y=values,
                    marker=dict(color=colors),
                    hovertemplate="%{x}: %{y}<extra></extra>",
                ))
                fig2.update_layout(title=dict(text="Priority Breakdown", font=dict(size=14, color="#E2E8F0")))
                _chart_layout(fig2)
                st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    # ─ Tab 4: Trends ───────────────────────────────────────────────────────────
    with tabs[3]:
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            days_range = st.slider("Days to show", 7, 90, 30)

        daily = an.complaint_trends_daily(days=days_range)
        monthly = an.complaint_trends_monthly(months=12)

        if daily:
            dates = [d["date"] for d in daily]
            counts = [d["count"] for d in daily]
            fig = _area_chart(dates, counts, f"Daily Complaints — Last {days_range} Days")
            st.plotly_chart(fig, use_container_width=True)

        if monthly:
            months_l = [d["month"] for d in monthly]
            m_counts = [d["count"] for d in monthly]
            fig2 = _bar_chart(months_l, m_counts, "Monthly Complaint Volume", "#8B5CF6")
            st.plotly_chart(fig2, use_container_width=True)

        if daily:
            st.dataframe(pd.DataFrame(daily), use_container_width=True, hide_index=True)

    # ─ Tab 5: Resolution Time ─────────────────────────────────────────────────
    with tabs[4]:
        data = an.avg_resolution_time_by_category()
        if data:
            cats = [d["category"] for d in data]
            hours = [d["avg_hours"] for d in data]
            fig = go.Figure(go.Bar(
                x=hours, y=cats, orientation="h",
                marker=dict(
                    color=hours,
                    colorscale=[[0, "#10B981"], [0.5, "#F59E0B"], [1, "#EF4444"]],
                    showscale=True,
                    colorbar=dict(title="Hours"),
                ),
                hovertemplate="%{y}: %{x:.1f}h avg<extra></extra>",
            ))
            fig.update_layout(
                title=dict(text="Avg Resolution Time by Category (Hours)", font=dict(size=14, color="#E2E8F0"))
            )
            _chart_layout(fig, height=400)
            st.plotly_chart(fig, use_container_width=True)
            df = pd.DataFrame(data)
            df.columns = ["Category", "Avg Hours", "Complaint Count"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No resolved complaints with valid timestamps found.")

    # ─ Tab 6: Departments ──────────────────────────────────────────────────────
    with tabs[5]:
        data = an.department_workload()
        if data:
            depts = [d["department"] for d in data]
            totals = [d["total"] for d in data]
            unresoled = [d["unresolved"] for d in data]
            resolved_c = [d["resolved"] for d in data]

            fig = go.Figure()
            fig.add_trace(go.Bar(name="Resolved", x=depts, y=resolved_c, marker_color="#10B981"))
            fig.add_trace(go.Bar(name="Unresolved", x=depts, y=unresoled, marker_color="#EF4444"))
            fig.update_layout(
                barmode="stack",
                title=dict(text="Department Workload (Stacked)", font=dict(size=14, color="#E2E8F0")),
            )
            _chart_layout(fig, height=400)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    # ─ Tab 7: High Priority ────────────────────────────────────────────────────
    with tabs[6]:
        data = an.high_priority_unresolved(limit=30)
        if data:
            st.markdown(
                f"<p style='color:#F87171; font-weight:600;'>🚨 {len(data)} High-Priority Unresolved Complaints</p>",
                unsafe_allow_html=True,
            )
            df = pd.DataFrame(data)
            for col in ["created_at"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")
            if "_id" in df.columns:
                df.drop(columns=["_id"], inplace=True)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No high-priority unresolved complaints!")

    # ─ Tab 8: Summary ──────────────────────────────────────────────────────────
    with tabs[7]:
        summary = an.get_dashboard_summary()
        top5 = an.top_five_categories()
        rv = an.resolved_vs_unresolved()

        s1, s2 = st.columns(2)
        with s1:
            st.markdown("#### 📌 Overall Summary")
            for k, v in summary.items():
                if v is not None:
                    label = k.replace("_", " ").title()
                    st.markdown(
                        f"<div style='padding:0.4rem 0; border-bottom:1px solid rgba(99,102,241,0.1);'>"
                        f"<span style='color:#64748B;'>{label}</span>"
                        f"<span style='float:right; color:#E2E8F0; font-weight:600;'>{v}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
        with s2:
            st.markdown("#### 🏆 Top 5 Categories")
            if top5:
                labels = [d["category"] for d in top5]
                values = [d["count"] for d in top5]
                fig = _bar_chart(labels, values, "", "#6366F1")
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### ✅ Resolved vs Unresolved")
        rv_col1, rv_col2 = st.columns(2)
        with rv_col1:
            fig_rv = go.Figure(go.Bar(
                x=["Resolved", "Pending", "In Progress"],
                y=[rv.get("resolved", 0), rv.get("pending", 0), rv.get("in_progress", 0)],
                marker=dict(color=["#10B981", "#F59E0B", "#6366F1"]),
            ))
            _chart_layout(fig_rv)
            st.plotly_chart(fig_rv, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: STUDENTS
# ═══════════════════════════════════════════════════════════════════════════════

def page_students():
    _require_db()
    _page_header(
        "🎓 Student Directory",
        "Manage student records linked to complaint submissions",
    )

    tab_list, tab_add = st.tabs(["📋 Students", "➕ Add Student"])

    # ─ List & Manage ────────────────────────────────────────────────────────────
    with tab_list:
        search_s = st.text_input("Search students", placeholder="Name, ID, email or building…")
        students = ops.get_students(search_text=search_s or None, limit=100)
        total_s = ops.count_students(search_text=search_s or None)

        st.markdown(
            f"<p style='color:#64748B; font-size:0.85rem;'>"
            f"Found <strong style='color:#E2E8F0'>{total_s}</strong> students</p>",
            unsafe_allow_html=True,
        )

        if not students:
            st.markdown(
                """<div class="empty-state">
                  <h3>📭 No Students Found</h3>
                  <p>Add students or load sample data from Settings.</p>
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            df_s = pd.DataFrame(students)
            if "created_at" in df_s.columns:
                df_s["created_at"] = pd.to_datetime(df_s["created_at"], errors="coerce").dt.strftime("%Y-%m-%d")
            if "_id" in df_s.columns:
                df_s.drop(columns=["_id"], inplace=True)
            st.dataframe(df_s, use_container_width=True, hide_index=True)

            # ── Edit / Delete ───────────────────────────────────────────────────
            st.divider()
            st.markdown("### ✏️ Edit / Delete Student")
            sel_student = st.selectbox("Select Student", [s["student_id"] for s in students])
            if sel_student:
                sdoc = ops.get_student(sel_student)
                if sdoc:
                    with st.expander(f"Edit {sel_student}", expanded=False):
                        with st.form(f"edit_student_{sel_student}"):
                            new_name = st.text_input("Name", value=sdoc["name"])
                            new_email = st.text_input("Email", value=sdoc["email"])
                            new_building = st.text_input("Building", value=sdoc["building"])
                            upd = st.form_submit_button("💾 Update")
                            if upd:
                                try:
                                    ops.update_student(sel_student, {
                                        "name": new_name.strip(),
                                        "email": new_email.strip(),
                                        "building": new_building.strip(),
                                    })
                                    st.success("Student updated.")
                                    st.rerun()
                                except (ValidationError, KeyError) as exc:
                                    st.error(str(exc))

                    with st.expander(f"🗑️ Delete {sel_student}", expanded=False):
                        st.warning("Deletion is blocked if the student has complaints.")
                        with st.form(f"del_student_{sel_student}"):
                            confirm_s = st.text_input("Confirm Student ID")
                            del_s = st.form_submit_button("Delete")
                            if del_s:
                                if confirm_s.strip() == sel_student:
                                    try:
                                        ops.delete_student(sel_student)
                                        st.success(f"Student {sel_student} deleted.")
                                        st.rerun()
                                    except (ValueError, Exception) as exc:
                                        st.error(str(exc))
                                else:
                                    st.error("IDs do not match.")

                    # Complaint history
                    with st.expander(f"📋 Complaint History: {sel_student}", expanded=False):
                        history = an.student_complaint_history(sel_student)
                        if history:
                            df_h = pd.DataFrame(history)
                            for c in ["created_at", "resolved_at"]:
                                if c in df_h.columns:
                                    df_h[c] = pd.to_datetime(df_h[c], errors="coerce").dt.strftime("%Y-%m-%d")
                            st.dataframe(df_h, use_container_width=True, hide_index=True)
                        else:
                            st.info("No complaints for this student.")

    # ─ Add Student ─────────────────────────────────────────────────────────────
    with tab_add:
        if st.session_state.get("student_just_added"):
            sid = st.session_state.pop("student_just_added")
            st.success(f"✅ Student **{sid}** added!")
            if st.button("➕ Add Another"):
                st.rerun()
            return

        try:
            suggested_sid = ops.generate_student_id()
        except Exception:
            suggested_sid = "STU101"

        with st.form("add_student_form"):
            s1c1, s1c2 = st.columns(2)
            with s1c1:
                new_sid = st.text_input("Student ID *", value=suggested_sid)
            with s1c2:
                new_sname = st.text_input("Full Name *", placeholder="e.g. Arjun Mehta")
            s2c1, s2c2 = st.columns(2)
            with s2c1:
                new_semail = st.text_input("Email *", placeholder="student@campus.edu")
            with s2c2:
                new_sbuilding = st.text_input("Building *", placeholder="e.g. Block A")

            add_sub = st.form_submit_button("➕ Add Student", use_container_width=True)
            if add_sub:
                try:
                    ops.create_student(new_sid.strip(), new_sname.strip(),
                                       new_semail.strip(), new_sbuilding.strip())
                    st.session_state["student_just_added"] = new_sid.strip()
                    st.rerun()
                except DuplicateKeyError:
                    st.error(f"Student ID '{new_sid.strip()}' already exists.")
                except (ValidationError, Exception) as exc:
                    st.error(str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: DATABASE EXPLORER
# ═══════════════════════════════════════════════════════════════════════════════

def page_db_explorer():
    _require_db()
    _page_header(
        "🔍 Database Explorer",
        "Inspect MongoDB collections, schemas, indexes, and run read-only analytical queries",
    )

    db = get_database()
    col_names = db.list_collection_names()

    # ── Collection Overview ────────────────────────────────────────────────────
    st.markdown("### 📦 Collections")
    stats_data = []
    for name in col_names:
        s = collection_stats(db[name])
        idxs = ", ".join(s["indexes"])
        stats_data.append({"Collection": name, "Documents": s["count"], "Indexes": idxs})

    if stats_data:
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True, hide_index=True)
    else:
        st.info("No collections found. Initialize the database in Settings.")

    st.divider()

    # ── Schema Validators ──────────────────────────────────────────────────────
    st.markdown("### 📐 Schema Validators ($jsonSchema)")
    sv1, sv2 = st.columns(2)
    with sv1:
        with st.expander("Complaints Schema"):
            st.json(COMPLAINT_JSON_SCHEMA)
    with sv2:
        with st.expander("Students Schema"):
            st.json(STUDENT_JSON_SCHEMA)

    st.divider()

    # ── Index Details ──────────────────────────────────────────────────────────
    st.markdown("### 🗂️ Index Details")
    for col_name in col_names:
        with st.expander(f"Indexes: {col_name}"):
            try:
                idx_info = db[col_name].index_information()
                st.json(idx_info)
            except Exception as exc:
                st.error(str(exc))

    st.divider()

    # ── Sample Documents ───────────────────────────────────────────────────────
    st.markdown("### 📄 Sample Documents")
    sd1, sd2 = st.columns(2)
    with sd1:
        with st.expander("Sample Complaint Document"):
            sample_c = ops.get_complaints(limit=1)
            if sample_c:
                st.json(sample_c[0])
            else:
                st.info("No complaints in database.")
    with sd2:
        with st.expander("Sample Student Document"):
            sample_s = ops.get_students(limit=1)
            if sample_s:
                st.json(sample_s[0])
            else:
                st.info("No students in database.")

    st.divider()

    # ── Predefined Read-Only Queries ───────────────────────────────────────────
    st.markdown("### 🔬 Run Analytical Queries")
    query_options = {
        "Complaints by Category": an.complaints_by_category,
        "Complaints by Status": an.complaints_by_status,
        "Complaints by Priority": an.complaints_by_priority,
        "Department Workload": an.department_workload,
        "Top 5 Categories": an.top_five_categories,
        "Avg Resolution Time by Category": an.avg_resolution_time_by_category,
        "Resolved vs Unresolved Summary": lambda: [an.resolved_vs_unresolved()],
        "Daily Trend (Last 30 days)": lambda: an.complaint_trends_daily(30),
        "High-Priority Unresolved (Top 10)": lambda: an.high_priority_unresolved(10),
    }

    selected_query = st.selectbox("Select a pipeline to run", list(query_options.keys()))
    if st.button("▶️ Run Query", key="run_query"):
        with st.spinner("Executing aggregation pipeline…"):
            try:
                result = query_options[selected_query]()
                st.success(f"Pipeline returned {len(result)} document(s).")
                st.dataframe(pd.DataFrame(result), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS / ABOUT
# ═══════════════════════════════════════════════════════════════════════════════

def page_settings():
    _page_header(
        "⚙️ Settings & About",
        "Project configuration, database management, and academic information",
    )

    tab_about, tab_db, tab_data = st.tabs(["ℹ️ About Project", "🗄️ Database", "🧪 Sample Data"])

    # ─ About ────────────────────────────────────────────────────────────────────
    with tab_about:
        st.markdown(
            f"""
            ### SmartCampus 360
            **{config.APP_DESCRIPTION}**

            ---
            **Course:** {config.COURSE_NAME}  
            **Version:** {config.APP_VERSION}  

            #### Technology Stack
            | Layer | Technology |
            |---|---|
            | Application Logic | Python 3.11+ |
            | Web Interface | Streamlit |
            | Database | MongoDB |
            | DB Driver | PyMongo |
            | Data Analysis | Pandas |
            | Visualizations | Plotly |
            | Schema Validation | MongoDB $jsonSchema |

            #### Document Database — Key Concepts
            - **Documents**: JSON-like BSON objects stored in collections
            - **Schema Validation**: $jsonSchema enforces types, required fields, and enumerations
            - **Aggregation Pipeline**: Chained stages ($match, $group, $sort, $project, $lookup) for data analysis
            - **Indexes**: B-tree structures that accelerate query execution; unique indexes enforce ID constraints
            - **PyMongo**: Official Python driver providing synchronous access to all MongoDB operations

            #### Aggregation Pipelines Implemented
            1. Complaints grouped by category  
            2. Complaints grouped by status  
            3. Priority distribution  
            4. Daily/monthly complaint trends  
            5. Average resolution time by category  
            6. Department-wise workload  
            7. High-priority unresolved complaints  
            8. Student complaint history ($lookup)  
            9. Top-5 categories  
            10. Resolved vs unresolved summary  
            """,
            unsafe_allow_html=False,
        )

    # ─ Database ─────────────────────────────────────────────────────────────────
    with tab_db:
        st.markdown("#### Connection Status")
        status = _db_ping()
        if status["connected"]:
            st.success(f"✅ Connected to **{status['database']}** at `{status['uri_hint']}`")
        else:
            st.error(f"❌ Cannot reach MongoDB: {status.get('error', 'Unknown error')}")
            st.info(
                "Ensure MongoDB is running locally (`mongod`) or update `MONGODB_URI` "
                "in your `.env` file to point to MongoDB Atlas."
            )

        st.divider()

        st.markdown("#### Schema Initialization")
        st.info(
            "This action creates collections with $jsonSchema validators and indexes. "
            "It is safe to run multiple times — existing data is NOT affected."
        )
        if st.button("⚙️ Initialize / Verify Database Schema", key="init_db"):
            with st.spinner("Initializing…"):
                try:
                    result = initialize_database(force_validator_update=True)
                    st.success("Database schema initialized successfully.")
                    st.json(result)
                except Exception as exc:
                    st.error(f"Initialization error: {exc}")

    # ─ Sample Data ──────────────────────────────────────────────────────────────
    with tab_data:
        st.markdown("#### Synthetic Sample Data")
        st.info(
            "Loads ~80 realistic (fictitious) complaints and 20 student records. "
            "Existing records are **never overwritten** — duplicates are silently skipped."
        )

        _conn = _db_ping()
        if not _conn["connected"]:
            st.warning("Database is not connected. Connect to MongoDB first.")
            return

        try:
            c_count = get_complaints_collection().count_documents({})
            s_count = get_students_collection().count_documents({})
            st.markdown(
                f"**Current dataset:** {c_count} complaints · {s_count} students"
            )
        except Exception:
            st.warning("Cannot read collection sizes.")
            c_count = -1

        if st.button("🌱 Load Sample Data", key="load_sample"):
            with st.spinner("Inserting sample records…"):
                try:
                    result = insert_sample_data()
                    st.success(
                        f"✅ Inserted **{result['complaints_inserted']}** complaints "
                        f"and **{result['students_inserted']}** students. "
                        f"({result['complaints_skipped']} complaints and "
                        f"{result['students_skipped']} students already existed — skipped.)"
                    )
                    st.cache_data.clear()
                except Exception as exc:
                    st.error(f"Error loading sample data: {exc}")

        st.divider()

        st.markdown("#### ⚠️ Danger Zone")
        st.warning(
            "The button below will permanently delete ALL complaints and students "
            "from the database. This action cannot be undone."
        )
        with st.form("wipe_form"):
            confirm_wipe = st.text_input("Type DELETE ALL to confirm")
            wipe_sub = st.form_submit_button("🗑️ Wipe All Data", type="primary")
            if wipe_sub:
                if confirm_wipe.strip() == "DELETE ALL":
                    try:
                        db = get_database()
                        c_del = db[config.COMPLAINTS_COLLECTION].delete_many({}).deleted_count
                        s_del = db[config.STUDENTS_COLLECTION].delete_many({}).deleted_count
                        st.success(f"Deleted {c_del} complaints and {s_del} students.")
                        st.cache_data.clear()
                    except Exception as exc:
                        st.error(f"Error: {exc}")
                else:
                    st.error("Confirmation text did not match. No data was deleted.")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # Ensure DB is initialized silently in background
    if _db_ping()["connected"]:
        _ensure_db_initialized()

    page = st.session_state.get("current_page", "Overview")

    dispatch = {
        "Overview":          page_overview,
        "Complaints":        page_complaints,
        "Create Complaint":  page_create_complaint,
        "Analytics":         page_analytics,
        "Students":          page_students,
        "Database Explorer": page_db_explorer,
        "Settings":          page_settings,
    }

    fn = dispatch.get(page, page_overview)
    fn()


if __name__ == "__main__":
    main()
