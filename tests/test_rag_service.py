import pytest
from unittest.mock import MagicMock, patch
from services.rag_service.application.services.rag_service import RAGService
from services.rag_service.domain.entities.rag_query import RAGQuery
from services.vector_service.domain.value_objects.chunk import Chunk
from services.vector_service.domain.entities.search_result import SearchResult

from typing import Any

class MockEventBus:
    def __init__(self):
        self.published = []

    def publish(self, topic: str, event: Any) -> None:
        self.published.append((topic, event))


def test_rag_service_success_flow():
    # 1. Mock search service
    search_service = MagicMock()
    
    mock_chunk = Chunk(
        id="c1",
        text="def authenticate(): pass",
        chunk_type="FUNCTION",
        metadata={"file_path": "auth.py", "symbol_name": "authenticate"},
        content_hash="h1",
        version=1,
        start_line=1,
        end_line=2
    )
    search_service.retrieve_context.return_value = [mock_chunk]
    
    mock_sec_result = SearchResult(
        score=0.9,
        file_path="auth.py",
        symbol_name="eval_rule",
        chunk_type="SECURITY_FINDING",
        snippet="eval('1+1')"
    )
    search_service.search_security_findings.return_value = [mock_sec_result]
    
    # 2. Mock LLM Provider
    llm_provider = MagicMock()
    llm_provider.provider_name = "mock-llm"
    llm_provider.model_name = "mock-model"
    llm_provider.generate.return_value = "Retrieved answer explanation."
    
    # 3. Event publisher
    publisher = MockEventBus()
    
    # Initialize RAG service
    service = RAGService(
        search_service=search_service,
        llm_provider=llm_provider,
        publisher=publisher
    )
    
    # Run query
    query = RAGQuery(
        repository_id="test-repo",
        question="How is auth handled?",
        include_code=True,
        include_docs=True,
        include_security=True
    )
    
    response = service.query_repository(query)
    
    assert response.answer == "Retrieved answer explanation."
    assert response.provider == "mock-llm"
    assert response.model == "mock-model"
    assert len(response.retrieved_chunks) == 2 # 1 code/doc chunk, 1 security finding chunk
    assert response.retrieved_chunks[0].file_path == "auth.py"
    assert response.retrieved_chunks[1].chunk_type == "SECURITY_FINDING"
    
    # Verify events
    topics = [t for t, e in publisher.published]
    assert "rag.question_asked" in topics
    assert "rag.answer_generated" in topics
    
    asked_event = next(e for t, e in publisher.published if t == "rag.question_asked")
    assert asked_event.repository_id == "test-repo"
    assert asked_event.question == "How is auth handled?"
    
    gen_event = next(e for t, e in publisher.published if t == "rag.answer_generated")
    assert gen_event.answer == "Retrieved answer explanation."
    assert gen_event.latency_ms >= 0

def test_rag_service_flags_filtering():
    search_service = MagicMock()
    mock_chunk = Chunk(
        id="c1",
        text="def authenticate(): pass",
        chunk_type="FUNCTION",
        metadata={"file_path": "auth.py"},
        content_hash="h1",
        version=1
    )
    search_service.retrieve_context.return_value = [mock_chunk]
    search_service.search_security_findings.return_value = []
    
    llm_provider = MagicMock()
    llm_provider.provider_name = "mock-llm"
    llm_provider.model_name = "mock-model"
    llm_provider.generate.return_value = "Mock answer"
    
    service = RAGService(search_service=search_service, llm_provider=llm_provider)
    
    # exclude_code = True but include_code = False in query
    query = RAGQuery(
        repository_id="test-repo",
        question="query",
        include_code=False,  # exclude code chunks
        include_docs=True,
        include_security=False
    )
    
    response = service.query_repository(query)
    assert len(response.retrieved_chunks) == 0 # Function chunk filtered out

def test_rag_service_failure_event():
    search_service = MagicMock()
    search_service.retrieve_context.side_effect = Exception("Retrieval timeout")
    
    llm_provider = MagicMock()
    llm_provider.provider_name = "mock-llm"
    llm_provider.model_name = "mock-model"
    publisher = MockEventBus()
    
    service = RAGService(
        search_service=search_service,
        llm_provider=llm_provider,
        publisher=publisher
    )
    
    query = RAGQuery(repository_id="test-repo", question="query")
    
    with pytest.raises(Exception, match="Retrieval timeout"):
        service.query_repository(query)
        
    # Verify failed event published
    topics = [t for t, e in publisher.published]
    assert "rag.question_asked" in topics
    assert "rag.answer_failed" in topics
    
    failed_event = next(e for t, e in publisher.published if t == "rag.answer_failed")
    assert failed_event.repository_id == "test-repo"
    assert "Retrieval timeout" in failed_event.reason
