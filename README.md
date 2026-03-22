# FAO Land-Use Efficiency ETL Pipeline

A production-grade ETL pipeline that ingests FAOSTAT crop and production value data, applies transformations (pivoting, standardization, validation), and loads into a clean analytics layer. Implements append-only raw tables and idempotent upserts to enable safe, repeatable loads.

## Architecture

Three-layer data stack:

**Raw Tables** → CSV data loaded as-is into Postgres (append-only design)
- `raw_crops` — crop data with auto-increment IDs
- `raw_production_value` — production values with auto-increment IDs

**ETL Layer** → Extract, transform, load pipeline
- Extracts by year (crops) and by ID cursor (production values)
- Transforms: pivots crops from long to wide, standardizes text, validates numeric types
- Loads via upserts on `(country, crop, year)` unique key

**Clean Tables** → Analysis-ready data
- `crops_clean` — pivoted crop data (one row per country/crop/year, columns: area, yield, production)
- `value_clean` — production values (one row per country/crop/year, column: gross_production_value_kusd)

## Getting Started

### Prerequisites

1. **Supabase Account** ([supabase.com](https://supabase.com))
   - Create a new project
   - Copy the database connection URL

2. **Python 3.8+** with required packages:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Environment Variables**
   - Create a `.env` file in the project root:
     ```
     SUPABASE_URL=postgresql://postgres.xxxxx:password@aws-0-region.pooler.supabase.com:6543/postgres
     ```
   - To find your connection string: Supabase dashboard → Connect → Copy the connection string, replace `[YOUR-PASSWORD]`

### Setup Steps

#### 1. Create Raw Tables

Execute `sql/raw_tables.sql` in Supabase to create the landing zone:
- `raw_crops` — auto-increment ID, untransformed crop production data
- `raw_production_value` — auto-increment ID, untransformed production values

Raw tables are append-only by design (no unique constraints).

#### 2. Create Clean Tables

Execute `sql/clean_tables.sql` to create the analysis layer:
- `crops_clean` — grain: `(country, crop, year)`, unique constraint prevents duplicates
- `value_clean` — grain: `(country, crop, year)`, unique constraint prevents duplicates

Both include `cleaned_at` timestamp for observability.

#### 3. (Optional) Add Indexes

For better query performance, execute `sql/indexes.sql`.

#### 4. Load Raw Data

```powershell
python load_raw.py
```

Reads CSVs from `data/raw/` and appends to raw tables in Supabase. Since raw tables only have auto-increment IDs, multiple runs simply add new rows.

#### 5. Run ETL

```powershell
python etl.py
```

Executes the transformation pipeline:
1. **Extract**: Filters raw data by year (2015–2024 default)
2. **Transform**: Pivots crops long→wide, standardizes text, validates numeric types
3. **Load**: Upserts into clean tables on conflict of `(country, crop, year)`

Upserts ensure idempotency—running again refreshes existing records without duplicates.

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
  IDs 1-33: 330 records loaded
value_clean: 330 total rows loaded

======================================================================
ETL PIPELINE COMPLETE
======================================================================
```

## File Structure

```
fao-landuse-efficiency/
├── etl.py                   # Main ETL: extract, transform, load with upserts
├── load_raw.py              # One-time loader: CSVs → raw tables
├── requirements.txt         # pandas, sqlalchemy, python-dotenv, psycopg2
├── README.md                # This file
├── data/raw/
│   ├── raw_crops.csv        # Crop production data
│   └── raw_production_value.csv
├── sql/
│   ├── raw_tables.sql       # Raw schema (append-only, auto-increment IDs)
│   ├── clean_tables.sql     # Clean schema (unique constraints on grain)
│   └── indexes.sql          # Optional indexes on foreign keys
├── app/
│   └── dashboard.py         # (Future) Streamlit dashboard
└── notebooks/
    └── eda_validation.ipynb # Validation scratch pad
```

## Pipeline Behavior

**First run:**
- `load_raw.py` appends raw data (~330 rows per table)
- `etl.py` extracts, transforms, and upserts into clean tables

**Subsequent runs of `etl.py`:**
- Processes the same raw data
- Upserts update existing `(country, crop, year)` rows
- `cleaned_at` timestamp refreshes
- No duplicates created

**Adding new years:**
- Append new rows to raw tables
- Update `ANALYSIS_YEAR_END` in `etl.py`
- Run `etl.py` to process new data

## Configuration

Edit `etl.py` to customize:

```python
ANALYSIS_YEAR_START = 2015  # Earliest year to extract
ANALYSIS_YEAR_END = 2024    # Latest year to extract
VALUE_BATCH_SIZE = 33       # Batch size for ID-based chunking (memory efficiency)
```

## Implementation Details

**Crops Pipeline:**
- Extracts by year, filters to analysis period
- Pivots from long (area, yield, production as rows) to wide (as columns)
- Validates all three measures present per country/crop/year (completeness check)
- Upserts to `crops_clean` on `(country, crop, year)` key

**Values Pipeline:**
- Uses ID-based cursor extraction (`WHERE id > last_seen_id`) for efficiency
- Processes in batches to manage memory
- Standardizes `gross_production_value_kusd` numeric column
- Upserts to `value_clean` on `(country, crop, year)` key

**Error Handling:**
- Type conversion errors logged and skipped
- Missing required fields trigger validation warnings
- Failed inserts rollback the transaction

## Next Steps

1. Set up Supabase and create tables via SQL scripts
2. Run `python load_raw.py` to populate raw tables
3. Run `python etl.py` to transform into clean layer
4. Query clean tables for analysis or build downstream views
5. Schedule `etl.py` as a cron job or use a cloud scheduler for incremental updates

## License

Internal project.
