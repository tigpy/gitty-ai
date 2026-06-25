from pydantic import BaseModel
from typing import List, Dict, Any

class VectorDocument(BaseModel):
    id: str
    vector: List[float]
    payload: Dict[str, Any]
