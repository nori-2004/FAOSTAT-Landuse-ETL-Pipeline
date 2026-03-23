""" 
Page 2 — Land Efficiency (Value per hectare)
FAOSTAT Agricultural Portfolio | UBC CSFS Application

Business question:
  Which country-crop combinations generate the most value per harvested hectare?

Core metric:
  - Value per hectare (USD/ha): gross_production_value_usd / area_harvested_ha

Data sources:
  - vw_agri_productivity_drivers (raw + rolling value/ha for trend)
  - vw_agri_base (KPIs, heatmap, rankings, period change)
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import text

from dashboard import get_engine

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Land Efficiency (Value/ha) | FAOSTAT",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  THEME / CSS
# ─────────────────────────────────────────────
AMBER = "#F0A500"
SLATE = "#0F1117"
CARD_BG = "#1A1F2E"
BORDER = "#2A3045"
TEXT = "#E8EAF0"
MUTED = "#6B7280"

st.markdown(
    f"""
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
""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
#  PLOTLY BASE
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
#  DATA ACCESS (mini-queries)
# ─────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def load_options():
    engine = get_engine()
    with engine.connect() as conn:
        year_df = pd.read_sql(text("SELECT DISTINCT year FROM vw_agri_base ORDER BY year"), conn)
        crop_df = pd.read_sql(text("SELECT DISTINCT crop FROM vw_agri_base ORDER BY crop"), conn)
        country_df = pd.read_sql(text("SELECT DISTINCT country FROM vw_agri_base ORDER BY country"), conn)

    return (
        int(year_df["year"].min()),
        int(year_df["year"].max()),
        sorted(crop_df["crop"].tolist()),
        sorted(country_df["country"].tolist()),
    )


@st.cache_data(ttl=600, show_spinner="Loading trend…")
def load_trend_timeseries(
    year_min: int,
    year_max: int,
    crop: str,
    focus_country: str,
    smoothing: str,
):
    """Time-series for value per hectare for a single country + crop."""
    engine = get_engine()

    metric_cols = {
        "Raw": {
            "value_per_ha": "value_per_ha",
        },
        "Rolling average": {
            "value_per_ha": "value_per_ha_roll3",
        },
    }

    cols = metric_cols["Rolling average" if smoothing == "Rolling average" else "Raw"]

    q = text(
        f"""
        SELECT
            year,
            {cols['value_per_ha']} AS value_per_ha
        FROM vw_agri_productivity_drivers
        WHERE year BETWEEN :ymin AND :ymax
          AND crop = :crop
          AND country = :country
        ORDER BY year;
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(
            q,
            conn,
            params={
                "ymin": year_min,
                "ymax": year_max,
                "crop": crop,
                "country": focus_country,
            },
        )

    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_kpi_aggregates(
    year_min: int,
    year_max: int,
    crop: str,
    countries: tuple[str, ...],
) -> pd.DataFrame:
    """Aggregates used for KPI cards (avg metrics + ranking candidates)."""
    engine = get_engine()

    q = text(
        """
        SELECT
            country,
            crop,
            AVG(value_per_ha) AS avg_value_per_ha
        FROM vw_agri_base
        WHERE year BETWEEN :ymin AND :ymax
          AND crop = :crop
          AND country = ANY(:countries)
        GROUP BY country, crop
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(
            q,
            conn,
            params={
                "ymin": year_min,
                "ymax": year_max,
                "crop": crop,
                "countries": list(countries),
            },
        )

    return df


@st.cache_data(ttl=600, show_spinner="Loading heatmap…")
def load_heatmap_agg(
    year_min: int,
    year_max: int,
    crops: tuple[str, ...],
    countries: tuple[str, ...],
) -> pd.DataFrame:
    """Country × crop averages over the selected period."""
    engine = get_engine()

    q = text(
        """
        SELECT
            country,
            crop,
            AVG(value_per_ha) AS avg_value_per_ha,
            AVG(area_harvested_ha) AS avg_area_harvested_ha,
            AVG(production_tonnes) AS avg_production_tonnes
        FROM vw_agri_base
        WHERE year BETWEEN :ymin AND :ymax
          AND crop = ANY(:crops)
          AND country = ANY(:countries)
        GROUP BY country, crop
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(
            q,
            conn,
            params={
                "ymin": year_min,
                "ymax": year_max,
                "crops": list(crops),
                "countries": list(countries),
            },
        )

    return df


@st.cache_data(ttl=600, show_spinner="Loading top 10…")
def load_top10(
    year_min: int,
    year_max: int,
    crops: tuple[str, ...],
    countries: tuple[str, ...],
) -> pd.DataFrame:
    """Top 10 country-crop combinations by average value/ha (computed in SQL)."""
    engine = get_engine()

    q = text(
        """
        SELECT
            country,
            crop,
            AVG(value_per_ha) AS avg_value_per_ha,
            AVG(area_harvested_ha) AS avg_area_harvested_ha,
            AVG(production_tonnes) AS avg_production_tonnes
        FROM vw_agri_base
        WHERE year BETWEEN :ymin AND :ymax
          AND crop = ANY(:crops)
          AND country = ANY(:countries)
        GROUP BY country, crop
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(
            q,
            conn,
            params={
                "ymin": year_min,
                "ymax": year_max,
                "crops": list(crops),
                "countries": list(countries),
            },
        )

    return df


@st.cache_data(ttl=600, show_spinner="Loading period change…")
def load_period_values(
    year_start: int,
    year_end: int,
    crop: str,
    countries: tuple[str, ...],
) -> pd.DataFrame:
    """Start/end year values per country for the selected crop (pandas computes % changes)."""
    engine = get_engine()
    q = text(
        """
        SELECT
            country,
            year,
            value_per_ha
        FROM vw_agri_base
        WHERE year IN (:y0, :y1)
          AND crop = :crop
          AND country = ANY(:countries)
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(
            q,
            conn,
            params={
                "y0": int(year_start),
                "y1": int(year_end),
                "crop": crop,
                "countries": list(countries),
            },
        )

    return df


def _pct_change(start: float, end: float) -> float | None:
    if start is None or end is None:
        return None
    if pd.isna(start) or pd.isna(end) or start == 0:
        return None
    return ((end - start) / start) * 100.0


def _fmt_usd_per_ha(x) -> str:
    try:
        if x is None or pd.isna(x):
            return "—"
        return f"${x:,.0f}"
    except Exception:
        return "—"


def _fmt_t_per_ha(x) -> str:
    try:
        if x is None or pd.isna(x):
            return "—"
        return f"{x:,.2f}"
    except Exception:
        return "—"


def _fmt_pct(x) -> str:
    try:
        if x is None or pd.isna(x):
            return "—"
        return f"{x:+.1f}%"
    except Exception:
        return "—"


def _index_series(df: pd.DataFrame, col: str) -> pd.Series:
    """Index a series to the first non-null, non-zero value = 100."""
    s = pd.to_numeric(df[col], errors="coerce")
    s_valid = s.replace([0, float("inf"), float("-inf")], pd.NA).dropna()
    if s_valid.empty:
        return pd.Series([pd.NA] * len(df), index=df.index)

    base = float(s_valid.iloc[0])
    if base == 0 or pd.isna(base):
        return pd.Series([pd.NA] * len(df), index=df.index)

    return (s / base) * 100.0


def main():
    st.title("Land Efficiency (Value per hectare)")
    st.caption(
        "Explore value per harvested hectare across countries and crops."
    )
    st.divider()

    # ── options ──
    try:
        db_year_min, db_year_max, all_crops, all_countries = load_options()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.info("Check that `database.url` is set in `.streamlit/secrets.toml`.")
        st.stop()

    # ─────────────────────────────────────────
    #  SIDEBAR CONTROLS (year + countries only)
    # ─────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Controls")

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
            default=all_countries,
        )

        st.markdown("---")
        st.caption("Page 2 · FAOSTAT Portfolio")

    if not sel_countries:
        st.warning("Select at least one country.")
        st.stop()

    y0, y1 = int(year_range[0]), int(year_range[1])
    countries_t = tuple(sel_countries)

    # ─────────────────────────────────────────
    #  KPI CARDS (value/ha only)
    #   - compute from ALL crops so it matches the Top 10 chart
    # ─────────────────────────────────────────
    kpi_df_all = load_top10(y0, y1, crops=tuple(all_crops), countries=countries_t)

    avg_value = float(kpi_df_all["avg_value_per_ha"].mean()) if not kpi_df_all.empty else None

    top_row = None
    if not kpi_df_all.empty:
        top_row = kpi_df_all.sort_values("avg_value_per_ha", ascending=False).iloc[0]

    # Largest improvement in value/ha between start and end year (for the same top crop context)
    improvement_label = "Largest improvement in value per hectare"
    improvement_value = "—"
    improvement_delta = None

    if y0 == y1:
        improvement_label = "Highest current value per hectare"
        if top_row is not None:
            improvement_value = f"{top_row['country']} – {top_row['crop']}"
            improvement_delta = _fmt_usd_per_ha(top_row["avg_value_per_ha"])
    else:
        # pick improvement across all country-crop pairs (consistent with Top 10 view)
        engine = get_engine()
        q = text(
            """
            SELECT
                country,
                crop,
                year,
                value_per_ha
            FROM vw_agri_base
            WHERE year IN (:y0, :y1)
              AND country = ANY(:countries)
            """
        )
        with engine.connect() as conn:
            period_df = pd.read_sql(
                q,
                conn,
                params={"y0": y0, "y1": y1, "countries": list(countries_t)},
            )

        if not period_df.empty:
            start = (
                period_df.loc[period_df["year"] == y0, ["country", "crop", "value_per_ha"]]
                .rename(columns={"value_per_ha": "value_start"})
                .groupby(["country", "crop"], as_index=False)
                .agg(value_start=("value_start", "mean"))
            )
            end = (
                period_df.loc[period_df["year"] == y1, ["country", "crop", "value_per_ha"]]
                .rename(columns={"value_per_ha": "value_end"})
                .groupby(["country", "crop"], as_index=False)
                .agg(value_end=("value_end", "mean"))
            )

            chg = start.merge(end, on=["country", "crop"], how="inner")
            if not chg.empty:
                chg["pct_value_per_ha"] = [
                    _pct_change(
                        float(s) if not pd.isna(s) else None,
                        float(e) if not pd.isna(e) else None,
                    )
                    for s, e in zip(chg["value_start"], chg["value_end"])
                ]
                chg = chg.dropna(subset=["pct_value_per_ha"])
                if not chg.empty:
                    best = chg.sort_values("pct_value_per_ha", ascending=False).iloc[0]
                    improvement_value = f"{best['country']} – {best['crop']}"
                    improvement_delta = _fmt_pct(best["pct_value_per_ha"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Average value per hectare", _fmt_usd_per_ha(avg_value))
    if top_row is None:
        c2.metric("Top country-crop by value per hectare", "—")
    else:
        c2.metric(
            "Top country-crop by value per hectare",
            f"{top_row['country']} – {top_row['crop']}",
            _fmt_usd_per_ha(top_row["avg_value_per_ha"]),
        )
    c3.metric(improvement_label, improvement_value, improvement_delta if improvement_delta else None)

    st.divider()

    # ─────────────────────────────────────────
    #  TOP ROW — bottom plots moved up: HEATMAP + TOP 10
    # ─────────────────────────────────────────
    top_left, top_right = st.columns([1, 1])

    with top_left:
        st.subheader("Average value per hectare by country and crop")
        st.caption("Cell values are period averages over the selected year range.")

        heat_df = load_heatmap_agg(
            y0,
            y1,
            crops=tuple(all_crops),
            countries=countries_t,
        )

        if heat_df.empty:
            st.warning("No data for heatmap.")
        else:
            pivot = heat_df.pivot(index="country", columns="crop", values="avg_value_per_ha")
            fig_h = px.imshow(
                pivot,
                color_continuous_scale="Viridis",
                aspect="auto",
                labels=dict(color="Avg value/ha (USD/ha)"),
            )
            fig_h.update_layout(**PLOTLY_BASE)
            fig_h.update_layout(
                height=max(420, 22 * len(pivot.index) + 120),
                margin=dict(t=0, l=10, r=10, b=10),
                coloraxis_colorbar=dict(title="Avg value/ha (USD/ha)"),
            )
            fig_h.update_xaxes(side="top")
            st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar": False})

    with top_right:
        st.subheader("Top-performing country-crop combinations")
        st.caption("Ranked by average value per hectare over the selected period.")

        top_df = load_top10(y0, y1, crops=tuple(all_crops), countries=countries_t)
        if top_df.empty:
            st.warning("No data for ranking.")
        else:
            top_df = top_df.copy()
            top_df["label"] = top_df["country"] + " – " + top_df["crop"]
            top_df = top_df.sort_values("avg_value_per_ha", ascending=False).head(10)

            fig_b = px.bar(
                top_df,
                x="avg_value_per_ha",
                y="label",
                orientation="h",
                title="",
                hover_data={
                    "country": True,
                    "crop": True,
                    "avg_value_per_ha": ":,.0f",
                    "avg_area_harvested_ha": ":,.0f",
                    "avg_production_tonnes": ":,.0f",
                    "label": False,
                },
            )
            fig_b.update_layout(**PLOTLY_BASE)
            fig_b.update_layout(
                height=max(360, 26 * len(top_df) + 120),
                xaxis_title="Value per ha (USD/ha)",
                yaxis_title=None,
                title="",
                margin=dict(t=0, l=10, r=10, b=10),
                showlegend=False,
            )
            fig_b.update_traces(marker_color=AMBER)
            st.plotly_chart(fig_b, use_container_width=True, config={"displayModeBar": False})

    st.divider()

    # ─────────────────────────────────────────
    #  BOTTOM CONTROLS (crop applies to both bottom charts)
    #  - remove Section 2 header
    #  - move Raw/Rolling toggle into the line chart panel
    # ─────────────────────────────────────────
    bottom_crop = st.selectbox(
        "Select Crop",
        options=all_crops,
        index=0,
        key="bottom_crop",
    )

    bottom_left, bottom_right = st.columns([1, 1])

    with bottom_left:
        st.subheader("Trend of value per hectare")
        st.caption("One line per selected country. Values are indexed to the first year in range.")

        smoothing = st.radio(
            "Trend display",
            options=["Raw", "Rolling average"],
            index=1,
            horizontal=True,
            key="bottom_smoothing",
        )

        # pull and index each country separately (keeps queries small and predictable)
        series_frames = []
        for ctry in sel_countries:
            ts = load_trend_timeseries(y0, y1, bottom_crop, ctry, smoothing)
            if ts.empty:
                continue
            ts = (
                ts.groupby("year", as_index=False)
                .agg(value_per_ha=("value_per_ha", "mean"))
                .sort_values("year")
            )
            ts["idx_value_per_ha"] = _index_series(ts, "value_per_ha")
            ts["country"] = ctry
            series_frames.append(ts[["year", "country", "idx_value_per_ha"]])

        if not series_frames:
            st.warning("No trend data found for the current selection.")
        else:
            trend_all = pd.concat(series_frames, ignore_index=True)
            fig = px.line(
                trend_all,
                x="year",
                y="idx_value_per_ha",
                color="country",
                markers=True,
                title="",
            )
            fig.update_layout(**PLOTLY_BASE)
            fig.update_layout(
                height=420,
                yaxis_title="Indexed value/ha (base year = 100)",
                xaxis_title=None,
                legend_title_text=None,
                title="",
                margin=dict(t=0, l=10, r=10, b=10),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with bottom_right:
        st.subheader("Change over selected period")
        st.caption("Percent change in value per hectare from the first to the last year in the selected range.")

        if y0 == y1:
            st.info("Select a multi-year range to compute period change.")
        else:
            period_df = load_period_values(y0, y1, bottom_crop, countries_t)
            if period_df.empty:
                st.warning("No start/end values found for this selection.")
            else:
                start = (
                    period_df.loc[period_df["year"] == y0, ["country", "value_per_ha"]]
                    .rename(columns={"value_per_ha": "value_start"})
                    .groupby("country", as_index=False)
                    .agg(value_start=("value_start", "mean"))
                )
                end = (
                    period_df.loc[period_df["year"] == y1, ["country", "value_per_ha"]]
                    .rename(columns={"value_per_ha": "value_end"})
                    .groupby("country", as_index=False)
                    .agg(value_end=("value_end", "mean"))
                )

                out = start.merge(end, on="country", how="inner")
                if out.empty:
                    st.warning("Not enough data to compute % changes (missing start/end values).")
                else:
                    out["pct_value_per_ha"] = [
                        _pct_change(
                            float(s) if not pd.isna(s) else None,
                            float(e) if not pd.isna(e) else None,
                        )
                        for s, e in zip(out["value_start"], out["value_end"])
                    ]
                    out = out.dropna(subset=["pct_value_per_ha"])

                    if out.empty:
                        st.warning("Not enough data to compute % changes (start value is 0/NULL).")
                    else:
                        out = out.sort_values("pct_value_per_ha", ascending=False)
                        fig_c = px.bar(
                            out,
                            x="country",
                            y="pct_value_per_ha",
                            title="",
                        )
                        fig_c.update_layout(**PLOTLY_BASE)
                        fig_c.update_layout(
                            height=420,
                            xaxis_title=None,
                            yaxis_title="Percent change (%)",
                            title="",
                            margin=dict(t=0, l=10, r=10, b=10),
                            showlegend=False,
                        )
                        fig_c.update_yaxes(ticksuffix="%")
                        fig_c.update_traces(marker_color=AMBER)
                        st.plotly_chart(fig_c, use_container_width=True, config={"displayModeBar": False})


if __name__ == "__main__":
    main()
