"""Source A + A': TLC Parquet -> bronze.raw_trips.

Both months land in ONE table via DuckDB's union_by_name, which pads the 2024 file's
missing cbd_congestion_fee column with null -- bronze ABSORBS the drift (real schema
drift, not synthetic) and silver resolves it explicitly with coalesce. That is the
whole argument for a bronze layer, made with real publisher data.
"""
import os, sys, glob, datetime
import duckdb

sys.path.insert(0, os.path.dirname(__file__))
from _iceberg import get_catalog, load_table

DATA = os.path.join(os.path.dirname(__file__), "..", "data")

files = sorted(glob.glob(os.path.join(DATA, "yellow_tripdata_*.parquet")))
if not files:
    sys.exit("no TLC parquet in data/ -- run scripts/01_download_data.sh first")

print(f"landing {len(files)} TLC file(s) into bronze.raw_trips")
for f in files:
    print(f"  {os.path.basename(f)}")

con = duckdb.connect()
file_list = ", ".join(f"'{f}'" for f in files)
ts = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)

# Real TLC column casing (VendorID, PULocationID, ...) renamed to the bronze contract's
# lower_snake_case. union_by_name=true reconciles the 2024/2025 shapes; filename=true
# gives per-row provenance without a second pass.
arrow = con.sql(f"""
    SELECT
      VendorID                             AS vendor_id,
      tpep_pickup_datetime,
      tpep_dropoff_datetime,
      passenger_count,
      trip_distance,
      RatecodeID                           AS ratecode_id,
      store_and_fwd_flag,
      PULocationID                         AS pu_location_id,
      DOLocationID                         AS do_location_id,
      payment_type,
      fare_amount,
      extra,
      mta_tax,
      tip_amount,
      tolls_amount,
      improvement_surcharge,
      total_amount,
      congestion_surcharge,
      Airport_fee                          AS airport_fee,
      cbd_congestion_fee,
      'tlc_yellow_trips'                   AS _source,
      regexp_extract(filename, '[^/]+$')   AS _source_file,
      TIMESTAMP '{ts.isoformat(sep=" ")}'   AS _ingested_at,
      row_number() OVER ()                 AS _record_no
    FROM read_parquet([{file_list}], union_by_name = true, filename = true)
""").to_arrow_table()

print(f"  {arrow.num_rows:,} rows total (2024 file's missing cbd_congestion_fee lands as null)")

catalog = get_catalog()
table = load_table(catalog, "bronze", "raw_trips", arrow)
print(f"bronze.raw_trips: {table.scan().to_arrow().num_rows:,} rows now in the table")
