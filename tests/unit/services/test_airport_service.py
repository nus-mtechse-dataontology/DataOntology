from ingestion.services.airport_service import AirportService
from dao.airport_dao import AirportDAO


def test_insert_and_get_airports(in_memory_engine):
    dao = AirportDAO(in_memory_engine)
    service = AirportService(dao)

    payload = [
        {"airportCode": "A1", "airportName": "Alpha", "cityCode": "C1"},
        {"airportCode": "A2", "airportName": "Beta", "cityCode": "C2"},
        # duplicate code should not result in two rows in the table
        {"airportCode": "A1", "airportName": "Alpha Duplicate", "cityCode": "C1"},
    ]

    service.insert_airports(payload)
    results = service.get_all_airports()

    assert len(results) == 2
    codes = {a.f_airport_code for a in results}
    assert codes == {"A1", "A2"}
