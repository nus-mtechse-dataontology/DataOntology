from sqlmodel import SQLModel, Field


class Accounts(SQLModel, table=True):
	__tablename__ = "dim_accounts"
	
	f_username: str = Field(index=True, nullable=False, primary_key=True, alias="username")
	f_full_name: str = Field(nullable=False, alias="full_name")
	f_email: str = Field(nullable=True, default=None, alias="email")
	f_hashed_password: str = Field(nullable=False)
	f_disabled: bool = Field(nullable=False, default=False, alias="disabled")
	