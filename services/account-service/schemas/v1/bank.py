from pydantic import BaseModel 
from typing import Optional

class CreateBankSchema(BaseModel):
    name: str
    logo: Optional[str] = None
