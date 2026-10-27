"""Design system and enterprise styling tokens for AEGIS Streamlit Workspace."""

import streamlit as st

# Enterprise Light Warm-White Color Palette
BG_COLOR = "#F8FAFC"
SURFACE_COLOR = "#FFFFFF"
TEXT_PRIMARY = "#172B46"
TEXT_MUTED = "#64748B"
ACCENT_PRIMARY = "#2367A3"  # Primary corporate blue
ACCENT_SECONDARY = "#378D73"  # Operations sage green
WARNING_COLOR = "#C78B31"  # Advisory amber
DANGER_COLOR = "#DC2626"  # Alert red
BORDER_COLOR = "#E2E8F0"  # Subtle card border
HOVER_COLOR = "#F1F5F9"

# Plotly Color Sequence aligned with Enterprise Design
PLOTLY_COLORS = [
    ACCENT_PRIMARY,
    ACCENT_SECONDARY,
    WARNING_COLOR,
    "#6366F1",  # Indigo
    "#0EA5E9",  # Cyan
    "#EC4899",  # Pink
]


def apply_custom_css() -> None:
    """Inject polished enterprise styling into Streamlit DOM."""
    css = f"""
    <style>
    /* Global Base */
    .stApp {{
        background-color: {BG_COLOR};
        color: {TEXT_PRIMARY};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    /* Header & Top Bar */
    header[data-testid="stHeader"] {{
        background-color: {BG_COLOR};
    }}

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {{
        background-color: {SURFACE_COLOR};
        border-right: 1px solid {BORDER_COLOR};
    }}
    section[data-testid="stSidebar"] .stMarkdown {{
        color: {TEXT_PRIMARY};
    }}

    /* Metric Cards */
    div[data-testid="stMetric"] {{
        background-color: {SURFACE_COLOR};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        padding: 14px 18px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08);
        border-color: {ACCENT_PRIMARY};
    }}
    div[data-testid="stMetric"] label {{
        color: {TEXT_MUTED} !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }}
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: {TEXT_PRIMARY} !important;
        font-weight: 700 !important;
    }}

    /* Buttons */
    .stButton > button {{
        background-color: {ACCENT_PRIMARY};
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1.25rem;
        font-weight: 600;
        transition: background-color 0.15s ease;
    }}
    .stButton > button:hover {{
        background-color: #1A4F7D;
        color: #FFFFFF;
    }}
    .stButton > button:active {{
        background-color: #133A5C;
    }}

    /* Custom Card Containers */
    .aegis-card {{
        background-color: {SURFACE_COLOR};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 18px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }}

    .aegis-badge {{
        display: inline-block;
        padding: 3px 9px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        margin-right: 6px;
        margin-bottom: 4px;
    }}
    .badge-synthetic {{
        background-color: #FEF3C7;
        color: #92400E;
        border: 1px solid #FDE68A;
    }}
    .badge-clinical {{
        background-color: #E0E7FF;
        color: #3730A3;
        border: 1px solid #C7D2FE;
    }}
    .badge-success {{
        background-color: #DEF7EC;
        color: #03543F;
        border: 1px solid #BCF0DA;
    }}
    .badge-danger {{
        background-color: #FDE8E8;
        color: #9B1C1C;
        border: 1px solid #FBD5D5;
    }}
    .badge-info {{
        background-color: #E1EFFE;
        color: #1E429F;
        border: 1px solid #B4C6FC;
    }}

    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        background-color: transparent;
        border-bottom: 2px solid {BORDER_COLOR};
        padding-bottom: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent;
        border-radius: 6px 6px 0 0;
        font-weight: 600;
        color: {TEXT_MUTED};
        padding: 8px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        color: {ACCENT_PRIMARY} !important;
        border-bottom: 2px solid {ACCENT_PRIMARY} !important;
    }}
    /* ---- Shell polish ---- */
    .block-container {{ max-width: 1280px; padding-top: 2.2rem; padding-bottom: 2rem; }}
    h1, h2, h3, h4 {{ color: {TEXT_PRIMARY}; letter-spacing: -0.01em; font-weight: 650; }}
    h4 {{ font-size: 1.05rem; margin: 0.4rem 0 0.2rem 0; }}
    hr {{ margin: 0.9rem 0; border-color: {BORDER_COLOR}; }}

    .aegis-header {{
        display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
        background: {SURFACE_COLOR}; border: 1px solid {BORDER_COLOR};
        border-radius: 10px; padding: 12px 16px; margin-bottom: 14px;
    }}
    .aegis-logo {{
        background: {ACCENT_PRIMARY}; color: #fff; width: 36px; height: 36px;
        border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.15rem;
    }}
    .aegis-title-block {{ flex: 1 1 320px; min-width: 0; }}
    .aegis-title {{ font-size: 1.2rem; font-weight: 700; color: {TEXT_PRIMARY}; line-height: 1.25; }}
    .aegis-subtitle {{ font-size: 0.8rem; color: {TEXT_MUTED}; }}
    .aegis-header-badges {{ display: flex; gap: 4px; flex-wrap: wrap; }}
    .aegis-header-badges .aegis-badge {{ margin: 0; }}

    .aegis-brand {{ padding-bottom: 12px; border-bottom: 1px solid {BORDER_COLOR}; margin-bottom: 4px; }}
    .aegis-brand-name {{ font-size: 1.3rem; font-weight: 800; letter-spacing: 0.08em; color: {ACCENT_PRIMARY}; }}
    .aegis-brand-sub {{ font-size: 0.72rem; color: {TEXT_MUTED}; }}
    .aegis-side-title {{
        font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;
        color: {TEXT_MUTED}; margin: 16px 0 6px 0;
    }}
    .aegis-kv {{
        display: flex; justify-content: space-between; gap: 8px; font-size: 0.78rem;
        padding: 4px 0; border-bottom: 1px dashed {BORDER_COLOR};
    }}
    .aegis-kv span {{ color: {TEXT_MUTED}; }}
    .aegis-kv b {{ color: {TEXT_PRIMARY}; font-weight: 600; text-align: right; }}
    .aegis-note {{
        font-size: 0.76rem; color: #475569; line-height: 1.4; padding: 6px 8px; margin-bottom: 6px;
        background: {BG_COLOR}; border-left: 3px solid {ACCENT_SECONDARY}; border-radius: 4px;
    }}

    div[data-testid="stMetric"] {{ padding: 10px 14px; }}
    div[data-testid="stMetricValue"] {{ font-size: 1.35rem; }}
    div[data-testid="stMetric"] label {{ font-size: 0.7rem !important; }}

    .stButton > button, .stDownloadButton > button {{ box-shadow: 0 1px 2px rgba(23,43,70,0.12); }}
    .stButton > button:focus-visible {{ outline: 2px solid {ACCENT_SECONDARY}; outline-offset: 2px; }}
    div[data-baseweb="select"] > div, .stNumberInput input, .stTextInput input {{
        border-radius: 6px; border-color: {BORDER_COLOR};
    }}
    div[data-testid="stAlert"] {{ border-radius: 8px; border: 1px solid {BORDER_COLOR}; }}
    div[data-testid="stDataFrame"] {{
        border: 1px solid {BORDER_COLOR}; border-radius: 8px; overflow: hidden;
    }}
    div[data-testid="stPlotlyChart"] {{
        background: {SURFACE_COLOR}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; padding: 4px;
    }}
    div[data-testid="stExpander"] {{ border: 1px solid {BORDER_COLOR}; border-radius: 8px; background: {SURFACE_COLOR}; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; flex-wrap: wrap; }}
    .stTabs [data-baseweb="tab"] {{ padding: 8px 14px; font-size: 0.9rem; }}
    .stTabs [data-baseweb="tab"]:hover {{ background: {HOVER_COLOR}; }}
    @media (max-width: 768px) {{
        .block-container {{ padding-left: 0.8rem; padding-right: 0.8rem; }}
        .aegis-header-badges {{ flex-basis: 100%; }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
