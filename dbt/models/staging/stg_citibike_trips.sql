select 
   ride_id, 
   rideable_type,
   cast(started_at as timestamp) as started_at,
   cast(ended_at as timestamp) as ended_at,
   start_station_id,
   start_station_name,
   end_station_id,
   end_station_name,
   start_lat,
   start_lng,
   end_lat,
   end_lng,
   member_casual
from {{ source('citibike_raw', 'trips') }}
