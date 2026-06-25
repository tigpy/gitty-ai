from typing import Dict, List, Any, Optional
from ...domain.repositories.graph_repository import IGraphRepository
from ...domain.repositories.node_repository import INodeRepository
from ...domain.repositories.edge_repository import IEdgeRepository
from ...domain.repositories.traversal_repository import ITraversalRepository

class MockGraphRepository(IGraphRepository):
    def create_database(self) -> None:
        pass
    def clear_database(self) -> None:
        pass
    def get_schema_summary(self) -> Dict[str, Any]:
        return {"nodes": 0, "edges": 0}

class MockNodeRepository(INodeRepository):
    def add_node(self, node_id: str, label: str, properties: Dict[str, Any]) -> None:
        pass
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return None
    def remove_node(self, node_id: str) -> None:
        pass
    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        return []
    def get_nodes_by_repository(self, repo_id: str) -> List[Dict[str, Any]]:
        return []

class MockEdgeRepository(IEdgeRepository):
    def add_edge(self, from_id: str, to_id: str, edge_type: str, properties: Dict[str, Any]) -> None:
        pass
    def remove_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        pass
    def get_outbound_edges(self, node_id: str) -> List[Dict[str, Any]]:
        return []
    def get_inbound_edges(self, node_id: str) -> List[Dict[str, Any]]:
        return []

class MockTraversalRepository(ITraversalRepository):
    def traverse_bfs(self, start_id: str, edge_types: List[str]) -> List[str]:
        return []
    def traverse_dfs(self, start_id: str, edge_types: List[str]) -> List[str]:
        return []
    def get_shortest_path(self, start_id: str, end_id: str) -> List[str]:
        return []
