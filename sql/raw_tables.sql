CREATE TABLE IF NOT EXISTS raw_crops (
  id                serial primary key,
  domain_code       text,
  domain            text,
  area_code         text,
  area              text,
  element_code      text,
  element           text,
  item_code         text,
  item              text,
  year_code         text,
  year              int,
  unit              text,
  value             text,
  flag              text,
  flag_description  text,
  note              text
);

CREATE TABLE IF NOT EXISTS raw_production_value (
  id                serial primary key,
  domain_code       text,
  domain            text,
  area_code         text,
  area              text,
  element_code      text,
  element           text,
  item_code         text,
  item              text,
  year_code         text,
  year              int,
  unit              text,
  value             text,
  flag              text,
  flag_description  text
);