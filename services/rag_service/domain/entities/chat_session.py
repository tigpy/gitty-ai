from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from .retrieved_chunk import RetrievedChunk

class ChatMessage(BaseModel):
    message_id: str
    session_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    citations: Optional[List[RetrievedChunk]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChatSession(BaseModel):
    session_id: str
    repository_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: List[ChatMessage] = Field(default_factory=list)
