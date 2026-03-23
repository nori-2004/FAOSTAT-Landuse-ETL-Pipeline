"""
dashboard.py — shared utilities for FAOSTAT dashboard
Imported by every page: engine, theme constants, Plotly base layout, CSS injection.
"""

import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd

# ─────────────────────────────────────────────
#  THEME CONSTANTS
# ─────────────────────────────────────────────
AMBER   = "#F0A500"
TEAL    = "#2DD4BF"
SLATE   = "#0F1117"
CARD_BG = "#1A1F2E"
BORDER  = "#2A3045"
TEXT    = "#E8EAF0"
MUTED   = "#6B7280"

# ─────────────────────────────────────────────
#  PLOTLY BASE LAYOUT (dark theme)
# ─────────────────────────────────────────────
PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, family="Inter, Segoe UI, -apple-system, sans-serif", size=12),
    title="",
    showlegend=True,
    margin=dict(l=10, r=10, t=0, b=10),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor=BORDER,
        borderwidth=1,
        font=dict(size=11),
    ),
    xaxis=dict(
        gridcolor=BORDER,
        showgrid=True,
        zeroline=False,
        tickfont=dict(size=10),
        showticklabels=True,
    ),
    yaxis=dict(
        gridcolor=BORDER,
        showgrid=True,
        zeroline=False,
        tickfont=dict(size=10),
        showticklabels=True,
    ),
)

# ─────────────────────────────────────────────
#  DATABASE ENGINE
# ─────────────────────────────────────────────
@st.cache_resource
def get_engine():
    """
    Returns a SQLAlchemy engine using the Supabase connection string.

    Set in .streamlit/secrets.toml:
        [database]
        url = "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"
    """
    url = st.secrets["database"]["url"]
    return create_engine(
        url,
        pool_pre_ping=True,   # reconnects after idle timeout
        pool_size=2,          # small pool — Streamlit is single-user
        max_overflow=3,
    )

# ─────────────────────────────────────────────
#  CSS INJECTION
# ─────────────────────────────────────────────
def apply_theme():
    """Inject app-wide dark theme CSS. Call once at the top of each page."""
    st.markdown(f"""
<style>
  [data-testid="stAppViewContainer"] {{
      background: {SLATE};
      color: {TEXT};
  }}
  [data-testid="stSidebar"] {{
      background: {CARD_BG};
      border-right: 1px solid {BORDER};
  }}
  .block-container {{
      padding-top: 2.0rem;
  }}
  .stSelectbox label, .stMultiSelect label,
  .stSlider label, .stRadio label {{
      font-size: 0.75rem !important;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: {MUTED} !important;
  }}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  FULL TABLE LOADER (used by EDA / notebooks)
# ─────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner="Loading FAOSTAT data…")
def load_vw_agri_base() -> pd.DataFrame:
    """
    Pulls every column from vw_agri_base.
    Cached for 10 minutes so repeated widget interactions don't hit the DB.

    Returns
    -------
    pd.DataFrame with columns:
        country, crop, year,
        area_harvested_ha, yield_kg_ha, production_tonnes,
        gross_production_value_kusd,
        gross_production_value_usd,
        gross_production_value_usd_millions,
        yield_t_per_ha, value_per_ha, value_per_tonne
    """
    engine = get_engine()
    q = text("SELECT * FROM vw_agri_base ORDER BY year, country, crop")
    with engine.connect() as conn:
        return pd.read_sql(q, conn)