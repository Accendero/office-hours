-- TRINO DIALECT (dbt model: models/staging/stg_trips.sql)
-- silver: typed, filtered, deduped. Every predicate maps to a defect class an
-- attendee can count in bronze first. Nothing is dropped without a visible reason.
with renamed as (
  select
    cast("VendorID"            as integer)   as vendor_id,
    cast(tpep_pickup_datetime  as timestamp) as pickup_at,
    cast(tpep_dropoff_datetime as timestamp) as dropoff_at,
    cast(passenger_count       as integer)   as passenger_count,
    cast(trip_distance         as double)    as trip_distance_mi,
    cast("PULocationID"        as integer)   as pickup_location_id,
    cast("DOLocationID"        as integer)   as dropoff_location_id,
    cast(payment_type          as integer)   as payment_type,
    cast(fare_amount           as double)    as fare_amount,
    cast(tip_amount            as double)    as tip_amount,
    cast(total_amount          as double)    as total_amount,
    date_diff('second', cast(tpep_pickup_datetime as timestamp),
                        cast(tpep_dropoff_datetime as timestamp)) as trip_duration_s
  from {{BRONZE}}
),
ranked as (
  select renamed.*, row_number() over (
      partition by vendor_id, pickup_at, dropoff_at, pickup_location_id,
                   dropoff_location_id, total_amount
      order by pickup_at
    ) as rn
  from renamed
)
select
  vendor_id, pickup_at, dropoff_at, passenger_count, trip_distance_mi,
  pickup_location_id, dropoff_location_id, payment_type,
  fare_amount, tip_amount, total_amount, trip_duration_s
from ranked
where rn = 1
  and trip_duration_s between 60 and 10800
  and trip_distance_mi > 0 and trip_distance_mi < 100
  and fare_amount > 0 and total_amount > 0
  and passenger_count between 1 and 6
  and pickup_at >= timestamp '2025-01-01'
  and pickup_at <  timestamp '2025-02-01'
