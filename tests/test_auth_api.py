import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import app
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository


@pytest.fixture
def api_client():
    return TestClient(app)


def test_repository_listing_works_without_authorization(api_client, tmp_path):
    """GET /api/v1/graph/repositories returns 200 without any Authorization header."""
    res = api_client.get("/api/v1/graph/repositories")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@patch("app.api.v1.repositories.celery_app.send_task")
def test_repository_analysis_accepted_without_authorization(mock_send, api_client):
    """POST /api/v1/repositories/analyze accepted without Authorization header."""
    res = api_client.post("/api/v1/repositories/analyze", json={"url": "https://8.8.8.8/sample/repo.git"})
    assert res.status_code == 200
    data = res.json()
    assert "repository_id" in data
    assert data["status"] == "queued"
    mock_send.assert_called_once()


def test_graph_data_access_works_without_authorization(api_client, tmp_path):
    """GET /api/v1/graph/repositories/{id}/data returns graph data without Authorization."""
    db_path = str(tmp_path / "test_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    repo.save_repository("repo-test-1", "sample", "/local/path", "python", "2026-01-01T00:00:00Z", "hash1")
    repo.add_node("repo-test-1", "Repository", {"name": "sample", "path": "/local/path"})

    with patch("app.api.v1.graph.get_graph_repository", return_value=repo):
        res = api_client.get("/api/v1/graph/repositories/repo-test-1/data")
        assert res.status_code == 200
        data = res.json()
        assert "nodes" in data
        assert "edges" in data


def test_rag_route_executes_without_authorization(api_client):
    """POST /api/v1/rag/query executes without Authorization header."""
    from app.api.v1.rag import get_rag_service
    from services.rag_service.domain.entities.rag_response import RAGResponse
    from services.rag_service.domain.entities.retrieved_chunk import RetrievedChunk

    mock_response = RAGResponse(
        answer="Found answer.",
        retrieved_chunks=[
            RetrievedChunk(score=0.9, file_path="main.py", symbol_name="run", chunk_type="FUNCTION")
        ],
        provider="mock-provider",
        model="mock-model",
        latency_ms=50
    )
    mock_service = MagicMock()
    mock_service.query_repository.return_value = mock_response

    app.dependency_overrides[get_rag_service] = lambda: mock_service
    try:
        res = api_client.post("/api/v1/rag/query", json={
            "repository_id": "test-repo",
            "question": "Where is the entrypoint?"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["answer"] == "Found answer."
    finally:
        app.dependency_overrides.pop(get_rag_service, None)


def test_chat_session_lifecycle_without_authorization(api_client):
    """Chat session creation, listing, retrieval, and deletion without Authorization."""
    # 1. Create session
    create_res = api_client.post("/api/v1/chat/sessions", json={"repository_id": "test-repo"})
    assert create_res.status_code == 200
    session_data = create_res.json()
    session_id = session_data["session_id"]
    assert session_id

    # 2. Get session
    get_res = api_client.get(f"/api/v1/chat/sessions/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["session_id"] == session_id

    # 3. List sessions
    list_res = api_client.get("/api/v1/chat/sessions?repository_id=test-repo")
    assert list_res.status_code == 200
    assert any(s["session_id"] == session_id for s in list_res.json())

    # 4. Delete session
    del_res = api_client.delete(f"/api/v1/chat/sessions/{session_id}")
    assert del_res.status_code == 200


def test_search_endpoints_work_without_authorization(api_client):
    """Search endpoints accept requests without Authorization."""
    with patch("app.api.v1.search.SemanticSearchService.search_semantic", return_value=[]), \
         patch("app.api.v1.search.SemanticSearchService.search_similar_code", return_value=[]), \
         patch("app.api.v1.search.SemanticSearchService.search_security_findings", return_value=[]):
        res1 = api_client.post("/api/v1/search/semantic", json={"repository_id": "repo-1", "query": "auth"})
        assert res1.status_code == 200

        res2 = api_client.post("/api/v1/search/similar", json={"repository_id": "repo-1", "code": "def run():"})
        assert res2.status_code == 200

        res3 = api_client.post("/api/v1/search/security", json={"repository_id": "repo-1", "query": "cve"})
        assert res3.status_code == 200


def test_auth_routes_no_longer_exist(api_client):
    """Authentication endpoints return 404 since they were completely removed."""
    res_reg = api_client.post("/api/v1/auth/register", json={"username": "alice", "email": "a@a.com", "password": "pwd"})
    assert res_reg.status_code == 404

    res_login = api_client.post("/api/v1/auth/login", json={"username": "alice", "password": "pwd"})
    assert res_login.status_code == 404

    res_me = api_client.get("/api/v1/auth/me")
    assert res_me.status_code == 404


def test_frontend_does_not_inject_authorization_header():
    """Verify frontend code does not store JWTs or inject Authorization headers."""
    api_ts_path = Path(__file__).resolve().parents[1] / "apps" / "frontend" / "src" / "services" / "api.ts"
    content = api_ts_path.read_text(encoding="utf-8")
    assert "Bearer" not in content
    assert "Authorization" not in content
    assert "gitty_access_token" not in content
    assert "login(" not in content
    assert "register(" not in content
