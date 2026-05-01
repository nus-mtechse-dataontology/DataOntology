import pytest
from sqlmodel import create_engine, SQLModel, Session
from dao.accounts_dao import AccountsDAO
from dao.registration_dao import RegistrationDAO
from dao.airport_dao import AirportDAO
from dao.city_dao import CityDAO
from dao.country_dao import CountryDAO
from dao.airline_coverage_dao import AirlineCoverageDAO
from entities.accounts import Accounts
from entities.airport import Airport
from entities.city import City
from entities.country import Country
from entities.airline_coverage import AirlineCoverage
from entities.airline import Airline

@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine

def test_accounts_dao_get_user(engine):
    dao = AccountsDAO(engine)
    user = Accounts(
        username="testuser",
        full_name="Test User",
        email="test@example.com",
        f_hashed_password="hashed_password"
    )
    with Session(engine) as session:
        session.add(user)
        session.commit()
    
    fetched_user = dao.get_user("testuser")
    assert fetched_user is not None
    assert fetched_user.f_username == "testuser"
    assert fetched_user.f_full_name == "Test User"

def test_registration_dao_register_user(engine):
    dao = RegistrationDAO(engine)
    user = Accounts(
        username="newuser",
        full_name="New User",
        email="new@example.com",
        f_hashed_password="hashed_password"
    )
    
    dao.register_user(user)
    
    accounts_dao = AccountsDAO(engine)
    assert accounts_dao.get_user("newuser") is not None

def test_airport_dao_get_all_airports(engine):
    dao = AirportDAO(engine)
    
    with Session(engine) as session:
        country = Country(f_country_code="SG", f_country_name="Singapore")
        session.add(country)
        session.commit()
        
        city = City(f_city_code="SIN", f_city_name="Singapore City", f_country_code="SG")
        session.add(city)
        session.commit()
        
        airport = Airport(f_airport_code="SIN", f_airport_name="Changi Airport", f_city_code="SIN")
        session.add(airport)
        session.commit()
    
    airports = dao.get_all_airports()
    assert len(airports) == 1
    assert airports[0].f_airport_code == "SIN"

def test_city_dao_get_all_cities(engine):
    dao = CityDAO(engine)
    
    with Session(engine) as session:
        country = Country(f_country_code="SG", f_country_name="Singapore")
        session.add(country)
        session.commit()
        
        city = City(f_city_code="SIN", f_city_name="Singapore City", f_country_code="SG")
        session.add(city)
        session.commit()
    
    cities = dao.get_all_cities()
    assert len(cities) == 1
    assert cities[0].f_city_code == "SIN"

def test_country_dao_get_all_countries(engine):
    dao = CountryDAO(engine)
    
    with Session(engine) as session:
        country = Country(f_country_code="SG", f_country_name="Singapore")
        session.add(country)
        session.commit()
    
    countries = dao.get_all_countries()
    assert len(countries) == 1
    assert countries[0].f_country_code == "SG"

def test_airline_coverage_dao_get_all_coverage(engine):
    dao = AirlineCoverageDAO(engine)
    
    with Session(engine) as session:
        airline = Airline(f_airline_code="SQ", f_airline_name="Singapore Airlines")
        session.add(airline)
        session.commit()
        
        country = Country(f_country_code="SG", f_country_name="Singapore")
        session.add(country)
        session.commit()
        
        city = City(f_city_code="SIN", f_city_name="Singapore City", f_country_code="SG")
        session.add(city)
        session.commit()
        
        airport = Airport(f_airport_code="SIN", f_airport_name="Changi Airport", f_city_code="SIN")
        session.add(airport)
        session.commit()
        
        coverage = AirlineCoverage(f_airport_code="SIN", f_airline_code="SQ", f_coverage=True)
        session.add(coverage)
        session.commit()
    
    coverages = dao.get_all_coverage()
    assert len(coverages) == 1
    assert coverages[0].f_airline_code == "SQ"
