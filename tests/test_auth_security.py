import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import app
from libs.config import SystemSettings, INSECURE_NEO4J_PASSWORDS
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository


@pytest.fixture
def api_client():
    return TestClient(app)


def test_repository_url_ssrf_validation_still_enforced(api_client):
    """Removing authentication does NOT weaken URL validation; SSRF is still rejected."""
    blocked_urls = [
        "http://127.0.0.1/repo.git",
        "https://localhost/repo.git",
        "https://10.0.0.1/repo.git",
        "https://169.254.169.254/meta-data",
        "file:///etc/passwd",
        "http://0.0.0.0/repo.git",
    ]
    for url in blocked_urls:
        res = api_client.post("/api/v1/repositories/analyze", json={"url": url})
        assert res.status_code == 400, f"URL {url} should be rejected with 400"


def test_graph_repository_isolation_boundary_preserved(api_client, tmp_path):
    """
    Removing authentication does NOT weaken repository boundary isolation.
    A caller requesting a node that belongs to a different repository receives 403 Forbidden.
    """
    db_path = str(tmp_path / "iso_test_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)

    # Save repo A and node in repo A
    repo.save_repository("repo-a", "repo-a", "/path/a", "python", "2026-01-01T00:00:00Z", "hash-a")
    repo.add_node("repo-a", "Repository", {"name": "repo-a", "path": "/path/a"})
    repo.add_node("file-a", "File", {"name": "a.py", "path": "a.py"})
    repo.add_edge("repo-a", "file-a", "CONTAINS", {})

    # Save repo B and node in repo B
    repo.save_repository("repo-b", "repo-b", "/path/b", "python", "2026-01-01T00:00:00Z", "hash-b")
    repo.add_node("repo-b", "Repository", {"name": "repo-b", "path": "/path/b"})
    repo.add_node("file-b", "File", {"name": "b.py", "path": "b.py"})
    repo.add_edge("repo-b", "file-b", "CONTAINS", {})

    with patch("app.api.v1.graph.get_graph_repository", return_value=repo):
        # Accessing node file-b through repo-b succeeds
        res_ok = api_client.get("/api/v1/graph/repositories/repo-b/expand/file-b")
        assert res_ok.status_code == 200

        # Attempting to access node file-b through repo-a is rejected
        res_forbidden = api_client.get("/api/v1/graph/repositories/repo-a/expand/file-b")
        assert res_forbidden.status_code == 403
        assert "Forbidden: Node does not belong to the requested repository" in res_forbidden.json()["detail"]


def test_production_security_validates_neo4j_and_embeddings_without_requiring_jwt():
    """
    Production security validation continues to reject insecure Neo4j passwords
    and mock embedding providers, but no longer mandates JWT_SECRET_KEY or DEV_AUTH_BYPASS.
    """
    # 1. Valid production settings pass without JWT settings
    valid_prod = SystemSettings(
        ENV="production",
        NEO4J_PASSWORD="a-unique-production-neo4j-password-999",
        EMBEDDING_PROVIDER="sentence-transformers"
    )
    valid_prod.validate_production_security()  # Should not raise

    # 2. Insecure Neo4j password is still rejected
    with pytest.raises(ValueError, match="NEO4J_PASSWORD"):
        SystemSettings(
            ENV="production",
            NEO4J_PASSWORD="gitty_password",
            EMBEDDING_PROVIDER="sentence-transformers"
        ).validate_production_security()

    # 3. Mock embedding provider is still rejected in production
    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER=mock"):
        SystemSettings(
            ENV="production",
            NEO4J_PASSWORD="a-unique-production-neo4j-password-999",
            EMBEDDING_PROVIDER="mock"
        ).validate_production_security()


def test_no_runtime_auth_in_backend_code():
    """Verify backend runtime code contains no get_current_user or JWT dependencies."""
    project_root = Path(__file__).resolve().parents[1]
    api_gateway_app = project_root / "apps" / "api-gateway" / "app"

    forbidden_terms = [
        "get_current_user",
        "DEV_AUTH_BYPASS",
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "resolve_bearer_user_id",
        "assert_repository_owner",
        "assert_session_owner"
    ]

    for py_file in api_gateway_app.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in content, f"Found forbidden auth term '{term}' in runtime file {py_file}"
