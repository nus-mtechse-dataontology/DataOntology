from pydantic import BaseModel


class UserModel(BaseModel):
	email: str | None = None
	disabled: bool
	full_name: str
	username: str
	exp: int
