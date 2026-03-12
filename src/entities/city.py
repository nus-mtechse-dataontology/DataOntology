from sqlmodel import Field, SQLModel, Relationship

from entities.country import Country


class City(SQLModel, table=True):
	__tablename__ = "dim_city"
	
	f_city_code: str = Field(index=True, nullable=False, primary_key=True)
	f_city_name: str = Field(default=None, nullable=False)
	f_country_code: str = Field(index=True, nullable=False, foreign_key="dim_country.f_country_code")
	
	country: Country | None = Relationship(back_populates="city")
	airport: list["Airport"] = Relationship(back_populates="city")
