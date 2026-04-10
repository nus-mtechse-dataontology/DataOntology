from pydantic import BaseModel


class AllowModel(BaseModel):
    origins: list[str]
    credentials: bool
    methods: list[str]
    headers: list[str]


class ApiModel(BaseModel):
    allow: AllowModel
    redoc_url: str
    docs_url: str
    root_path: str


class AppModel(BaseModel):
    host: str
    port: int
    reload: bool
    scheme: str
    api_endpoint: ApiModel
