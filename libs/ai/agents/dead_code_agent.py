from typing import Dict, Any, List
from .base_agent import BaseAgent, AgentResult

class DeadCodeAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "DeadCodeAgent"

    def analyze(self, repository_id: str, context: Dict[str, Any]) -> AgentResult:
        from services.graph_service.infrastructure.repositories.graph_repository_factory import get_graph_repository
        from services.dead_code_service.application.dead_code_detector import DeadCodeDetectionService
        
        try:
            repo = get_graph_repository()
            detector = DeadCodeDetectionService(repo)
            report = detector.run_analysis(repository_id)
            
            findings = []
            recommendations = []
            for f in report.dead_functions:
                findings.append(f"Dead Function: {f.get('name')} in {f.get('path')}")
                recommendations.append(f"Remove unused function {f.get('name')}() in {f.get('path')}")
            for c in report.dead_classes:
                findings.append(f"Dead Class: {c.get('name')} in {c.get('path')}")
                recommendations.append(f"Remove unused class {c.get('name')} in {c.get('path')}")
            for fl in report.dead_files:
                findings.append(f"Dead File: {fl.get('path')}")
                recommendations.append(f"Remove unused file {fl.get('path')}")

            score = float(report.repository_health)
            severity = "HIGH" if score < 70 else "MEDIUM" if score < 90 else "LOW"
            
            return AgentResult(
                agent_name=self.agent_name,
                score=score,
                findings=findings,
                recommendations=recommendations,
                severity=severity,
                metadata={
                    "dead_functions": report.dead_functions,
                    "dead_classes": report.dead_classes,
                    "dead_files": report.dead_files,
                    "repository_health": report.repository_health
                }
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.agent_name,
                score=100.0,
                findings=[f"Failed to scan dead code: {str(e)}"],
                recommendations=["Ensure scanner parses repository code successfully."],
                severity="INFO",
                metadata={"error": str(e), "status": "failed"}
            )
