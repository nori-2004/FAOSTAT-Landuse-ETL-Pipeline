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
from sqlalchemy import create_engine, text

# ─────────────────────────────────────────────
#  PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Value, Scale & Composition | FAOSTAT",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  THEME / CUSTOM CSS
# ─────────────────────────────────────────────
AMBER   = "#F0A500"
TEAL    = "#2DD4BF"
SLATE   = "#0F1117"
CARD_BG = "#1A1F2E"
BORDER  = "#2A3045"
TEXT    = "#E8EAF0"
MUTED   = "#6B7280"

PALETTE_COUNTRY = px.colors.qualitative.Safe      # 10 distinct hues
PALETTE_CROP    = px.colors.qualitative.Vivid

# NOTE: Keep a light CSS layer only for app background/sidebar colors and label styling.
st.markdown(f"""
<style>
  /* ── root ── */
  [data-testid="stAppViewContainer"] {{
      background: {SLATE};
      color: {TEXT};
  }}
  [data-testid="stSidebar"] {{
      background: {CARD_BG};
      border-right: 1px solid {BORDER};
  }}

  /* Layout: tweak top spacing so header isn't flush with the top */
  .block-container {{
      padding-top: 2.0rem;
  }}

  /* Streamlit widget label overrides */
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
#  DATABASE CONNECTION
# ─────────────────────────────────────────────
@st.cache_resource
def get_engine():
    """
    Reads DATABASE_URL from st.secrets.
    In secrets.toml:
        [database]
        url = "postgresql://user:pass@host:5432/dbname"
    """
    url = st.secrets["database"]["url"]
    return create_engine(url)

# ─────────────────────────────────────────────
#  DATA LOADING (mini-queries)
# ─────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner="Loading KPI data…")
def load_kpi_summary(year_min: int, year_max: int, countries: list = None, crops: list = None) -> dict:
    """Load aggregated KPI metrics."""
    engine = get_engine()
    where_clauses = [f"year >= {year_min} AND year <= {year_max}"]
    if countries:
        country_list = "', '".join(countries)
        where_clauses.append(f"country IN ('{country_list}')")
    if crops:
        crop_list = "', '".join(crops)
        where_clauses.append(f"crop IN ('{crop_list}')")
    
    where_str = " AND ".join(where_clauses)
    query = text(f"""
        SELECT
            SUM(gross_production_value_usd) as total_value,
            SUM(area_harvested_ha) as total_area,
            SUM(production_tonnes) as total_prod,
            COUNT(DISTINCT country) as n_countries,
            COUNT(DISTINCT crop) as n_crops,
            COUNT(DISTINCT year) as n_years
        FROM vw_agri_base
        WHERE {where_str}
    """)
    with engine.connect() as conn:
        result = pd.read_sql(query, conn).iloc[0].to_dict()
    result['avg_value_ha'] = result['total_value'] / max(result['total_area'], 1)
    return result

@st.cache_data(ttl=600, show_spinner="Loading time series data…")
def load_timeseries(year_min: int, year_max: int, dim: str, countries: list = None, crops: list = None):
    """Load time-series data grouped by dimension."""
    engine = get_engine()
    where_clauses = [f"year >= {year_min} AND year <= {year_max}"]
    if countries:
        country_list = "', '".join(countries)
        where_clauses.append(f"country IN ('{country_list}')")
    if crops:
        crop_list = "', '".join(crops)
        where_clauses.append(f"crop IN ('{crop_list}')")
    
    where_str = " AND ".join(where_clauses)
    query = text(f"""
        SELECT year, {dim}, SUM(gross_production_value_usd_millions) as gross_production_value_usd_millions
        FROM vw_agri_base
        WHERE {where_str}
        GROUP BY year, {dim}
        ORDER BY year, {dim}
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df

@st.cache_data(ttl=600, show_spinner="Loading top values…")
def load_top_values(dim: str, year_min: int, year_max: int, limit: int = 10, countries: list = None, crops: list = None):
    """Load top N items by value."""
    engine = get_engine()
    where_clauses = [f"year >= {year_min} AND year <= {year_max}"]
    if countries:
        country_list = "', '".join(countries)
        where_clauses.append(f"country IN ('{country_list}')")
    if crops:
        crop_list = "', '".join(crops)
        where_clauses.append(f"crop IN ('{crop_list}')")
    
    where_str = " AND ".join(where_clauses)
    query = text(f"""
        SELECT {dim}, SUM(gross_production_value_usd_millions) as gross_production_value_usd_millions
        FROM vw_agri_base
        WHERE {where_str}
        GROUP BY {dim}
        ORDER BY gross_production_value_usd_millions DESC
        LIMIT {limit}
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df

@st.cache_data(ttl=600, show_spinner="Loading totals…")
def load_yearly_totals(year_min: int, year_max: int, countries: list = None, crops: list = None):
    """Load yearly total values."""
    engine = get_engine()
    where_clauses = [f"year >= {year_min} AND year <= {year_max}"]
    if countries:
        country_list = "', '".join(countries)
        where_clauses.append(f"country IN ('{country_list}')")
    if crops:
        crop_list = "', '".join(crops)
        where_clauses.append(f"crop IN ('{crop_list}')")
    
    where_str = " AND ".join(where_clauses)
    query = text(f"""
        SELECT year, SUM(gross_production_value_usd_millions) as gross_production_value_usd_millions
        FROM vw_agri_base
        WHERE {where_str}
        GROUP BY year
        ORDER BY year
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df

# ─────────────────────────────────────────────
#  HELPER: number formatting
# ─────────────────────────────────────────────
def fmt_usd(val: float, decimals: int = 1) -> str:
    if val >= 1e9:
        return f"${val/1e9:.{decimals}f}B"
    if val >= 1e6:
        return f"${val/1e6:.{decimals}f}M"
    if val >= 1e3:
        return f"${val/1e3:.{decimals}f}K"
    return f"${val:,.0f}"

def fmt_ha(val: float) -> str:
    if val >= 1e9:
        return f"{val/1e9:.2f}B ha"
    if val >= 1e6:
        return f"{val/1e6:.1f}M ha"
    return f"{val/1e3:.1f}K ha"

def fmt_tonnes(val: float) -> str:
    if val >= 1e9:
        return f"{val/1e9:.2f}B t"
    if val >= 1e6:
        return f"{val/1e6:.1f}M t"
    return f"{val/1e3:.1f}K t"

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

def apply_base(fig: go.Figure) -> go.Figure:
    fig.update_layout(**PLOTLY_BASE)
    return fig

# ─────────────────────────────────────────────
#  UI HELPERS 
# ─────────────────────────────────────────────

def render_header():
    st.title("Value, Scale & Composition")
    st.caption("Where does agricultural value come from — across countries, crops, and time?")
    st.divider()


def render_sidebar(db_year_min: int, db_year_max: int, all_countries: list, all_crops: list):
    with st.sidebar:
        st.markdown("### Filters")

        year_range = st.slider(
            "Year range",
            min_value=db_year_min,
            max_value=db_year_max,
            value=(db_year_min, db_year_max),
            step=1,
        )

        sel_countries = st.multiselect(
            "Countries",
            options=all_countries,
            default=[],
            placeholder="Select countries or leave blank for all",
        )

        sel_crops = st.multiselect(
            "Crops",
            options=all_crops,
            default=[],
            placeholder="Select crops or leave blank for all",
        )

        grouping = st.radio(
            "Group by",
            options=["Country", "Crop"],
            index=0,
            horizontal=True,
        )

        st.markdown("---")
        st.markdown(
            f"<span style='font-size:0.72rem;color:{MUTED}'>"
            "Page 1 of 2· FAOSTAT Portfolio"
            "</span>",
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

# ═══════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════
def main():


    # ── get year/country/crop options ──
    try:
        engine = get_engine()
        with engine.connect() as conn:
            year_df = pd.read_sql(text("SELECT DISTINCT year FROM vw_agri_base ORDER BY year"), conn)
            country_df = pd.read_sql(text("SELECT DISTINCT country FROM vw_agri_base ORDER BY country"), conn)
            crop_df = pd.read_sql(text("SELECT DISTINCT crop FROM vw_agri_base ORDER BY crop"), conn)
        db_year_min, db_year_max = int(year_df["year"].min()), int(year_df["year"].max())
        all_countries = sorted(country_df["country"].tolist())
        all_crops = sorted(crop_df["crop"].tolist())
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.info("Check that `database.url` is set in `.streamlit/secrets.toml`.")
        st.stop()

    render_header()

    year_range, sel_countries, sel_crops, grouping = render_sidebar(
        db_year_min, db_year_max, all_countries, all_crops
    )

    # ─────────────────────────────────────────
    #  LOAD KPI DATA (mini-query)
    # ─────────────────────────────────────────
    dim = grouping.lower()
    palette = PALETTE_COUNTRY if dim == "country" else PALETTE_CROP

    kpi_data = load_kpi_summary(
        year_range[0],
        year_range[1],
        countries=sel_countries if sel_countries else None,
        crops=sel_crops if sel_crops else None,
    )

    if kpi_data["total_value"] == 0:
        st.warning("No data for the current filter selection.")
        st.stop()

    render_kpis(kpi_data)

    # ─────────────────────────────────────────
    #  MIDDLE ROW  (line chart | stacked area)
    # ─────────────────────────────────────────
    mid_l, mid_r = st.columns([1, 1], gap="medium")

    # ── LEFT: Total value over time ──
    with mid_l:
        st.subheader("Total Gross Value Over Time")
        line_toggle = st.radio(
            "Breakdown",
            options=[f"By {grouping}", "Total only"],
            key="line_toggle",
            horizontal=True,
            label_visibility="collapsed",
        )

        if line_toggle == "Total only":
            yr_total = load_yearly_totals(
                year_range[0], year_range[1],
                countries=sel_countries if sel_countries else None,
                crops=sel_crops if sel_crops else None
            )
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=yr_total["year"],
                y=yr_total["gross_production_value_usd_millions"],
                mode="lines+markers",
                line=dict(color=AMBER, width=2.5),
                marker=dict(size=5),
                name="Total",
                hovertemplate="<b>%{x}</b><br>$%{y:,.1f}M<extra></extra>",
            ))
        else:
            yr_grp = load_timeseries(
                year_range[0], year_range[1], dim,
                countries=sel_countries if sel_countries else None,
                crops=sel_crops if sel_crops else None
            )
            top_dims = (
                yr_grp.groupby(dim)["gross_production_value_usd_millions"]
                .sum().nlargest(10).index.tolist()
            )
            yr_top = yr_grp[yr_grp[dim].isin(top_dims)]
            fig_line = px.line(
                yr_top,
                x="year", y="gross_production_value_usd_millions",
                color=dim,
                color_discrete_sequence=palette,
                labels={"gross_production_value_usd_millions": "Value (USD M)", "year": "Year", dim: grouping},
            )
            fig_line.update_traces(
                mode="lines+markers",
                line=dict(width=2),
                hovertemplate="<b>%{fullData.name}</b><br>%{x}: $%{y:,.1f}M<extra></extra>",
            )

        fig_line.update_layout(**PLOTLY_BASE)
        fig_line.update_layout(
            height=320,
            yaxis_title="USD Millions",
            xaxis_title=None,
            legend_title_text=grouping,
            title="",
            margin=dict(t=0, l=10, r=10, b=10)
        )
        st.plotly_chart(fig_line, use_container_width=True, key="line_chart", config={'displayModeBar': False})

    # ── RIGHT: Share of value over time (stacked area) ──
    with mid_r:
        st.subheader("Composition of Value Over Time")
        area_toggle = st.radio(
            "Chart type",
            options=["Stacked Area", "Stacked Bar"],
            key="area_toggle",
            horizontal=True,
            label_visibility="collapsed",
        )

        yr_grp = load_timeseries(
            year_range[0], year_range[1], dim,
            countries=sel_countries if sel_countries else None,
            crops=sel_crops if sel_crops else None
        )
        top_dims_r = (
            yr_grp.groupby(dim)["gross_production_value_usd_millions"]
            .sum().nlargest(8).index.tolist()
        )
        yr_top_r = yr_grp[yr_grp[dim].isin(top_dims_r)].copy()

        # compute percentage share per year
        yr_yr_total = yr_top_r.groupby("year")["gross_production_value_usd_millions"].transform("sum")
        yr_top_r["share_pct"] = yr_top_r["gross_production_value_usd_millions"] / yr_yr_total * 100

        if area_toggle == "Stacked Area":
            fig_area = px.area(
                yr_top_r.sort_values(["year", dim]),
                x="year", y="share_pct",
                color=dim,
                color_discrete_sequence=palette,
                labels={"share_pct": "Share (%)", "year": "Year", dim: grouping},
            )
        else:
            fig_area = px.bar(
                yr_top_r.sort_values(["year", dim]),
                x="year", y="share_pct",
                color=dim,
                color_discrete_sequence=palette,
                barmode="stack",
                labels={"share_pct": "Share (%)", "year": "Year", dim: grouping},
            )

        fig_area.update_layout(**PLOTLY_BASE)
        fig_area.update_layout(
            height=320,
            yaxis_title="Share of Total Value (%)",
            xaxis_title=None,
            legend_title_text=f"Top 8 {grouping}s",
            title="",
            margin=dict(t=0, l=10, r=10, b=10)
        )
        fig_area.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.1f}%<extra></extra>"
        )
        st.plotly_chart(fig_area, use_container_width=True, key="area_chart", config={'displayModeBar': False})

    # ─────────────────────────────────────────
    #  BOTTOM ROW  (horizontal bar chart)
    # ─────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader(f"Top {grouping}s by Gross Production Value")

    bar_data = load_top_values(
        dim, year_range[0], year_range[1], limit=50,
        countries=sel_countries if sel_countries else None,
        crops=sel_crops if sel_crops else None
    )

    # colour bars by rank (single-colour gradient from muted → amber)
    n_bars = len(bar_data)

    fig_bar = go.Figure(go.Bar(
        x=bar_data["gross_production_value_usd_millions"],
        y=bar_data[dim],
        orientation="h",
        marker_color=AMBER,
        hovertemplate="<b>%{y}</b><br>$%{x:,.1f}M<extra></extra>",
        text=bar_data["gross_production_value_usd_millions"].apply(
            lambda v: fmt_usd(v * 1e6)),
        textposition="outside",
        textfont=dict(size=10, color=MUTED),
        showlegend=False,
        name="",
    ))

    fig_bar.update_layout(**PLOTLY_BASE)
    fig_bar.update_layout(
        height=max(280, n_bars * 26),
        xaxis_title="Gross Production Value (USD Millions)",
        yaxis_title=None,
        title="",
        margin=dict(l=10, r=80, t=0, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True, key="bar_chart", config={'displayModeBar': False})


# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()
