from sqlmodel import SQLModel, Field, Relationship


class Airline(SQLModel, table=True):
    __tablename__ = "dim_airline"
    
    f_airline_code: str = Field(index=True, nullable=False, primary_key=True)
    f_airline_name: str = Field(nullable=False)
    
    airline_coverage: list["AirlineCoverage"] = Relationship(back_populates="airline")
    fact_flight_info: list["FactFlightInfo"] = Relationship(back_populates="airline")
