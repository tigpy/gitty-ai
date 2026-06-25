import pytest
import os
import shutil
import sqlite3
from unittest.mock import MagicMock, patch
from libs.config import get_settings
from apps.worker.worker_app import index_repository, app

app.conf.task_always_eager = True

@pytest.fixture
def clean_repo_data(tmp_path):
    # Setup mock repo directory
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    
    # Create simple python code files
    f1 = repo_dir / "user_service.py"
    f1.write_text("""
class UserService:
    def login(self, username):
        print("login", username)
""", encoding="utf-8")
    
    f2 = repo_dir / "auth.py"
    f2.write_text("""
from user_service import UserService
def authenticate():
    u = UserService()
    u.login("admin")
""", encoding="utf-8")

    yield str(repo_dir)
    
    # Cleanup target folders
    if os.path.exists("data/repos/test-worker-repo"):
        shutil.rmtree("data/repos/test-worker-repo", ignore_errors=True)

@patch("apps.worker.worker_app.detect_dead_code")
@patch("apps.worker.worker_app.GithubRepositoryScanner")
@patch("apps.worker.worker_app.RabbitMQPublisher")
def test_ingestion_worker_task(mock_publisher_cls, mock_scanner_cls, mock_detect_dead_code, clean_repo_data, tmp_path):
    settings = get_settings()
    
    # Configure mock scanner
    mock_scanner = MagicMock()
    mock_scanner_cls.return_value = mock_scanner
    
    def mock_clone(repo_url, dest_path):
        os.makedirs(dest_path, exist_ok=True)
        for f in os.listdir(clean_repo_data):
            shutil.copy(os.path.join(clean_repo_data, f), os.path.join(dest_path, f))
        return dest_path
        
    mock_scanner.clone_or_fetch.side_effect = mock_clone
    
    # Configure mock publisher
    mock_publisher = MagicMock()
    mock_publisher_cls.return_value = mock_publisher
    
    # Setup temporary SQLite DB path to keep test isolated
    original_db = settings.SQLITE_DB_PATH
    test_db = str(tmp_path / "worker_gitty_graph.db")
    settings.SQLITE_DB_PATH = test_db
    
    try:
        # Execute Celery worker task
        repo_id = "test-worker-repo"
        res = index_repository(repo_id, "https://github.com/mock/repo.git")
        
        # Verify execution status
        assert res["status"] == "completed"
        assert res["repository_id"] == repo_id
        assert res["nodes_created"] > 0
        assert res["edges_created"] > 0
        
        # Verify DB contents
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM repositories WHERE id = ?", (repo_id,))
        repo = cursor.fetchone()
        assert repo is not None
        assert repo[1] == "repo"
        
        cursor.execute("SELECT type, name FROM nodes")
        nodes = cursor.fetchall()
        node_types = {n[0] for n in nodes}
        assert "Repository" in node_types
        assert "File" in node_types
        assert "Class" in node_types
        assert "Function" in node_types
        assert "Import" in node_types
        assert "Call" in node_types
        
        conn.close()
        
    finally:
        # Restore configuration
        settings.SQLITE_DB_PATH = original_db

from apps.worker.worker_app import worker_health_check, generate_embeddings

def test_worker_health_check():
    res = worker_health_check()
    assert res == {"status": "ok", "worker": "gitty-worker"}

def test_generate_embeddings():
    res = generate_embeddings("test-repo")
    assert res == {"status": "completed", "repository_id": "test-repo"}

@patch("apps.worker.worker_app.GithubRepositoryScanner")
def test_ingestion_worker_scan_failure(mock_scanner_cls, tmp_path):
    mock_scanner = MagicMock()
    mock_scanner_cls.return_value = mock_scanner
    mock_scanner.clone_or_fetch.side_effect = Exception("Clone failed")

    res = index_repository("test-repo-fail", "https://github.com/mock/repo.git")
    assert res["status"] == "failed"
    assert "Scan failed" in res["error"]

@patch("apps.worker.worker_app.detect_dead_code")
@patch("apps.worker.worker_app.GithubRepositoryScanner")
@patch("apps.worker.worker_app.RabbitMQPublisher")
def test_ingestion_worker_publisher_init_failure(mock_publisher_cls, mock_scanner_cls, mock_detect_dead_code, clean_repo_data, tmp_path):
    mock_scanner = MagicMock()
    mock_scanner_cls.return_value = mock_scanner
    def mock_clone(repo_url, dest_path):
        os.makedirs(dest_path, exist_ok=True)
        return dest_path
    mock_scanner.clone_or_fetch.side_effect = mock_clone

    # publisher init raises exception
    mock_publisher_cls.side_effect = Exception("MQ Connection error")

    # This should still succeed because the exception in publisher init is caught
    settings = get_settings()
    original_db = settings.SQLITE_DB_PATH
    test_db = str(tmp_path / "worker_gitty_graph.db")
    settings.SQLITE_DB_PATH = test_db

    try:
        res = index_repository("test-worker-repo-mq-fail", "https://github.com/mock/repo.git")
        assert res["status"] == "completed"
    finally:
        settings.SQLITE_DB_PATH = original_db

@patch("apps.worker.worker_app.GithubRepositoryScanner")
@patch("apps.worker.worker_app.SQLiteGraphRepository")
@patch("apps.worker.worker_app.RabbitMQPublisher")
def test_ingestion_worker_graph_build_failure(mock_publisher_cls, mock_repo_cls, mock_scanner_cls, clean_repo_data, tmp_path):
    mock_scanner = MagicMock()
    mock_scanner_cls.return_value = mock_scanner
    def mock_clone(repo_url, dest_path):
        os.makedirs(dest_path, exist_ok=True)
        return dest_path
    mock_scanner.clone_or_fetch.side_effect = mock_clone

    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.save_repository.side_effect = Exception("DB error")

    # Mock publisher
    mock_publisher = MagicMock()
    mock_publisher_cls.return_value = mock_publisher

    res = index_repository("test-worker-repo-db-fail", "https://github.com/mock/repo.git")
    assert res["status"] == "failed"
    assert "Graph build failed" in res["error"]
