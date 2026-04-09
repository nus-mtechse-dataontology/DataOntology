from pydantic import BaseModel


class RegisterModel(BaseModel):
	username: str
	password: str
	email: str | None = None
	full_name: str | None = None