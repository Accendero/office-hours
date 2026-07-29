"""The highest-value five minutes in the tutorial.

TWO THINGS ARE DELIBERATE HERE, both learned the hard way:

1. The corrupt data ARRIVES FROM UPSTREAM as a new file. Writing to the bronze TABLE
   instead gets erased on the next pipeline run -- the gate stays open and the demo
   silently fails. Bad data arrives as files, so corrupt a file.

2. The defect is chosen to PASS EVERY SILVER FILTER. A 12x tip on a plausible fare
   survives every WHERE clause in stg_trips and is caught only by the tip_rate bound
   in the gate. Demonstrating a gate on a defect the filters already remove teaches
   nothing about why the gate exists.
"""
import os, sys, glob, duckdb

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
src = sorted(glob.glob(os.path.join(DATA, "yellow_tripdata_2025-*.parquet")))
src = [f for f in src if "CORRUPT" not in f]
if not src:
    sys.exit("no clean TLC parquet found -- run scripts/01_download_data.sh")
out = os.path.join(DATA, "yellow_tripdata_2025-01-CORRUPT.parquet")

duckdb.connect().execute(f"""
COPY (
  SELECT * REPLACE (fare_amount * 12 AS tip_amount)
  FROM read_parquet('{src[0]}')
  WHERE fare_amount > 5 AND trip_distance BETWEEN 1 AND 5
  LIMIT 900
) TO '{out}' (FORMAT parquet)
""")
print(f"landed {os.path.basename(out)}: 900 rows, tip_amount = 12x fare")
print("passes every silver filter. Now: make bronze && make silver-gold && make gate")
print("expected: the tip_rate test FAILS and promotion halts.")
