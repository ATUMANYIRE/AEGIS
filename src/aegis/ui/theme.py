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
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
