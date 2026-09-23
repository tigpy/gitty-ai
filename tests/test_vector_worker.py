import pytest
import os
from unittest.mock import MagicMock, patch
from libs.config import get_settings
from apps.worker.worker_app import build_vector_index, app
from services.vector_service.infrastructure.vector_store.qdrant_repository import QdrantRepository
from services.vector_service.infrastructure.embeddings.sentence_transformer_provider import MockEmbeddingProvider

app.conf.task_always_eager = True

@patch("apps.worker.worker_app.RabbitMQPublisher")
@patch("services.vector_service.infrastructure.vector_store.qdrant_repository.QdrantRepository")
@patch("services.vector_service.infrastructure.embeddings.provider_factory.build_embedding_provider")
def test_worker_build_vector_index_task(
    mock_provider_cls,
    mock_qdrant_repo_cls,
    mock_publisher_cls,
    tmp_path
):
    # Set up mock repository directory
    repo_dir = tmp_path / "mock_vector_repo"
    repo_dir.mkdir()
    
    # Create simple python code files
    f1 = repo_dir / "app.py"
    f1.write_text("""
def calculate(a, b):
    # A dangerous eval
    eval("a + b")
    return a + b
""", encoding="utf-8")

    readme = repo_dir / "README.md"
    readme.write_text("# Mock Repository\nThis repository is for testing vector worker tasks.", encoding="utf-8")

    settings = get_settings()
    
    # Mock publisher
    mock_publisher = MagicMock()
    mock_publisher_cls.return_value = mock_publisher
    
    # Use real in-memory QdrantRepository and mock provider for SentenceTransformer
    mock_qdrant_repo_cls.return_value = QdrantRepository(in_memory=True, vector_size=384)
    mock_provider_cls.return_value = MockEmbeddingProvider(dimensions=384, model_name="unit-test-mock")
    
    # Setup temporary SQLite DB path to keep test isolated
    original_db = settings.SQLITE_DB_PATH
    test_db = str(tmp_path / "worker_vector_graph.db")
    settings.SQLITE_DB_PATH = test_db
    
    # Setup SQLite Graph Repository mock
    repo_id = "test-vector-worker-repo"
    
    with patch("apps.worker.worker_app.publish_progress") as mock_progress:
        with patch("apps.worker.worker_app.get_graph_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_get_repo.return_value = mock_repo
            
            mock_repo.get_nodes_by_repository.return_value = [
                {"type": "Repository", "id": repo_id, "name": "mock_vector_repo", "path": str(repo_dir)},
                {"type": "File", "id": "file_node_1", "name": "app.py", "path": "app.py"},
                {"type": "Function", "id": "func_node_1", "name": "calculate", "path": "app.py", "metadata": {"start_line": 2, "end_line": 5}},
                {"type": "File", "id": "file_node_2", "name": "README.md", "path": "README.md"}
            ]
            
            try:
                # Execute Celery worker task
                res = build_vector_index(repo_id)
                
                assert res["status"] == "completed"
                assert res["repository_id"] == repo_id
                
                # The indexing stats returned should contain function, file, documentation, and security chunks
                # 2 files (app.py, README.md), 1 function (calculate), 1 documentation (README.md), 1 security (eval issue)
                assert res["vector_count"] == 5
                
                # Verify progress publisher was notified
                assert mock_progress.called
                statuses = [args[1] for args, _ in mock_progress.call_args_list]
                assert "completed" in statuses
            finally:
                # Restore configuration
                settings.SQLITE_DB_PATH = original_db
