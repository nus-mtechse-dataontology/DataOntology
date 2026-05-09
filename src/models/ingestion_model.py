from pydantic import BaseModel



class IngestionModel(BaseModel):
	table_name: str
	truncate: bool = False
	data: list[dict[str, str | int | bool]] = []
