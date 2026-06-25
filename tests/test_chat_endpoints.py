import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.chat import get_chat_service
from services.rag_service.domain.entities.chat_session import ChatSession, ChatMessage
from services.rag_service.domain.entities.retrieved_chunk import RetrievedChunk

class MockChatService:
    def create_session(self, repository_id: str):
        return ChatSession(
            session_id="mock-session-id",
            repository_id=repository_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            messages=[]
        )

    def get_session(self, session_id: str):
        if session_id == "unknown-session-id":
            return None
        return ChatSession(
            session_id=session_id,
            repository_id="test-repo",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            messages=[
                ChatMessage(
                    message_id="msg-1",
                    session_id=session_id,
                    role="user",
                    content="Hello",
                    timestamp=datetime.now(timezone.utc)
                ),
                ChatMessage(
                    message_id="msg-2",
                    session_id=session_id,
                    role="assistant",
                    content="Hi",
                    timestamp=datetime.now(timezone.utc),
                    citations=[
                        RetrievedChunk(
                            score=0.95,
                            file_path="jwt.py",
                            symbol_name="validator",
                            chunk_type="FUNCTION"
                        )
                    ]
                )
            ]
        )

    def list_sessions(self, repository_id=None):
        return [
            ChatSession(
                session_id="mock-session-id",
                repository_id=repository_id or "test-repo",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                messages=[]
            )
        ]

    def delete_session(self, session_id: str):
        pass

    def send_message(self, session_id: str, content: str, **kwargs):
        if session_id == "unknown-session-id":
            raise ValueError("Session not found")
        if session_id == "error-session-id":
            raise Exception("Internal database failure")
            
        return ChatMessage(
            message_id="msg-3",
            session_id=session_id,
            role="assistant",
            content="Answer content",
            timestamp=datetime.now(timezone.utc),
            citations=[
                RetrievedChunk(
                    score=0.99,
                    file_path="app.py",
                    symbol_name="auth",
                    chunk_type="FUNCTION"
                )
            ],
            metadata={
                "provider": "mock-provider",
                "model": "mock-model",
                "latency_ms": 100,
                "prompt_version": "v1"
            }
        )

@pytest.fixture
def override_chat():
    mock_service = MockChatService()
    app.dependency_overrides[get_chat_service] = lambda: mock_service
    yield
    app.dependency_overrides.pop(get_chat_service, None)

def test_api_create_session(override_chat):
    client = TestClient(app)
    response = client.post("/api/v1/chat/sessions", json={"repository_id": "test-repo"})
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "mock-session-id"
    assert data["repository_id"] == "test-repo"

def test_api_get_session_success(override_chat):
    client = TestClient(app)
    response = client.get("/api/v1/chat/sessions/mock-session-id")
    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["citations"][0]["file_path"] == "jwt.py"

def test_api_get_session_not_found(override_chat):
    client = TestClient(app)
    response = client.get("/api/v1/chat/sessions/unknown-session-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Chat session not found"

def test_api_list_sessions(override_chat):
    client = TestClient(app)
    response = client.get("/api/v1/chat/sessions?repository_id=test-repo")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_id"] == "mock-session-id"

def test_api_send_message_success(override_chat):
    client = TestClient(app)
    response = client.post("/api/v1/chat/sessions/mock-session-id/messages", json={
        "content": "Where is jwt?",
        "include_code": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert data["content"] == "Answer content"
    assert data["citations"][0]["file_path"] == "app.py"
    assert data["metadata"]["provider"] == "mock-provider"

def test_api_send_message_not_found(override_chat):
    client = TestClient(app)
    response = client.post("/api/v1/chat/sessions/unknown-session-id/messages", json={
        "content": "Where is jwt?"
    })
    assert response.status_code == 404

def test_api_send_message_error(override_chat):
    client = TestClient(app)
    response = client.post("/api/v1/chat/sessions/error-session-id/messages", json={
        "content": "Where is jwt?"
    })
    assert response.status_code == 500

def test_api_delete_session(override_chat):
    client = TestClient(app)
    response = client.delete("/api/v1/chat/sessions/mock-session-id")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
