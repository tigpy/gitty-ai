from pydantic import BaseModel
from typing import List
from .retrieved_chunk import RetrievedChunk

class RAGResponse(BaseModel):
    answer: str
    retrieved_chunks: List[RetrievedChunk]
    provider: str
    model: str
    latency_ms: int
