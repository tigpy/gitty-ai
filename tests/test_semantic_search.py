import os
import pytest
from unittest.mock import MagicMock, patch
from services.vector_service.application.services.chunking_service import ChunkingService
from services.vector_service.application.services.embedding_service import EmbeddingService
from services.vector_service.application.services.indexing_service import IndexingService
from services.vector_service.application.services.semantic_search_service import SemanticSearchService
from services.vector_service.infrastructure.embeddings.sentence_transformer_provider import SentenceTransformerProvider
from services.vector_service.infrastructure.vector_store.qdrant_repository import QdrantRepository

from typing import Any

class MockEventBus:
    def __init__(self):
        self.published = []

    def publish(self, topic: str, event: Any) -> None:
        self.published.append((topic, event))


def test_indexing_and_semantic_search(tmp_path):
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    
    # Python file
    f = repo_dir / "app.py"
    f.write_text("def auth():\n    return 'success'\n", encoding="utf-8")
    
    # README
    readme = repo_dir / "README.md"
    readme.write_text("# Doc\nSome text\n", encoding="utf-8")

    # SQLite repository mock
    sqlite_repo = MagicMock()
    repo_id = "test-repo-1"
    sqlite_repo.get_nodes_by_repository.return_value = [
        {"type": "Repository", "id": repo_id, "name": "mock_repo", "path": str(repo_dir)},
        {"type": "File", "id": "f1_node", "name": "app.py", "path": "app.py"},
        {"type": "Function", "id": "func_node", "name": "auth", "path": "app.py", "metadata": {"start_line": 1, "end_line": 2}}
    ]

    # In-memory Qdrant repository
    vector_repo = QdrantRepository(in_memory=True, vector_size=384)
    provider = SentenceTransformerProvider(force_mock=True)
    embedding_service = EmbeddingService(provider, cache=None)
    chunking_service = ChunkingService()
    
    publisher = MockEventBus()
    
    # 1. IndexingService
    indexing_service = IndexingService(
        sqlite_repo=sqlite_repo,
        vector_repo=vector_repo,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        publisher=publisher
    )
    
    res = indexing_service.index_repository(repo_id)
    assert res["vector_count"] == 3 # 1 function, 1 file, 1 README doc
    assert res["function_chunks"] == 1
    assert res["documentation_chunks"] == 1
    
    # Verify events
    topics = [t for t, e in publisher.published]
    assert "vector.embedding_created" in topics
    assert "vector.index_built" in topics
    
    built_event = next(e for t, e in publisher.published if t == "vector.index_built")
    assert built_event.function_chunks == 1
    assert built_event.vector_count == 3
    
    # 2. SemanticSearchService
    search_service = SemanticSearchService(
        vector_repo=vector_repo,
        embedding_service=embedding_service,
        publisher=publisher
    )
    
    # Test semantic search (merges code & doc)
    results = search_service.search_semantic(repo_id, "authentication query", limit=5)
    assert len(results) > 0
    assert results[0].snippet in ("def auth():\n    return 'success'\n", "# Doc\nSome text\n")
    assert results[0].score >= 0.65
    
    assert "vector.search_completed" in [t for t, e in publisher.published]
    
    # Test similar code search
    similar_results = search_service.search_similar_code(repo_id, "def auth(): pass")
    assert len(similar_results) > 0
    
    # Test retrieve context (for Phase 7 RAG)
    chunks = search_service.retrieve_context(repo_id, "auth", limit=5)
    assert chunks[0].text is not None
    assert chunks[0].chunk_type in ("FUNCTION", "DOCUMENTATION")

    # Test security findings search
    from services.vector_service.domain.entities.vector_document import VectorDocument
    vector_repo.upsert_documents([
        VectorDocument(
            id="00000000-0000-0000-0000-000000000100",
            vector=provider.embed("eval issue"),
            payload={
                "repository_id": repo_id,
                "file_path": "app.py",
                "chunk_type": "SECURITY_FINDING",
                "symbol_name": "eval_rule",
                "text_content": "Severity: HIGH, Rule: eval_rule"
            }
        )
    ], "repository_security_chunks")
    
    sec_results = search_service.search_security_findings(repo_id, "eval", limit=5)
    assert len(sec_results) > 0
    assert sec_results[0].symbol_name == "eval_rule"

def test_indexing_service_security_scan_failure(tmp_path):
    repo_id = "test-fail-sec-repo"
    sqlite_repo = MagicMock()
    # Mock Repository node
    sqlite_repo.get_nodes_by_repository.return_value = [
        {"type": "Repository", "id": repo_id, "name": "mock_repo", "path": str(tmp_path)}
    ]
    
    # We patch run_security_scan to raise an Exception
    with patch("services.vector_service.application.services.indexing_service.SecurityAnalysisService") as mock_sec_service_cls:
        mock_sec_service = MagicMock()
        mock_sec_service.run_security_scan.side_effect = Exception("Security Scan failed")
        mock_sec_service_cls.return_value = mock_sec_service
        
        vector_repo = MagicMock()
        chunking_service = MagicMock()
        embedding_service = MagicMock()
        
        indexing_service = IndexingService(
            sqlite_repo=sqlite_repo,
            vector_repo=vector_repo,
            chunking_service=chunking_service,
            embedding_service=embedding_service
        )
        
        # This should complete successfully and catch the exception internally, setting findings = []
        res = indexing_service.index_repository(repo_id)
        assert res["repository_id"] == repo_id
        
        # Verify generate_chunks was called with empty security findings
        chunking_service.generate_chunks.assert_called_once_with(
            nodes=sqlite_repo.get_nodes_by_repository.return_value,
            repo_id=repo_id,
            repo_name="mock_repo",
            repo_path=str(tmp_path),
            security_findings=[]
        )


