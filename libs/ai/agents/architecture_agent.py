from typing import Dict, Any, List
from .base_agent import BaseAgent, AgentResult

class ArchitectureAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "ArchitectureAgent"

    def analyze(self, repository_id: str, context: Dict[str, Any]) -> AgentResult:
        from services.graph_service.infrastructure.repositories.graph_repository_factory import get_graph_repository
        from services.dead_code_service.application.dead_code_detector import DeadCodeDetectionService
        
        try:
            repo = get_graph_repository()
            detector = DeadCodeDetectionService(repo)
            report = detector.run_analysis(repository_id)
            
            findings = []
            recommendations = []
            
            smells = report.architecture_smells or []
            
            for smell in smells:
                findings.append(
                    f"Architecture Smell: {smell.get('type')} on {smell.get('entity_name')} "
                    f"in {smell.get('path')} - {smell.get('message')}"
                )
                recommendations.append(
                    f"Refactor {smell.get('entity_name')} in {smell.get('path')} to resolve the {smell.get('type')} smell."
                )
                
            score = max(0.0, 100.0 - (len(smells) * 10.0))
            severity = "HIGH" if score < 70 else "MEDIUM" if score < 90 else "LOW"
            
            return AgentResult(
                agent_name=self.agent_name,
                score=score,
                findings=findings,
                recommendations=recommendations,
                severity=severity,
                metadata={
                    "architecture_smells": smells,
                    "smells_count": len(smells)
                }
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.agent_name,
                score=100.0,
                findings=[f"Failed to scan architecture: {str(e)}"],
                recommendations=["Ensure graph repository and parser run successfully."],
                severity="INFO",
                metadata={"error": str(e), "status": "failed", "architecture_smells": [], "smells_count": 0}
            )
