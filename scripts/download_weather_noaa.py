import argparse
import logging 
import os 
from pathlib import Path
import duckdb 
import pandas as pd 
import requests 


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

noaa_base_url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"
dataset_id = "GHCND"

station_id = 'GHCND:USW00094728'

def fetch_noaa_weather(start_date: str, end_date: str) -> list[dict]:
        token = os.getenv("NOAA_API_TOKEN")
        if not token:
               raise ValueError("NOAA_API_TOKEN environment variable is not set")

        headers = {"token": token}
        params = {
                "datasetid": dataset_id,
                "stationid": station_id,
                "startdate": start_date,
                "enddate": end_date,
                "units": "metric",
                "limit": 1000,
                 "datatypeid": ["TMAX", "TMIN", "PRCP", "SNOW", "AWND"],
        }

        logging.info("Fetching NOAA weather data for %s to %s", start_date, end_date)

        response = requests.get(noaa_base_url, headers= headers, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        return payload.get("results", [])

def transform_weather_data(results: list[dict]) -> pd.DataFrame:
        if not results:
               raise ValueError("No NOAA weather data returned. Check station ID, date range, or API token.")
        
        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['date']).dt.date

        pivot_df = (
                df.pivot_table(
                        index="date",
                        columns="datatype",
                        values="value",
                        aggfunc="first",
                )
                .reset_index()
                .rename(
                        columns={
                             "date": "weather_date",
                             "TMAX": "temperature_max_c",
                             "TMIN": "temperature_min_c",
                             "PRCP": "precipitation_mm",
                             "SNOW": "snowfall_mm",
                             "AWND": "avg_wind_speed_mps",    
                        }
                )
        )

        return pivot_df 

def save_to_parquet(df : pd.DataFrame, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect()
        conn.register("weather_df", df)
        conn.execute(f"""
                     COPY weather_df
                     to '{output_path}'
                     (FORMAT PARQUET)
                     """)
        conn.close()

        logging.info("Saved NOAA weather data to: %s", output_path)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download NOAA daily weather data")
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD format")
    return parser.parse_args()

def main() -> None:
       args = parse_args()
       results = fetch_noaa_weather(
              start_date= args.start_date,
              end_date=args.end_date
       )
       weather_df = transform_weather_data(results)

       output_path = Path("data/bronze/weather/daily_weather.parquet")
       save_to_parquet(weather_df, output_path)

if __name__ == "__main__":
       main()