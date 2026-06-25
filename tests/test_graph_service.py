import pytest
from unittest.mock import MagicMock, patch
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.graph_service.application.graph_application_service import GraphApplicationService
from services.graph_service.domain.entities.graph_entities import GraphNode, GraphEdge
from services.dead_code_service.domain.entities.dead_code_report import DeadCodeReport
from services.security_service.domain.entities.security_report import SecurityReport
from services.security_service.domain.entities.security_finding import SecurityFinding

def test_graph_service_repositories_list(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    
    # Save a test repo
    repo.save_repository("r1", "test-repo", "/home/test", "python", "2026-06-22T00:00:00Z", "hash123")
    
    service = GraphApplicationService(repo)
    repos = service.get_repositories()
    assert len(repos) == 1
    assert repos[0]["name"] == "test-repo"

def test_get_repository_graph_initial(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    
    # Save Repo node
    repo.save_repository("repo-1", "my-repo", "/home/repo", "python", "2026-06-22T00:00:00Z", "hash")
    repo.add_node("repo-1", "Repository", {"name": "my-repo", "path": "/home/repo"})
    
    # Save File nodes
    repo.add_node("file-1", "File", {"name": "main.py", "path": "main.py"})
    repo.add_node("file-2", "File", {"name": "auth.py", "path": "auth.py"})
    
    # Add contains edges Repo -> File
    repo.add_edge("repo-1", "file-1", "CONTAINS", {})
    repo.add_edge("repo-1", "file-2", "CONTAINS", {})
    
    # Mock imports to create File -> File dependency edges
    repo.add_node("imp-1", "Import", {"name": "auth", "path": "main.py"})
    repo.add_edge("file-1", "imp-1", "IMPORTS", {})
    
    service = GraphApplicationService(repo)
    
    # Mock run_analysis & run_security_scan to return clean reports
    mock_dead = DeadCodeReport(
        repository_id="repo-1", repository_name="my-repo", analysis_timestamp="Z", summary={},
        dead_functions=[], dead_classes=[], dead_files=[{"id": "file-2", "name": "auth.py", "path": "auth.py", "confidence_score": 0.9, "confidence_level": "HIGH"}],
        dead_modules=[], architecture_smells=[], confidence_score=0.9, confidence_level="HIGH", repository_health=90
    )
    mock_sec = SecurityReport(
        repository_id="repo-1", critical_count=0, high_count=1, medium_count=0, low_count=0, info_count=0,
        security_score=75, findings=[
            SecurityFinding(
                id="fnd-1", rule_id="hardcoded-secret", severity="HIGH", file_path="main.py",
                line_number=5, description="AWS secret", confidence="HIGH", code_snippet="", recommendation="Rotate secret"
            )
        ]
    )
    
    with patch.object(service.dead_detector, 'run_analysis', return_value=mock_dead) as mock_d_run, \
         patch.object(service.sec_service, 'run_security_scan', return_value=mock_sec) as mock_s_run:
         
        graph_response = service.get_repository_graph("repo-1")
        
        # Verify Repo node, File nodes, Contains edges and File dependencies edges
        assert len(graph_response.nodes) == 3 # Repo + 2 Files
        repo_node = next(n for n in graph_response.nodes if n.node_type == "REPOSITORY")
        file1 = next(n for n in graph_response.nodes if n.id == "file-1")
        file2 = next(n for n in graph_response.nodes if n.id == "file-2")
        
        assert repo_node.label == "my-repo"
        assert file1.security_score == 75 # 100 - 25 (High deduction)
        assert file2.dead_code is True
        
        # Verify contains edges + depends edge (file-1 depends on file-2 because of import)
        assert len(graph_response.edges) == 3 # 2 CONTAINS, 1 DEPENDS
        depends_edge = next(e for e in graph_response.edges if e.relationship == "DEPENDS")
        assert depends_edge.source == "file-1"
        assert depends_edge.target == "file-2"

def test_expand_node_progressive(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    
    # Save File & Symbol nodes
    repo.add_node("file-1", "File", {"name": "main.py", "path": "main.py"})
    repo.add_node("func-1", "Function", {"name": "start_app", "path": "main.py", "start_line": 10, "end_line": 20})
    repo.add_node("class-1", "Class", {"name": "AppRunner", "path": "main.py", "start_line": 25, "end_line": 50})
    
    # Contains links File -> Function, Class
    repo.add_edge("file-1", "func-1", "CONTAINS", {})
    repo.add_edge("file-1", "class-1", "CONTAINS", {})
    
    service = GraphApplicationService(repo)
    
    with patch.object(service.dead_detector, 'run_analysis') as mock_d_run, \
         patch.object(service.sec_service, 'run_security_scan') as mock_s_run:
        mock_d_run.side_effect = Exception("Analysis failure")
        mock_s_run.side_effect = Exception("Security scan failure")
        
        expansion = service.expand_node("file-1", "repo-1")
        
        # Should catch failures gracefully and return child nodes
        assert len(expansion.nodes) == 2
        func_node = next(n for n in expansion.nodes if n.node_type == "FUNCTION")
        class_node = next(n for n in expansion.nodes if n.node_type == "CLASS")
        
        assert func_node.label == "start_app"
        assert class_node.label == "AppRunner"
        assert func_node.start_line == 10
        assert class_node.start_line == 25
        assert len(expansion.edges) == 2
        
def test_traverse_node_call_graph(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    
    # Functions
    repo.add_node("func-a", "Function", {"name": "func_a", "path": "app.py"})
    repo.add_node("func-b", "Function", {"name": "func_b", "path": "app.py"})
    repo.add_node("func-c", "Function", {"name": "func_c", "path": "app.py"})
    
    # Spring relationships: A -> calls -> B -> calls -> C
    repo.add_node("call-ab", "Call", {"name": "func_b", "path": "app.py"})
    repo.add_edge("func-a", "call-ab", "CALLS", {})
    repo.add_edge("call-ab", "func-b", "BELONGS_TO", {})
    
    repo.add_node("call-bc", "Call", {"name": "func_c", "path": "app.py"})
    repo.add_edge("func-b", "call-bc", "CALLS", {})
    repo.add_edge("call-bc", "func-c", "BELONGS_TO", {})
    
    service = GraphApplicationService(repo)
    
    # Traverse from func-a
    call_graph = service.traverse_node("func-a")
    
    assert len(call_graph.nodes) == 3
    node_ids = {n.id for n in call_graph.nodes}
    assert "func-a" in node_ids
    assert "func-b" in node_ids
    assert "func-c" in node_ids
    
    assert len(call_graph.edges) == 4 # 2 CALLS + 2 BELONGS_TO

def test_node_details_panel(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    
    repo.add_node("func-1", "Function", {"name": "login", "path": "auth.py", "start_line": 5, "end_line": 15})
    
    service = GraphApplicationService(repo)
    
    # Mock scanner report
    mock_sec = SecurityReport(
        repository_id="repo-1", critical_count=1, high_count=0, medium_count=0, low_count=0, info_count=0,
        security_score=60, findings=[
            SecurityFinding(
                id="fnd-critical", rule_id="eval-usage", severity="CRITICAL", file_path="auth.py",
                line_number=8, description="arbitrary execution", confidence="HIGH", code_snippet="", recommendation="Avoid eval"
            )
        ]
    )
    
    with patch.object(service.dead_detector, 'run_analysis') as mock_d_run, \
         patch.object(service.sec_service, 'run_security_scan', return_value=mock_sec) as mock_s_run:
         
        details = service.get_node_details("func-1", "repo-1")
        
        assert details.id == "func-1"
        assert details.name == "login"
        assert details.file_path == "auth.py"
        assert len(details.security_findings) == 1
        assert details.security_findings[0]["severity"] == "CRITICAL"
        assert details.security_findings[0]["line_number"] == 8
        assert details.dead_code is False
        
        # Verify ValueError if node doesn't exist
        with pytest.raises(ValueError, match="Node not found"):
            service.get_node_details("unknown-node", "repo-1")

def test_get_repository_graph_empty(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    service = GraphApplicationService(repo)
    res = service.get_repository_graph("nonexistent-repo")
    assert len(res.nodes) == 0
    assert len(res.edges) == 0

def test_get_repository_graph_exceptions_and_severities(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    repo.save_repository("repo-1", "my-repo", "/home/repo", "python", "2026-06-22T00:00:00Z", "hash")
    repo.add_node("repo-1", "Repository", {"name": "my-repo", "path": "/home/repo"})
    repo.add_node("file-1", "File", {"name": "main.py", "path": "main.py"})
    repo.add_edge("repo-1", "file-1", "CONTAINS", {})
    
    service = GraphApplicationService(repo)
    
    mock_sec = SecurityReport(
        repository_id="repo-1", critical_count=1, high_count=0, medium_count=1, low_count=1, info_count=0,
        security_score=40, findings=[
            SecurityFinding(id="f1", rule_id="r1", severity="CRITICAL", file_path="main.py", line_number=1, description="d1", confidence="HIGH", code_snippet="", recommendation="rec1"),
            SecurityFinding(id="f2", rule_id="r2", severity="MEDIUM", file_path="main.py", line_number=2, description="d2", confidence="HIGH", code_snippet="", recommendation="rec2"),
            SecurityFinding(id="f3", rule_id="r3", severity="LOW", file_path="main.py", line_number=3, description="d3", confidence="HIGH", code_snippet="", recommendation="rec3"),
        ]
    )
    
    with patch.object(service.dead_detector, 'run_analysis', side_effect=Exception("Dead code fail")), \
         patch.object(service.sec_service, 'run_security_scan', return_value=mock_sec):
         
        graph_response = service.get_repository_graph("repo-1")
        assert len(graph_response.nodes) == 2
        file1 = next(n for n in graph_response.nodes if n.id == "file-1")
        assert file1.security_score == 40

def test_expand_node_empty_and_missing_child(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    repo.add_node("file-1", "File", {"name": "main.py", "path": "main.py"})
    
    service = GraphApplicationService(repo)
    res1 = service.expand_node("file-1", "repo-1")
    assert len(res1.nodes) == 0
    
    repo.add_edge("file-1", "missing-child", "CONTAINS", {})
    res2 = service.expand_node("file-1", "repo-1")
    assert len(res2.nodes) == 0

def test_expand_node_security_deductions_and_calls(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    repo.add_node("file-1", "File", {"name": "main.py", "path": "main.py"})
    repo.add_node("func-1", "Function", {"name": "start", "path": "main.py", "start_line": 5, "end_line": 10})
    repo.add_node("func-2", "Function", {"name": "stop", "path": "main.py", "start_line": 15, "end_line": 20})
    repo.add_edge("file-1", "func-1", "CONTAINS", {})
    repo.add_edge("file-1", "func-2", "CONTAINS", {})
    repo.add_edge("func-1", "func-2", "CALLS", {})
    
    service = GraphApplicationService(repo)
    
    mock_sec = SecurityReport(
        repository_id="repo-1", critical_count=0, high_count=0, medium_count=1, low_count=0, info_count=0,
        security_score=85, findings=[
            SecurityFinding(id="f1", rule_id="r1", severity="MEDIUM", file_path="main.py", line_number=8, description="d1", confidence="HIGH", code_snippet="", recommendation="rec1"),
        ]
    )
    
    with patch.object(service.dead_detector, 'run_analysis', side_effect=Exception("Dead code fail")), \
         patch.object(service.sec_service, 'run_security_scan', return_value=mock_sec):
         
        res = service.expand_node("file-1", "repo-1")
        assert len(res.nodes) == 2
        f1_node = next(n for n in res.nodes if n.id == "func-1")
        assert f1_node.security_score == 85
        
        calls_edge = next(e for e in res.edges if e.relationship == "CALLS")
        assert calls_edge.source == "func-1"
        assert calls_edge.target == "func-2"

def test_traverse_node_missing_start(tmp_path):
    db_path = str(tmp_path / "test_gitty_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    service = GraphApplicationService(repo)
    res = service.traverse_node("nonexistent-func")
    assert len(res.nodes) == 0
    assert len(res.edges) == 0
