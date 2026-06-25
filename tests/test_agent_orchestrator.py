import pytest
from typing import Any
from unittest.mock import MagicMock, patch
from libs.ai.agents.orchestrator import AgentOrchestrator, RepositoryAnalysisReport
from libs.ai.agents.base_agent import AgentResult

class MockEventBus:
    def __init__(self):
        self.published = []

    def publish(self, topic: str, event: Any) -> None:
        self.published.append((topic, event))

def test_orchestrator_success_flow():
    # Mock all agents to succeed with specific scores
    # Security: 90.0 (weight 0.40) -> 36.0
    # Architecture: 80.0 (weight 0.25) -> 20.0
    # DeadCode: 70.0 (weight 0.15) -> 10.5
    # Impact: 60.0 (weight 0.10) -> 6.0
    # RepositoryQA: 100.0 (weight 0.10) -> 10.0
    # Expected overall score: 36.0 + 20.0 + 10.5 + 6.0 + 10.0 = 82.5

    mock_publisher = MagicMock()
    orchestrator = AgentOrchestrator(publisher=mock_publisher)

    with patch('libs.ai.agents.security_agent.SecurityAgent.analyze') as mock_sec, \
         patch('libs.ai.agents.architecture_agent.ArchitectureAgent.analyze') as mock_arch, \
         patch('libs.ai.agents.dead_code_agent.DeadCodeAgent.analyze') as mock_dead, \
         patch('libs.ai.agents.impact_agent.ImpactAgent.analyze') as mock_impact, \
         patch('libs.ai.agents.repository_qa_agent.RepositoryQAAgent.analyze') as mock_qa:

        mock_sec.return_value = AgentResult(
            agent_name="SecurityAgent",
            score=90.0,
            findings=["sec finding"],
            recommendations=["fix sec"],
            severity="HIGH"
        )
        mock_arch.return_value = AgentResult(
            agent_name="ArchitectureAgent",
            score=80.0,
            findings=["arch finding"],
            recommendations=["fix arch"],
            severity="MEDIUM"
        )
        mock_dead.return_value = AgentResult(
            agent_name="DeadCodeAgent",
            score=70.0,
            findings=["dead finding"],
            recommendations=["fix dead"],
            severity="LOW"
        )
        mock_impact.return_value = AgentResult(
            agent_name="ImpactAgent",
            score=60.0,
            findings=["impact finding"],
            recommendations=["fix impact"],
            severity="MEDIUM"
        )
        mock_qa.return_value = AgentResult(
            agent_name="RepositoryQAAgent",
            score=100.0,
            findings=["qa finding"],
            recommendations=["fix qa"],
            severity="INFO"
        )

        report = orchestrator.run_analysis("test-repo")

        assert report.repository_id == "test-repo"
        assert report.overall_score == 82.5
        assert report.security_result.score == 90.0
        assert report.dead_code_result.score == 70.0
        assert report.architecture_result.score == 80.0
        assert report.impact_result.score == 60.0
        assert report.repository_summary.score == 100.0

        # Assert recommendations are aggregated
        assert "fix sec" in report.recommendations
        assert "fix arch" in report.recommendations
        assert "fix dead" in report.recommendations
        assert "fix impact" in report.recommendations
        assert "fix qa" in report.recommendations

        # Assert publisher calls
        assert mock_publisher.publish.call_count == 2
        calls = mock_publisher.publish.call_args_list
        assert calls[0][0][0] == "analysis.started"
        assert calls[1][0][0] == "analysis.completed"
        assert calls[1][0][1].score == 82.5


def test_orchestrator_partial_failure_and_renormalization():
    # If SecurityAgent fails (raises exception), it should be excluded
    # Remaining agents:
    # Architecture: 80.0 (weight 0.25) -> 20.0
    # DeadCode: 70.0 (weight 0.15) -> 10.5
    # Impact: 60.0 (weight 0.10) -> 6.0
    # RepositoryQA: 100.0 (weight 0.10) -> 10.0
    # Remaining total weight: 0.25 + 0.15 + 0.10 + 0.10 = 0.60
    # Sum of weighted scores: 20.0 + 10.5 + 6.0 + 10.0 = 46.5
    # Re-normalized score: 46.5 / 0.60 = 77.5

    mock_publisher = MagicMock()
    orchestrator = AgentOrchestrator(publisher=mock_publisher)

    with patch('libs.ai.agents.security_agent.SecurityAgent.analyze') as mock_sec, \
         patch('libs.ai.agents.architecture_agent.ArchitectureAgent.analyze') as mock_arch, \
         patch('libs.ai.agents.dead_code_agent.DeadCodeAgent.analyze') as mock_dead, \
         patch('libs.ai.agents.impact_agent.ImpactAgent.analyze') as mock_impact, \
         patch('libs.ai.agents.repository_qa_agent.RepositoryQAAgent.analyze') as mock_qa:

        mock_sec.side_effect = Exception("Security Scan Timed out")
        
        mock_arch.return_value = AgentResult(
            agent_name="ArchitectureAgent",
            score=80.0,
            findings=["arch finding"],
            recommendations=["fix arch"],
            severity="MEDIUM"
        )
        mock_dead.return_value = AgentResult(
            agent_name="DeadCodeAgent",
            score=70.0,
            findings=["dead finding"],
            recommendations=["fix dead"],
            severity="LOW"
        )
        mock_impact.return_value = AgentResult(
            agent_name="ImpactAgent",
            score=60.0,
            findings=["impact finding"],
            recommendations=["fix impact"],
            severity="MEDIUM"
        )
        mock_qa.return_value = AgentResult(
            agent_name="RepositoryQAAgent",
            score=100.0,
            findings=["qa finding"],
            recommendations=["fix qa"],
            severity="INFO"
        )

        report = orchestrator.run_analysis("test-repo")

        assert report.repository_id == "test-repo"
        assert report.overall_score == 77.5
        assert report.security_result.metadata.get("status") == "failed"
        assert "Security Scan Timed out" in report.security_result.findings[0]
        assert report.dead_code_result.score == 70.0

        # Assert recommendation from failed agent is NOT included, others are
        assert "fix sec" not in report.recommendations
        assert "fix arch" in report.recommendations

        # Completed event should still publish
        calls = mock_publisher.publish.call_args_list
        assert calls[-1][0][0] == "analysis.completed"
        assert calls[-1][0][1].score == 77.5


def test_orchestrator_agent_internal_failure_dto():
    # If DeadCodeAgent catches an exception internally and returns an AgentResult with status: failed,
    # it must be excluded from scoring.
    # Security: 90.0 (weight 0.40) -> 36.0
    # Architecture: 80.0 (weight 0.25) -> 20.0
    # DeadCode: 100.0 (weight 0.15) but status: failed -> Excluded
    # Impact: 60.0 (weight 0.10) -> 6.0
    # RepositoryQA: 100.0 (weight 0.10) -> 10.0
    # Remaining total weight: 0.40 + 0.25 + 0.10 + 0.10 = 0.85
    # Sum of weighted scores: 36.0 + 20.0 + 6.0 + 10.0 = 72.0
    # Re-normalized score: 72.0 / 0.85 = 84.71

    mock_publisher = MagicMock()
    orchestrator = AgentOrchestrator(publisher=mock_publisher)

    with patch('libs.ai.agents.security_agent.SecurityAgent.analyze') as mock_sec, \
         patch('libs.ai.agents.architecture_agent.ArchitectureAgent.analyze') as mock_arch, \
         patch('libs.ai.agents.dead_code_agent.DeadCodeAgent.analyze') as mock_dead, \
         patch('libs.ai.agents.impact_agent.ImpactAgent.analyze') as mock_impact, \
         patch('libs.ai.agents.repository_qa_agent.RepositoryQAAgent.analyze') as mock_qa:

        mock_sec.return_value = AgentResult(
            agent_name="SecurityAgent",
            score=90.0,
            findings=["sec finding"],
            recommendations=["fix sec"],
            severity="HIGH"
        )
        mock_arch.return_value = AgentResult(
            agent_name="ArchitectureAgent",
            score=80.0,
            findings=["arch finding"],
            recommendations=["fix arch"],
            severity="MEDIUM"
        )
        mock_dead.return_value = AgentResult(
            agent_name="DeadCodeAgent",
            score=100.0,
            findings=["failed to scan"],
            recommendations=[],
            severity="INFO",
            metadata={"status": "failed", "error": "Internal database error"}
        )
        mock_impact.return_value = AgentResult(
            agent_name="ImpactAgent",
            score=60.0,
            findings=["impact finding"],
            recommendations=["fix impact"],
            severity="MEDIUM"
        )
        mock_qa.return_value = AgentResult(
            agent_name="RepositoryQAAgent",
            score=100.0,
            findings=["qa finding"],
            recommendations=["fix qa"],
            severity="INFO"
        )

        report = orchestrator.run_analysis("test-repo")

        assert report.repository_id == "test-repo"
        assert report.overall_score == 84.71
        assert report.dead_code_result.metadata.get("status") == "failed"


from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.agents import get_orchestrator

class MockAgentOrchestrator:
    def run_analysis(self, repository_id: str, context: Any = None, timeout: float = 30.0) -> RepositoryAnalysisReport:
        if repository_id == "error-repo":
            raise Exception("Failed analysis run")
        
        return RepositoryAnalysisReport(
            repository_id=repository_id,
            overall_score=95.0,
            security_result=AgentResult(
                agent_name="SecurityAgent", score=100.0, findings=[], recommendations=[], severity="LOW"
            ),
            dead_code_result=AgentResult(
                agent_name="DeadCodeAgent", score=90.0, findings=[], recommendations=[], severity="LOW"
            ),
            architecture_result=AgentResult(
                agent_name="ArchitectureAgent", score=95.0, findings=[], recommendations=[], severity="LOW"
            ),
            impact_result=AgentResult(
                agent_name="ImpactAgent", score=100.0, findings=[], recommendations=[], severity="LOW"
            ),
            repository_summary=AgentResult(
                agent_name="RepositoryQAAgent", score=100.0, findings=["summary"], recommendations=[], severity="LOW"
            ),
            recommendations=["Rec 1"]
        )

@pytest.fixture
def override_orchestrator():
    mock_orch = MockAgentOrchestrator()
    app.dependency_overrides[get_orchestrator] = lambda: mock_orch
    yield
    app.dependency_overrides.pop(get_orchestrator, None)

def test_api_agents_analyze_success(override_orchestrator):
    client = TestClient(app)
    response = client.post("/api/v1/agents/analyze", json={
        "repository_id": "test-repo",
        "changed_component": "libs/config.py",
        "timeout": 15.0
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["repository_id"] == "test-repo"
    assert data["overall_score"] == 95.0
    assert data["security_result"]["score"] == 100.0
    assert "Rec 1" in data["recommendations"]

def test_api_agents_analyze_failure(override_orchestrator):
    client = TestClient(app)
    response = client.post("/api/v1/agents/analyze", json={
        "repository_id": "error-repo"
    })
    
    assert response.status_code == 500
    data = response.json()
    assert "Autonomous analysis orchestration failed" in data["detail"]

def test_api_agents_analyze_invalid_repository_id():
    client = TestClient(app)
    response = client.post("/api/v1/agents/analyze", json={
        "repository_id": "../../etc/passwd"
    })
    assert response.status_code == 400
    assert "Invalid repository_id format" in response.json()["detail"]

def test_local_file_walker_symlink_traversal(tmp_path):
    import os
    from services.scanner_service.infrastructure.local_file_walker import LocalFileWalker
    
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    valid_file = repo_dir / "valid.py"
    valid_file.write_text("print('hello')")
    
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("confidential")
    
    sym_link = repo_dir / "sym_secret.txt"
    try:
        os.symlink(str(secret_file), str(sym_link))
    except OSError:
        pytest.skip("Symlink creation not supported in this test environment")
        
    walker = LocalFileWalker()
    files = walker.walk(str(repo_dir))
    
    file_paths = [f["path"] for f in files]
    assert "valid.py" in file_paths
    assert "sym_secret.txt" not in file_paths


