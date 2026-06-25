from pydantic import BaseModel

class EmbeddingRecord(BaseModel):
    id: str
    repository_id: str
    model_name: str
    created_at: str
