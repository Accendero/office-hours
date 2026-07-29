-- Quarantine, don't drop. "We dropped 11% of rows" is only defensible if you can
-- SHOW the 11%. Every exclusion carries a reason and stays inspectable.
with cleaned as (
  select
    _record_no, "LocationID", "Borough", "Zone", "service_zone",
    try_cast(replace(nullif(trim("LocationID"), ''), ',', '') as integer) as location_id,
    nullif(trim("Borough"), '') as borough_c,
    nullif(trim("Zone"), '')    as zone_c
  from {{ source('bronze', 'raw_zone_lookup') }}
)
select
  _record_no, "LocationID", "Borough", "Zone", "service_zone",
  case
    when location_id is null then 'location_id not numeric'
    when zone_c is null      then 'zone missing'
    else 'borough not a known NYC borough (field shift?)'
  end as _reject_reason
from cleaned
where location_id is null
   or zone_c is null
   or borough_c not in ('Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island', 'EWR')
