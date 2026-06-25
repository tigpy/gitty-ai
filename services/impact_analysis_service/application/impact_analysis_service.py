from typing import Dict, List, Any, Set
from services.graph_service.application.call_graph_service import CallGraphService
from services.graph_service.application.dependency_traversal_service import DependencyTraversalService

class ImpactAnalysisService:
    def __init__(self, repository: Any):
        self.repository = repository
        self.call_service = CallGraphService(repository)
        self.dep_service = DependencyTraversalService(repository)

    def calculate_blast_radius(self, changed_node_id: str, repo_id: str) -> Dict[str, Any]:
        """
        Calculates the blast radius of a changed node (File, Class, or Function).
        Returns a summary of impacted nodes, their properties, and distance from change.
        """
        changed_node = self.repository.get_node(changed_node_id)
        if not changed_node:
            return {
                "changed_component": None,
                "impacted_components": {},
                "total_impact_count": 0
            }
            
        node_type = changed_node.get("type")
        
        # Build dependents adjacency list
        dependents: Dict[str, Set[str]] = {}
        
        # Get all nodes in repo
        nodes = self.repository.get_nodes_by_repository(repo_id)
        
        if node_type == "Function":
            for n in nodes:
                if n["type"] == "Function":
                    callees = self.call_service.get_called_functions(n["id"])
                    for callee in callees:
                        dependents.setdefault(callee, set()).add(n["id"])
                        
        elif node_type == "Class":
            for n in nodes:
                if n["type"] == "Class":
                    edges = self.repository.get_outbound_edges(n["id"])
                    parents = [e["target_node"] for e in edges if e["relationship_type"] == "INHERITS"]
                    for parent in parents:
                        dependents.setdefault(parent, set()).add(n["id"])
                        
        elif node_type == "File":
            for n in nodes:
                if n["type"] == "File":
                    deps = self.dep_service.get_file_dependencies(n["id"], repo_id)
                    for dep in deps:
                        dependents.setdefault(dep, set()).add(n["id"])
                        
        # Run BFS starting at changed_node_id
        visited = {changed_node_id}
        queue = [(changed_node_id, 0)] # (node_id, distance)
        impacted = {}
        
        while queue:
            curr, dist = queue.pop(0)
            if curr != changed_node_id:
                node_info = self.repository.get_node(curr)
                if node_info:
                    impacted[curr] = {
                        "name": node_info.get("name"),
                        "type": node_info.get("type"),
                        "path": node_info.get("path"),
                        "distance": dist
                    }
                    
            for dep in dependents.get(curr, set()):
                if dep not in visited:
                    visited.add(dep)
                    queue.append((dep, dist + 1))
                    
        return {
            "changed_component": {
                "id": changed_node_id,
                "name": changed_node.get("name"),
                "type": node_type,
                "path": changed_node.get("path")
            },
            "impacted_components": impacted,
            "total_impact_count": len(impacted)
        }
