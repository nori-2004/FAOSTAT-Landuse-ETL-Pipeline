"""
utils/db.py — shared database helpers for FAOSTAT dashboard
All pages import from here so the engine is created once per session.
"""

import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd


@st.cache_resource
def get_engine():
    """
    Returns a SQLAlchemy engine using the Supabase connection string.

    Set this in .streamlit/secrets.toml:
        [database]
        url = "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"

    For local dev you can also use a .env file and load with python-dotenv,
    then pass the URL via st.secrets or os.environ.
    """
    url = st.secrets["database"]["url"]
    return create_engine(
        url,
        pool_pre_ping=True,       # reconnects after idle timeout
        pool_size=2,              # small pool — Streamlit is single-user
        max_overflow=3,
    )


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
        yield_t_per_ha,
        value_per_ha,
        value_per_tonne
    """
    engine = get_engine()
    q = text("SELECT * FROM vw_agri_base ORDER BY year, country, crop")
    with engine.connect() as conn:
        return pd.read_sql(q, conn)