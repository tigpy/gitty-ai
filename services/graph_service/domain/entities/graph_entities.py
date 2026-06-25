from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class GraphNode(BaseModel):
    id: str
    label: str
    node_type: str  # "REPOSITORY", "FILE", "CLASS", "FUNCTION", "SECURITY_FINDING"
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    security_score: Optional[int] = None
    dead_code: bool = False
    architecture_smell: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str  # "CONTAINS", "CALLS", "DEPENDS", "CONTAINS_FILE", etc.

class RepositoryGraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class NodeDetailsResponse(BaseModel):
    id: str
    type: str
    name: str
    file_path: Optional[str] = None
    symbol_name: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    security_findings: List[Dict[str, Any]] = Field(default_factory=list)
    dead_code: bool = False
    architecture_smell: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
