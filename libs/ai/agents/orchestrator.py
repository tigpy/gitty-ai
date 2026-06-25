import uuid
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from libs.config import get_settings
from libs.events.schemas import (
    RepositoryAnalysisStartedV1,
    RepositoryAnalysisCompletedV1,
    RepositoryAnalysisFailedV1
)
from libs.core.message_bus.rabbitmq.publisher import RabbitMQPublisher
from libs.ai.agents.base_agent import AgentResult
from libs.ai.agents.security_agent import SecurityAgent
from libs.ai.agents.dead_code_agent import DeadCodeAgent
from libs.ai.agents.architecture_agent import ArchitectureAgent
from libs.ai.agents.impact_agent import ImpactAgent
from libs.ai.agents.repository_qa_agent import RepositoryQAAgent

logger = logging.getLogger(__name__)

class RepositoryAnalysisReport(BaseModel):
    repository_id: str
    overall_score: float
    security_result: AgentResult
    dead_code_result: AgentResult
    architecture_result: AgentResult
    impact_result: AgentResult
    repository_summary: AgentResult
    recommendations: List[str]

class AgentOrchestrator:
    def __init__(self, publisher: Optional[Any] = None):
        self.publisher = publisher
        if not self.publisher:
            try:
                settings = get_settings()
                self.publisher = RabbitMQPublisher(
                    host=settings.RABBITMQ_HOST,
                    port=settings.RABBITMQ_PORT
                )
            except Exception as e:
                logger.warning(f"Failed to initialize RabbitMQPublisher: {e}")
                self.publisher = None

    def run_analysis(
        self,
        repository_id: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> RepositoryAnalysisReport:
        context = context or {}
        
        # Publish start event
        if self.publisher:
            try:
                start_event = RepositoryAnalysisStartedV1(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    repository_id=repository_id
                )
                self.publisher.publish("analysis.started", start_event)
            except Exception as e:
                logger.error(f"Failed to publish analysis start event: {e}")

        # Initialize agents with their respective weights
        agents = {
            "security": (SecurityAgent(), 0.40),
            "architecture": (ArchitectureAgent(), 0.25),
            "dead_code": (DeadCodeAgent(), 0.15),
            "impact": (ImpactAgent(), 0.10),
            "repository_summary": (RepositoryQAAgent(), 0.10)
        }

        results: Dict[str, AgentResult] = {}
        
        def execute_agent(name: str, agent: Any) -> AgentResult:
            try:
                return agent.analyze(repository_id, context)
            except Exception as e:
                logger.error(f"Agent {name} failed: {e}", exc_info=True)
                return AgentResult(
                    agent_name=agent.agent_name,
                    score=0.0,
                    findings=[f"Agent execution failed: {str(e)}"],
                    recommendations=["Verify service status and input data."],
                    severity="CRITICAL",
                    metadata={"status": "failed", "error": str(e)}
                )

        # Execute concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            futures = {
                executor.submit(execute_agent, name, agent_info[0]): name
                for name, agent_info in agents.items()
            }
            
            for future in as_completed(futures):
                name = futures[future]
                try:
                    res = future.result(timeout=timeout)
                    results[name] = res
                except Exception as e:
                    logger.error(f"Agent {name} future error or timeout: {e}")
                    agent_instance = agents[name][0]
                    results[name] = AgentResult(
                        agent_name=agent_instance.agent_name,
                        score=0.0,
                        findings=[f"Agent timeout or execution failure: {str(e)}"],
                        recommendations=["Verify service response and latency settings."],
                        severity="CRITICAL",
                        metadata={"status": "failed", "error": str(e)}
                    )

        # Verify all agents exist in results dict, fallback if not
        for name in agents:
            if name not in results:
                agent_instance = agents[name][0]
                results[name] = AgentResult(
                    agent_name=agent_instance.agent_name,
                    score=0.0,
                    findings=["Agent did not execute or return results."],
                    recommendations=["Verify orchestrator execution flow."],
                    severity="CRITICAL",
                    metadata={"status": "failed", "error": "Not executed"}
                )

        # Calculate scores with dynamic weight re-normalization for failed agents
        successful_weights = []
        successful_scores = []
        
        for name, agent_info in agents.items():
            res = results[name]
            weight = agent_info[1]
            
            is_failed = (
                res.metadata.get("status") == "failed"
                or res.metadata.get("error") is not None
            )
            
            if not is_failed:
                successful_weights.append(weight)
                successful_scores.append(res.score * weight)
            else:
                logger.warning(f"Agent {name} result marked as failed, excluding from composite score.")

        total_weight = sum(successful_weights)
        if total_weight > 0:
            overall_score = sum(successful_scores) / total_weight
            overall_score = round(overall_score, 2)
        else:
            overall_score = 0.0

        # Aggregate recommendations from successful agents
        recommendations = []
        for name in agents:
            res = results[name]
            is_failed = (
                res.metadata.get("status") == "failed"
                or res.metadata.get("error") is not None
            )
            if not is_failed:
                recommendations.extend(res.recommendations)

        # Build final report DTO
        report = RepositoryAnalysisReport(
            repository_id=repository_id,
            overall_score=overall_score,
            security_result=results["security"],
            dead_code_result=results["dead_code"],
            architecture_result=results["architecture"],
            impact_result=results["impact"],
            repository_summary=results["repository_summary"],
            recommendations=recommendations
        )

        # Publish completion event
        if self.publisher:
            try:
                completed_event = RepositoryAnalysisCompletedV1(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    repository_id=repository_id,
                    score=overall_score
                )
                self.publisher.publish("analysis.completed", completed_event)
            except Exception as e:
                logger.error(f"Failed to publish analysis completed event: {e}")

        return report
