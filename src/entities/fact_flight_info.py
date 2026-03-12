from decimal import Decimal

from sqlmodel import SQLModel, Field, Relationship

from entities.aircraft import Aircraft
from entities.airline import Airline
from entities.airport import Airport
from entities.currency_rate import CurrencyRate


class FactFlightInfo(SQLModel, table=True):
	__tablename__ = "fact_flight_info"
	
	f_flight_combination: int = Field(default=None, nullable=False, primary_key=True)
	f_departure_airport_code: str = Field(default=None, nullable=False, foreign_key="dim_airport.f_airport_code")
	f_destination_airport_code: str = Field(default=None, nullable=False, foreign_key="dim_airport.f_airport_code")
	f_airline_code: str = Field(default=None, nullable=False, foreign_key="dim_airline.f_airline_code")
	f_currency_code: str = Field(default=None, nullable=False, foreign_key="dim_currency_rate.f_currency_code")
	f_aircraft_code: str = Field(default=None, nullable=False, foreign_key="dim_aircraft.f_aircraft_code")
	f_departure_date: str = Field(default=None, nullable=False)
	f_arrival_date: str = Field(default=None, nullable=False)
	f_cabin_class: str = Field(default=None, nullable=False)
	f_trip_type: str = Field(default=None, nullable=False)
	f_num_of_last_seats: int = Field(default=None, nullable=False)
	f_flight_duration: int = Field(default=None, nullable=False)
	f_total_amount_fare_total: Decimal = Field(default=None, nullable=False, max_digits=38, decimal_places=2)
	
	departure_airport: Airport | None = Relationship(
		back_populates="departure_airport",
		sa_relationship_kwargs={
			"foreign_keys": "FactFlightInfo.f_departure_airport_code"
		}
	)
	destination_airport: Airport | None = Relationship(
		back_populates="destination_airport",
		sa_relationship_kwargs={
			"foreign_keys": "FactFlightInfo.f_destination_airport_code",
		}
	)
	airline: Airline | None = Relationship(back_populates="fact_flight_info")
	aircraft: Aircraft | None = Relationship(back_populates="fact_flight_info")
	currency_rate: CurrencyRate | None = Relationship(back_populates="fact_flight_info")
	