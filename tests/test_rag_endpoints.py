import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.rag import get_rag_service
from services.rag_service.domain.entities.rag_response import RAGResponse
from services.rag_service.domain.entities.retrieved_chunk import RetrievedChunk

class MockRAGService:
    def query_repository(self, query):
        if query.repository_id == "error-repo":
            raise Exception("RAG execution failed error")
            
        return RAGResponse(
            answer="This is a mock RAG answer citation.",
            retrieved_chunks=[
                RetrievedChunk(
                    score=0.99,
                    file_path="app.py",
                    symbol_name="auth",
                    chunk_type="FUNCTION"
                )
            ],
            provider="mock-provider",
            model="mock-model",
            latency_ms=150
        )

@pytest.fixture
def override_rag():
    mock_service = MockRAGService()
    app.dependency_overrides[get_rag_service] = lambda: mock_service
    yield
    app.dependency_overrides.pop(get_rag_service, None)

def test_api_rag_query_success(override_rag):
    client = TestClient(app)
    response = client.post("/api/v1/rag/query", json={
        "repository_id": "test-repo",
        "question": "Show authentication implementation details.",
        "limit": 5,
        "include_code": True,
        "include_docs": True,
        "include_security": True
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "This is a mock RAG answer citation."
    assert len(data["retrieved_chunks"]) == 1
    assert data["retrieved_chunks"][0]["file_path"] == "app.py"
    assert data["provider"] == "mock-provider"
    assert data["model"] == "mock-model"
    assert data["latency_ms"] == 150

def test_api_rag_query_failure(override_rag):
    client = TestClient(app)
    response = client.post("/api/v1/rag/query", json={
        "repository_id": "error-repo",
        "question": "query"
    })
    
    assert response.status_code == 500
    data = response.json()
    assert "RAG query execution failed" in data["detail"]
