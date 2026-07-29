"""ONE landing pattern, three source shapes.

Bronze's contract is not a file format. It is three properties:
  1. arrival fidelity  -- the original payload is recoverable, so replay is possible
  2. provenance        -- identical columns on EVERY bronze table, whatever the shape
  3. no business logic -- nothing that can fail: no casts, no filters, no joins

Note every loader below lands text as VARCHAR. That is the whole trick: a cast that
fails in bronze loses data you cannot get back. Casting is silver's job.
"""
import duckdb, datetime

PROV = """
  '{src}'                      as _source,
  '{path}'                     as _source_file,
  timestamp '{ts}'             as _ingested_at,
"""
ts = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0).isoformat(sep=' ')
con = duckdb.connect("/tmp/messy.duckdb")
con.execute("create schema if not exists bronze; create schema if not exists silver;")

# --- shape 1: delimited text. Read EVERY column as VARCHAR; do not let the parser guess. ---
con.execute(f"""
create or replace table bronze.raw_zone_lookup as
select
  {PROV.format(src='tlc_zone_lookup', path='raw/taxi_zone_lookup.csv', ts=ts)}
  filename                     as _file,
  row_number() over ()         as _record_no,
  *
from read_csv('raw/taxi_zone_lookup.csv',
  all_varchar = true,          -- no type inference: nothing can fail
  header = true,
  ignore_errors = true,        -- ragged rows land in a reject path rather than killing the load
  null_padding = true,
  parallel = false,          -- quoted newlines force a serial scan: CSV cannot be split safely
  filename = true,
  encoding = 'latin-1')        -- cp1252 bytes would otherwise raise on utf-8 decode
""")

# --- shape 2: append-only semi-structured log. Land the RAW LINE, parse in silver. ---
con.execute(f"""
create or replace table bronze.raw_app_log as
select
  {PROV.format(src='app_log', path='raw/app-2025-01.jsonl', ts=ts)}
  filename                     as _file,
  row_number() over ()         as _record_no,
  line                         as _raw            -- verbatim; corrupt lines included
from read_csv('raw/app-2025-01.jsonl',
  columns = {{'line': 'VARCHAR'}},                  -- one VARCHAR column = "give me the line"
  delim = '\\x07', quote = '', escape = '',
  header = false, filename = true)
""")

# --- shape 3: free text documents. The row IS the payload. ---
con.execute(f"""
create or replace table bronze.raw_reviews as
select
  {PROV.format(src='reviews', path='raw/reviews-2025-01.json', ts=ts)}
  filename                     as _file,
  row_number() over ()         as _record_no,
  to_json(j)                   as _raw            -- whole document kept, not just parsed fields
from read_json('raw/reviews-2025-01.json', format='array', records=false,
                columns={{'j':'JSON'}}, filename=true)
""")

for t in ["raw_zone_lookup", "raw_app_log", "raw_reviews"]:
    n = con.sql(f"select count(*) from bronze.{t}").fetchone()[0]
    cols = [c for c in con.sql(f"select * from bronze.{t} limit 0").columns if c.startswith('_')]
    print(f"bronze.{t:18} {n:>6,} rows   provenance: {', '.join(cols)}")
con.close()
