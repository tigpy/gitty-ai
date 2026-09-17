import pytest
import tempfile
import os
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository

@pytest.fixture
def temp_graph_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_batch_graph.db")
    repo = SQLiteGraphRepository(db_path=db_path)
    yield repo
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(temp_dir)
    except Exception:
        pass

def test_add_nodes_and_edges_batch(temp_graph_db):
    repo = temp_graph_db
    repo_id = "test-batch-repo"
    
    # 1. Create repository
    repo.save_repository(
        repo_id=repo_id,
        name="batch-repo",
        root_path="/repos/batch-repo",
        language="python",
        indexed_at="2026-09-17T00:00:00Z",
        repo_hash="hash123"
    )

    # 2. Prepare 1,200 nodes
    node_count = 1200
    nodes_data = []
    edges_data = []
    
    # Root node for the repo
    nodes_data.append((repo_id, "REPOSITORY", {"name": "batch-repo", "path": "/"}))

    for i in range(1, node_count):
        node_id = f"node_{i}"
        nodes_data.append((
            node_id,
            "FUNCTION",
            {
                "name": f"func_{i}",
                "path": f"module_{i // 50}.py",
                "start_line": i * 10,
                "end_line": i * 10 + 9,
                "complexity": i % 5
            }
        ))
        # Edge from repo or previous node
        edges_data.append((repo_id, node_id, "CONTAINS", {"index": i}))

    # 3. Execute batch insertions
    repo.add_nodes_batch(nodes_data)
    repo.add_edges_batch(edges_data)

    # 4. Verify nodes retrieval via batched queries
    retrieved_nodes = repo.get_nodes_by_repository(repo_id)
    assert len(retrieved_nodes) == node_count
    
    # Verify metadata fields are preserved
    sample_node = next(n for n in retrieved_nodes if n["id"] == "node_42")
    assert sample_node["name"] == "func_42"
    assert sample_node["path"] == "module_0.py"
    assert sample_node["complexity"] == 2

def test_delete_repository_exceeding_variable_limit(temp_graph_db):
    repo = temp_graph_db
    repo_id = "large-delete-repo"
    
    repo.save_repository(
        repo_id=repo_id,
        name="large-repo",
        root_path="/repos/large",
        language="python",
        indexed_at="2026-09-17T00:00:00Z",
        repo_hash="hash456"
    )

    # Insert 1,500 nodes and edges (well above SQLite's legacy 999 parameter limit)
    node_count = 1500
    nodes_data = [(repo_id, "REPOSITORY", {"name": "large-repo", "path": "/"})]
    edges_data = []

    for i in range(1, node_count):
        node_id = f"large_node_{i}"
        nodes_data.append((node_id, "FUNCTION", {"name": f"f_{i}", "path": "large.py"}))
        edges_data.append((repo_id, node_id, "CONTAINS", {}))

    repo.add_nodes_batch(nodes_data)
    repo.add_edges_batch(edges_data)

    assert len(repo.get_nodes_by_repository(repo_id)) == node_count

    # Delete repository — this exercises chunked deletion in batches of 400
    repo.delete_repository(repo_id)

    # Verify repository and all nodes/edges are deleted
    assert repo.get_nodes_by_repository(repo_id) == []
    assert repo.get_node(repo_id) is None
    assert repo.get_node("large_node_1") is None
    assert repo.get_node(f"large_node_{node_count - 1}") is None
