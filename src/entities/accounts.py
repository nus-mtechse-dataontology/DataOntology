from sqlmodel import SQLModel, Field


class Accounts(SQLModel, table=True):
	__tablename__ = "dim_accounts"
	
	f_username: str = Field(index=True, nullable=False, primary_key=True)
	f_full_name: str = Field(nullable=False)
	f_email: str = Field(nullable=True, default=None)
	f_hashed_password: str = Field(nullable=False)
	f_disabled: bool = Field(nullable=False, default=False)
	