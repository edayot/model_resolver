from pydantic import BaseModel, Field
from typing import Optional, Any

class Item(BaseModel):
    id: str
    count: int = 1
    components: dict[str, Any] = Field(default_factory=dict)