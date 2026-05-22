import argparse
import logging
import zipfile
import tempfile
from pathlib import Path
import duckdb
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

base_url = "https://s3.amazonaws.com/tripdata"

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

def convert_zip_to_parquet(zip_path:Path, parquet_path: Path) -> None:
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        
        logging.info("Converting ZIP to parquet: %s", zip_path)

        with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_dir = Path(tmp_dir)

                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(tmp_dir)

                        csv_files = list(tmp_dir.glob("*.csv"))

                        csv_path = csv_files[0]

                        conn = duckdb.connect()

                        conn.execute(f"""
                                     COPY (SELECT *
                                     FROM read_csv_auto('{csv_path}')
                                     )
                                     TO '{parquet_path}'
                                     (FORMAT PARQUET);
                                     """)
                        
                        conn.close()


def main():
        year = 2026
        month = "01"
        file_name = f"{year}{month}-citibike-tripdata.zip"
        url = f"{base_url}/{file_name}"
        zip_path = Path("data/raw")/file_name
        parquet_path = (Path("data/bronze")/f"year={year}"/f"month={month}"/"trips.parquet")
        download_file(url, zip_path)
        convert_zip_to_parquet(zip_path, parquet_path)

if __name__ == "__main__":
        main()