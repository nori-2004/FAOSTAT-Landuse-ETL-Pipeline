import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv()
engine = create_engine(os.getenv("SUPABASE_URL"))

crops = pd.read_csv("data/raw/raw_crops.csv")
crops.columns = [
    "domain_code", "domain", "area_code", "area",
    "element_code", "element", "item_code", "item",
    "year_code", "year", "unit", "value",
    "flag", "flag_description", "note"
]
crops.to_sql("raw_crops", engine, if_exists="append", index=False)

value = pd.read_csv("data/raw/raw_production_value.csv")
value.columns = [
    "domain_code", "domain", "area_code", "area",
    "element_code", "element", "item_code", "item",
    "year_code", "year", "unit", "value",
    "flag", "flag_description"
]
value.to_sql("raw_production_value", engine, if_exists="append", index=False)

print("Data loaded successfully.")