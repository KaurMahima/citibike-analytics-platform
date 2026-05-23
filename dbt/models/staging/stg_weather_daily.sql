select 
  cast(weather_date as date) as weather_date,
  cast(temperature_max_c as double) as temperature_max_c,
  cast(temperature_min_c as double) as temperature_min_c,
  cast(precipitation_mm as double) as precipitation_mm,
  cast(snowfall_mm as double) as snowfall_mm,
  cast(avg_wind_speed_mps as double) as avg_wind_speed_mps
from {{ source('weather_raw', 'daily_weather')}}