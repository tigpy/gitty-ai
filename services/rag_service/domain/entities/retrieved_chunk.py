from pydantic import BaseModel
from typing import Optional

class RetrievedChunk(BaseModel):
    score: float
    file_path: str
    symbol_name: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    chunk_type: str
