from datetime import datetime
from pathlib import Path

import duckdb 

warehouse_path = "warehouse/citibike.duckdb"

def ensure_pipeline_state_table() -> None:
    Path("warehouse").mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(warehouse_path)
    try:
        conn.execute(
            """
            create table if not exists pipeline_loads (
                pipeline_name varchar,
                year integer,
                month integer,
                output_path varchar,
                status varchar,
                loaded_at timestamp
            )
            """
        )
    finally:
        conn.close()

def load_already_recorded(pipeline_name: str, year: int, month: int) -> bool:
    ensure_pipeline_state_table()

    conn = duckdb.connect(warehouse_path)
    try:
        result = conn.execute(
            """
            select count(*)
            from pipeline_loads
            where pipeline_name = ?
              and year = ?
              and month = ?
              and status = 'success'
            """,
            [pipeline_name, year, month],
        ).fetchone()
    finally:
        conn.close()

    return bool(result and result[0] > 0)


def record_pipeline_load(
    pipeline_name: str,
    year: int,
    month: int,
    output_path: str,
    status: str = "success",
) -> None:
    ensure_pipeline_state_table()

    conn = duckdb.connect(warehouse_path)
    try:
        conn.execute(
            """
            insert into pipeline_loads (
                pipeline_name,
                year,
                month,
                output_path,
                status,
                loaded_at
            )
            values (?, ?, ?, ?, ?, ?)
            """,
            [pipeline_name, year, month, output_path, status, datetime.utcnow()],
        )
    finally:
        conn.close()