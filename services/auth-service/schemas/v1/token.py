from pydantic import BaseModel

class GenerateToken(BaseModel):
    key: str
    secret: str