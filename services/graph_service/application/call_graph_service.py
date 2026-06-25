from typing import List, Dict, Any, Set
from libs.graph.algorithms.bfs import bfs_traverse

class CallGraphService:
    def __init__(self, repository: Any):
        self.repository = repository

    def get_called_functions(self, func_id: str) -> List[str]:
        """Finds all functions called directly by the given function."""
        edges = self.repository.get_outbound_edges(func_id)
        call_nodes = [e["target_node"] for e in edges if e["relationship_type"] == "CALLS"]
        
        called = []
        for c_id in call_nodes:
            c_edges = self.repository.get_outbound_edges(c_id)
            for ce in c_edges:
                if ce["relationship_type"] == "BELONGS_TO":
                    called.append(ce["target_node"])
        return list(set(called))

    def get_calling_functions(self, func_id: str) -> List[str]:
        """Finds all functions that directly call the given function."""
        edges = self.repository.get_inbound_edges(func_id)
        call_nodes = [e["source_node"] for e in edges if e["relationship_type"] == "BELONGS_TO"]
        
        callers = []
        for c_id in call_nodes:
            c_edges = self.repository.get_inbound_edges(c_id)
            for ce in c_edges:
                if ce["relationship_type"] == "CALLS":
                    callers.append(ce["source_node"])
        return list(set(callers))

    def find_call_chain(self, start_function_id: str, max_depth: int = 5) -> Dict[str, Any]:
        """
        Builds a call chain tree up to a maximum depth.
        Returns a tree structure representing call paths.
        """
        def build_tree(func_id: str, current_depth: int) -> Dict[str, Any]:
            node_info = self.repository.get_node(func_id) or {"id": func_id, "name": func_id}
            if current_depth >= max_depth:
                return {"node": node_info, "calls": []}
                
            callees = self.get_called_functions(func_id)
            return {
                "node": node_info,
                "calls": [build_tree(c, current_depth + 1) for c in callees]
            }
            
        return build_tree(start_function_id, 0)

    def find_all_reachable_callers(self, function_id: str) -> List[str]:
        """
        Finds all functions that can transitively call this function.
        """
        return bfs_traverse(function_id, self.get_calling_functions)
