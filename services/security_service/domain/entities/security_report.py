from pydantic import BaseModel, Field
from typing import List
from .security_finding import SecurityFinding

class SecurityReport(BaseModel):
    repository_id: str
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    security_score: int = 100
    findings: List[SecurityFinding] = Field(default_factory=list)
