import logging 
import os 
from pathlib import Path
import pandas as pd 
import requests 
from citibike_analytics.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

config = load_config()

base_url = config["noaa_weather"]["base_url"]
start_date = config["date_range"]["start_date"]
end_date = config["date_range"]["end_date"]
dataset_id = config["weather"]["dataset_id"]
station_id = config["weather"]["station_id"]
weather_bronze_dir = Path(config["paths"]["weather_bronze_dir"])

def fetch_noaa_weather(start_date: str, end_date: str) -> list[dict]:
        token = os.getenv("NOAA_API_TOKEN")
        if not token:
               raise ValueError("NOAA_API_TOKEN environment variable is not set")

        headers = {"token": token}
        all_results = []
        limit = 1000
        offset = 1

        while True:
                params = {
                        "datasetid": dataset_id,
                        "stationid": station_id,
                        "startdate": start_date,
                        "enddate": end_date,
                        "units": "metric",
                        "limit": limit,
                        "offset": offset,
                        "datatypeid": ["TMAX", "TMIN", "PRCP", "SNOW", "AWND"],
                }

                logging.info("Fetching NOAA weather data with offset %s", offset)

                response = requests.get(base_url, headers= headers, params=params, timeout=60)
                response.raise_for_status()
                results = response.json().get("results", [])
                if not results:
                       break
                all_results.extend(results)
                if len(results) < limit:
                       break

                offset += limit

        return all_results

def transform_weather_data(results: list[dict]) -> pd.DataFrame:
        if not results:
               raise ValueError("No NOAA weather data returned. Check station ID, date range, or API token.")
        
        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['date']).dt.date

        weather_df = (
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

        weather_df["weather_date"] = pd.to_datetime(weather_df["weather_date"])
        return weather_df

def save_monthly_parquet(weather_df : pd.DataFrame) -> None:
        weather_df["year"] = weather_df["weather_date"].dt.year
        weather_df["month"] = weather_df["weather_date"].dt.month

        for (year,month), month_df in weather_df.groupby(["year", "month"]):
               output_path = (
                      weather_bronze_dir
                      / f"year={year}"
                      / f"month={month:02d}"
                      / f"daily_weather.parquet"
               )
               output_path.parent.mkdir(parents=True, exist_ok=True)
               final_df = month_df.drop(columns=["year", "month"]).copy()
               final_df["weather_date"] = final_df["weather_date"].dt.date
               final_df.to_parquet(output_path, index=False)

        logging.info("Saved NOAA weather data to: %s", output_path)

def main() -> None:
        results = fetch_noaa_weather(start_date=start_date, end_date=end_date)
        weather_df = transform_weather_data(results)
        save_monthly_parquet(weather_df)

if __name__ == "__main__":
       main()