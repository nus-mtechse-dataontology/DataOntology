from pydantic import BaseModel



class IngestionModel(BaseModel):
	table_name: str
	truncate: bool
	data: list[dict[str, str | int | bool]]
