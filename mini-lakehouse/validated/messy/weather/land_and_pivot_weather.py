"""GHCN-Daily: real, free, one URL -- and awkward in three ways a tutorial can teach.
  1. LONG/NARROW: one row per element per day. Must be PIVOTED to be usable.
  2. SCALED INTEGERS: PRCP and TMAX/TMIN are TENTHS. Skip this and every number is 10x wrong.
  3. QUALITY FLAGS: Q-FLAG non-blank means the value FAILED NOAA's own QC. Must be excluded.
Bronze lands it verbatim, all VARCHAR, exactly like every other source.
"""
import duckdb
con = duckdb.connect("/tmp/weather.duckdb")
con.execute("create schema if not exists bronze; create schema if not exists silver;")

# ---- BRONZE: verbatim, all VARCHAR, no header in the source file ----
con.execute("""
create or replace table bronze.raw_ghcn as
select 'noaa_ghcn_daily' as _source, filename as _source_file,
       now()::timestamp as _ingested_at, row_number() over () as _record_no, *
from read_csv('USW00094728.csv',
  header = false,
  all_varchar = true,
  columns = {'station_id':'VARCHAR','ymd':'VARCHAR','element':'VARCHAR','value':'VARCHAR',
             'm_flag':'VARCHAR','q_flag':'VARCHAR','s_flag':'VARCHAR','obs_time':'VARCHAR'},
  filename = true)
""")
print("bronze.raw_ghcn:", con.sql("select count(*) from bronze.raw_ghcn").fetchone()[0], "element-days")
print("\nelements present, and how many failed NOAA's QC:")
print(con.sql("""select element, count(*) as n,
                 sum(case when nullif(trim(q_flag),'') is not null then 1 else 0 end) as failed_qc
                 from bronze.raw_ghcn group by 1 order by 2 desc""").df().to_string(index=False))

# ---- SILVER: exclude failed QC, then PIVOT, then rescale ----
con.execute("""
create or replace table silver.weather_daily as
with valid as (
  select try_strptime(ymd,'%Y%m%d')::date as obs_date, element,
         try_cast(value as integer) as raw_value
  from bronze.raw_ghcn
  where nullif(trim(q_flag),'') is null        -- (3) drop values NOAA itself flagged
    and try_cast(value as integer) is not null
),
pivoted as (                                   -- (2) long -> wide
  select obs_date,
    max(case when element='TMAX' then raw_value end) as tmax_raw,
    max(case when element='TMIN' then raw_value end) as tmin_raw,
    max(case when element='PRCP' then raw_value end) as prcp_raw,
    max(case when element='SNOW' then raw_value end) as snow_raw,
    max(case when element='AWND' then raw_value end) as awnd_raw
  from valid group by 1
)
select obs_date,
  tmax_raw / 10.0                        as tmax_c,      -- (1) tenths of degrees C
  tmin_raw / 10.0                        as tmin_c,
  coalesce(prcp_raw, 0) / 10.0           as precip_mm,   -- (1) tenths of mm
  coalesce(snow_raw, 0) * 1.0            as snow_mm,     -- already mm: DIFFERENT scale, same file
  awnd_raw / 10.0                        as avg_wind_ms, -- tenths of m/s
  case when coalesce(prcp_raw,0) > 0 then 1 else 0 end as is_wet_day,
  case when coalesce(snow_raw,0) > 0 then 1 else 0 end as is_snow_day
from pivoted order by obs_date
""")
print("\nsilver.weather_daily -- one row per day, ready to join to taxi on date:")
print(con.sql("""select obs_date, tmax_c, tmin_c, precip_mm, snow_mm, avg_wind_ms, is_wet_day, is_snow_day
                 from silver.weather_daily limit 8""").df().to_string(index=False))
print("\ncoverage / sanity:")
print(con.sql("""select count(*) n_days, sum(is_wet_day) wet_days, sum(is_snow_day) snow_days,
   round(min(tmax_c),1) coldest_high, round(max(tmax_c),1) warmest_high,
   round(max(precip_mm),1) wettest_mm,
   sum(case when tmax_c is null then 1 else 0 end) days_missing_tmax
   from silver.weather_daily""").df().to_string(index=False))
con.close()
