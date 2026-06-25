from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pydantic import BaseModel, Field

class AgentResult(BaseModel):
    agent_name: str
    score: float
    findings: List[str]
    recommendations: List[str]
    severity: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseAgent(ABC):
    @property
    @abstractmethod
    def agent_name(self) -> str:
        pass

    @abstractmethod
    def analyze(self, repository_id: str, context: Dict[str, Any]) -> AgentResult:
        pass

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        repo_id = input_data.get("repository_id", "test-repo")
        try:
            res = self.analyze(repo_id, input_data)
            return {
                **res.metadata,
                "status": "success",
                "agent": self.agent_name,
                "answer": res.findings[0] if res.findings else f"Mock response from {self.agent_name}",
                "findings": res.findings,
                "score": res.score
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def validate(self, input_data: Dict[str, Any]) -> bool:
        return True

    def prepare_context(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return input_data
