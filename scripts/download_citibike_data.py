import logging
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
import duckdb
import requests
import yaml 

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

with open("config/pipeline_config.yml", "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

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

def main():
        current = datetime(start_date.year, start_date.month,1)
        while current <= end_date:
                year = current.year
                month = f"{current.month:02d}"

                file_name = f"{year}{month}-citibike-tripdata.zip"
                url = f"{base_url}/{file_name}"
                zip_path = raw_dir/file_name
                parquet_path = bronze_dir/f"year={year}"/f"month={month}"/"trips.parquet"
                download_file(url, zip_path)
                convert_zip_to_parquet(zip_path, parquet_path)

                if current.month == 12:
                        current = datetime(current.year + 1,1,1)
                else:
                        current = datetime(current.year, current.month + 1,1)

if __name__ == "__main__":
        main()