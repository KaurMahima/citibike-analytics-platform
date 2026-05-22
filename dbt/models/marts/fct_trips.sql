select 
  ride_id,
  rideable_type,
  started_at,
  ended_at,
  date_trunc('day', started_at) as trip_date,
  datediff('minute', started_at, ended_at) as trip_duration_minutes,
  start_station_id,
  start_station_name,
  end_station_id,
  end_station_name,
  member_casual
from {{ ref('stg_citibike_trips') }}
where ended_at >= started_at

