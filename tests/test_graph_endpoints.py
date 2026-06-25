import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.graph import get_graph_service
from services.graph_service.domain.entities.graph_entities import (
    GraphNode,
    GraphEdge,
    RepositoryGraphResponse,
    NodeDetailsResponse,
)

class MockGraphService:
    def get_repositories(self):
        return [{"id": "repo-1", "name": "my-repo", "path": "/home/repo"}]

    def get_repository_graph(self, repo_id: str):
        if repo_id == "error-repo":
            raise Exception("Graph load error")
        return RepositoryGraphResponse(
            nodes=[
                GraphNode(id="repo-1", label="my-repo", node_type="REPOSITORY"),
                GraphNode(id="file-1", label="main.py", node_type="FILE", file_path="main.py")
            ],
            edges=[
                GraphEdge(source="repo-1", target="file-1", relationship="CONTAINS")
            ]
        )

    def expand_node(self, node_id: str, repo_id: str):
        if repo_id == "error-repo":
            raise Exception("Expand error")
        return RepositoryGraphResponse(
            nodes=[
                GraphNode(id="func-1", label="start", node_type="FUNCTION", file_path="main.py")
            ],
            edges=[
                GraphEdge(source=node_id, target="func-1", relationship="CONTAINS")
            ]
        )

    def get_node_details(self, node_id: str, repo_id: str):
        if node_id == "unknown-node":
            raise ValueError("Node not found")
        if repo_id == "error-repo":
            raise Exception("Details error")
        return NodeDetailsResponse(
            id=node_id,
            type="FUNCTION",
            name="start",
            file_path="main.py",
            security_findings=[],
            dead_code=False,
            architecture_smell=False
        )

    def traverse_node(self, node_id: str):
        if node_id == "error-node":
            raise Exception("Traversal error")
        return RepositoryGraphResponse(
            nodes=[
                GraphNode(id="func-a", label="func_a", node_type="FUNCTION"),
                GraphNode(id="func-b", label="func_b", node_type="FUNCTION")
            ],
            edges=[
                GraphEdge(source="func-a", target="func-b", relationship="CALLS")
            ]
        )

@pytest.fixture
def override_graph():
    mock_service = MockGraphService()
    app.dependency_overrides[get_graph_service] = lambda: mock_service
    yield
    app.dependency_overrides.pop(get_graph_service, None)

def test_api_list_repositories(override_graph):
    client = TestClient(app)
    response = client.get("/api/v1/graph/repositories")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "my-repo"

def test_api_get_repository_graph_success(override_graph):
    client = TestClient(app)
    response = client.get("/api/v1/graph/repositories/repo-1/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 2
    assert data["nodes"][0]["node_type"] == "REPOSITORY"
    assert data["edges"][0]["relationship"] == "CONTAINS"

def test_api_get_repository_graph_failure(override_graph):
    client = TestClient(app)
    response = client.get("/api/v1/graph/repositories/error-repo/data")
    assert response.status_code == 500

def test_api_expand_node_success(override_graph):
    client = TestClient(app)
    response = client.get("/api/v1/graph/repositories/repo-1/expand/file-1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["node_type"] == "FUNCTION"

def test_api_get_node_details_success(override_graph):
    client = TestClient(app)
    response = client.get("/api/v1/graph/nodes/func-1?repo_id=repo-1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "func-1"
    assert data["type"] == "FUNCTION"

def test_api_get_node_details_not_found(override_graph):
    client = TestClient(app)
    response = client.get("/api/v1/graph/nodes/unknown-node?repo_id=repo-1")
    assert response.status_code == 404
    assert "Node not found" in response.json()["detail"]

def test_api_traverse_node_success(override_graph):
    client = TestClient(app)
    response = client.get("/api/v1/graph/nodes/func-a/traversal")
    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 2
    assert data["edges"][0]["relationship"] == "CALLS"

def test_api_traverse_node_failure(override_graph):
    client = TestClient(app)
    response = client.get("/api/v1/graph/nodes/error-node/traversal")
    assert response.status_code == 500
