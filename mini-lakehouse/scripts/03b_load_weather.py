"""Source B: NOAA GHCN-Daily -> bronze.raw_ghcn.

HEADERLESS, LONG/NARROW: one row per element per day.
  ID, YYYYMMDD, ELEMENT, VALUE, M-FLAG, Q-FLAG, S-FLAG, OBS-TIME

Everything lands as VARCHAR. Three traps deliberately left for silver:
  1. long/narrow -- must be pivoted
  2. scaled integers, INCONSISTENTLY: PRCP and TMAX/TMIN are tenths, SNOW is plain mm
  3. Q-FLAG non-blank means NOAA itself failed the value -- must be excluded

Also filters to the canonical window here, so the warehouse is insensitive to how large
NOAA's period-of-record file grows.
"""
import os, sys, duckdb

sys.path.insert(0, os.path.dirname(__file__))
from _iceberg import get_catalog, load_table

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
SRC = os.path.join(DATA, "USW00094728.csv")
YEARS = os.getenv("GHCN_YEARS", "2024,2025").split(",")

if not os.path.exists(SRC):
    sys.exit("missing data/USW00094728.csv -- run scripts/01_download_data.sh first")
print(f"source file: {os.path.getsize(SRC)/1e6:.1f} MB  (printed, not assumed)")

con = duckdb.connect()
years = ",".join(f"'{y.strip()}'" for y in YEARS)
arrow = con.sql(f"""
  SELECT
    'noaa_ghcn_daily'        AS _source,
    'USW00094728.csv'        AS _source_file,
    now()::timestamp         AS _ingested_at,
    row_number() OVER ()     AS _record_no,
    *
  FROM read_csv('{SRC}',
    header = false, all_varchar = true,
    columns = {{'station_id':'VARCHAR','ymd':'VARCHAR','element':'VARCHAR','value':'VARCHAR',
                'm_flag':'VARCHAR','q_flag':'VARCHAR','s_flag':'VARCHAR','obs_time':'VARCHAR'}})
  WHERE substr(ymd, 1, 4) IN ({years})
""").to_arrow_table()

catalog = get_catalog()
table = load_table(catalog, "bronze", "raw_ghcn", arrow)
n = table.scan().to_arrow().num_rows
print(f"staged {arrow.num_rows:,} element-days for years {YEARS} -> bronze.raw_ghcn ({n:,} rows now in table)")
print(con.sql("""SELECT element, count(*) AS n,
  sum(CASE WHEN nullif(trim(q_flag),'') IS NOT NULL THEN 1 ELSE 0 END) AS failed_qc
  FROM arrow GROUP BY 1 ORDER BY 2 DESC""").df().to_string(index=False))
con.close()
