from pydantic import BaseModel, Field
from typing import Optional
from libs.events.schemas import Severity

class SecurityFinding(BaseModel):
    id: str
    rule_id: str
    severity: Severity
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    confidence: str = "HIGH"  # "HIGH", "MEDIUM", "LOW"
    file_path: str
    line_number: int
    code_snippet: str
    description: str
    recommendation: str
