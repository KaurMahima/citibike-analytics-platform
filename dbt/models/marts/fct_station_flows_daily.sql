select
  cast(started_at as date) as trip_date,
  start_station_id,
  start_station_name,
  avg(start_lat) as start_lat,
  avg(start_lng) as start_lng,
  end_station_id,
  end_station_name,
  avg(end_lat) as end_lat,
  avg(end_lng) as end_lng,
  count(*) as trip_count,
  sum(case when member_casual = 'member' then 1 else 0 end) as member_trips,
  sum(case when member_casual = 'casual' then 1 else 0 end) as casual_trips
from {{ ref('stg_citibike_trips') }}
where start_station_id is not null
  and start_station_name is not null
  and end_station_id is not null
  and end_station_name is not null
  and start_lat is not null
  and start_lng is not null
  and end_lat is not null
  and end_lng is not null
group by 1, 2, 3, 6, 7
order by trip_date, trip_count desc