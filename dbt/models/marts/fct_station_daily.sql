select 
  cast(started_at as date) as trip_date,
  start_station_id as station_id, 
  start_station_name as station_name,
  avg(start_lat) as lat,
  avg(start_lng) as lon,
  count(*) as trip_count,
  sum(Case when member_casual = 'member' then 1 else 0 end) as member_trips,
  sum(Case when member_casual = 'casual' then 1 else 0 end) as casual_trips
from {{ ref('stg_citibike_trips') }}
where start_station_id is not null
  and start_station_name is not null
  and start_lat is not null
  and start_lng is not null
group by 1, 2, 3
order by trip_date, trip_count desc
  
