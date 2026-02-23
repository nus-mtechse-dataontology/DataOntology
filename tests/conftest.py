"""Pytest fixtures for testing."""

import sqlite3
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def mock_flight_db():
    """Create an in-memory SQLite database with flight pricing test data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE airport (
            payload_id TEXT,
            airport_code TEXT PRIMARY KEY,
            city_name TEXT,
            country_name TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE search_response (
            payload_id TEXT PRIMARY KEY,
            session_id TEXT,
            currency_code TEXT,
            trip_type TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE flight (
            payload_id TEXT,
            flight_idx INTEGER,
            origin_airport_code TEXT,
            destination_airport_code TEXT,
            departure_date TEXT,
            PRIMARY KEY (payload_id, flight_idx)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE flight_segment (
            payload_id TEXT,
            flight_idx INTEGER,
            segment_idx INTEGER,
            departure_datetime TEXT,
            arrival_datetime TEXT,
            PRIMARY KEY (payload_id, flight_idx, segment_idx)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE flight_leg (
            payload_id TEXT,
            flight_idx INTEGER,
            segment_idx INTEGER,
            leg_idx INTEGER,
            flight_number TEXT,
            PRIMARY KEY (payload_id, flight_idx, segment_idx, leg_idx)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE recommendation (
            payload_id TEXT,
            recommendation_id TEXT PRIMARY KEY,
            fare_total_amount REAL,
            fare_amount_without_tax REAL,
            fare_tax REAL,
            fare_family TEXT
        )
        """
    )

    cursor.execute(
        """
        INSERT INTO airport VALUES
        ('p1', 'SIN', 'Singapore', 'Singapore'),
        ('p1', 'BKK', 'Bangkok', 'Thailand'),
        ('p1', 'KUL', 'Kuala Lumpur', 'Malaysia'),
        ('p1', 'NRT', 'Tokyo', 'Japan')
        """
    )

    cursor.execute(
        """
        INSERT INTO search_response VALUES
        ('p1', 'sess-001', 'SGD', 'R')
        """
    )

    base_date = datetime(2019, 9, 10)
    cursor.execute(
        """
        INSERT INTO flight VALUES
        ('p1', 0, 'SIN', 'BKK', '2019-09-10'),
        ('p1', 1, 'BKK', 'SIN', '2019-09-15')
        """
    )

    cursor.execute(
        """
        INSERT INTO flight_segment VALUES
        ('p1', 0, 0, '2019-09-10T08:00:00Z', '2019-09-10T11:00:00Z'),
        ('p1', 1, 0, '2019-09-15T14:00:00Z', '2019-09-15T17:00:00Z')
        """
    )

    cursor.execute(
        """
        INSERT INTO flight_leg VALUES
        ('p1', 0, 0, 0, 'SQ101'),
        ('p1', 1, 0, 0, 'SQ102')
        """
    )

    cursor.execute(
        """
        INSERT INTO recommendation VALUES
        ('p1', 'rec-001', 450.0, 400.0, 50.0, 'ECONOMY'),
        ('p1', 'rec-002', 480.0, 430.0, 50.0, 'ECONOMY'),
        ('p1', 'rec-003', 520.0, 470.0, 50.0, 'PREMIUM_ECONOMY')
        """
    )

    conn.commit()
    yield conn
    conn.close()
