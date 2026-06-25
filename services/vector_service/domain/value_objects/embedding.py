from pydantic import BaseModel
from typing import List

class Embedding(BaseModel):
    vector: List[float]
