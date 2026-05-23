select 
  t.trip_date,
  t.total_trips,
  t.member_trips,
  t.casual_trips,
  t.avg_trip_duration_minutes,
  w.temperature_max_c,
  w.temperature_min_c,
  w.precipitation_mm,
  w.snowfall_mm,
  w.avg_wind_speed_mps,
  coalesce(h.is_holiday, false) as is_holiday,
  h.holiday_name,
  extract(month from t.trip_date) as month_number, 
  strftime(t.trip_date, '%B') as month_name, 
  strftime(t.trip_date, '%A') as day_name, 
  case 
        when strftime(t.trip_date, '%w') in ('0', '6') then true
        else false 
   end as is_weekend, 
   case 
        when extract(month from t.trip_date) in (12,1,2) then 'Winter'
        when extract(month from t.trip_date) in (3,4,5) then 'Spring'
        when extract(month from t.trip_date) in (6,7,8) then 'Summer'
        else 'Fall'
   end as season 
from {{ ref('fct_trip_daily' )}} t 
left join {{ ref('stg_weather_daily') }} w 
        on t.trip_date = w.weather_date
left join {{ ref('holiday_calendar' )}} h 
        on t.trip_date = h.holiday_date
order by t.trip_date 

