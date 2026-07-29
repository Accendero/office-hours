-- Values NOAA's own quality control rejected, kept for inspection rather than discarded.
select
  _record_no, station_id, ymd, element, value, q_flag,
  'failed NOAA quality control (q_flag=' || trim(q_flag) || ')' as _reject_reason
from {{ source('bronze', 'raw_ghcn') }}
where nullif(trim(q_flag), '') is not null
