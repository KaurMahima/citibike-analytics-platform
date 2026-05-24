import logging
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
import duckdb
import requests
import argparse
from citibike_analytics.config import load_config
from citibike_analytics.state import load_already_recorded, record_pipeline_load

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

config = load_config()

start_date = datetime.strptime(config["date_range"]["start_date"], "%Y-%m-%d")
end_date = datetime.strptime(config["date_range"]["end_date"], "%Y-%m-%d")
base_url = config["citibike"]["base_url"]
raw_dir = Path(config["paths"]["raw_data_dir"])
bronze_dir = Path(config["paths"]["bronze_data_dir"])

def download_file(url:str, output_path:Path)-> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        logging.info("Downloading: %s", url)
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                                f.write(chunk)

                logging.info("Saved file to: %s", output_path)

def convert_zip_to_parquet(zip_path: Path, parquet_path: Path) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    logging.info("Converting ZIP to parquet: %s", zip_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmp_path)

        csv_pattern = (tmp_path / "**" / "*.csv").as_posix()

        conn = duckdb.connect()
        conn.execute(f"""
            COPY (
                SELECT *
                FROM read_csv_auto(
                    '{csv_pattern}',
                    union_by_name=true,
                    types={{
                        'ride_id': 'VARCHAR',
                        'rideable_type': 'VARCHAR',
                        'started_at': 'TIMESTAMP',
                        'ended_at': 'TIMESTAMP',
                        'start_station_name': 'VARCHAR',
                        'start_station_id': 'VARCHAR',
                        'end_station_name': 'VARCHAR',
                        'end_station_id': 'VARCHAR',
                        'start_lat': 'DOUBLE',
                        'start_lng': 'DOUBLE',
                        'end_lat': 'DOUBLE',
                        'end_lng': 'DOUBLE',
                        'member_casual': 'VARCHAR'
                    }}
                )
            )
            TO '{parquet_path.as_posix()}'
            (FORMAT PARQUET);
        """)
        conn.close()

    logging.info("Saved parquet to: %s", parquet_path)

def run_month(year: int, month: int, force: bool = False) -> None:
    file_name = f"{year}{month:02d}-citibike-tripdata.zip"
    url = f"{base_url}/{file_name}"
    zip_path = raw_dir / file_name
    parquet_path = bronze_dir / f"year={year}" / f"month={month:02d}" / "trips.parquet"

    if parquet_path.exists() and not force:
        logging.info("Skipping month %s-%02d because parquet already exists", year, month)
        return

    if load_already_recorded("citibike_trips", year, month) and not force:
        logging.info("Skipping month %s-%02d because it is already recorded as loaded", year, month)
        return

    download_file(url, zip_path)
    convert_zip_to_parquet(zip_path, parquet_path)
    record_pipeline_load(
        pipeline_name="citibike_trips",
        year=year,
        month=month,
        output_path=parquet_path.as_posix(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Citi Bike data for one month")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    run_month(year=args.year, month=args.month, force=args.force)


if __name__ == "__main__":
    main()