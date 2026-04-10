from ingestion.services.airline_coverage_service import AirlineCoverageService
from ingestion.services.city_service import CityService
from ingestion.services.country_service import CountryService


class StubDAO:
    def __init__(self):
        self.inserted = None

    def insert_many(self, items):
        self.inserted = items
        return items


def test_city_service_deduplicates_by_city_code():
    dao = StubDAO()
    service = CityService(dao)

    payload = [
        {"cityCode": "SIN", "cityName": "Singapore", "countryCode": "SG"},
        {"cityCode": "NRT", "cityName": "Narita", "countryCode": "JP"},
        {"cityCode": "SIN", "cityName": "Singapore Updated", "countryCode": "SG"},
    ]

    service.insert_cities(payload)

    assert dao.inserted is not None
    assert len(dao.inserted) == 2
    codes = {c.f_city_code for c in dao.inserted}
    assert codes == {"SIN", "NRT"}


def test_country_service_deduplicates_by_country_code():
    dao = StubDAO()
    service = CountryService(dao)

    payload = [
        {"countryCode": "SG", "countryName": "Singapore"},
        {"countryCode": "JP", "countryName": "Japan"},
        {"countryCode": "SG", "countryName": "Singapore Updated"},
    ]

    service.insert_countries(payload)

    assert dao.inserted is not None
    assert len(dao.inserted) == 2
    code_to_name = {c.f_country_code: c.f_country_name for c in dao.inserted}
    assert code_to_name["SG"] == "Singapore Updated"
    assert code_to_name["JP"] == "Japan"


def test_airline_coverage_service_builds_sq_tr_pairs_and_skips_sin():
    dao = StubDAO()
    service = AirlineCoverageService(dao)

    payload = [
        {"airportCode": "SIN", "isSQGtwyFlg": True, "isTRDestination": True},
        {"airportCode": "NRT", "isSQGtwyFlg": True, "isTRDestination": False},
        {"airportCode": "SFO", "isSQGtwyFlg": False, "isTRDestination": True},
    ]

    service.insert_coverages(payload)

    assert dao.inserted is not None
    assert len(dao.inserted) == 4
    rows = {(c.f_airport_code, c.f_airline_code): c.f_coverage for c in dao.inserted}
    assert ("SIN", "SQ") not in rows
    assert rows[("NRT", "SQ")] is True
    assert rows[("NRT", "TR")] is False
    assert rows[("SFO", "SQ")] is False
    assert rows[("SFO", "TR")] is True
