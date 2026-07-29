import duckdb, pathlib
from shim import to_duckdb
con = duckdb.connect("/tmp/proto.duckdb")
RAW = "data/yellow_tripdata_2025-01*.parquet"   # glob: picks up anything landed in raw/

con.execute("create schema if not exists bronze; create schema if not exists silver; create schema if not exists gold;")
con.execute(f"create or replace table bronze.raw_trips as select * from read_parquet('{RAW}')")

def load(p, **sub):
    s = pathlib.Path(p).read_text()
    for k,v in sub.items(): s = s.replace("{{%s}}" % k, v)
    return to_duckdb(s)

con.execute("create or replace table silver.stg_trips as " + load("sql/stg_trips.sql", BRONZE="bronze.raw_trips"))
con.execute("create or replace table gold.fct_trips as "  + load("sql/fct_trips.sql",  SILVER="silver.stg_trips"))

b = con.sql("select count(*) from bronze.raw_trips").fetchone()[0]
s = con.sql("select count(*) from silver.stg_trips").fetchone()[0]
g = con.sql("select count(*) from gold.fct_trips").fetchone()[0]
print(f"bronze {b:,}  ->  silver {s:,}  ->  gold {g:,}   (dropped {b-s:,} = {100*(b-s)/b:.2f}%)")

print("\n-- what bronze actually contains (the 'why we filter' slide) --")
print(con.sql("""
select 'negative fare'      as defect, count(*) from bronze.raw_trips where fare_amount <= 0
union all select 'dropoff before pickup', count(*) from bronze.raw_trips where tpep_dropoff_datetime < tpep_pickup_datetime
union all select 'zero distance',         count(*) from bronze.raw_trips where trip_distance = 0
union all select 'distance > 100mi',      count(*) from bronze.raw_trips where trip_distance > 100
union all select 'passenger_count = 0',   count(*) from bronze.raw_trips where passenger_count = 0
union all select 'passenger_count null',  count(*) from bronze.raw_trips where passenger_count is null
union all select 'pickup outside month',  count(*) from bronze.raw_trips where tpep_pickup_datetime < timestamp '2025-01-01' or tpep_pickup_datetime >= timestamp '2025-02-01'
order by 2 desc
""").df().to_string(index=False))

print("\n-- gold sanity --")
print(con.sql("""select count(*) as n_rows, round(avg(trip_duration_min),2) avg_min,
 round(avg(avg_speed_mph),2) avg_mph, round(avg(tip_rate),4) avg_tip_rate,
 min(pickup_at) min_pickup, max(pickup_at) max_pickup from gold.fct_trips""").df().to_string(index=False))
con.close()
