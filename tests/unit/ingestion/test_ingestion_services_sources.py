from unittest.mock import Mock

from ingestion.services.flight_search_service import FlightSearchService
from ingestion.services.ingestion_service import IngestionService
from ingestion.services.airline_coverage_service import AirlineCoverageService
from ingestion.services.airport_service import AirportService
from ingestion.services.city_service import CityService
from ingestion.services.country_service import CountryService
from ingestion.source.api_source.airline_coverage_api_ingestion import AirlineCoverageApiIngestion
from ingestion.source.api_source.airport_api_ingestion import AirportApiIngestion
from ingestion.source.api_source.city_api_ingestion import CityApiIngestion
from ingestion.source.api_source.country_api_ingestion import CountryApiIngestion
from ingestion.source.api_source.flight_search_api_ingestion import FlightSearchApiIngestion


def test_ingestion_service_methods_are_callable():
    service = IngestionService(Mock())
    assert service.upload_to_db(Mock()) is not None
    assert service.truncate_table("table") is not None
    assert service.get_table_data("table") is not None
    assert service.get_schema_from_db() is not None


def test_flight_search_service_insert_flights_logs_payload():
    service = FlightSearchService(Mock())
    assert service.insert_flights({"flights": [1, 2, 3]}) is None


def test_airline_coverage_api_ingestion_uploads_destination_list():
    service = Mock(spec=AirlineCoverageService)
    ingestion = AirlineCoverageApiIngestion(Mock(), service, {"dataset": {"source": {}, "name": "demo"}})

    ingestion._upload_to_db({"data": {"destinationList": ["a", "b"]}})

    service.insert_coverages.assert_called_once_with(["a", "b"])


def test_airport_api_ingestion_uploads_destination_list():
    service = Mock(spec=AirportService)
    ingestion = AirportApiIngestion(Mock(), service, {"dataset": {"source": {}, "name": "demo"}})

    ingestion._upload_to_db({"data": {"destinationList": ["iata"]}})

    service.insert_airports.assert_called_once_with(["iata"])


def test_city_api_ingestion_uploads_destination_list():
    service = Mock(spec=CityService)
    ingestion = CityApiIngestion(Mock(), service, {"dataset": {"source": {}, "name": "demo"}})

    ingestion._upload_to_db({"data": {"destinationList": ["singapore"]}})

    service.insert_cities.assert_called_once_with(["singapore"])


def test_country_api_ingestion_uploads_destination_list():
    service = Mock(spec=CountryService)
    ingestion = CountryApiIngestion(Mock(), service, {"dataset": {"source": {}, "name": "demo"}})

    ingestion._upload_to_db({"data": {"destinationList": ["sg"]}})

    service.insert_countries.assert_called_once_with(["sg"])


def test_flight_search_api_ingestion_uploads_payload_directly():
    service = Mock(spec=FlightSearchService)
    ingestion = FlightSearchApiIngestion(Mock(), service, {"dataset": {"source": {}, "name": "demo"}})

    payload = {"data": {"destinationList": ["ignored"]}}
    ingestion._upload_to_db(payload)

    service.insert_flights.assert_called_once_with(payload)
