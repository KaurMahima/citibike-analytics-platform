# Citi Bike Analytics Platform

Analytics pipeline for Citi Bike trips and NYC weather data using Python, DuckDB, dbt, and Streamlit.

## Overview

This project downloads monthly Citi Bike trip data and NOAA daily weather data, stores curated parquet files in a bronze layer, models analytics tables in DuckDB with dbt, and serves an interactive Streamlit dashboard for trip, station, and flow analysis.

The repository currently supports:

- Citi Bike trip ingestion from the public S3 tripdata bucket
- NOAA weather ingestion for a configured station and date range
- DuckDB-backed dbt staging and mart models
- Daily trip, station, and flow marts
- Hourly station and station-flow marts for dashboard mobility analysis
- A Streamlit dashboard for KPI, map, and movement exploration

## Architecture

The data flow is:

1. Python ingestion scripts download raw Citi Bike ZIP files and NOAA weather API responses.
2. Raw files are converted into parquet files in the bronze layer under `data/bronze/`.
3. dbt reads parquet files as external sources and materializes views and tables into `warehouse/citibike.duckdb`.
4. Streamlit reads the mart tables from DuckDB and renders the dashboard.

## Project Structure

```text
.
|-- app/
|   `-- dashboard.py
|-- config/
|   `-- pipeline_config.yml
|-- data/
|   |-- bronze/
|   `-- raw/
|-- dbt/
|   |-- models/
|   |-- seeds/
|   `-- dbt_project.yml
|-- scripts/
|   |-- download_citibike_data.py
|   `-- download_weather_noaa.py
|-- warehouse/
|   `-- citibike.duckdb
`-- environment.yml
```

## Tech Stack

- Python 3.11
- DuckDB
- dbt-duckdb
- pandas
- pyarrow
- Streamlit
- Altair
- Folium

## Prerequisites

- Conda or another environment manager capable of installing from `environment.yml`
- A dbt profile named `citibike_dbt`
- NOAA API token for weather ingestion

## Setup

Create and activate the environment:

```bash
conda env create -f environment.yml
conda activate citibike-analytics
```

Set the NOAA token before running weather ingestion:

```bash
export NOAA_API_TOKEN="your_token_here"
```

## Configuration

Pipeline settings live in `config/pipeline_config.yml`.

Current configurable items include:

- `date_range.start_date`
- `date_range.end_date`
- Citi Bike base URL
- NOAA base URL
- Weather dataset and station identifiers
- Raw and bronze storage paths

## Running The Pipeline

Run all commands from the repository root unless noted otherwise.

### 1. Download Citi Bike Trips

```bash
python scripts/download_citibike_data.py
```

This downloads monthly ZIP files into `data/raw/` and writes parquet outputs to:

```text
data/bronze/year=YYYY/month=MM/trips.parquet
```

### 2. Download Weather Data

```bash
python scripts/download_weather_noaa.py
```

This writes monthly parquet files to:

```text
data/bronze/weather/year=YYYY/month=MM/daily_weather.parquet
```

### 3. Build dbt Models

Change into the dbt project directory:

```bash
cd dbt
```

Run models:

```bash
dbt run
```

Run tests:

```bash
dbt test
```

Or build everything in one command:

```bash
dbt build
```

## dbt Model Layers

### Staging

- `stg_citibike_trips`
- `stg_weather_daily`

### Marts

- `fct_trips`: trip-level fact table
- `fct_trip_daily`: daily trip aggregates
- `fct_trip_daily_enriched`: daily trip aggregates enriched with weather and holiday context
- `fct_station_daily`: daily station-level activity
- `fct_station_flows_daily`: daily origin-destination flows
- `fct_station_hourly`: hourly station-level activity
- `fct_station_flows_hourly`: hourly origin-destination flows

## DuckDB Output

The analytical warehouse is stored locally at:

```text
warehouse/citibike.duckdb
```

You can inspect it directly with DuckDB:

```bash
duckdb warehouse/citibike.duckdb
```

## Dashboard

The Streamlit dashboard lives in `app/dashboard.py` and reads from the DuckDB warehouse.

Start it from the `app/` directory so the relative database path resolves correctly:

```bash
cd app
streamlit run dashboard.py
```

The dashboard is designed to support:

- Daily trip KPIs
- Member vs casual trip trends
- Weather relationships
- Station activity maps
- Station-to-station flow maps
- Hourly mobility analysis using station and flow marts

## Dagster Orchestration

The project includes a basic Dagster pipeline to orchestrate monthly ingestion and dbt builds.

Dagster currently runs these steps in order:

1. Citi Bike monthly trip ingestion
2. NOAA monthly weather ingestion
3. `dbt build`

The Dagster definitions live in `src/citibike_analytics/dagster_pipeline/definitions.py`.

### Start Dagster Locally

From the repository root:

```bash
conda activate citibike-analytics
export NOAA_API_TOKEN="your_token_here"
dagster dev -m citibike_analytics.dagster_pipeline.definitions
```

This starts the Dagster UI locally so you can launch and monitor pipeline runs.

### Run The Monthly Pipeline

In the Dagster UI, launch `monthly_pipeline_job`.

For manual runs, provide config like:

```yaml
ops:
	run_trip_ingestion_op:
		config:
			year: 2026
			month: 5
			force: false
	run_weather_ingestion_op:
		config:
			year: 2026
			month: 5
			force: false
```

This is useful for reruns and backfills.

### Schedule Behavior

The Dagster schedule is configured to run monthly and defaults to the previous month.

That means:

- routine scheduled runs process the most recently completed month
- manual runs can target specific historical months for backfills

## Important Notes

- Weather ingestion requires `NOAA_API_TOKEN`.
- The ingestion scripts expect to be run from the repository root because they read `config/pipeline_config.yml` with a relative path.
- Dagster must be started from a terminal session where `NOAA_API_TOKEN` is exported.
- The dashboard expects the DuckDB warehouse to already contain the dbt marts.
- dbt materializes staging models as views and marts as tables.

## Suggested Workflow

```bash
conda activate citibike-analytics
export NOAA_API_TOKEN="your_token_here"
python scripts/download_citibike_data.py
python scripts/download_weather_noaa.py
cd dbt
dbt build
cd ../app
streamlit run dashboard.py
```