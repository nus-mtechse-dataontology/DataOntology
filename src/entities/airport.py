from sqlmodel import Field, SQLModel, Relationship

from entities.city import City


class Airport(SQLModel, table=True):
	__tablename__ = "dim_airport"
	
	f_airport_code: str = Field(index=True, nullable=False, primary_key=True)
	f_airport_name: str = Field(default=None, nullable=False)
	f_city_code: str = Field(default=None, nullable=False, foreign_key="dim_city.f_city_code")
	
	city: City | None = Relationship(back_populates="airport")
	airline_coverage: list["AirlineCoverage"] = Relationship(back_populates="airport")
	departure_airport: list["FactFlightInfo"] = Relationship(
		back_populates="departure_airport",
		sa_relationship_kwargs={
			"foreign_keys": "FactFlightInfo.f_departure_airport_code"
		}
	)
	destination_airport: list["FactFlightInfo"] = Relationship(
		back_populates="destination_airport",
		sa_relationship_kwargs={
			"foreign_keys": "FactFlightInfo.f_destination_airport_code"
		}
	)
