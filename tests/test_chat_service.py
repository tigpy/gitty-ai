import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from services.rag_service.application.services.chat_service import ChatService
from services.rag_service.infrastructure.persistence.sqlite_session_repository import SQLiteChatSessionRepository
from services.rag_service.domain.entities.chat_session import ChatSession, ChatMessage
from services.vector_service.domain.value_objects.chunk import Chunk
from libs.config import SystemSettings, get_settings

class MockEventBus:
    def __init__(self):
        self.published = []

    def publish(self, topic: str, event: any) -> None:
        self.published.append((topic, event))

def test_chat_service_complete_lifecycle(tmp_path):
    # 1. Setup SQLite repo with temp database path
    db_path = str(tmp_path / "test_chat.db")
    session_repo = SQLiteChatSessionRepository(db_path=db_path)
    
    # 2. Setup mock search service
    search_service = MagicMock()
    mock_chunk = Chunk(
        id="chunk-1",
        text="class JWTValidator:\n    def validate(self): pass",
        chunk_type="CLASS",
        metadata={"file_path": "jwt.py", "symbol_name": "JWTValidator"},
        content_hash="h1",
        version=1,
        start_line=1,
        end_line=5
    )
    search_service.retrieve_context.return_value = [mock_chunk]
    search_service.search_security_findings.return_value = []
    
    # 3. Setup mock LLM
    llm_provider = MagicMock()
    llm_provider.provider_name = "mock-provider"
    llm_provider.model_name = "mock-model"
    llm_provider.generate.return_value = "This is the answer."
    
    # 4. Setup mock publisher
    publisher = MockEventBus()
    
    # 5. Initialize ChatService
    service = ChatService(
        search_service=search_service,
        session_repo=session_repo,
        llm_provider=llm_provider,
        publisher=publisher
    )
    
    # Create session
    session = service.create_session(repository_id="test-repo")
    assert session.session_id is not None
    assert session.repository_id == "test-repo"
    
    # Check start event
    assert len(publisher.published) == 1
    assert publisher.published[0][0] == "chat.started"
    assert publisher.published[0][1].session_id == session.session_id
    
    # First turn
    user_q1 = "Where is JWT validation implemented?"
    reply1 = service.send_message(session_id=session.session_id, content=user_q1)
    
    assert reply1.role == "assistant"
    assert reply1.content == "This is the answer."
    assert len(reply1.citations) == 1
    assert reply1.citations[0].file_path == "jwt.py"
    assert reply1.metadata["provider"] == "mock-provider"
    assert reply1.metadata["model"] == "mock-model"
    
    # Check message events: 1 start + 1 user msg + 1 context retrieval + 1 assistant msg
    topics = [t for t, _ in publisher.published]
    assert "chat.started" in topics
    assert "chat.message_added" in topics
    assert "chat.context_retrieved" in topics
    
    # Verify the saved database records
    db_session = service.get_session(session.session_id)
    assert len(db_session.messages) == 2
    assert db_session.messages[0].role == "user"
    assert db_session.messages[0].content == user_q1
    assert db_session.messages[1].role == "assistant"
    assert db_session.messages[1].content == "This is the answer."
    assert len(db_session.messages[1].citations) == 1
    
    # Second turn (follow-up query)
    user_q2 = "Show me the validate function."
    
    # We patch PromptBuilder's build_chat_prompt to capture the history argument passed to it
    with patch.object(service.prompt_builder, 'build_chat_prompt', wraps=service.prompt_builder.build_chat_prompt) as mock_build:
        reply2 = service.send_message(session_id=session.session_id, content=user_q2)
        
        mock_build.assert_called_once()
        call_kwargs = mock_build.call_args[1]
        history_passed = call_kwargs["history"]
        
        # Verify the history passed contains the previous turn (user q1 and assistant reply1)
        assert len(history_passed) == 2
        assert history_passed[0].content == user_q1
        assert history_passed[1].content == "This is the answer."
        
    # Test delete session
    service.delete_session(session.session_id)
    assert service.get_session(session.session_id) is None
    assert publisher.published[-1][0] == "chat.ended"

def test_chat_history_clamping(tmp_path):
    db_path = str(tmp_path / "test_chat_clamping.db")
    session_repo = SQLiteChatSessionRepository(db_path=db_path)
    search_service = MagicMock()
    search_service.retrieve_context.return_value = []
    search_service.search_security_findings.return_value = []
    
    llm_provider = MagicMock()
    llm_provider.provider_name = "mock"
    llm_provider.model_name = "mock-model"
    llm_provider.generate.return_value = "Answer"
    
    settings = get_settings()
    # Explicitly set limit to 2 for testing clamping
    settings.CHAT_HISTORY_LIMIT = 2
    
    service = ChatService(
        search_service=search_service,
        session_repo=session_repo,
        llm_provider=llm_provider
    )
    
    session = service.create_session(repository_id="test-repo")
    
    # Add multiple messages to build history
    service.send_message(session_id=session.session_id, content="Q1") # turn 1
    service.send_message(session_id=session.session_id, content="Q2") # turn 2
    
    with patch.object(service.prompt_builder, 'build_chat_prompt', wraps=service.prompt_builder.build_chat_prompt) as mock_build:
        service.send_message(session_id=session.session_id, content="Q3")
        
        history_passed = mock_build.call_args[1]["history"]
        # History is clamped to CHAT_HISTORY_LIMIT = 2 messages
        assert len(history_passed) == 2
        assert history_passed[0].content == "Q2"
        assert history_passed[1].content == "Answer"

from contextlib import contextmanager

def test_chat_list_sessions_and_failures(tmp_path):
    db_path = str(tmp_path / "test_failures.db")
    session_repo = SQLiteChatSessionRepository(db_path=db_path)
    search_service = MagicMock()
    search_service.retrieve_context.return_value = []
    search_service.search_security_findings.return_value = []
    
    llm_provider = MagicMock()
    llm_provider.provider_name = "mock"
    llm_provider.model_name = "mock-model"
    llm_provider.generate.return_value = "Answer"
    
    # 1. Event Publisher that throws exceptions to cover catch blocks in ChatService
    bad_publisher = MagicMock()
    bad_publisher.publish.side_effect = Exception("Message bus down")
    
    service = ChatService(
        search_service=search_service,
        session_repo=session_repo,
        llm_provider=llm_provider,
        publisher=bad_publisher
    )
    
    # Verify starting a session catches message bus exceptions
    session = service.create_session(repository_id="test-repo")
    assert session.session_id is not None
    
    # Verify sending message catches message bus exceptions
    msg = service.send_message(session_id=session.session_id, content="What is auth?")
    assert msg.content == "Answer"
    
    # Verify list sessions works with and without filter
    sessions_all = service.list_sessions()
    assert len(sessions_all) == 1
    assert sessions_all[0].session_id == session.session_id
    
    sessions_filtered = service.list_sessions("test-repo")
    assert len(sessions_filtered) == 1
    
    sessions_empty = service.list_sessions("non-existent-repo")
    assert len(sessions_empty) == 0
    
    # Verify session not found ValueError
    with pytest.raises(ValueError, match="Chat session not found"):
        service.send_message(session_id="unknown-session", content="query")
        
    # Verify deleting session catches publisher exceptions
    service.delete_session(session.session_id)
    assert service.get_session(session.session_id) is None

def test_sqlite_repository_rollback(tmp_path):
    db_path = str(tmp_path / "test_rollback.db")
    session_repo = SQLiteChatSessionRepository(db_path=db_path)
    
    # Force connection error to trigger transaction rollback coverage in repository
    with patch.object(session_repo, '_get_connection') as mock_conn:
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Write error")
        mock_db.cursor.return_value = mock_cursor
        
        # This makes _get_connection yield mock_db
        @contextmanager
        def mock_get_conn_ctx():
            try:
                yield mock_db
                mock_db.commit()
            except Exception:
                mock_db.rollback()
                raise
            finally:
                mock_db.close()
                
        mock_conn.side_effect = mock_get_conn_ctx
        
        session = ChatSession(
            session_id="test-id",
            repository_id="repo-id",
            messages=[]
        )
        with pytest.raises(Exception, match="Write error"):
            session_repo.create_session(session)
            
        mock_db.rollback.assert_called_once()
