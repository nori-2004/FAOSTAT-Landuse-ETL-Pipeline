"""
Page 1 — Value, Scale & Composition
FAOSTAT Agricultural Portfolio | UBC CSFS Application

Research question:
  Where does agricultural value come from across countries, crops, and time?

Data source: vw_agri_base (PostgreSQL via Supabase)
  Key columns: country, crop, year, area_harvested_ha, production_tonnes,
               gross_production_value_usd, value_per_ha, value_per_tonne
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import text

from dashboard import get_engine, apply_theme, PLOTLY_BASE, AMBER, MUTED

# ─────────────────────────────────────────────
#  PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Value, Scale & Composition | FAOSTAT",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

# ─────────────────────────────────────────────
#  COLOUR PALETTES (page-specific)
# ─────────────────────────────────────────────
PALETTE_COUNTRY = px.colors.qualitative.Safe   # 10 distinct hues
PALETTE_CROP    = px.colors.qualitative.Vivid

# ═══════════════════════════════════════════════
#  DATA LOADING (mini-queries, all cached)
# ═══════════════════════════════════════════════

def _where(year_min, year_max, countries=None, crops=None) -> str:
    """Build a WHERE clause string from common filter args."""
    clauses = [f"year >= {year_min} AND year <= {year_max}"]

    if countries:
        country_list = "', '".join(str(c) for c in countries)
        clauses.append(f"country IN ('{country_list}')")

    if crops:
        crop_list = "', '".join(str(c) for c in crops)
        clauses.append(f"crop IN ('{crop_list}')")

    return " AND ".join(clauses)


@st.cache_data(ttl=600, show_spinner="Loading KPI data…")
def load_kpi_summary(year_min, year_max, countries=None, crops=None) -> dict:
    """Aggregated KPI metrics for the selected filters."""
    engine = get_engine()
    where = _where(year_min, year_max, countries, crops)
    q = text(f"""
        SELECT
            SUM(gross_production_value_usd)     AS total_value,
            SUM(area_harvested_ha)              AS total_area,
            SUM(production_tonnes)              AS total_prod,
            COUNT(DISTINCT country)             AS n_countries,
            COUNT(DISTINCT crop)                AS n_crops,
            COUNT(DISTINCT year)                AS n_years
        FROM vw_agri_base
        WHERE {where}
    """)
    with engine.connect() as conn:
        result = pd.read_sql(q, conn).iloc[0].to_dict()
    result["avg_value_ha"] = result["total_value"] / max(result["total_area"], 1)
    return result


@st.cache_data(ttl=600, show_spinner="Loading time series data…")
def load_timeseries(year_min, year_max, dim, countries=None, crops=None) -> pd.DataFrame:
    """Gross production value grouped by year and a dimension (country or crop)."""
    engine = get_engine()
    where = _where(year_min, year_max, countries, crops)
    q = text(f"""
        SELECT year, {dim}, SUM(gross_production_value_usd_millions) AS gross_production_value_usd_millions
        FROM vw_agri_base
        WHERE {where}
        GROUP BY year, {dim}
        ORDER BY year, {dim}
    """)
    with engine.connect() as conn:
        return pd.read_sql(q, conn)


@st.cache_data(ttl=600, show_spinner="Loading top values…")
def load_top_values(dim, year_min, year_max, limit=10, countries=None, crops=None) -> pd.DataFrame:
    """Top N items by total gross production value."""
    engine = get_engine()
    where = _where(year_min, year_max, countries, crops)
    q = text(f"""
        SELECT {dim}, SUM(gross_production_value_usd_millions) AS gross_production_value_usd_millions
        FROM vw_agri_base
        WHERE {where}
        GROUP BY {dim}
        ORDER BY gross_production_value_usd_millions DESC
        LIMIT {limit}
    """)
    with engine.connect() as conn:
        return pd.read_sql(q, conn)


@st.cache_data(ttl=600, show_spinner="Loading totals…")
def load_yearly_totals(year_min, year_max, countries=None, crops=None) -> pd.DataFrame:
    """Yearly total gross production value (no dimension breakdown)."""
    engine = get_engine()
    where = _where(year_min, year_max, countries, crops)
    q = text(f"""
        SELECT year, SUM(gross_production_value_usd_millions) AS gross_production_value_usd_millions
        FROM vw_agri_base
        WHERE {where}
        GROUP BY year
        ORDER BY year
    """)
    with engine.connect() as conn:
        return pd.read_sql(q, conn)


# ═══════════════════════════════════════════════
#  FORMATTERS
# ═══════════════════════════════════════════════

def fmt_usd(val: float, decimals: int = 1) -> str:
    if val >= 1e9:  return f"${val/1e9:.{decimals}f}B"
    if val >= 1e6:  return f"${val/1e6:.{decimals}f}M"
    if val >= 1e3:  return f"${val/1e3:.{decimals}f}K"
    return f"${val:,.0f}"

def fmt_ha(val: float) -> str:
    if val >= 1e9:  return f"{val/1e9:.2f}B ha"
    if val >= 1e6:  return f"{val/1e6:.1f}M ha"
    return f"{val/1e3:.1f}K ha"

def fmt_tonnes(val: float) -> str:
    if val >= 1e9:  return f"{val/1e9:.2f}B t"
    if val >= 1e6:  return f"{val/1e6:.1f}M t"
    return f"{val/1e3:.1f}K t"


# ═══════════════════════════════════════════════
#  UI COMPONENTS
# ═══════════════════════════════════════════════

def render_header():
    st.title("Value, Scale & Composition")
    st.caption("Where does agricultural value come from — across countries, crops, and time?")
    st.divider()


def render_sidebar(db_year_min, db_year_max, all_countries, all_crops):
    with st.sidebar:
        st.markdown("### Filters")
        year_range = st.slider(
            "Year range",
            min_value=db_year_min, max_value=db_year_max,
            value=(db_year_min, db_year_max), step=1,
        )
        sel_countries = st.multiselect(
            "Countries", options=all_countries, default=[],
            placeholder="Select countries or leave blank for all",
        )
        sel_crops = st.multiselect(
            "Crops", options=all_crops, default=[],
            placeholder="Select crops or leave blank for all",
        )
        grouping = st.radio("Group by", options=["Country", "Crop"], index=0, horizontal=True)
        st.markdown("---")
        st.markdown(
            f"<span style='font-size:0.72rem;color:{MUTED}'>Page 1 of 2 · FAOSTAT Portfolio</span>",
            unsafe_allow_html=True,
        )
    return year_range, sel_countries, sel_crops, grouping


def render_kpis(kpi_data: dict):
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total Gross Production Value", fmt_usd(kpi_data["total_value"]))
        st.caption(f"{kpi_data['n_countries']} countries · {kpi_data['n_years']} years")
    with k2:
        st.metric("Total Harvested Area", fmt_ha(kpi_data["total_area"]))
        st.caption(f"{kpi_data['n_crops']} crops in selection")
    with k3:
        st.metric("Total Production Volume", fmt_tonnes(kpi_data["total_prod"]))
        st.caption("All crops combined")
    with k4:
        st.metric("Avg Value per Hectare", fmt_usd(kpi_data["avg_value_ha"], decimals=0))
        st.caption("Gross production value ÷ area")
    st.divider()


def render_value_over_time(year_range, sel_countries, sel_crops, dim, palette, grouping):
    """Left middle column: total gross value over time (line chart)."""
    st.subheader("Total Gross Value Over Time")
    line_toggle = st.radio(
        "Breakdown",
        options=[f"By {grouping}", "Total only"],
        key="line_toggle", horizontal=True, label_visibility="collapsed",
    )
    countries = sel_countries or None
    crops     = sel_crops or None

    if line_toggle == "Total only":
        yr_total = load_yearly_totals(year_range[0], year_range[1], countries, crops)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=yr_total["year"],
            y=yr_total["gross_production_value_usd_millions"],
            mode="lines+markers",
            line=dict(color=AMBER, width=2.5),
            marker=dict(size=5),
            name="Total",
            hovertemplate="<b>%{x}</b><br>$%{y:,.1f}M<extra></extra>",
        ))
    else:
        yr_grp = load_timeseries(year_range[0], year_range[1], dim, countries, crops)
        top_dims = yr_grp.groupby(dim)["gross_production_value_usd_millions"].sum().nlargest(10).index
        yr_top = yr_grp[yr_grp[dim].isin(top_dims)]
        fig = px.line(
            yr_top,
            x="year", y="gross_production_value_usd_millions", color=dim,
            color_discrete_sequence=palette,
            labels={"gross_production_value_usd_millions": "Value (USD M)", "year": "Year", dim: grouping},
        )
        fig.update_traces(
            mode="lines+markers", line=dict(width=2),
            hovertemplate="<b>%{fullData.name}</b><br>%{x}: $%{y:,.1f}M<extra></extra>",
        )

    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=320, yaxis_title="USD Millions", xaxis_title=None,
        legend_title_text=grouping, title="", margin=dict(t=0, l=10, r=10, b=10),
    )
    st.plotly_chart(fig, use_container_width=True, key="line_chart", config={"displayModeBar": False})


def render_composition_over_time(year_range, sel_countries, sel_crops, dim, palette, grouping):
    """Right middle column: share of value over time (stacked area or bar)."""
    st.subheader("Composition of Value Over Time")
    area_toggle = st.radio(
        "Chart type", options=["Stacked Area", "Stacked Bar"],
        key="area_toggle", horizontal=True, label_visibility="collapsed",
    )
    countries = sel_countries or None
    crops     = sel_crops or None

    yr_grp = load_timeseries(year_range[0], year_range[1], dim, countries, crops)
    top_dims = yr_grp.groupby(dim)["gross_production_value_usd_millions"].sum().nlargest(8).index
    yr_top = yr_grp[yr_grp[dim].isin(top_dims)].copy()

    yr_yr_total = yr_top.groupby("year")["gross_production_value_usd_millions"].transform("sum")
    yr_top["share_pct"] = yr_top["gross_production_value_usd_millions"] / yr_yr_total * 100

    sorted_data = yr_top.sort_values(["year", dim])
    chart_labels = {"share_pct": "Share (%)", "year": "Year", dim: grouping}

    if area_toggle == "Stacked Area":
        fig = px.area(sorted_data, x="year", y="share_pct", color=dim,
                      color_discrete_sequence=palette, labels=chart_labels)
    else:
        fig = px.bar(sorted_data, x="year", y="share_pct", color=dim,
                     color_discrete_sequence=palette, barmode="stack", labels=chart_labels)

    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=320, yaxis_title="Share of Total Value (%)", xaxis_title=None,
        legend_title_text=f"Top 8 {grouping}s", title="", margin=dict(t=0, l=10, r=10, b=10),
    )
    fig.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>")
    st.plotly_chart(fig, use_container_width=True, key="area_chart", config={"displayModeBar": False})


def render_top_values_bar(year_range, sel_countries, sel_crops, dim, grouping):
    """Bottom row: horizontal bar chart of top items by gross production value."""
    st.subheader(f"Top {grouping}s by Gross Production Value")

    bar_data = load_top_values(
        dim, year_range[0], year_range[1], limit=50,
        countries=sel_countries or None,
        crops=sel_crops or None,
    )
    fig = go.Figure(go.Bar(
        x=bar_data["gross_production_value_usd_millions"],
        y=bar_data[dim],
        orientation="h",
        marker_color=AMBER,
        hovertemplate="<b>%{y}</b><br>$%{x:,.1f}M<extra></extra>",
        text=bar_data["gross_production_value_usd_millions"].apply(lambda v: fmt_usd(v * 1e6)),
        textposition="outside",
        textfont=dict(size=10, color=MUTED),
        showlegend=False,
        name="",
    ))
    fig.update_layout(**PLOTLY_BASE)
    fig.update_layout(
        height=max(280, len(bar_data) * 26),
        xaxis_title="Gross Production Value (USD Millions)",
        yaxis_title=None, title="",
        margin=dict(l=10, r=80, t=0, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key="bar_chart", config={"displayModeBar": False})


# ═══════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════
def main():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            year_df    = pd.read_sql(text("SELECT DISTINCT year    FROM vw_agri_base ORDER BY year"),    conn)
            country_df = pd.read_sql(text("SELECT DISTINCT country FROM vw_agri_base ORDER BY country"), conn)
            crop_df    = pd.read_sql(text("SELECT DISTINCT crop    FROM vw_agri_base ORDER BY crop"),    conn)
        db_year_min  = int(year_df["year"].min())
        db_year_max  = int(year_df["year"].max())
        all_countries = sorted(country_df["country"].tolist())
        all_crops     = sorted(crop_df["crop"].tolist())
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.info("Check that `database.url` is set in `.streamlit/secrets.toml`.")
        st.stop()

    render_header()
    year_range, sel_countries, sel_crops, grouping = render_sidebar(
        db_year_min, db_year_max, all_countries, all_crops
    )

    dim     = grouping.lower()
    palette = PALETTE_COUNTRY if dim == "country" else PALETTE_CROP

    kpi_data = load_kpi_summary(
        year_range[0], year_range[1],
        countries=sel_countries or None,
        crops=sel_crops or None,
    )
    if kpi_data["total_value"] == 0:
        st.warning("No data for the current filter selection.")
        st.stop()

    render_kpis(kpi_data)

    mid_l, mid_r = st.columns([1, 1], gap="medium")
    with mid_l:
        render_value_over_time(year_range, sel_countries, sel_crops, dim, palette, grouping)
    with mid_r:
        render_composition_over_time(year_range, sel_countries, sel_crops, dim, palette, grouping)

    st.markdown("<br>", unsafe_allow_html=True)
    render_top_values_bar(year_range, sel_countries, sel_crops, dim, grouping)


# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()