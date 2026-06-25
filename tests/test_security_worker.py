import pytest
import os
from unittest.mock import MagicMock, patch
from libs.config import get_settings
from apps.worker.worker_app import analyze_repository_security, app

app.conf.task_always_eager = True

@patch("apps.worker.worker_app.build_vector_index")
@patch("apps.worker.worker_app.RabbitMQPublisher")
def test_worker_security_analysis_task(mock_publisher_cls, mock_build_vector_index, tmp_path):
    repo_dir = tmp_path / "worker_sec_repo"
    repo_dir.mkdir()
    
    f1 = repo_dir / "app.py"
    f1.write_text("""
def run():
    eval("1+1")
""", encoding="utf-8")
    
    settings = get_settings()
    
    mock_publisher = MagicMock()
    mock_publisher_cls.return_value = mock_publisher
    
    # Mock Repository node queries
    repo_id = "test-worker-sec-repo"
    
    # We patch SQLiteGraphRepository to return mock nodes pointing to our tmp_path repo
    with patch("apps.worker.worker_app.SQLiteGraphRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        
        mock_repo.get_nodes_by_repository.return_value = [
            {"type": "Repository", "id": repo_id, "name": "worker_sec", "path": str(repo_dir)},
            {"type": "File", "id": "app_file", "name": "app.py", "path": "app.py"}
        ]
        
        # Execute Celery worker task
        res = analyze_repository_security(repo_id)
        
        assert res["status"] == "completed"
        assert res["repository_id"] == repo_id
        assert res["findings_count"] == 1 # eval() call
        assert res["security_score"] == 90 # 100 - 10 (HIGH) = 90
