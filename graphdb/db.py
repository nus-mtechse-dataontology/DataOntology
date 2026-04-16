"""
SQLite database — load fact_flight_info.csv once into an in-memory DB per session.
Provides a single get_connection() that returns the shared connection.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from config import FACT_CSV

_conn: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _load()
    return _conn


def _load() -> sqlite3.Connection:
    print(f"  [db] Loading {FACT_CSV.name} into SQLite...")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE fact_flight_info (
            f_flight_combination    TEXT PRIMARY KEY,
            f_departure_airport_code TEXT NOT NULL,
            f_destination_airport_code TEXT NOT NULL,
            f_airline_code          TEXT NOT NULL,
            f_currency_code         TEXT NOT NULL,
            f_aircraft_code         TEXT NOT NULL,
            f_departure_date        TEXT NOT NULL,
            f_arrival_date          TEXT NOT NULL,
            f_cabin_class           TEXT NOT NULL,
            f_trip_type             TEXT NOT NULL,
            f_flight_duration       INTEGER NOT NULL,
            f_total_amount_fare_total REAL NOT NULL
        )
    """)

    with open(FACT_CSV, newline="") as f:
        reader = csv.DictReader(f)
        rows = [
            (
                r["f_flight_combination"],
                r["f_departure_airport_code"],
                r["f_destination_airport_code"],
                r["f_airline_code"],
                r["f_currency_code"],
                r["f_aircraft_code"],
                r["f_departure_date"],
                r["f_arrival_date"],
                r["f_cabin_class"],
                r["f_trip_type"],
                int(r["f_flight_duration"]),
                float(r["f_total_amount_fare_total"]),
            )
            for r in reader
        ]

    conn.executemany(
        "INSERT INTO fact_flight_info VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()

    row_count = conn.execute("SELECT COUNT(*) FROM fact_flight_info").fetchone()[0]
    print(f"  [db] Loaded {row_count:,} rows into fact_flight_info")
    return conn


def execute_sql(sql: str, params: dict) -> list[dict]:
    conn = get_connection()
    cursor = conn.execute(sql, params)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
