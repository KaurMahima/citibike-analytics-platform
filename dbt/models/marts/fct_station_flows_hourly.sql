select
  cast(started_at as date) as trip_date,
  extract(hour from started_at) as trip_hour,
  case 
   when extract(hour from started_at) between 6 and 9 then 'Morning commute'
   when extract(hour from started_at) between 10 and 15 then 'Midday'
   when extract(hour from started_at) between 16 and 19 then 'Evening commute'
   else 'Night / Early morning'
  end as hour_bucket,
  case 
   when extract(hour from started_at) between 6 and 9 
     or extract(hour from started_at) between 16 and 19
   then true 
   else false 
  end as is_rush_hour,
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
  and end_station_id is not null
  and start_station_id <> end_station_id
  and start_lat is not null
  and start_lng is not null
  and end_lat is not null
  and end_lng is not null
group by 1, 2, 3, 4, 5, 6, 9, 10
order by trip_date, trip_hour, trip_count desc