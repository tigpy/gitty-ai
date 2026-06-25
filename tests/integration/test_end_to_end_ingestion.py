import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.repositories import generate_repo_id

def test_repo_id_generation():
    url = "https://github.com/pallets/flask.git"
    repo_id = generate_repo_id(url)
    assert repo_id.startswith("flask-")
    assert len(repo_id.split("-")[-1]) == 8

    url_no_git = "https://github.com/expressjs/express"
    repo_id_2 = generate_repo_id(url_no_git)
    assert repo_id_2.startswith("express-")

@patch("app.api.v1.repositories.celery_app.send_task")
@patch("app.api.v1.repositories.RepositoryCleanupService.cleanup")
def test_analyze_repository_endpoint(mock_cleanup, mock_send_task):
    client = TestClient(app)
    
    payload = {"url": "https://github.com/pallets/flask"}
    response = client.post("/api/v1/repositories/analyze", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "repository_id" in data
    assert data["status"] == "queued"
    
    # Celery task should be called
    mock_send_task.assert_called_once()
    args, kwargs = mock_send_task.call_args
    assert args[0] == "gitty.tasks.index_repository"
    assert kwargs["args"][0] == data["repository_id"]
    assert kwargs["args"][1] == "https://github.com/pallets/flask"

@patch("app.api.v1.repositories.RepositoryCleanupService.cleanup")
def test_delete_repository_endpoint(mock_cleanup):
    client = TestClient(app)
    
    response = client.delete("/api/v1/repositories/flask-a91f23de")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    mock_cleanup.assert_called_once_with("flask-a91f23de")

@patch("app.api.v1.repositories.redis.Redis")
def test_progress_stream_endpoint(mock_redis_class):
    # Set up mock redis pub/sub
    mock_redis = MagicMock()
    mock_pubsub = MagicMock()
    mock_redis_class.return_value = mock_redis
    mock_redis.pubsub.return_value = mock_pubsub
    
    # Queue up a progress log message then None to exit loop
    mock_pubsub.get_message.side_effect = [
        {"data": b'{"status": "processing", "message": "Cloning repository..."}'},
        {"data": b'{"status": "completed", "message": "Completed."}'},
        None
    ]
    
    client = TestClient(app)
    response = client.get("/api/v1/repositories/flask-a91f23de/progress")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    
    # Check that events are streamed in SSE format
    lines = response.text.strip().split("\n\n")
    assert len(lines) >= 3
    assert "Connecting live log stream..." in lines[0]
    assert "Cloning repository..." in lines[1]
    assert "Completed." in lines[2]
