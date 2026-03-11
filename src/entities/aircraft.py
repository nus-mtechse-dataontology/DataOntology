from sqlmodel import SQLModel, Field, Relationship


class Aircraft(SQLModel, table=True):
    __tablename__ = "dim_aircraft"
    
    f_aircraft_code: str = Field(default=None, nullable=False, primary_key=True)
    f_aircraft_model: str = Field(default=None, nullable=False)
    
    fact_flight_info: list["FactFlightInfo"] = Relationship(back_populates="aircraft")
