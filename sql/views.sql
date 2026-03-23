CREATE OR REPLACE VIEW vw_agri_base AS
SELECT
    c.country,
    c.crop,
    c.year,
    c.area_harvested_ha,
    c.yield_kg_ha,
    c.production_tonnes,
    v.gross_production_value_kusd,
    
    -- standardized units
    v.gross_production_value_kusd * 1000.0 AS gross_production_value_usd,
    v.gross_production_value_kusd / 1000.0 AS gross_production_value_usd_millions,
    c.yield_kg_ha / 1000.0 AS yield_t_per_ha,

    -- engineered metrics
    (v.gross_production_value_kusd * 1000.0) / NULLIF(c.area_harvested_ha, 0) AS value_per_ha,
    (v.gross_production_value_kusd * 1000.0) / NULLIF(c.production_tonnes, 0) AS value_per_tonne

FROM crops_clean c
JOIN value_clean v
    ON c.country = v.country
   AND c.crop    = v.crop
   AND c.year    = v.year;


CREATE OR REPLACE VIEW v_efficiency AS
SELECT
    c.country,
    c.crop,
    c.year,
    c.area_harvested_ha,
    c.yield_kg_ha,
    c.production_tonnes,
    ROUND(v.gross_production_value_kusd / 1000.0, 2) AS gpv_usd_millions,
    ROUND(
        (v.gross_production_value_kusd * 1000.0) / NULLIF(c.area_harvested_ha, 0),
        2
    ) AS gpv_usd_per_ha
FROM crops_clean c
JOIN value_clean v
    ON c.country = v.country
   AND c.crop    = v.crop
   AND c.year    = v.year;


CREATE OR REPLACE VIEW vw_agri_productivity_drivers AS
SELECT
    b.country,
    b.crop,
    b.year,
    b.value_per_ha,
    b.yield_t_per_ha,
    b.value_per_tonne,

    -- rolling (3-year) to support smoother trends
    AVG(b.value_per_ha) OVER (
        PARTITION BY b.country, b.crop
        ORDER BY b.year
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS value_per_ha_roll3,

    AVG(b.yield_t_per_ha) OVER (
        PARTITION BY b.country, b.crop
        ORDER BY b.year
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS yield_t_per_ha_roll3,

    AVG(b.value_per_tonne) OVER (
        PARTITION BY b.country, b.crop
        ORDER BY b.year
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS value_per_tonne_roll3

FROM vw_agri_base b;


