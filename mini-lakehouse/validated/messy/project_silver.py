"""Silver is where every shape CONVERGES on the same contract: typed, tested, explainable.
The key move is TRY_CAST + a quarantine table -- messy rows are set aside with a reason,
never silently dropped. "Dropped 11%" is only defensible if you can show the 11%.
"""
import duckdb
con = duckdb.connect("/tmp/messy.duckdb")

# ---------- shape 1: delimited text -> typed dimension, with quarantine ----------
con.execute("""
create or replace table silver.zone_lookup_typed as
with cleaned as (
  select _source, _source_file, _ingested_at, _record_no,
         -- strip thousands separators before casting; Excel/locale damage is repairable
         try_cast(replace(nullif(trim("LocationID"), ''), ',', '') as integer) as location_id,
         nullif(nullif(trim("Borough"), ''), 'N/A')      as borough,
         -- repair the cp1252 smart quote that latin-1 decoding surfaced
         replace(nullif(trim("Zone"), ''), chr(146), '''') as zone,
         nullif(nullif(trim(service_zone), ''), 'NULL')  as service_zone
  from bronze.raw_zone_lookup
)
select * from cleaned where location_id is not null and zone is not null
""")
con.execute("""
create or replace table silver.zone_lookup_quarantine as
select *, case
    when try_cast(replace(nullif(trim("LocationID"),''),',','') as integer) is null
         then 'location_id not numeric'
    else 'zone missing' end as _reject_reason
from bronze.raw_zone_lookup
where try_cast(replace(nullif(trim("LocationID"),''),',','') as integer) is null
   or nullif(trim("Zone"),'') is null
""")

# ---------- shape 2: semi-structured log -> typed events, with quarantine ----------
con.execute("""
create or replace table silver.app_events as
select _source, _source_file, _ingested_at, _record_no,
       try_cast(json_extract_string(_raw, '$.ts') as timestamp)   as event_at,
       json_extract_string(_raw, '$.level')                        as level,
       json_extract_string(_raw, '$.svc')                          as service,
       json_extract_string(_raw, '$.msg')                          as message,
       -- trip_id is sometimes int, sometimes string: extract as text, then try_cast
       try_cast(json_extract_string(_raw, '$.trip_id') as bigint)  as trip_id,
       try_cast(json_extract_string(_raw, '$.surge_multiplier') as double) as surge_multiplier,
       try_cast(json_extract_string(_raw, '$.ctx.lat') as double)  as lat,
       try_cast(json_extract_string(_raw, '$.ctx.lon') as double)  as lon
from bronze.raw_app_log
where json_valid(_raw)
""")
con.execute("""
create or replace table silver.app_log_quarantine as
select *, 'not valid json' as _reject_reason from bronze.raw_app_log where not json_valid(_raw)
""")

# ---------- shape 3: free text -> documents. "Cleaning" text means DESCRIBING it. ----------
con.execute("""
create or replace table silver.reviews_docs as
select _source, _source_file, _ingested_at, _record_no,
       try_cast(json_extract_string(_raw, '$.review_id') as bigint) as review_id,
       try_cast(json_extract_string(_raw, '$.trip_id')   as bigint) as trip_id,
       try_cast(json_extract_string(_raw, '$.stars')     as integer) as stars,
       -- three inbound date formats, coalesced. try_strptime returns null, never raises.
       coalesce(
         try_strptime(json_extract_string(_raw,'$.submitted'), '%Y-%m-%d'),
         try_strptime(json_extract_string(_raw,'$.submitted'), '%m/%d/%Y'),
         try_strptime(json_extract_string(_raw,'$.submitted'), '%d-%m-%Y')
       )::date                                                      as submitted_on,
       json_extract_string(_raw, '$.body')                          as body,
       length(json_extract_string(_raw, '$.body'))                  as body_chars,
       array_length(regexp_split_to_array(trim(json_extract_string(_raw,'$.body')), '\\s+')) as body_words
from bronze.raw_reviews
""")

print("=== silver: three shapes, one contract ===")
for t in ["zone_lookup_typed","app_events","reviews_docs"]:
    n = con.sql(f"select count(*) from silver.{t}").fetchone()[0]; print(f"  silver.{t:22} {n:>5,} rows")
print("=== quarantined, with reasons (NOT dropped) ===")
print(con.sql("""
 select 'zone_lookup' src, _reject_reason, count(*) n from silver.zone_lookup_quarantine group by 1,2
 union all
 select 'app_log', _reject_reason, count(*) from silver.app_log_quarantine group by 1,2
""").df().to_string(index=False))
print("\n=== text is described, not cleaned ===")
print(con.sql("""select
  count(*) docs,
  sum(case when body_chars = 0 then 1 else 0 end) empty_docs,
  sum(case when body_chars > 500 then 1 else 0 end) runaway_docs,
  sum(case when stars is null then 1 else 0 end) missing_stars,
  sum(case when submitted_on is null then 1 else 0 end) unparsed_dates,
  max(body_chars) max_chars from silver.reviews_docs""").df().to_string(index=False))
print("\n=== the payoff: the messy CSV now joins to the Parquet fact table ===")
print(con.sql("""select borough, count(*) zones from silver.zone_lookup_typed
                group by 1 order by 2 desc""").df().to_string(index=False))
con.close()
