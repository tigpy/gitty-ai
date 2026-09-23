"""Bounded graph context around vector-retrieved chunks.

Vector search chooses the seeds. This expander adds only relationships the
graph already stores (CONTAINS, IMPORTS, CALLS, BELONGS_TO, INHERITS). It does
not invent edges, read extra source files, or follow a node into another
repository. Any graph failure leaves the caller with the original vector chunks.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from services.vector_service.domain.value_objects.chunk import Chunk

STRUCTURAL_RELATIONSHIPS = ("BELONGS_TO", "CALLS", "CONTAINS", "IMPORTS", "INHERITS")
_CHUNK_TYPE_TO_NODE = {
    "FUNCTION": "Function",
    "CLASS": "Class",
    "FILE": "File",
    "DOCUMENTATION": "File",
}


class GraphContextExpander:
    def __init__(
        self,
        graph_repo: Any,
        *,
        max_seeds: int = 5,
        max_depth: int = 2,
        max_nodes: int = 24,
        max_relationships: int = 32,
    ):
        self.graph_repo = graph_repo
        self.max_seeds = max(0, max_seeds)
        self.max_depth = max(0, max_depth)
        self.max_nodes = max(0, max_nodes)
        self.max_relationships = max(0, max_relationships)
        self._owners: Dict[str, Set[str]] = {}

    def expand(self, repository_id: str, vector_chunks: List[Chunk]) -> List[Chunk]:
        """Return extra graph chunks. Never raises; an empty list means no graph evidence."""
        if not repository_id or not vector_chunks or self.max_nodes == 0 or self.max_depth == 0:
            return []
        try:
            return self._expand(repository_id, vector_chunks)
        except Exception:
            return []

    def _expand(self, repository_id: str, vector_chunks: List[Chunk]) -> List[Chunk]:
        repo_nodes = self._load_repository_nodes(repository_id)
        seeds: List[str] = []
        for chunk in vector_chunks:
            if len(seeds) >= self.max_seeds:
                break
            node_id = self._resolve_seed(repository_id, chunk, repo_nodes)
            if node_id and node_id not in seeds:
                seeds.append(node_id)
        if not seeds:
            return []

        node_cache: Dict[str, Dict[str, Any]] = {
            node["id"]: node for node in repo_nodes if node.get("id")
        }
        for seed in seeds:
            self._remember(node_cache, seed)

        relationships: List[Tuple[str, str, str]] = []
        seen_relationships: Set[Tuple[str, str, str]] = set()
        visited = set(seeds)
        related: List[str] = []
        queue: List[Tuple[str, int]] = [(seed, 0) for seed in seeds]

        while queue and len(related) < self.max_nodes and len(relationships) < self.max_relationships:
            current, depth = queue.pop(0)
            if depth >= self.max_depth:
                continue
            for direction, edge in self._sorted_edges(current):
                if len(relationships) >= self.max_relationships and len(related) >= self.max_nodes:
                    break
                kind = edge.get("relationship_type")
                if kind not in STRUCTURAL_RELATIONSHIPS:
                    continue
                other = edge.get("target_node") if direction == "out" else edge.get("source_node")
                source = edge.get("source_node")
                target = edge.get("target_node")
                if not other or not source or not target or other == current:
                    continue
                if not self._in_repository(repository_id, other, reached_from_trusted=True):
                    continue
                other_node = self._remember(node_cache, other)
                if other_node is None:
                    continue
                key = (source, kind, target)
                if key not in seen_relationships and len(relationships) < self.max_relationships:
                    seen_relationships.add(key)
                    relationships.append(key)
                if other in visited:
                    continue
                visited.add(other)
                if other_node.get("type") == "Repository":
                    continue
                if len(related) >= self.max_nodes:
                    continue
                related.append(other)
                if depth + 1 < self.max_depth:
                    queue.append((other, depth + 1))

        chunks: List[Chunk] = []
        for node_id in related:
            node = node_cache.get(node_id)
            if not node or node.get("type") == "Repository":
                continue
            incident = [
                item for item in relationships
                if item[0] == node_id or item[2] == node_id
            ]
            chunks.append(self._to_chunk(repository_id, node, incident, node_cache))
        return chunks

    def _load_repository_nodes(self, repository_id: str) -> List[Dict[str, Any]]:
        loader = getattr(self.graph_repo, "get_nodes_by_repository", None)
        if loader is None:
            return []
        return list(loader(repository_id) or [])

    def _resolve_seed(
        self,
        repository_id: str,
        chunk: Chunk,
        repo_nodes: List[Dict[str, Any]],
    ) -> Optional[str]:
        meta = chunk.metadata or {}
        explicit = meta.get("graph_node_id")
        if explicit and self._in_repository(repository_id, str(explicit), reached_from_trusted=False):
            return str(explicit)
        wanted_type = _CHUNK_TYPE_TO_NODE.get(chunk.chunk_type)
        if not wanted_type:
            return None
        file_path = meta.get("file_path")
        symbol = meta.get("symbol_name")
        for node in repo_nodes:
            if node.get("path") != file_path or node.get("type") != wanted_type:
                continue
            if wanted_type != "File" and symbol and node.get("name") != symbol:
                continue
            node_id = node.get("id")
            if node_id and self._in_repository(repository_id, node_id, reached_from_trusted=False):
                return node_id
        return None

    def _remember(self, cache: Dict[str, Dict[str, Any]], node_id: str) -> Optional[Dict[str, Any]]:
        if node_id in cache:
            return cache[node_id]
        getter = getattr(self.graph_repo, "get_node", None)
        if getter is None:
            return None
        try:
            node = getter(node_id)
        except Exception:
            return None
        if not node:
            return None
        node = dict(node)
        node.setdefault("id", node_id)
        cache[node_id] = node
        return node

    def _sorted_edges(self, node_id: str) -> List[Tuple[str, Dict[str, Any]]]:
        found: List[Tuple[str, Dict[str, Any]]] = []
        try:
            outbound = self.graph_repo.get_outbound_edges(node_id) or []
        except Exception:
            outbound = []
        try:
            inbound = self.graph_repo.get_inbound_edges(node_id) or []
        except Exception:
            inbound = []
        for edge in outbound:
            found.append(("out", edge))
        for edge in inbound:
            found.append(("in", edge))
        found.sort(key=lambda item: (
            item[1].get("relationship_type") or "",
            item[1].get("source_node") or "",
            item[1].get("target_node") or "",
            item[0],
        ))
        return found

    def _in_repository(self, repository_id: str, node_id: str, *, reached_from_trusted: bool) -> bool:
        """
        Containment (CONTAINS edges up to a repository) is the boundary.
        Call and import nodes have no CONTAINS parent, so they are accepted only
        when the walk already came from a node inside this repository. A node
        contained by a different repository is never accepted.
        """
        if node_id == repository_id:
            return True
        owners = self._containment_owners(node_id)
        if repository_id in owners:
            return True
        if owners:
            return False
        return reached_from_trusted

    def _containment_owners(self, node_id: str) -> Set[str]:
        cached = self._owners.get(node_id)
        if cached is not None:
            return cached
        owners: Set[str] = set()
        visited = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if len(visited) > 10000:
                break
            getter = getattr(self.graph_repo, "get_repository", None)
            if getter is not None and current != node_id:
                try:
                    found = getter(current)
                except Exception:
                    found = None
                if found:
                    owners.add(current)
                    continue
            try:
                inbound = self.graph_repo.get_inbound_edges(current) or []
            except Exception:
                break
            for edge in inbound:
                if edge.get("relationship_type") != "CONTAINS":
                    continue
                source = edge.get("source_node")
                if source and source not in visited:
                    queue.append(source)
        self._owners[node_id] = owners
        return owners

    def _to_chunk(
        self,
        repository_id: str,
        node: Dict[str, Any],
        relationships: List[Tuple[str, str, str]],
        cache: Dict[str, Dict[str, Any]],
    ) -> Chunk:
        node_id = node.get("id", "")
        lines = [
            f"Graph node {node.get('name') or node_id} "
            f"({node.get('type') or 'unknown'}) path {node.get('path') or 'unknown'}."
        ]
        rendered = []
        for source, kind, target in relationships:
            source_label = _node_label(cache, source)
            target_label = _node_label(cache, target)
            statement = f"{source_label} {kind} {target_label}."
            rendered.append(statement)
            lines.append(statement)
        start = node.get("start_line")
        end = node.get("end_line")
        return Chunk(
            id=f"graph:{node_id}",
            text="\n".join(lines),
            chunk_type="GRAPH",
            metadata={
                "repository_id": repository_id,
                "file_path": node.get("path") or "unknown",
                "symbol_name": node.get("name"),
                "graph_node_id": node_id,
                "origin": "graph",
                "node_type": node.get("type"),
                "relationships": rendered,
            },
            content_hash="",
            version=1,
            start_line=start if isinstance(start, int) else None,
            end_line=end if isinstance(end, int) else None,
        )


def assemble_hybrid_context(
    graph_repo: Any,
    repository_id: str,
    vector_chunks: List[Chunk],
    *,
    max_seeds: Optional[int] = None,
    max_depth: Optional[int] = None,
    max_nodes: Optional[int] = None,
    max_relationships: Optional[int] = None,
) -> List[Chunk]:
    """Vector chunks stay first. Graph chunks, when available, follow them."""
    base = list(vector_chunks)
    if graph_repo is None:
        return base
    from libs.config import get_settings

    settings = get_settings()
    expander = GraphContextExpander(
        graph_repo,
        max_seeds=settings.RAG_MAX_GRAPH_SEEDS if max_seeds is None else max_seeds,
        max_depth=settings.RAG_MAX_GRAPH_DEPTH if max_depth is None else max_depth,
        max_nodes=settings.RAG_MAX_GRAPH_NODES if max_nodes is None else max_nodes,
        max_relationships=(
            settings.RAG_MAX_GRAPH_RELATIONSHIPS if max_relationships is None else max_relationships
        ),
    )
    return base + expander.expand(repository_id, base)


def _node_label(cache: Dict[str, Dict[str, Any]], node_id: str) -> str:
    node = cache.get(node_id) or {}
    name = node.get("name") or node_id
    kind = node.get("type") or "node"
    return f"{name} ({kind})"
