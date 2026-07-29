-- Quarantine, don't drop. Trips failing the physical-plausibility guard
-- (avg_speed_mph) or the tip_rate bound -- real, rare outliers already present
-- in real data (e.g. a $3 fare with a $126 tip), not only the defect
-- 07_break_the_data.py injects. See fct_trips.sql.
with enriched as (
  select
    t.vendor_id, t.pickup_at, t.dropoff_at, t.pickup_location_id, t.dropoff_location_id,
    t.trip_distance_mi, t.trip_duration_s, t.fare_amount, t.tip_amount, t.total_amount,
    round(t.trip_distance_mi / (t.trip_duration_s / 3600.0), 2)   as avg_speed_mph,
    round(t.tip_amount / nullif(t.fare_amount, 0), 4)             as tip_rate
  from {{ ref('stg_trips') }} t
)
select
  vendor_id, pickup_at, dropoff_at, pickup_location_id, dropoff_location_id,
  trip_distance_mi, trip_duration_s, fare_amount, tip_amount, total_amount,
  avg_speed_mph, tip_rate,
  case
    when not (avg_speed_mph > 0 and avg_speed_mph < 80)
      then 'avg_speed_mph outside (0, 80) -- physically implausible'
    else 'tip_rate outside [0, 3] -- tip more than 3x the fare'
  end as _reject_reason
from enriched
where not (avg_speed_mph > 0 and avg_speed_mph < 80)
   or not (tip_rate >= 0 and tip_rate <= 3)
