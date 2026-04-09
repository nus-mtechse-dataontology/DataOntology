from decimal import Decimal

from sqlmodel import Field, SQLModel, Relationship


class CurrencyRate(SQLModel, table=True):
	__tablename__ = "dim_currency_rate"
	f_currency_code: str = Field(default=None, nullable=False, primary_key=True, index=True)
	f_currency_name: str = Field(default=None, nullable=False)
	f_currency_rate: Decimal = Field(default=None, nullable=False, max_digits=38, decimal_places=2)
	
	fact_flight_info: list["FactFlightInfo"] = Relationship(back_populates="currency_rate")
