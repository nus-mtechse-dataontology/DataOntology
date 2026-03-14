from sqlmodel import Field, SQLModel, Relationship


class Country(SQLModel, table=True):
	__tablename__ = "dim_country"
	
	f_country_code: str = Field(index=True, nullable=False, primary_key=True)
	f_country_name: str = Field(default=None, nullable=False)
	
	city: list["City"] = Relationship(back_populates="country")
