from pydantic import BaseModel
from typing import Dict, Any, Optional

class Chunk(BaseModel):
    id: str
    text: str
    chunk_type: str  # "FUNCTION", "CLASS", "FILE", "DOCUMENTATION", "SECURITY_FINDING"
    metadata: Dict[str, Any]
    content_hash: str
    version: int = 1
    start_line: Optional[int] = None
    end_line: Optional[int] = None
