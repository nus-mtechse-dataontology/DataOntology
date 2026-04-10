import pytest
from sqlmodel import SQLModel, create_engine

from dao import *
from entities import *
from entities.aircraft import Aircraft


@pytest.fixture
def in_memory_engine():
    """Return a fresh SQLite in-memory engine with tables created."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def fact_flight_info_dao(in_memory_engine):
    return FactFlightInfoDAO(in_memory_engine)


@pytest.fixture
def accounts_dao(in_memory_engine):
    return AccountsDAO(in_memory_engine)


@pytest.fixture
def aircraft_dao(in_memory_engine):
    return AircraftDAO(in_memory_engine)


@pytest.fixture
def airline_dao(in_memory_engine):
    return AirlineDAO(in_memory_engine)


@pytest.fixture
def airline_coverage_dao(in_memory_engine):
    return AirlineCoverageDAO(in_memory_engine)

@pytest.fixture
def airport_dao(in_memory_engine):
    return AirportDAO(in_memory_engine)


@pytest.fixture
def city_dao(in_memory_engine):
    return CityDAO(in_memory_engine)


@pytest.fixture
def country_dao(in_memory_engine):
    return CountryDAO(in_memory_engine)


@pytest.fixture
def currency_rate_dao(in_memory_engine):
    return CurrencyRateDAO(in_memory_engine)


@pytest.fixture
def registration_dao(in_memory_engine):
    return RegistrationDAO(in_memory_engine)


@pytest.fixture
def populate_fact_flight_info():
    return [
        FactFlightInfo(
            f_flight_combination=70,
            f_departure_airport_code="SIN",
            f_destination_airport_code="BKK",
            f_airline_code="SQ",
            f_currency_code="SGD",
            f_aircraft_code="A350",
            f_departure_date="2026-03-01",
            f_arrival_date="2026-03-01",
            f_cabin_class="J",
            f_trip_type="normal",
            f_num_of_last_seats=9,
            f_flight_duration=180,
            f_total_amount_fare_total=80
        ),
        FactFlightInfo(
            f_flight_combination=71,
            f_departure_airport_code="SIN",
            f_destination_airport_code="BKK",
            f_airline_code="SQ",
            f_currency_code="SGD",
            f_aircraft_code="A350",
            f_departure_date="2026-03-01",
            f_arrival_date="2026-03-01",
            f_cabin_class="J",
            f_trip_type="normal",
            f_num_of_last_seats=9,
            f_flight_duration=180,
            f_total_amount_fare_total=200
        )
    ]

@pytest.fixture
def populate_aircraft():
    return [
        Aircraft(
            f_aircraft_code="A350",
            f_aircraft_model="Airbus"
        )
    ]


@pytest.fixture
def populate_airline():
    return [
        Airline(
            f_airline_code="SQ",
            f_airline_name="Singapore Airlines",
        ),
        Airline(
            f_airline_code="TR",
            f_airline_name="Scoot",
        )
    ]


@pytest.fixture
def populate_airline_coverage():
    return [
        AirlineCoverage(
            f_airport_code="BKK",
            f_airline_code="SQ",
            f_coverage=True
        ),
        AirlineCoverage(
            f_airport_code="BKK",
            f_airline_code="TR",
            f_coverage=True
        ),
        AirlineCoverage(
            f_airport_code="SIN",
            f_airline_code="SQ",
            f_coverage=True
        ),
        AirlineCoverage(
            f_airport_code="SIN",
            f_airline_code="TR",
            f_coverage=True
        )
    ]


@pytest.fixture
def populate_airport():
    return [
        Airport(
            f_airport_code="SIN",
            f_airport_name="Changi",
            f_city_code="SIN"
        ),
        Airport(
            f_airport_code="BKK",
            f_airport_name="Suvarnabhumi Airport",
            f_city_code="BKK"
        )
    ]


@pytest.fixture
def populate_city():
    return [
        City(
            f_city_code="SIN",
            f_city_name="Singapore",
            f_country_code="SG"
        ),
        City(
            f_city_code="BKK",
            f_city_name="Bangkok",
            f_country_code="TH"
        )
    ]


@pytest.fixture
def populate_country():
    return [
        Country(
            f_country_code="SG",
            f_country_name="Singapore"
        ),
        Country(
            f_country_code="TH",
            f_country_name="Thailand"
        )
    ]


@pytest.fixture
def populate_currency_rate():
    return [
        CurrencyRate(
            f_currency_code="SGD",
            f_currency_name="Singapore Dollars",
            f_currency_rate=1
        )
    ]


@pytest.fixture
def populate_db(
        populate_fact_flight_info,
        populate_aircraft,
        populate_airline,
        populate_airline_coverage,
        populate_airport,
        populate_city,
        populate_country,
        populate_currency_rate,
        aircraft_dao,
        airline_dao,
        airline_coverage_dao,
        airport_dao,
        city_dao,
        country_dao,
        currency_rate_dao,
        fact_flight_info_dao,
):
    country_dao.insert_many(populate_country)
    city_dao.insert_many(populate_city)
    airport_dao.insert_many(populate_airport)
    aircraft_dao.insert_many(populate_aircraft)
    airline_dao.insert_many(populate_airline)
    airline_coverage_dao.insert_many(populate_airline_coverage)
    currency_rate_dao.insert_many(populate_currency_rate)
    fact_flight_info_dao.insert_many(populate_fact_flight_info)
    
    yield
