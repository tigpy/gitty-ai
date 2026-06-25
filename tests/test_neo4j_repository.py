import pytest
import json
from unittest.mock import MagicMock, patch
from services.graph_service.infrastructure.repositories.neo4j_graph_repository import Neo4jGraphRepository

class MockNode:
    def __init__(self, properties):
        self._properties = properties
    def __iter__(self):
        return iter(self._properties)
    def keys(self):
        return self._properties.keys()
    def get(self, key, default=None):
        return self._properties.get(key, default)
    def __getitem__(self, key):
        return self._properties[key]

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_create_database(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    
    repo = Neo4jGraphRepository()
    
    # Verify session run calls for create_database
    session = mock_driver.session.return_value
    assert session.run.call_count >= 4
    
    # Check that constraints/indexes are in calls
    run_calls = [c[0][0] for c in session.run.call_args_list]
    assert any("CONSTRAINT" in call for call in run_calls)

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_clear_database(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    repo = Neo4jGraphRepository()
    
    session = mock_driver.session.return_value
    session.run.reset_mock()
    
    repo.clear_database()
    session.run.assert_called_once_with("MATCH (n) DETACH DELETE n")

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_get_schema_summary(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    
    session = mock_driver.session.return_value
    
    # Mock return values for counts
    m1 = MagicMock()
    m1.single.return_value = {"c": 5}
    m2 = MagicMock()
    m2.single.return_value = {"c": 25}
    m3 = MagicMock()
    m3.single.return_value = {"c": 10}
    session.run.side_effect = [MagicMock(), MagicMock(), MagicMock(), MagicMock(), m1, m2, m3]
    
    repo = Neo4jGraphRepository()
    summary = repo.get_schema_summary()
    assert summary["repositories_count"] == 5
    assert summary["nodes_count"] == 25
    assert summary["edges_count"] == 10

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_save_repository(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    repo = Neo4jGraphRepository()
    
    session = mock_driver.session.return_value
    session.run.reset_mock()
    
    repo.save_repository("r1", "my-repo", "/home/repo", "python", "indexed_time", "hash123")
    
    args, kwargs = session.run.call_args
    assert "MERGE (r:Repository {id: $repo_id})" in args[0]
    assert kwargs["repo_id"] == "r1"
    assert kwargs["name"] == "my-repo"

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_add_get_node(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    repo = Neo4jGraphRepository()
    
    session = mock_driver.session.return_value
    session.run.reset_mock()
    
    # 1. Test add_node
    repo.add_node("n1", "File", {"name": "app.py", "path": "app.py", "custom_prop": True})
    args, kwargs = session.run.call_args
    assert "SET n:File" in args[0]
    assert kwargs["node_id"] == "n1"
    assert kwargs["props"]["custom_prop"] is True
    
    # 2. Test get_node
    mock_result = MagicMock()
    mock_node = MockNode({"id": "n1", "name": "app.py", "path": "app.py", "metadata": '{"custom_prop": true}'})
    mock_result.single.return_value = {"n": mock_node}
    session.run.return_value = mock_result
    
    node = repo.get_node("n1")
    assert node is not None
    assert node["name"] == "app.py"
    assert node["custom_prop"] is True

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_get_nodes_by_type(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    repo = Neo4jGraphRepository()
    
    session = mock_driver.session.return_value
    
    # Mock nodes by type return
    mock_node = MockNode({"id": "n1", "name": "app.py", "path": "app.py", "metadata": '{"custom_prop": true}'})
    mock_record = {"n": mock_node}
    session.run.return_value = [mock_record]
    
    nodes = repo.get_nodes_by_type("File")
    assert len(nodes) == 1
    assert nodes[0]["name"] == "app.py"

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_get_nodes_by_repository(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    repo = Neo4jGraphRepository()
    
    session = mock_driver.session.return_value
    
    # Mock nodes by repository return
    mock_node = MockNode({"id": "n1", "name": "app.py", "path": "app.py", "metadata": '{"custom_prop": true}'})
    mock_record = {"n": mock_node}
    session.run.return_value = [mock_record]
    
    nodes = repo.get_nodes_by_repository("repo-1")
    assert len(nodes) == 1
    assert nodes[0]["name"] == "app.py"

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_add_remove_edge(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    repo = Neo4jGraphRepository()
    
    session = mock_driver.session.return_value
    session.run.reset_mock()
    
    # 1. Add edge
    repo.add_edge("n1", "n2", "CONTAINS", {"weight": 1.0})
    args, kwargs = session.run.call_args
    assert "MERGE (a)-[r:CONTAINS]->(b)" in args[0]
    assert kwargs["from_id"] == "n1"
    assert kwargs["to_id"] == "n2"
    
    # 2. Remove edge
    session.run.reset_mock()
    repo.remove_edge("n1", "n2", "CALLS")
    args, kwargs = session.run.call_args
    assert "MATCH (a:Node {id: $from_id})-[r:CALLS]->(b:Node {id: $to_id})" in args[0]
    assert "DELETE r" in args[0]

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_get_inout_edges(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    repo = Neo4jGraphRepository()
    
    session = mock_driver.session.return_value
    
    # 1. Outbound edges
    session.run.return_value = [
        {"target_node": "n2", "relationship_type": "CONTAINS", "properties": {"weight": 1.0}}
    ]
    edges = repo.get_outbound_edges("n1")
    assert len(edges) == 1
    assert edges[0]["target_node"] == "n2"
    assert edges[0]["relationship_type"] == "CONTAINS"
    
    # 2. Inbound edges
    session.run.return_value = [
        {"source_node": "n2", "relationship_type": "CONTAINS", "properties": {"weight": 1.0}}
    ]
    edges = repo.get_inbound_edges("n1")
    assert len(edges) == 1
    assert edges[0]["source_node"] == "n2"

@patch("services.graph_service.infrastructure.repositories.neo4j_graph_repository.GraphDatabase")
def test_neo4j_traversals(mock_db):
    mock_driver = MagicMock()
    mock_db.driver.return_value = mock_driver
    repo = Neo4jGraphRepository()
    
    # Mock get_outbound_edges for n1 and n2
    # n1 -> n2, n2 -> n3
    m1 = [
        {"target_node": "n2", "relationship_type": "CONTAINS"}
    ]
    m2 = [
        {"target_node": "n3", "relationship_type": "CONTAINS"}
    ]
    
    with patch.object(repo, "get_outbound_edges") as mock_out:
        def side_effect(node_id):
            if node_id == "n1":
                return m1
            elif node_id == "n2":
                return m2
            return []
        mock_out.side_effect = side_effect
        
        bfs = repo.traverse_bfs("n1", edge_types=["CONTAINS"])
        assert bfs == ["n1", "n2", "n3"]
        
        dfs = repo.traverse_dfs("n1", edge_types=["CONTAINS"])
        assert dfs == ["n1", "n2", "n3"]
        
        path = repo.get_shortest_path("n1", "n3")
        assert path == ["n1", "n2", "n3"]
