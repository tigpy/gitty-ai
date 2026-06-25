from typing import Dict, Any, List
from .base_agent import BaseAgent, AgentResult

class SecurityAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "SecurityAgent"

    def analyze(self, repository_id: str, context: Dict[str, Any]) -> AgentResult:
        from services.graph_service.infrastructure.repositories.graph_repository_factory import get_graph_repository
        from services.security_service.application.security_analysis_service import SecurityAnalysisService
        
        try:
            repo = get_graph_repository()
            service = SecurityAnalysisService(repo)
            report = service.run_security_scan(repository_id)
            
            findings = []
            recommendations = []
            max_severity_val = 0
            severity_str = "INFO"
            
            severity_weights = {
                "CRITICAL": 4,
                "HIGH": 3,
                "MEDIUM": 2,
                "LOW": 1,
                "INFO": 0
            }
            
            for f in report.findings:
                findings.append(f"[{f.severity}] {f.rule_id} in {f.file_path}:{f.line_number} - {f.description}")
                recommendations.append(f"Fix {f.rule_id} in {f.file_path}: {f.recommendation}")
                val = severity_weights.get(f.severity, 0)
                if val > max_severity_val:
                    max_severity_val = val
                    severity_str = f.severity
                    
            score = float(report.security_score)
            
            return AgentResult(
                agent_name=self.agent_name,
                score=score,
                findings=findings,
                recommendations=recommendations,
                severity=severity_str,
                metadata={
                    "findings": [f.model_dump() for f in report.findings],
                    "security_score": report.security_score
                }
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.agent_name,
                score=100.0,
                findings=[f"Failed to scan security: {str(e)}"],
                recommendations=["Ensure static analyzers run successfully."],
                severity="INFO",
                metadata={"error": str(e), "status": "failed"}
            )
