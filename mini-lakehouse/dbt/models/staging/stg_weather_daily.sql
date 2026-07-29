-- Silver: the three GHCN traps, handled in order.
-- Ported from validated/messy/weather/land_and_pivot_weather.py.
with valid as (
  select
    date_parse(ymd, '%Y%m%d')      as obs_date,
    element,
    try_cast(value as integer)     as raw_value
  from {{ source('bronze', 'raw_ghcn') }}
  -- TRAP 3: Q-FLAG non-blank means NOAA itself failed this value. Exclude it.
  where nullif(trim(q_flag), '') is null
    and try_cast(value as integer) is not null
),
pivoted as (   -- TRAP 1: long/narrow -> wide
  select
    obs_date,
    max(case when element = 'TMAX' then raw_value end) as tmax_raw,
    max(case when element = 'TMIN' then raw_value end) as tmin_raw,
    max(case when element = 'PRCP' then raw_value end) as prcp_raw,
    max(case when element = 'SNOW' then raw_value end) as snow_raw,
    max(case when element = 'AWND' then raw_value end) as awnd_raw
  from valid
  group by obs_date
)
select
  cast(obs_date as date)                          as obs_date,
  -- TRAP 2: scales differ WITHIN THE SAME FILE. Miss this and every number is 10x wrong.
  tmax_raw / 10.0                                 as tmax_c,        -- tenths of degC
  tmin_raw / 10.0                                 as tmin_c,        -- tenths of degC
  coalesce(prcp_raw, 0) / 10.0                    as precip_mm,     -- tenths of mm
  coalesce(snow_raw, 0) * 1.0                     as snow_mm,       -- already mm!
  awnd_raw / 10.0                                 as avg_wind_ms,   -- tenths of m/s
  case when coalesce(prcp_raw, 0) > 0 then 1 else 0 end as is_wet_day,
  case when coalesce(snow_raw, 0) > 0 then 1 else 0 end as is_snow_day
from pivoted
