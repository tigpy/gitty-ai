import os
import hashlib
from typing import List, Dict, Any, Set, Optional
from libs.graph.algorithms.bfs import bfs_traverse

class DependencyTraversalService:
    def __init__(self, repository: Any):
        self.repository = repository

    def get_all_file_dependencies(
        self,
        repo_id: str,
        nodes: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, List[str]]:
        """
        Resolves file-to-file import dependencies for all file nodes in a repository in a single batch pass.
        Eliminates N+1 database queries by prefetching repository nodes and relationships once.
        """
        if nodes is None:
            nodes = self.repository.get_nodes_by_repository(repo_id)

        file_nodes = [n for n in nodes if n.get("type") == "File"]
        if not file_nodes:
            return {}

        file_node_ids = {fn["id"] for fn in file_nodes}
        node_by_id = {n["id"]: n for n in nodes}

        file_path_map: Dict[str, str] = {}
        file_name_map: Dict[str, str] = {}
        for fn in file_nodes:
            p = fn.get("path", "")
            nid = fn["id"]
            file_path_map[p] = nid
            file_path_map[p.replace("\\", "/")] = nid
            file_path_map[p.replace("/", "\\")] = nid
            file_name_map[fn.get("name", "")] = nid

        # Fetch all relationships where source_node is a file in this repository
        if hasattr(self.repository, "get_edges_between_nodes"):
            edges = self.repository.get_edges_between_nodes(list(file_node_ids))
        else:
            edges = []
            for fnid in file_node_ids:
                edges.extend(self.repository.get_outbound_edges(fnid))

        imports_by_file: Dict[str, List[str]] = {}
        for e in edges:
            if e.get("relationship_type") == "IMPORTS":
                imports_by_file.setdefault(e["source_node"], []).append(e["target_node"])

        all_deps: Dict[str, List[str]] = {}
        for fn in file_nodes:
            fid = fn["id"]
            source_path = fn.get("path", "")
            source_dir = os.path.dirname(source_path).replace("\\", "/")
            import_node_ids = imports_by_file.get(fid, [])

            dependencies: Set[str] = set()
            for imp_id in import_node_ids:
                imp_node = node_by_id.get(imp_id)
                if not imp_node:
                    continue
                imp_name = imp_node.get("name", "").strip()
                if not imp_name:
                    continue

                candidate_paths: List[str] = []
                candidate_names: List[str] = []

                # 1. JS/TS Relative imports (./ or ../)
                if imp_name.startswith("./") or imp_name.startswith("../"):
                    resolved_rel = os.path.normpath(os.path.join(source_dir, imp_name)).replace("\\", "/")
                    candidate_paths.append(resolved_rel)
                    for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]:
                        candidate_paths.append(resolved_rel + ext)
                        candidate_paths.append(f"{resolved_rel}/index{ext}")

                # 2. JS/TS Alias imports (@/ or ~/)
                elif imp_name.startswith("@/") or imp_name.startswith("~/"):
                    sub_path = imp_name[2:].lstrip("/\\")
                    for prefix in ["", "src/"]:
                        base = f"{prefix}{sub_path}".strip("/")
                        candidate_paths.append(base)
                        for ext in [".ts", ".tsx", ".js", ".jsx", ".mjs"]:
                            candidate_paths.append(base + ext)
                            candidate_paths.append(f"{base}/index{ext}")

                # 3. Python or Java dot notation (e.g. services.user_service.UserService)
                else:
                    parts = imp_name.split(".")
                    for i in range(len(parts), 0, -1):
                        for ext in [".py", ".ts", ".tsx", ".js", ".jsx"]:
                            candidate_paths.append("/".join(parts[:i]) + ext)
                        candidate_names.append(parts[:i][-1] + ".py")
                        candidate_names.append(parts[:i][-1] + ".ts")
                        candidate_names.append(parts[:i][-1] + ".tsx")
                        candidate_names.append(parts[:i][-1] + ".js")

                # Check matches in repository nodes
                found = False
                for c_path in candidate_paths:
                    c_id = hashlib.sha256(f"{repo_id}:{c_path}".encode()).hexdigest()
                    if c_id in file_node_ids:
                        dependencies.add(c_id)
                        found = True
                        break
                    elif c_path in file_path_map:
                        dependencies.add(file_path_map[c_path])
                        found = True
                        break

                if not found:
                    for c_name in candidate_names:
                        if c_name in file_name_map:
                            dependencies.add(file_name_map[c_name])
                            break
            all_deps[fid] = list(dependencies)

        return all_deps

    def get_file_dependencies(
        self,
        file_node_id: str,
        repo_id: str,
        all_deps: Optional[Dict[str, List[str]]] = None
    ) -> List[str]:
        """Resolves file-to-file import dependencies for a given file node."""
        if all_deps is not None:
            return all_deps.get(file_node_id, [])
        return self.get_all_file_dependencies(repo_id).get(file_node_id, [])

    def find_dependency_chain(self, start_file_id: str, repo_id: str) -> List[str]:
        """Finds all files that start_file_id depends on directly and transitively."""
        all_deps = self.get_all_file_dependencies(repo_id)
        def get_neighbors(fid: str) -> List[str]:
            return all_deps.get(fid, [])
            
        return bfs_traverse(start_file_id, get_neighbors)

    def strongly_connected_components(
        self,
        repo_id: str,
        all_deps: Optional[Dict[str, List[str]]] = None
    ) -> List[List[str]]:
        """Finds strongly connected components in the file dependency graph using Tarjan's algorithm."""
        if all_deps is None:
            all_deps = self.get_all_file_dependencies(repo_id)

        file_node_ids = list(all_deps.keys())

        index_counter = 0
        indexes: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        stack: List[str] = []
        on_stack: Set[str] = set()
        sccs: List[List[str]] = []

        def strongconnect(node: str):
            nonlocal index_counter
            indexes[node] = index_counter
            lowlinks[node] = index_counter
            index_counter += 1
            stack.append(node)
            on_stack.add(node)

            for neighbor in all_deps.get(node, []):
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

    def detect_cycles(
        self,
        repo_id: str,
        all_deps: Optional[Dict[str, List[str]]] = None
    ) -> List[List[str]]:
        """Detects circular dependency loops (SCCs of size > 1) in the repository."""
        sccs = self.strongly_connected_components(repo_id, all_deps=all_deps)
        return [scc for scc in sccs if len(scc) > 1]

    def topological_sort(
        self,
        repo_id: str,
        all_deps: Optional[Dict[str, List[str]]] = None
    ) -> List[str]:
        """Performs a topological sort to find a valid compile/build order of files."""
        if all_deps is None:
            all_deps = self.get_all_file_dependencies(repo_id)

        file_node_ids = list(all_deps.keys())

        in_degree = {nid: 0 for nid in file_node_ids}
        adj_list: Dict[str, List[str]] = {nid: [] for nid in file_node_ids}

        for nid in file_node_ids:
            for dep in all_deps.get(nid, []):
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
