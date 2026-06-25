from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum

class BaseEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str

class RepositoryDiscoveredV1(BaseEvent):
    repository_id: str
    name: str
    root_path: str
    url: Optional[str] = None
    version: str = Field(default="v1")

class RepositoryIndexedV1(BaseEvent):
    repository_id: str
    repository_url: str
    indexed_files_count: int
    status: str # "success", "failed"
    error_message: Optional[str] = None
    version: str = Field(default="v1")

class GraphBuiltV1(BaseEvent):
    repository_id: str
    nodes_created: int
    edges_created: int
    duration_ms: int
    version: str = Field(default="v1")

class EmbeddingCreatedV1(BaseEvent):
    repository_id: str
    chunk_id: str
    model_name: str
    vector_dimensions: int
    version: str = Field(default="v1")

class DeadCodeDetectedV1(BaseEvent):
    repository_id: str
    dead_functions: List[Dict[str, Any]] = Field(default_factory=list)
    dead_classes: List[Dict[str, Any]] = Field(default_factory=list)
    dead_files: List[Dict[str, Any]] = Field(default_factory=list)
    unused_imports: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 1.0
    confidence_level: str = "HIGH"
    version: str = Field(default="v1")

class DeadModuleDetectedV1(BaseEvent):
    repository_id: str
    dead_files: List[str] = Field(default_factory=list)
    root_files: List[str] = Field(default_factory=list)
    version: str = Field(default="v1")

class DeadCodeAnalysisCompletedV1(BaseEvent):
    repository_id: str
    analysis_timestamp: str
    repository_health: int = 100
    summary: Dict[str, int] = Field(default_factory=dict)
    version: str = Field(default="v1")

class VulnerabilityFoundV1(BaseEvent):
    repository_id: str
    cve_id: str
    cwe_id: str
    file_path: str
    line_number: int
    severity: str # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    version: str = Field(default="v1")

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class SecurityIssueDetectedV1(BaseEvent):
    repository_id: str
    finding_id: str
    rule_id: str
    severity: Severity
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    confidence: str # "HIGH", "MEDIUM", "LOW"
    file_path: str
    line_number: int
    description: str
    version: str = Field(default="v1")

class CriticalSecurityFindingV1(BaseEvent):
    repository_id: str
    finding_id: str
    rule_id: str
    cwe_id: Optional[str] = None
    file_path: str
    line_number: int
    description: str
    version: str = Field(default="v1")

class SecurityScanCompletedV1(BaseEvent):
    repository_id: str
    scan_timestamp: str
    security_score: int
    summary: Dict[str, int] = Field(default_factory=dict)
    version: str = Field(default="v1")

class VectorIndexBuildRequestedV1(BaseEvent):
    repository_id: str
    version: str = Field(default="v1")

class EmbeddingCreatedV1(BaseEvent):
    repository_id: str
    chunk_count: int
    version: str = Field(default="v1")

class VectorIndexBuiltV1(BaseEvent):
    repository_id: str
    vector_count: int
    function_chunks: int = 0
    class_chunks: int = 0
    file_chunks: int = 0
    documentation_chunks: int = 0
    security_chunks: int = 0
    version: str = Field(default="v1")

class SemanticSearchCompletedV1(BaseEvent):
    repository_id: str
    query: str
    result_count: int
    version: str = Field(default="v1")

class RepositoryQuestionAskedV1(BaseEvent):
    repository_id: str
    question: str
    provider: str
    model: str
    version: str = Field(default="v1")

class RepositoryAnswerGeneratedV1(BaseEvent):
    repository_id: str
    question: str
    answer: str
    provider: str
    model: str
    latency_ms: int
    version: str = Field(default="v1")

class RepositoryAnswerFailedV1(BaseEvent):
    repository_id: str
    question: str
    reason: str
    version: str = Field(default="v1")


class ConversationStartedV1(BaseEvent):
    session_id: str
    repository_id: str
    version: str = Field(default="v1")


class ConversationMessageAddedV1(BaseEvent):
    session_id: str
    message_id: str
    role: str
    content: str
    version: str = Field(default="v1")


class ConversationEndedV1(BaseEvent):
    session_id: str
    version: str = Field(default="v1")


class ConversationContextRetrievedV1(BaseEvent):
    session_id: str
    chunk_count: int
    version: str = Field(default="v1")


class RepositoryAnalysisStartedV1(BaseEvent):
    repository_id: str
    version: str = Field(default="v1")


class RepositoryAnalysisCompletedV1(BaseEvent):
    repository_id: str
    score: float
    version: str = Field(default="v1")


class RepositoryAnalysisFailedV1(BaseEvent):
    repository_id: str
    error: str
    version: str = Field(default="v1")



