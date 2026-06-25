import sqlite3
import json
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
from ...domain.repositories.graph_repository import IGraphRepository
from ...domain.repositories.node_repository import INodeRepository
from ...domain.repositories.edge_repository import IEdgeRepository
from ...domain.repositories.traversal_repository import ITraversalRepository
from ..sqlite_connection_factory import SQLiteConnectionFactory

class SQLiteGraphRepository(IGraphRepository, INodeRepository, IEdgeRepository, ITraversalRepository):
    def __init__(self, db_path: str = "gitty_graph.db"):
        self.connection_factory = SQLiteConnectionFactory(db_path)
        self.db_path = db_path
        self.create_database()

    @contextmanager
    def _get_connection(self):
        conn = self.connection_factory.create_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_database(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Repositories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repositories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    language TEXT,
                    indexed_at TEXT,
                    hash TEXT
                )
            """)

            # 2. Nodes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            # 3. Relationships table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id TEXT PRIMARY KEY,
                    source_node TEXT NOT NULL,
                    target_node TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (source_node) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_node) REFERENCES nodes(id) ON DELETE CASCADE
                )
            """)

            # 4. Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_node)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_node)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type)")
            conn.commit()

    def clear_database(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM relationships")
            cursor.execute("DELETE FROM nodes")
            cursor.execute("DELETE FROM repositories")
            conn.commit()

    def get_schema_summary(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM nodes")
            nodes_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM relationships")
            edges_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM repositories")
            repos_count = cursor.fetchone()[0]

            return {
                "repositories_count": repos_count,
                "nodes_count": nodes_count,
                "edges_count": edges_count
            }

    # Repository operations
    def save_repository(self, repo_id: str, name: str, root_path: str, language: str, indexed_at: str, repo_hash: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO repositories (id, name, root_path, language, indexed_at, hash)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    root_path=excluded.root_path,
                    language=excluded.language,
                    indexed_at=excluded.indexed_at,
                    hash=excluded.hash
            """, (repo_id, name, root_path, language, indexed_at, repo_hash))
            conn.commit()

    def get_repository(self, repo_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repositories WHERE id = ?", (repo_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def list_repositories(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repositories ORDER BY indexed_at DESC")
            return [dict(r) for r in cursor.fetchall()]

    def delete_repository(self, repo_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            node_ids = self.traverse_bfs(repo_id, edge_types=[])
            if node_ids:
                placeholders = ",".join("?" for _ in node_ids)
                cursor.execute(f"DELETE FROM relationships WHERE source_node IN ({placeholders}) OR target_node IN ({placeholders})", node_ids + node_ids)
                cursor.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", node_ids)
            cursor.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
            conn.commit()

    # Node operations
    def add_node(self, node_id: str, label: str, properties: Dict[str, Any]) -> None:
        # Separate schema properties (name, path) from arbitrary metadata
        name = properties.get("name", "")
        path = properties.get("path", "")
        metadata_dict = {k: v for k, v in properties.items() if k not in ("name", "path")}
        metadata_json = json.dumps(metadata_dict)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO nodes (id, type, name, path, metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type=excluded.type,
                    name=excluded.name,
                    path=excluded.path,
                    metadata=excluded.metadata
            """, (node_id, label, name, path, metadata_json))
            conn.commit()

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                meta = json.loads(res["metadata"] or "{}")
                # Merge metadata fields back
                res.update(meta)
                return res
            return None

    def remove_node(self, node_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM relationships WHERE source_node = ? OR target_node = ?", (node_id, node_id))
            cursor.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            conn.commit()

    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM nodes WHERE type = ?", (node_type,))
            rows = cursor.fetchall()
            res = []
            for r in rows:
                res_dict = dict(r)
                meta = json.loads(res_dict["metadata"] or "{}")
                res_dict.update(meta)
                res.append(res_dict)
            return res

    def get_nodes_by_repository(self, repo_id: str) -> List[Dict[str, Any]]:
        node_ids = self.traverse_bfs(repo_id, edge_types=[])
        res = []
        for nid in node_ids:
            node = self.get_node(nid)
            if node:
                res.append(node)
        return res

    # Edge operations
    def add_edge(self, from_id: str, to_id: str, edge_type: str, properties: Dict[str, Any]) -> None:
        edge_id = f"{from_id}->{edge_type}->{to_id}"
        metadata_json = json.dumps(properties)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO relationships (id, source_node, target_node, relationship_type, metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    metadata=excluded.metadata
            """, (edge_id, from_id, to_id, edge_type, metadata_json))
            conn.commit()

    def remove_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        edge_id = f"{from_id}->{edge_type}->{to_id}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM relationships WHERE id = ?", (edge_id,))
            conn.commit()

    def get_outbound_edges(self, node_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM relationships WHERE source_node = ?", (node_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_inbound_edges(self, node_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM relationships WHERE target_node = ?", (node_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    # Traversal operations
    def traverse_bfs(self, start_id: str, edge_types: List[str]) -> List[str]:
        visited = {start_id}
        queue = [start_id]
        order = []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            while queue:
                curr = queue.pop(0)
                order.append(curr)

                # Fetch child nodes linked via given edge types
                if edge_types:
                    placeholders = ",".join("?" for _ in edge_types)
                    query = f"SELECT target_node FROM relationships WHERE source_node = ? AND relationship_type IN ({placeholders})"
                    params = [curr] + edge_types
                else:
                    query = "SELECT target_node FROM relationships WHERE source_node = ?"
                    params = [curr]

                cursor.execute(query, params)
                neighbors = [r[0] for r in cursor.fetchall()]

                for n in neighbors:
                    if n not in visited:
                        visited.add(n)
                        queue.append(n)
        return order

    def traverse_dfs(self, start_id: str, edge_types: List[str]) -> List[str]:
        visited = set()
        order = []

        with self._get_connection() as conn:
            cursor = conn.cursor()

            def _dfs(node_id: str):
                visited.add(node_id)
                order.append(node_id)

                if edge_types:
                    placeholders = ",".join("?" for _ in edge_types)
                    query = f"SELECT target_node FROM relationships WHERE source_node = ? AND relationship_type IN ({placeholders})"
                    params = [node_id] + edge_types
                else:
                    query = "SELECT target_node FROM relationships WHERE source_node = ?"
                    params = [node_id]

                cursor.execute(query, params)
                neighbors = [r[0] for r in cursor.fetchall()]

                for n in neighbors:
                    if n not in visited:
                        _dfs(n)

            _dfs(start_id)
        return order

    def get_shortest_path(self, start_id: str, end_id: str) -> List[str]:
        # Simple BFS path search
        if start_id == end_id:
            return [start_id]

        visited = {start_id}
        queue = [[start_id]]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            while queue:
                path = queue.pop(0)
                node = path[-1]

                cursor.execute("SELECT target_node FROM relationships WHERE source_node = ?", (node,))
                neighbors = [r[0] for r in cursor.fetchall()]

                for n in neighbors:
                    if n == end_id:
                        return path + [end_id]
                    if n not in visited:
                        visited.add(n)
                        queue.append(path + [n])
        return []
Class = SQLiteGraphRepository
