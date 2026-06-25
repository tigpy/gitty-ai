import hashlib
from typing import List, Dict, Any, Set
from libs.graph.algorithms.bfs import bfs_traverse

class DependencyTraversalService:
    def __init__(self, repository: Any):
        self.repository = repository

    def get_file_dependencies(self, file_node_id: str, repo_id: str) -> List[str]:
        """Resolves file-to-file import dependencies for a given file node."""
        edges = self.repository.get_outbound_edges(file_node_id)
        import_node_ids = [e["target_node"] for e in edges if e["relationship_type"] == "IMPORTS"]
        
        # Build fallback path & name maps for repositories with custom IDs
        all_repo_nodes = self.repository.get_nodes_by_repository(repo_id)
        file_path_map = {n.get("path"): n["id"] for n in all_repo_nodes if n.get("type") == "File"}
        file_name_map = {n.get("name"): n["id"] for n in all_repo_nodes if n.get("type") == "File"}

        dependencies = set()
        for imp_id in import_node_ids:
            imp_node = self.repository.get_node(imp_id)
            if not imp_node:
                continue
            imp_name = imp_node.get("name", "")
            
            # Resolve to a file in the repository
            # e.g., "services.user_service.UserService" -> candidate paths:
            # - "services/user_service/UserService.py"
            # - "services/user_service.py"
            # - "services.py"
            parts = imp_name.split(".")
            for i in range(len(parts), 0, -1):
                candidate_path = "/".join(parts[:i]) + ".py"
                candidate_name = parts[:i][-1] + ".py"
                candidate_id = hashlib.sha256(f"{repo_id}:{candidate_path}".encode()).hexdigest()
                
                if self.repository.get_node(candidate_id):
                    dependencies.add(candidate_id)
                    break
                elif candidate_path in file_path_map:
                    dependencies.add(file_path_map[candidate_path])
                    break
                elif candidate_name in file_name_map:
                    dependencies.add(file_name_map[candidate_name])
                    break
        return list(dependencies)

    def find_dependency_chain(self, start_file_id: str, repo_id: str) -> List[str]:
        """Finds all files that start_file_id depends on directly and transitively."""
        def get_neighbors(fid: str) -> List[str]:
            return self.get_file_dependencies(fid, repo_id)
            
        return bfs_traverse(start_file_id, get_neighbors)

    def strongly_connected_components(self, repo_id: str) -> List[List[str]]:
        """Finds strongly connected components in the file dependency graph using Tarjan's algorithm."""
        nodes = self.repository.get_nodes_by_repository(repo_id)
        file_node_ids = [n["id"] for n in nodes if n["type"] == "File"]
        
        def get_neighbors(nid: str) -> List[str]:
            return self.get_file_dependencies(nid, repo_id)
            
        index_counter = 0
        indexes = {}
        lowlinks = {}
        stack = []
        on_stack = set()
        sccs = []
        
        def strongconnect(node: str):
            nonlocal index_counter
            indexes[node] = index_counter
            lowlinks[node] = index_counter
            index_counter += 1
            stack.append(node)
            on_stack.add(node)
            
            for neighbor in get_neighbors(node):
                if neighbor not in indexes:
                    strongconnect(neighbor)
                    lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
                elif neighbor in on_stack:
                    lowlinks[node] = min(lowlinks[node], indexes[neighbor])
                    
            if lowlinks[node] == indexes[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node:
                        break
                sccs.append(scc)
                
        for nid in file_node_ids:
            if nid not in indexes:
                strongconnect(nid)
                
        return sccs

    def detect_cycles(self, repo_id: str) -> List[List[str]]:
        """Detects circular dependency loops (SCCs of size > 1) in the repository."""
        sccs = self.strongly_connected_components(repo_id)
        return [scc for scc in sccs if len(scc) > 1]

    def topological_sort(self, repo_id: str) -> List[str]:
        """Performs a topological sort to find a valid compile/build order of files."""
        nodes = self.repository.get_nodes_by_repository(repo_id)
        file_node_ids = [n["id"] for n in nodes if n["type"] == "File"]
        
        dependencies = {}
        for nid in file_node_ids:
            dependencies[nid] = self.get_file_dependencies(nid, repo_id)
            
        in_degree = {nid: 0 for nid in file_node_ids}
        adj_list = {nid: [] for nid in file_node_ids}
        
        for nid in file_node_ids:
            for dep in dependencies.get(nid, []):
                if dep in adj_list:
                    adj_list[dep].append(nid)
                    in_degree[nid] += 1
                    
        queue = [nid for nid in file_node_ids if in_degree[nid] == 0]
        sorted_order = []
        
        while queue:
            u = queue.pop(0)
            sorted_order.append(u)
            
            for v in adj_list[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
                    
        if len(sorted_order) != len(file_node_ids):
            raise ValueError("Graph has circular dependencies (cycle detected)")
            
        return sorted_order
