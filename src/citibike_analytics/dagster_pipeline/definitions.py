from datetime import datetime, timezone 

from dagster import(
        Definitions,
        In,
        Nothing, 
        OpExecutionContext,
        ScheduleDefinition,
        job,
        op
)
import subprocess

def run_command(command: list[str], cwd: str | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, check=False, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}")

@op(config_schema={"year":int, "month":int, "force": bool})
def run_trip_ingestion_op(context: OpExecutionContext) -> None:
    year = context.op_config["year"]
    month = context.op_config["month"]
    force = context.op_config["force"]

    command = [
        "python",
        "scripts/download_citibike_data.py",
        "--year",
        str(year),
        "--month",
        str(month),
    ]

    if force:
        command.append("--force")

    context.log.info("Running Citi Bike ingestion for %s-%02d", year, month)
    run_command(command, cwd=".")


@op(ins={"start": In(Nothing)}, config_schema={"year": int, "month": int, "force": bool})
def run_weather_ingestion_op(context: OpExecutionContext) -> None:
    year = context.op_config["year"]
    month = context.op_config["month"]
    force = context.op_config["force"]

    command = [
        "python",
        "scripts/download_weather_noaa.py",
        "--year",
        str(year),
        "--month",
        str(month),
    ]

    if force:
        command.append("--force")

    context.log.info("Running NOAA weather ingestion for %s-%02d", year, month)
    run_command(command, cwd=".")

@op(ins={"start": In(Nothing)})
def run_dbt_build_op(context: OpExecutionContext) -> None:
    context.log.info("Running dbt build")
    run_command(["dbt", "build"], cwd="dbt")

@job
def monthly_pipeline_job():
        trip = run_trip_ingestion_op()
        weather = run_weather_ingestion_op(start=trip)
        run_dbt_build_op(start=weather)

def previous_month_config() -> dict:
    now = datetime.now(timezone.utc)
    year = now.year
    month = now.month - 1
    if month ==0:
        year -= 1
        month = 12 

    return {
        "ops": {
            "run_trip_ingestion_op": {
                "config": {
                    "year": year,
                    "month": month,
                    "force": False,
                }
            },
            "run_weather_ingestion_op": {
                "config": {
                    "year": year,
                    "month": month,
                    "force": False,
                }
            },
        }
    }

monthly_pipeline_schedule = ScheduleDefinition(
    job=monthly_pipeline_job,
    cron_schedule="0 6 5 * *",
    execution_fn=lambda _context: previous_month_config(),
)

defs = Definitions(
    jobs=[monthly_pipeline_job],
    schedules=[monthly_pipeline_schedule],
)