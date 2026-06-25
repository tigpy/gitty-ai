from pydantic import BaseModel, Field
from typing import List, Dict, Any

class DeadCodeReport(BaseModel):
    repository_id: str
    repository_name: str
    analysis_timestamp: str
    summary: Dict[str, int] = Field(default_factory=dict)
    dead_functions: List[Dict[str, Any]] = Field(default_factory=list)
    dead_classes: List[Dict[str, Any]] = Field(default_factory=list)
    dead_files: List[Dict[str, Any]] = Field(default_factory=list)
    unused_imports: List[Dict[str, Any]] = Field(default_factory=list)
    dead_modules: List[List[str]] = Field(default_factory=list)
    architecture_smells: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 1.0
    confidence_level: str = "HIGH"
    repository_health: int = 100
