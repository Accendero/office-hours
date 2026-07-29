-- Gold: model-ready fact table. Derived features computed once, here.
-- NOTE: Trino cannot reference a select alias in WHERE, hence the outer select.
--       This bit DuckDB-validated SQL once already -- see validated/shim.py.
-- Rows failing the physical-plausibility guard or the tip_rate bound are
-- quarantined, not dropped -- see models/marts/quarantine/qtn_trips.sql.
select * from (
  select
    t.vendor_id, t.pickup_at, t.dropoff_at,
    t.pickup_location_id, t.dropoff_location_id, t.payment_type,
    t.passenger_count, t.trip_distance_mi, t.trip_duration_s,
    t.fare_amount, t.tip_amount, t.total_amount,
    round(t.trip_duration_s / 60.0, 2)                            as trip_duration_min,
    round(t.trip_distance_mi / (t.trip_duration_s / 3600.0), 2)   as avg_speed_mph,
    round(t.tip_amount / nullif(t.fare_amount, 0), 4)             as tip_rate,
    hour(t.pickup_at)                                             as pickup_hour,
    day_of_week(t.pickup_at)                                      as pickup_dow,
    case when day_of_week(t.pickup_at) in (6, 7) then 1 else 0 end as is_weekend,
    -- source C: borough names
    pu.borough                                                    as pickup_borough,
    dz.borough                                                    as dropoff_borough,
    -- source B: weather. Whether these features EARN their place is the open
    -- experiment -- run `make lift`. Keep only if MAE improves by >= 2%.
    w.precip_mm, w.snow_mm, w.tmax_c, w.avg_wind_ms, w.is_wet_day, w.is_snow_day
  from {{ ref('stg_trips') }} t
  left join {{ ref('stg_zone_lookup') }} pu on t.pickup_location_id  = pu.location_id
  left join {{ ref('stg_zone_lookup') }} dz on t.dropoff_location_id = dz.location_id
  left join {{ ref('stg_weather_daily') }} w on cast(t.pickup_at as date) = w.obs_date
) x
where avg_speed_mph > 0 and avg_speed_mph < 80
  and tip_rate >= 0 and tip_rate <= 3
