-- TRINO DIALECT (dbt model: models/marts/fct_trips.sql)
-- gold: model-ready fact table. Derived features computed once, here.
-- NOTE: Trino cannot reference a select alias in WHERE, hence the outer select.
select * from (
  select
    vendor_id, pickup_at, dropoff_at,
    pickup_location_id, dropoff_location_id, payment_type,
    passenger_count, trip_distance_mi, trip_duration_s,
    fare_amount, tip_amount, total_amount,
    round(trip_duration_s / 60.0, 2)                        as trip_duration_min,
    round(trip_distance_mi / (trip_duration_s / 3600.0), 2) as avg_speed_mph,
    round(tip_amount / nullif(fare_amount, 0), 4)           as tip_rate,
    hour(pickup_at)                                         as pickup_hour,
    day_of_week(pickup_at)                                  as pickup_dow,
    case when day_of_week(pickup_at) in (6,7) then 1 else 0 end as is_weekend
  from {{SILVER}}
) t
where avg_speed_mph < 80
