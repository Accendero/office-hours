-- Silver: typed AND domain-checked.
-- The domain check on borough is not decoration. A thousands separator in an unquoted
-- CSV field shifts every column one position right and still passes type validation --
-- the row arrives fully typed, fully "valid", and completely wrong. Only the domain
-- check catches it. See the plan, section 7.4.
with cleaned as (
  select
    _source, _source_file, _ingested_at, _record_no,
    try_cast(replace(nullif(trim("LocationID"), ''), ',', '') as integer) as location_id,
    nullif(nullif(trim("Borough"), ''), 'N/A')                            as borough,
    nullif(trim("Zone"), '')                                              as zone,
    nullif(nullif(trim("service_zone"), ''), 'NULL')                      as service_zone
  from {{ source('bronze', 'raw_zone_lookup') }}
)
select location_id, borough, zone, service_zone
from cleaned
where location_id is not null
  and zone is not null
  and borough in ('Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island', 'EWR')
