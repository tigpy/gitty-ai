import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.search import get_search_service
from services.vector_service.domain.entities.search_result import SearchResult

class MockSearchService:
    def search_semantic(self, repo_id: str, query: str, limit: int):
        return [
            SearchResult(
                score=0.92,
                file_path="app.py",
                symbol_name="auth",
                chunk_type="FUNCTION",
                snippet="def auth(): pass"
            )
        ]

    def search_similar_code(self, repo_id: str, code: str, limit: int):
        return [
            SearchResult(
                score=0.88,
                file_path="helper.py",
                symbol_name="helper_func",
                chunk_type="FUNCTION",
                snippet="def helper_func(): pass"
            )
        ]

    def search_security_findings(self, repo_id: str, query: str, limit: int):
        return [
            SearchResult(
                score=0.95,
                file_path="vuln.py",
                symbol_name="HARDCODED_SECRET",
                chunk_type="SECURITY_FINDING",
                snippet="API_KEY = 'sk-123'"
            )
        ]

@pytest.fixture
def override_search():
    mock_service = MockSearchService()
    app.dependency_overrides[get_search_service] = lambda: mock_service
    yield
    app.dependency_overrides.pop(get_search_service, None)

def test_api_search_semantic(override_search):
    client = TestClient(app)
    response = client.post("/api/v1/search/semantic", json={
        "repository_id": "test-repo",
        "query": "JWT validation logic",
        "limit": 5
    })
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["score"] == 0.92
    assert data[0]["file_path"] == "app.py"
    assert data[0]["symbol_name"] == "auth"
    assert data[0]["chunk_type"] == "FUNCTION"
    assert data[0]["snippet"] == "def auth(): pass"

def test_api_search_similar(override_search):
    client = TestClient(app)
    response = client.post("/api/v1/search/similar", json={
        "repository_id": "test-repo",
        "code": "def custom(): pass",
        "limit": 5
    })
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["score"] == 0.88
    assert data[0]["file_path"] == "helper.py"
    assert data[0]["symbol_name"] == "helper_func"

def test_api_search_security(override_search):
    client = TestClient(app)
    response = client.post("/api/v1/search/security", json={
        "repository_id": "test-repo",
        "query": "credentials",
        "limit": 5
    })
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["score"] == 0.95
    assert data[0]["symbol_name"] == "HARDCODED_SECRET"
    assert data[0]["chunk_type"] == "SECURITY_FINDING"
