"""ETL: raw_crops and raw_production_value to crops_clean and value_clean."""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)
supabase_url = os.getenv("SUPABASE_URL")
if not supabase_url:
    raise ValueError(f"SUPABASE_URL not found in {env_path}")

engine = create_engine(supabase_url)

# Configuration
ANALYSIS_YEAR_START = 2015
ANALYSIS_YEAR_END = 2024
VALUE_BATCH_SIZE = 33

# ============================================================================
# CROPS CLEANING
# ============================================================================

def extract_crops_batch(year):
    """
    Extract raw_crops for a single year.
    Filters: year matches parameter, element is one of (Area harvested, Yield, Production).
    Returns DataFrame with [area, item, year, element, value].
    """
    query = text("""
    SELECT area, item, year, element, value
    FROM raw_crops
    WHERE year = :year
      AND element IN ('Area harvested', 'Yield', 'Production')
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"year": year})
    return df

def transform_crops_batch(df):
    """
    Transform crops from long to wide format.
    Trims text, converts value to numeric, pivots on element, enforces completeness.
    Returns one row per (country, crop, year) with measures in separate columns.
    """
    
    if df.empty:
        return pd.DataFrame()
    
    df["area"] = df["area"].str.strip()
    df["item"] = df["item"].str.strip()
    
    df = df.rename(columns={"area": "country", "item": "crop"})
    
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    
    df = df.dropna(subset=["value"])
    
    pivot_map = {
        "Area harvested": "area_harvested_ha",
        "Yield": "yield_kg_ha",
        "Production": "production_tonnes"
    }
    
    df["element"] = df["element"].map(pivot_map)
    
    df_wide = df.pivot_table(
        index=["country", "crop", "year"],
        columns="element",
        values="value",
        aggfunc="first"
    ).reset_index()
    
    required_cols = ["area_harvested_ha", "yield_kg_ha", "production_tonnes"]
    df_wide = df_wide.dropna(subset=required_cols)
    
    return df_wide

def load_crops_batch(df):
    """
    Upsert crop records into crops_clean.
    Adds cleaned_at timestamp and inserts or updates on conflict (country, crop, year).
    """
    if df.empty:
        return
    
    cleaned_at = datetime.now(timezone.utc)
    df["cleaned_at"] = cleaned_at
    
    columns = ["country", "crop", "year", "area_harvested_ha", "yield_kg_ha", "production_tonnes", "cleaned_at"]
    df = df[columns]
    
    upsert_query = """
    INSERT INTO crops_clean (country, crop, year, area_harvested_ha, yield_kg_ha, production_tonnes, cleaned_at)
    VALUES (:country, :crop, :year, :area_harvested_ha, :yield_kg_ha, :production_tonnes, :cleaned_at)
    ON CONFLICT (country, crop, year)
    DO UPDATE SET
        area_harvested_ha = EXCLUDED.area_harvested_ha,
        yield_kg_ha = EXCLUDED.yield_kg_ha,
        production_tonnes = EXCLUDED.production_tonnes,
        cleaned_at = EXCLUDED.cleaned_at;
    """
    
    with engine.begin() as conn:
        records = df.to_dict(orient="records")
        conn.execute(text(upsert_query), records)

def process_crops_clean():
    """
    Process all years 2015-2024 for crops.
    Extracts, transforms, and loads each year separately. Reports rows per year.
    """
    print("\nProcessing crops_clean...")
    
    total_rows = 0
    for year in range(ANALYSIS_YEAR_START, ANALYSIS_YEAR_END + 1):
        df_raw = extract_crops_batch(year)
        
        if df_raw.empty:
            print(f"  {year}: no data")
            continue
        
        df_clean = transform_crops_batch(df_raw)
        
        if df_clean.empty:
            print(f"  {year}: no complete records after transformation")
            continue
        
        load_crops_batch(df_clean)
        total_rows += len(df_clean)
        print(f"  {year}: {len(df_clean)} complete records loaded")
    
    print(f"crops_clean: {total_rows} total rows loaded")

# ============================================================================
# VALUE CLEANING
# ============================================================================

def extract_value_batch(last_seen_id, batch_size):
    """
    Extract raw_production_value records using ID-based chunking.
    Filters: year 2015-2024, id > last_seen_id. Ordered by id.
    Returns DataFrame with [id, area, item, year, value].
    """
    query = text("""
    SELECT id, area, item, year, value
    FROM raw_production_value
    WHERE year BETWEEN :year_start AND :year_end
      AND id > :last_seen_id
    ORDER BY id
    LIMIT :batch_size
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={
            "year_start": ANALYSIS_YEAR_START,
            "year_end": ANALYSIS_YEAR_END,
            "last_seen_id": last_seen_id,
            "batch_size": batch_size
        })
    
    return df

def transform_value_batch(df):
    """
    Transform production value records.
    Trims text, converts value to numeric, drops incomplete rows.
    Returns one row per (country, crop, year) with gross_production_value_kusd.
    """
    if df.empty:
        return pd.DataFrame()
    
    df["area"] = df["area"].str.strip()
    df["item"] = df["item"].str.strip()
    
    df = df.rename(columns={
        "area": "country",
        "item": "crop",
        "value": "gross_production_value_kusd"
    })
    
    df["gross_production_value_kusd"] = pd.to_numeric(
        df["gross_production_value_kusd"],
        errors="coerce"
    )
    
    df = df.dropna(subset=["country", "crop", "year", "gross_production_value_kusd"])
    
    df = df[["country", "crop", "year", "gross_production_value_kusd"]]
    
    return df

def load_value_batch(df):
    """
    Upsert production value records into value_clean.
    Adds cleaned_at timestamp and inserts or updates on conflict (country, crop, year).
    """
    if df.empty:
        return
    
    cleaned_at = datetime.now(timezone.utc)
    df["cleaned_at"] = cleaned_at
    
    columns = ["country", "crop", "year", "gross_production_value_kusd", "cleaned_at"]
    df = df[columns]
    
    upsert_query = """
    INSERT INTO value_clean (country, crop, year, gross_production_value_kusd, cleaned_at)
    VALUES (:country, :crop, :year, :gross_production_value_kusd, :cleaned_at)
    ON CONFLICT (country, crop, year)
    DO UPDATE SET
        gross_production_value_kusd = EXCLUDED.gross_production_value_kusd,
        cleaned_at = EXCLUDED.cleaned_at;
    """
    
    with engine.begin() as conn:
        records = df.to_dict(orient="records")
        conn.execute(text(upsert_query), records)

def process_value_clean():
    """
    Process production value in ID-based batches.
    Extracts, transforms, and loads in chunks of 5k rows. Reports ID ranges.
    """
    print("\nProcessing value_clean...")
    
    total_rows = 0
    last_seen_id = 0
    
    while True:
        df_raw = extract_value_batch(int(last_seen_id), VALUE_BATCH_SIZE)
        
        if df_raw.empty:
            break
        
        df_clean = transform_value_batch(df_raw)
        
        if not df_clean.empty:
            load_value_batch(df_clean)
            total_rows += len(df_clean)
            print(f"  IDs {last_seen_id + 1}-{df_raw['id'].max()}: {len(df_clean)} records loaded")
        
        last_seen_id = int(df_raw["id"].max())
    
    print(f"value_clean: {total_rows} total rows loaded")

# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_etl():
    """
    Execute the complete ETL pipeline.
    Orchestrates extraction, transformation, and loading of crops and production value.
    """
    print("=" * 70)
    print("ETL PIPELINE: raw to clean")
    print("=" * 70)
    print(f"Analysis period: {ANALYSIS_YEAR_START} - {ANALYSIS_YEAR_END}")
    
    try:
        process_crops_clean()
        process_value_clean()
        
        print("\n" + "=" * 70)
        print("ETL PIPELINE COMPLETE")
        print("=" * 70)
        
    except Exception as e:
        print(f"\nETL PIPELINE FAILED: {e}")
        raise

if __name__ == "__main__":
    run_etl()
