from sqlmodel import SQLModel, Field, Relationship

from entities.airport import Airport
from entities.airline import Airline


class AirlineCoverage(SQLModel, table=True):
	__tablename__ = "dim_airline_coverage"
	
	f_airport_code: str = Field(
		default=None,
		index=True,
		nullable=False,
		primary_key=True,
		foreign_key="dim_airport.f_airport_code"
	)
	f_airline_code: str = Field(
		default=None,
		index=True,
		nullable=False,
		primary_key=True,
		foreign_key="dim_airline.f_airline_code"
	)
	f_coverage: bool = Field(default=False, nullable=False)
	
	airport: Airport = Relationship(back_populates="airline_coverage")
	airline: Airline = Relationship(back_populates="airline_coverage")
