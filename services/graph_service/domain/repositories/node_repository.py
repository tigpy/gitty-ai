from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class INodeRepository(ABC):
    @abstractmethod
    def add_node(self, node_id: str, label: str, properties: Dict[str, Any]) -> None:
        """Adds or updates a node in the graph."""
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a node with its properties."""
        pass

    @abstractmethod
    def remove_node(self, node_id: str) -> None:
        """Removes a node and its adjacent edges."""
        pass

    @abstractmethod
    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """Retrieves all nodes of a given type/label."""
        pass

    @abstractmethod
    def get_nodes_by_repository(self, repo_id: str) -> List[Dict[str, Any]]:
        """Retrieves all nodes belonging to a repository."""
        pass
