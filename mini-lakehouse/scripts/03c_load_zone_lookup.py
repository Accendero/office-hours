"""Source C: TLC taxi zone lookup -> bronze.raw_zone_lookup.

ALL columns VARCHAR. A cast that fails in bronze destroys data you cannot re-fetch.
parallel=false because quoted newlines make a CSV non-splittable -- this is true of
Trino and Spark too, not a DuckDB quirk.
"""
import os, sys, duckdb

sys.path.insert(0, os.path.dirname(__file__))
from _iceberg import get_catalog, load_table

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
SRC = os.path.join(DATA, "taxi_zone_lookup.csv")
if not os.path.exists(SRC):
    sys.exit("missing data/taxi_zone_lookup.csv -- run scripts/01_download_data.sh first")

con = duckdb.connect()
# Column names land exactly as the CSV header has them (LocationID, Borough, Zone,
# service_zone) -- stg_zone_lookup.sql quotes them to match this casing precisely.
arrow = con.sql(f"""
  SELECT 'tlc_zone_lookup' AS _source, 'taxi_zone_lookup.csv' AS _source_file,
         now()::timestamp AS _ingested_at, row_number() OVER () AS _record_no, *
  FROM read_csv('{SRC}',
    header = true, all_varchar = true, ignore_errors = true,
    null_padding = true, parallel = false, encoding = 'latin-1')
""").to_arrow_table()

catalog = get_catalog()
table = load_table(catalog, "bronze", "raw_zone_lookup", arrow)
n = table.scan().to_arrow().num_rows
print(f"staged {arrow.num_rows:,} zone rows -> bronze.raw_zone_lookup ({n:,} rows now in table)")
con.close()
