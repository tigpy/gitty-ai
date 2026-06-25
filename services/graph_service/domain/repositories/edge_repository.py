from abc import ABC, abstractmethod
from typing import List, Dict, Any

class IEdgeRepository(ABC):
    @abstractmethod
    def add_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        properties: Dict[str, Any]
    ) -> None:
        """Adds or updates an edge between two nodes."""
        pass

    @abstractmethod
    def remove_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        """Removes a specific edge between two nodes."""
        pass

    @abstractmethod
    def get_outbound_edges(self, node_id: str) -> List[Dict[str, Any]]:
        """Gets all outgoing edges for a given node."""
        pass

    @abstractmethod
    def get_inbound_edges(self, node_id: str) -> List[Dict[str, Any]]:
        """Gets all incoming edges for a given node."""
        pass
