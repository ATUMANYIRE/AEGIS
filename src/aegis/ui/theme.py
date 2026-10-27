"""Design system and enterprise styling tokens for AEGIS Streamlit Workspace."""

import streamlit as st

# AEGIS / Clarity Under Pressure palette
BG_COLOR = "#F5F3ED"  # warm ivory canvas
SURFACE_COLOR = "#FFFFFF"
SURFACE_SOFT = "#FBFAF6"
NAV_COLOR = "#101E2B"  # midnight navy
TEXT_PRIMARY = "#172B36"  # ink
TEXT_MUTED = "#5B6B75"
ACCENT_PRIMARY = "#216C65"  # deep teal
ACCENT_SECONDARY = "#4F9A8B"  # chart-safe supporting teal
TEAL_TINT = "#BBDDD0"
WARNING_COLOR = "#D8A15B"  # muted amber
DANGER_COLOR = "#B4443C"
BORDER_COLOR = "#DDD9CE"
HOVER_COLOR = "#ECE9DF"

FONT_HEAD = 'Georgia, "Iowan Old Style", "Palatino Linotype", "Times New Roman", serif'
FONT_UI = '"Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif'

# Plotly Color Sequence aligned with Enterprise Design
PLOTLY_COLORS = [
    ACCENT_PRIMARY,
    ACCENT_SECONDARY,
    WARNING_COLOR,
    "#101E2B",
    "#7A8B94",
    "#B4443C",
]


def apply_custom_css() -> None:
    """Inject polished enterprise styling into Streamlit DOM."""
    css = f"""
    <style>
    .stApp {{ background-color: {BG_COLOR}; color: {TEXT_PRIMARY}; font-family: {FONT_UI}; }}
    header[data-testid="stHeader"] {{ background-color: transparent; }}
    .block-container {{ max-width: 1320px; padding-top: 2.4rem; padding-bottom: 2.5rem; }}
    h1, h2, h3, h4 {{ font-family: {FONT_HEAD}; color: {TEXT_PRIMARY}; font-weight: 600; letter-spacing: -0.005em; }}
    h4 {{ font-size: 1.2rem; margin: 0.6rem 0 0.15rem 0; }}
    hr {{ margin: 1rem 0; border-color: {BORDER_COLOR}; }}

    /* Sidebar: midnight navigation */
    section[data-testid="stSidebar"] {{ background-color: {NAV_COLOR}; border-right: none; }}
    section[data-testid="stSidebar"] * {{ color: #D9E2E7; }}
    .aegis-brand {{ padding-bottom: 14px; border-bottom: 1px solid #2A3B4A; margin-bottom: 4px; }}
    .aegis-brand-name {{ font-family: {FONT_HEAD}; font-size: 1.7rem; font-weight: 600; letter-spacing: 0.14em; color: #FFFFFF !important; }}
    .aegis-brand-sub {{ font-size: 0.72rem; color: {TEAL_TINT} !important; letter-spacing: 0.04em; }}
    .aegis-side-title {{ font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: {TEAL_TINT} !important; margin: 18px 0 6px 0; }}
    .aegis-kv {{ display: flex; justify-content: space-between; gap: 10px; font-size: 0.78rem; padding: 5px 0; border-bottom: 1px solid #22323F; }}
    .aegis-kv span {{ color: #93A4AE !important; }}
    .aegis-kv b {{ color: #FFFFFF !important; font-weight: 600; text-align: right; }}
    .aegis-note {{ font-size: 0.76rem; line-height: 1.45; padding: 7px 10px; margin-bottom: 6px; background: #17293A; border-left: 3px solid {WARNING_COLOR}; border-radius: 4px; }}

    /* Product header */
    .aegis-header {{ display: flex; align-items: center; gap: 14px; flex-wrap: wrap; background: {NAV_COLOR}; border-radius: 12px; padding: 14px 20px; margin-bottom: 16px; }}
    .aegis-brand-lockup {{ display: flex; align-items: center; gap: 10px; }}
    .aegis-logo {{ width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; }}
    .aegis-title-block {{ flex: 1 1 320px; min-width: 0; }}
    .aegis-title {{ font-family: {FONT_HEAD}; font-size: 1.35rem; font-weight: 600; color: #FFFFFF; line-height: 1.25; }}
    .aegis-subtitle {{ font-size: 0.8rem; color: {TEAL_TINT}; }}
    .aegis-header-badges {{ display: flex; gap: 6px; flex-wrap: wrap; }}
    .aegis-header-badges .aegis-badge {{ margin: 0; }}

    /* Badges */
    .aegis-badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.03em; margin-right: 6px; margin-bottom: 4px; white-space: nowrap; }}
    .badge-synthetic {{ background: {WARNING_COLOR}; color: #2B1E08; }}
    .badge-clinical {{ background: {TEAL_TINT}; color: #0E3B37; }}
    .badge-success {{ background: #D5EBDF; color: #0E4A33; border: 1px solid #A9D3BE; }}
    .badge-danger {{ background: #F5DAD7; color: #7A241E; border: 1px solid #E6B3AE; }}
    .badge-info {{ background: #DCEBEF; color: #1B4A57; border: 1px solid #B5D2DA; }}

    /* Cards */
    .aegis-card {{ background: {SURFACE_COLOR}; border: 1px solid {BORDER_COLOR}; border-radius: 10px; padding: 18px; margin-bottom: 16px; }}
    div[data-testid="stMetric"] {{ background: {SURFACE_COLOR}; border: 1px solid {BORDER_COLOR}; border-top: 3px solid {ACCENT_PRIMARY}; border-radius: 10px; padding: 12px 14px; min-width: 0; min-height: 112px; height: 100%; box-sizing: border-box; }}
    section[data-testid="stSidebar"] code {{ background: #22323F; color: {TEAL_TINT}; padding: 1px 5px; border-radius: 4px; }}
    div[data-testid="stMetric"] label, div[data-testid="stMetric"] label p {{ color: {TEXT_MUTED} !important; font-size: 0.72rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.05em; white-space: normal !important; overflow: visible !important; text-overflow: clip !important; line-height: 1.25; }}
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] div {{ color: {TEXT_PRIMARY} !important; font-family: {FONT_HEAD}; font-weight: 600 !important; font-size: clamp(1.05rem, 1.7vw, 1.35rem); font-variant-numeric: tabular-nums; white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }}
    div[data-testid="stMetricDelta"] {{ font-size: 0.78rem; white-space: normal !important; }}

    /* Controls */
    .stButton > button, .stDownloadButton > button {{ background: {ACCENT_PRIMARY}; color: #FFFFFF; border: 1px solid {ACCENT_PRIMARY}; border-radius: 8px; padding: 0.5rem 1.3rem; font-weight: 600; }}
    .stButton > button:hover, .stDownloadButton > button:hover {{ background: #174F4A; border-color: #174F4A; color: #FFFFFF; }}
    .stButton > button:focus-visible {{ outline: 3px solid {WARNING_COLOR}; outline-offset: 2px; }}
    div[data-baseweb="select"] > div, .stNumberInput input, .stTextInput input {{ border-radius: 8px; border-color: {BORDER_COLOR}; background: {SURFACE_COLOR}; }}
    div[data-testid="stAlert"] {{ border-radius: 10px; border: 1px solid {BORDER_COLOR}; }}
    div[data-testid="stDataFrame"] {{ border: 1px solid {BORDER_COLOR}; border-radius: 10px; overflow: hidden; }}
    div[data-testid="stPlotlyChart"] {{ background: {SURFACE_COLOR}; border: 1px solid {BORDER_COLOR}; border-radius: 10px; padding: 6px; overflow: hidden; }}
    div[data-testid="stPlotlyChart"] .js-plotly-plot, div[data-testid="stPlotlyChart"] .plot-container {{ overflow: hidden !important; }}
    div[data-testid="stExpander"] {{ border: 1px solid {BORDER_COLOR}; border-radius: 10px; background: {SURFACE_COLOR}; }}

    /* Tabs as primary navigation */
    .stTabs [data-baseweb="tab-list"] {{ gap: 2px; flex-wrap: wrap; border-bottom: 1px solid {BORDER_COLOR}; background: transparent; }}
    .stTabs [data-baseweb="tab"] {{ font-weight: 600; color: {TEXT_MUTED}; padding: 10px 16px; font-size: 0.92rem; border-radius: 8px 8px 0 0; }}
    .stTabs [data-baseweb="tab"]:hover {{ background: {HOVER_COLOR}; color: {TEXT_PRIMARY}; }}
    .stTabs [aria-selected="true"] {{ color: {ACCENT_PRIMARY} !important; }}
    .stTabs [data-baseweb="tab-highlight"] {{ background-color: {ACCENT_PRIMARY} !important; height: 3px; }}

    @media (max-width: 768px) {{
        .block-container {{ padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 1.5rem; }}
        .aegis-header-badges {{ flex-basis: 100%; }}
        .aegis-title {{ font-size: 1.15rem; }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
