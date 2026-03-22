CREATE INDEX IF NOT EXISTS idx_crops_clean_country ON crops_clean (country);
CREATE INDEX IF NOT EXISTS idx_crops_clean_crop    ON crops_clean (crop);
CREATE INDEX IF NOT EXISTS idx_crops_clean_year    ON crops_clean (year);
CREATE INDEX IF NOT EXISTS idx_value_clean_country ON value_clean (country);
CREATE INDEX IF NOT EXISTS idx_value_clean_crop    ON value_clean (crop);
CREATE INDEX IF NOT EXISTS idx_value_clean_year    ON value_clean (year);