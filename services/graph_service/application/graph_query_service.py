from typing import List, Dict, Any, Optional
import json

class GraphQueryService:
    def __init__(self, repository: Any):
        self.repository = repository

    def find_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.repository.get_node(node_id)

    def find_neighbors(self, node_id: str, edge_types: List[str] = None) -> List[Dict[str, Any]]:
        edges = self.repository.get_outbound_edges(node_id)
        if edge_types:
            edges = [e for e in edges if e["relationship_type"] in edge_types]
            
        neighbors = []
        for e in edges:
            node = self.repository.get_node(e["target_node"])
            if node:
                neighbors.append(node)
        return neighbors

    def find_callers(self, function_node_id: str) -> List[Dict[str, Any]]:
        edges = self.repository.get_inbound_edges(function_node_id)
        callers = []
        for e in edges:
            if e["relationship_type"] in ("CALLS", "BELONGS_TO"):
                node = self.repository.get_node(e["source_node"])
                if node:
                    callers.append(node)
        return callers

    def find_callees(self, function_node_id: str) -> List[Dict[str, Any]]:
        edges = self.repository.get_outbound_edges(function_node_id)
        callees = []
        for e in edges:
            if e["relationship_type"] in ("CALLS", "BELONGS_TO"):
                node = self.repository.get_node(e["target_node"])
                if node:
                    callees.append(node)
        return callees

    def find_path(self, start_id: str, end_id: str) -> List[str]:
        return self.repository.get_shortest_path(start_id, end_id)

    def get_unused_imports(self, repo_id: str) -> List[Dict[str, Any]]:
        nodes = self.repository.get_nodes_by_repository(repo_id)
        import_nodes = [n for n in nodes if n["type"] == "Import"]
        call_nodes = [n for n in nodes if n["type"] == "Call"]
        
        # Group imports by file
        imports_by_file = {}
        for imp in import_nodes:
            path = imp.get("path")
            if path:
                imports_by_file.setdefault(path, []).append(imp)
                
        # Group calls by file
        calls_by_file = {}
        for c in call_nodes:
            path = c.get("path")
            if path:
                calls_by_file.setdefault(path, []).append(c)
                
        unused = []
        for path, imps in imports_by_file.items():
            calls = calls_by_file.get(path, [])
            # Extract all call target names and split by dot
            call_names = set()
            for c in calls:
                name = c.get("name", "")
                call_names.add(name)
                # Also add segments (e.g. "sys" from "sys.exit")
                parts = name.split(".")
                call_names.update(parts)
                
            for imp in imps:
                imp_name = imp.get("name", "")
                alias = imp.get("alias")
                
                # Determine local names this import introduces
                candidates = set()
                if alias:
                    candidates.add(alias)
                else:
                    parts = imp_name.split(".")
                    if parts:
                        candidates.add(parts[0])
                        candidates.add(parts[-1])
                        
                # Check if any candidate is used in the call names
                if not (candidates & call_names):
                    unused.append(imp)
        return unused

    def get_largest_modules(self, repo_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        nodes = self.repository.get_nodes_by_repository(repo_id)
        file_nodes = [n for n in nodes if n["type"] == "File"]
        file_nodes.sort(key=lambda x: x.get("size", 0), reverse=True)
        return file_nodes[:limit]

    def get_most_called_functions(self, repo_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        nodes = self.repository.get_nodes_by_repository(repo_id)
        call_nodes = [n for n in nodes if n["type"] == "Call"]
        
        counts = {}
        for c in call_nodes:
            target = c.get("resolved_target") or c.get("name")
            if target:
                counts[target] = counts.get(target, 0) + 1
                
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        res = []
        for target, count in sorted_counts[:limit]:
            res.append({
                "function_name": target,
                "call_count": count
            })
        return res

    def get_dependency_hotspots(self, repo_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        nodes = self.repository.get_nodes_by_repository(repo_id)
        import_nodes = [n for n in nodes if n["type"] == "Import"]
        
        counts = {}
        for imp in import_nodes:
            name = imp.get("name")
            if name:
                counts[name] = counts.get(name, 0) + 1
                
        sorted_hotspots = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        res = []
        for name, count in sorted_hotspots[:limit]:
            res.append({
                "dependency_name": name,
                "import_count": count
            })
        return res
