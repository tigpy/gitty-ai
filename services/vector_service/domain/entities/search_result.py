from pydantic import BaseModel
from typing import Optional

class SearchResult(BaseModel):
    score: float
    file_path: str
    symbol_name: Optional[str] = None
    chunk_type: str
    snippet: str
