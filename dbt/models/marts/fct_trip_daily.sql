select 
  trip_date,
  count(*) as total_trips,
  sum(case when member_casual = 'member' then 1 else 0 end) as member_trips,
  sum(case when member_casual = 'casual' then 1 else 0 end) as casual_trips,
  avg(trip_duration_minutes) as avg_trip_duration_minutes
from {{ ref('fct_trips') }}
group by trip_date 
order by trip_date 
