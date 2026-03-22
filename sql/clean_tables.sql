CREATE TABLE IF NOT EXISTS crops_clean (
  id                serial primary key,
  country           text,
  crop              text,
  year              int,
  area_harvested_ha numeric,
  yield_kg_ha       numeric,
  production_tonnes numeric,
  cleaned_at        timestamptz default now(),
  UNIQUE (country, crop, year)
);

CREATE TABLE IF NOT EXISTS value_clean (
  id                          serial primary key,
  country                     text,
  crop                        text,
  year                        int,
  gross_production_value_kusd numeric,
  cleaned_at                  timestamptz default now(),
  UNIQUE (country, crop, year)
);