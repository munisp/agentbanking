from pydantic import BaseModel

class Pagination(BaseModel):
    limit: int
    page: int
