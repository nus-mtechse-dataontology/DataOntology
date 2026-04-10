from pydantic import BaseModel


class AdminModel(BaseModel):
    admin_host: str
    admin_port: int
    context_path: str
    scheme: str
