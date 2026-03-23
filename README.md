# FAO Land-Use Efficiency (ETL + Dashboard)

A small end-to-end data project built on **FAOSTAT** crop area/production/value data:

- **Backend**: a Python ETL pipeline that loads raw CSVs into Postgres (Supabase) and upserts an analysis-ready clean layer.
- **Analytics layer**: SQL views that join/engineer metrics (e.g., **value per hectare**).
- **Frontend**: a 2-page Streamlit dashboard that reveals where agricultural value comes from and which country–crop pairs are most land-efficient.

---

## Index

- [Architecture](#architecture)
- [Setup](#setup)
- [Pipeline behavior](#pipeline-behavior)
- [Pipeline overview](#pipeline-overview)
- [Why it’s good / efficient](#why-its-good--efficient)
- [Dashboards (frontend)](#dashboards-frontend)
- [File structure](#file-structure)
- [Running the pipeline](#running-the-pipeline)
- [Principles](#principles)
- [Future improvements](#future-improvements)
- [License](#license)

---

## Architecture

**3-layer data stack (Supabase Postgres)**

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND: Streamlit Dashboard (app/)                      │
│  ├─ Page 1: Value, Scale & Composition                    │
│  └─ Page 2: Land Efficiency (Value/ha)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ Mini-queries (filtered aggregates)
┌──────────────────────▼──────────────────────────────────────┐
│  SEMANTIC LAYER: SQL Views (sql/views.sql)                 │
│  ├─ vw_agri_base (join + engineered metrics)              │
│  └─ vw_agri_productivity_drivers (rolling averages)       │
└──────────────────────┬──────────────────────────────────────┘
                       │ Analytics queries
┌──────────────────────▼──────────────────────────────────────┐
│  CLEAN LAYER: Analysis-Ready Tables (sql/clean_tables.sql)│
│  ├─ crops_clean (grain: country, crop, year)              │
│  └─ value_clean (grain: country, crop, year)              │
│  • Unique constraints prevent duplicates                   │
│  • Upserts ensure idempotency                              │
│  • cleaned_at timestamps for observability                │
└──────────────────────┬──────────────────────────────────────┘
                       │ ETL pipeline (etl.py)
┌──────────────────────▼──────────────────────────────────────┐
│  RAW LAYER: Landing Zone (sql/raw_tables.sql)              │
│  ├─ raw_crops (append-only)                                │
│  └─ raw_production_value (append-only)                     │
│  • No constraints; original data untouched                 │
│  • Source of truth for reprocessing                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ load_raw.py (initial setup only)
┌──────────────────────▼──────────────────────────────────────┐
│  CSV FILES: Data Source (data/raw/)                        │
│  ├─ raw_crops.csv (FAOSTAT)                                │
│  └─ raw_production_value.csv (FAOSTAT)                     │
└─────────────────────────────────────────────────────────────┘
```

**Layer responsibilities:**

1. **Raw Layer (Landing Zone)**
   - Append-only tables preserve original data as-is
   - Used as a stable source for reprocessing
   - Rebuilt on schema changes only (rare)

2. **Clean Layer (Analysis-Ready)**
   - Idempotent upserts ensure safe reruns
   - Grain: `(country, crop, year)` per table
   - Timestamps for observability

3. **Semantic Layer (Views)**
   - Encode business logic once; reuse everywhere
   - Join raw data and create engineered metrics
   - Enable fast aggregations for dashboards

---

## Setup

### 1) Python environment

Install dependencies:

```powershell
pip install -r requirements.txt
```

### 2) Configure the database connection

This project supports two entrypoints:

- **ETL scripts** (`etl.py`, `load_raw.py`) read `SUPABASE_URL` from a `.env` file.
- **Streamlit app** pages read `database.url` from `.streamlit/secrets.toml`.

#### A) `.env` (for ETL)

Create `.env` in the repo root:

```
SUPABASE_URL=postgresql://postgres:<PASSWORD>@db.<PROJECT-REF>.supabase.co:5432/postgres
```

#### B) `.streamlit/secrets.toml` (for Streamlit)

Create `.streamlit/secrets.toml`:

```toml
[database]
url = "postgresql://postgres:<PASSWORD>@db.<PROJECT-REF>.supabase.co:5432/postgres"
```

> Note: `.streamlit/secrets.toml` should not be committed (it’s in `.gitignore`).

### 3) Create tables + views in Supabase

Run these SQL scripts in the Supabase SQL editor (in this order):

1. `sql/raw_tables.sql`
2. `sql/clean_tables.sql`
3. (optional) `sql/indexes.sql`
4. `sql/views.sql`

---

## Pipeline behavior

### Raw loading (`load_raw.py`) — Initial setup only

- **Purpose**: populate the landing zone on first run
- **How**: reads CSVs from `data/raw/` and appends to raw tables
- **Idempotency**: raw tables have no unique constraints, so multiple runs append duplicate rows (this is okay; the clean layer deduplicates)
- **When to run**: once at project start, or after getting fresh raw CSVs
- **Not for production**: if raw data is updated, manually delete the affected raw records and reload, or build a custom upsert for raw tables

### Clean layer ETL (`etl.py`) — Recurring pipeline

- **Purpose**: transform raw data into an analysis-ready clean layer
- **Safety**: uses idempotent upserts; safe to run multiple times per day
- **Configurability**: `ANALYSIS_YEAR_START`, `ANALYSIS_YEAR_END`, `VALUE_BATCH_SIZE` can be tuned in `etl.py`
- **When to run**: whenever raw data changes or on a schedule (daily, weekly, etc.)

---

## Pipeline overview

### 1) Crops → `crops_clean` (year-by-year batches)

For each year in the analysis range:

- Extracts `raw_crops` rows where `element` is one of:
  - `Area harvested`, `Yield`, `Production`
- Cleans text fields (`area`, `item`)
- Converts `value` to numeric
- Pivots long → wide to produce:
  - `area_harvested_ha`
  - `yield_kg_ha`
  - `production_tonnes`
- Enforces completeness (drops rows missing any of the 3 measures)
- Upserts into `crops_clean` on conflict `(country, crop, year)`

### 2) Production value → `value_clean` (ID-cursor batches)

- Extracts from `raw_production_value` in chunks using an **ID cursor**:
  - `WHERE id > last_seen_id ORDER BY id LIMIT :batch_size`
- Cleans text fields (`area`, `item`)
- Converts `value` to numeric → `gross_production_value_kusd`
- Upserts into `value_clean` on conflict `(country, crop, year)`

### 3) Views power the dashboard

- `vw_agri_base` joins crops + values and engineers:
  - `gross_production_value_usd`
  - `gross_production_value_usd_millions`
  - `yield_t_per_ha`
  - `value_per_ha`
  - `value_per_tonne`

- `vw_agri_productivity_drivers` adds rolling 3-year averages:
  - `value_per_ha_roll3`
  - (also includes rolling yield/value-per-tonne for extensibility)

---

## Why it’s good / efficient

- **Separation of concerns**: raw → clean → views → dashboard.
- **Safe reruns**: clean tables are filled using **upserts**, so you can rerun without duplicates.
- **Batch processing**:
  - Crops are processed **year-by-year** (small, predictable chunks).
  - Values are processed using an **ID-based cursor** with `VALUE_BATCH_SIZE`, keeping memory usage stable.
- **Fast dashboards**:
  - Streamlit pages use **mini-queries** (aggregations filtered by current controls), rather than loading full tables.
  - Cached DB engine (`@st.cache_resource`) and cached query results (`@st.cache_data`).
- **Analytics-ready metrics** defined once in SQL views, rather than recomputed in every chart.

---

## Dashboards (frontend)

The Streamlit dashboard lives in `app/`.

### Page 1 — Value, Scale & Composition (`app/pg1.py`)

Focus: **Where does agricultural value come from?**

What it shows:

- KPI summary: total value, total area, total production, value/ha
- Total value over time (overall or broken down by country/crop)
- Composition of value over time (share by top contributors)
- Rankings of top countries/crops by gross production value

Data source:
- `vw_agri_base`

### Page 2 — Land Efficiency (Value/ha) (`app/pg2.py`)

Focus: **Which country–crop combinations generate the most value per harvested hectare?**

What it shows:

- Heatmap: average value/ha by country × crop
- Top-10 combos by value/ha (with area + production context)
- Trend: indexed value/ha over time (Raw vs rolling average)
- Period change: % change in value/ha over selected years

Data sources:
- `vw_agri_base` (heatmap, ranks, start/end change)
- `vw_agri_productivity_drivers` (trend time series, raw vs rolling)

---

## File structure

```
fao-landuse-efficiency/
├── etl.py                          # Main ETL pipeline (extract → transform → load)
├── load_raw.py                     # One-time raw data loader (initial setup only)
├── requirements.txt                # Python dependencies
├── README.md                        # This file
├── .env                            # Local env vars (for ETL; .gitignore'd)
├── .gitignore                      # Excludes secrets, cache, etc.
├── .streamlit/
│   └── secrets.toml                # Streamlit secrets (database URL; .gitignore'd)
├── data/raw/
│   ├── raw_crops.csv              # FAOSTAT crops data (source)
│   └── raw_production_value.csv   # FAOSTAT production value data (source)
├── sql/
│   ├── raw_tables.sql             # Schema: raw_crops, raw_production_value
│   ├── clean_tables.sql           # Schema: crops_clean, value_clean
│   ├── indexes.sql                # Performance indexes (optional)
│   └── views.sql                  # Analytics views: vw_agri_base, vw_agri_productivity_drivers
├── app/
│   ├── dashboard.py               # Shared utilities (theme, engine, constants)
│   ├── pg1.py                     # Page 1: Value, Scale & Composition
│   └── pg2.py                     # Page 2: Land Efficiency (Value/ha)
└── notebooks/
    └── eda_validation.ipynb       # EDA scratch pad (optional)
```

---

## Running the pipeline

### Initial setup (one time)

1. **Create tables & views** in Supabase SQL editor:
   ```sql
   -- Run these in order:
   -- 1. sql/raw_tables.sql
   -- 2. sql/clean_tables.sql
   -- 3. sql/indexes.sql (optional)
   -- 4. sql/views.sql
   ```

2. **Load raw data** into landing zone:
   ```powershell
   python load_raw.py
   ```
   Expected output:
   ```
   Data loaded successfully.
   ```
   This appends CSV rows into `raw_crops` and `raw_production_value` (one-time setup only).

### Recurring ETL

Every time you want to refresh the analysis-ready layer:

```powershell
python etl.py
```

Expected output:

```
======================================================================
ETL PIPELINE: raw to clean
======================================================================
Analysis period: 2015 - 2024

Processing crops_clean...
  2015: 33 complete records loaded
  2016: 33 complete records loaded
  ...
  2024: 33 complete records loaded
crops_clean: 330 total rows loaded

Processing value_clean...
  IDs 1-33: 33 records loaded
  IDs 34-66: 33 records loaded
  ...
value_clean: 330 total rows loaded

======================================================================
ETL PIPELINE COMPLETE
======================================================================
```

### Run the Streamlit app

```powershell
streamlit run app/pg1.py
```

or use Streamlit's multipage navigation to switch between pages.

---

## Principles

This project follows data engineering best practices:

- **Immutability at the source**: raw tables are append-only; original data is never modified.
- **Idempotency**: the clean layer uses upserts; rerunning ETL is safe and deterministic.
- **Separation of concerns**: raw → clean → views → dashboard keeps each layer independent and testable.
- **Observability**: `cleaned_at` timestamps on clean tables show when data was last processed.
- **Type safety**: numeric columns are validated during transformation; errors are logged and skipped.
- **Batch efficiency**: crops are chunked by year, values by ID cursor; memory stays constant as data grows.
- **Semantic layer**: SQL views encode business logic once; dashboards reuse rather than duplicate.

---

## Future improvements

- **Incremental ETL**: persist a watermark (e.g., `max(raw_production_value.id)` and/or per-file load timestamp) so subsequent runs process only new rows instead of rescanning the full range.
- **Materialized views** for expensive aggregates if the dataset grows beyond current size.
- **Stronger validation** (e.g., outlier detection, unit consistency checks, missingness reports exported as artifacts).
- **Pipeline orchestration**: schedule ETL runs using GitHub Actions, Supabase cron, or a job runner.
- **Performance tuning**: add query-specific indexes and validate with `EXPLAIN` plans.
- **Data quality dashboard**: expose validation metrics and data freshness to stakeholders.

---

---

## Data source

This project uses publicly available data from **FAOSTAT** (Food and Agriculture Organization of the United Nations):

- **FAOSTAT Production Data**: crop production, area harvested, and yield across countries and years
- **FAOSTAT Value Data**: gross production value of agricultural commodities

Data is sourced via the FAOSTAT bulk download API and stored in the `/data/raw/` directory.

For more information, visit: [FAOSTAT](https://www.fao.org/faostat/)

---

## License

Personal project for exploring agricultural land-use efficiency and data engineering best practices.

