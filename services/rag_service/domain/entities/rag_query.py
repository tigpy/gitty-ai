from pydantic import BaseModel, Field

class RAGQuery(BaseModel):
    repository_id: str
    question: str
    limit: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.60, ge=-1.0, le=1.0)
    include_code: bool = True
    include_docs: bool = True
    include_security: bool = True
