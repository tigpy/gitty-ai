import json
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
from neo4j import GraphDatabase
from ...domain.repositories.graph_repository import IGraphRepository
from ...domain.repositories.node_repository import INodeRepository
from ...domain.repositories.edge_repository import IEdgeRepository
from ...domain.repositories.traversal_repository import ITraversalRepository

class Neo4jGraphRepository(IGraphRepository, INodeRepository, IEdgeRepository, ITraversalRepository):
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "gitty_password"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.create_database()

    def close(self) -> None:
        self.driver.close()

    @contextmanager
    def _get_session(self):
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()

    def create_database(self) -> None:
        with self._get_session() as session:
            # Create uniqueness constraints and indexes
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE")
            session.run("CREATE INDEX IF NOT EXISTS FOR (n:Node) ON (n.type)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (n:Node) ON (n.path)")

    def clear_database(self) -> None:
        with self._get_session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def get_schema_summary(self) -> Dict[str, Any]:
        with self._get_session() as session:
            r_count = session.run("MATCH (r:Repository) RETURN count(r) AS c").single()["c"]
            n_count = session.run("MATCH (n:Node) RETURN count(n) AS c").single()["c"]
            e_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            return {
                "repositories_count": r_count,
                "nodes_count": n_count,
                "edges_count": e_count
            }

    # Repository operations
    def save_repository(self, repo_id: str, name: str, root_path: str, language: str, indexed_at: str, repo_hash: str) -> None:
        with self._get_session() as session:
            query = """
            MERGE (r:Repository {id: $repo_id})
            SET r.name = $name, r.root_path = $root_path, r.language = $language, r.indexed_at = $indexed_at, r.hash = $repo_hash, r.type = "Repository"
            SET r:Node
            """
            session.run(
                query, 
                repo_id=repo_id, 
                name=name, 
                root_path=root_path, 
                language=language, 
                indexed_at=indexed_at, 
                repo_hash=repo_hash
            )

    def get_repository(self, repo_id: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            query = "MATCH (r:Repository {id: $repo_id}) RETURN r"
            result = session.run(query, repo_id=repo_id).single()
            if result:
                return dict(result["r"])
            return None

    def list_repositories(self) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            query = "MATCH (r:Repository) RETURN r ORDER BY r.indexed_at DESC"
            records = session.run(query)
            return [dict(record["r"]) for record in records]

    def delete_repository(self, repo_id: str) -> None:
        with self._get_session() as session:
            session.run("""
            MATCH (r:Repository {id: $repo_id})-[*0..]->(n:Node)
            DETACH DELETE n
            """, repo_id=repo_id)

    # Node operations
    def add_node(self, node_id: str, label: str, properties: Dict[str, Any]) -> None:
        with self._get_session() as session:
            name = properties.get("name", "")
            path = properties.get("path", "")
            metadata_dict = {k: v for k, v in properties.items() if k not in ("name", "path")}
            metadata_json = json.dumps(metadata_dict)
            
            props = {
                "name": name,
                "path": path,
                "type": label,
                "metadata": metadata_json
            }
            for k, v in metadata_dict.items():
                if isinstance(v, (str, int, float, bool)):
                    props[k] = v
                    
            allowed_labels = {"Repository", "File", "Class", "Function", "Call", "Import"}
            clean_label = label if label in allowed_labels else "Node"
            
            query = f"""
            MERGE (n:Node {{id: $node_id}})
            SET n += $props
            SET n:{clean_label}
            """
            session.run(query, node_id=node_id, props=props)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._get_session() as session:
            query = "MATCH (n:Node {id: $node_id}) RETURN n"
            result = session.run(query, node_id=node_id).single()
            if not result:
                return None
            node = result["n"]
            res = dict(node)
            meta = json.loads(res.get("metadata") or "{}")
            res.update(meta)
            return res

    def remove_node(self, node_id: str) -> None:
        with self._get_session() as session:
            session.run("MATCH (n:Node {id: $node_id}) DETACH DELETE n", node_id=node_id)

    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            query = "MATCH (n:Node) WHERE n.type = $node_type RETURN n"
            records = session.run(query, node_type=node_type)
            res = []
            for record in records:
                node = record["n"]
                node_dict = dict(node)
                meta = json.loads(node_dict.get("metadata") or "{}")
                node_dict.update(meta)
                res.append(node_dict)
            return res

    def get_nodes_by_repository(self, repo_id: str) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            # Traverses reachable nodes from Repository start node
            query = """
            MATCH (r:Node {id: $repo_id})-[*0..]->(n:Node)
            RETURN DISTINCT n
            """
            records = session.run(query, repo_id=repo_id)
            res = []
            for record in records:
                node = record["n"]
                node_dict = dict(node)
                meta = json.loads(node_dict.get("metadata") or "{}")
                node_dict.update(meta)
                res.append(node_dict)
            return res

    # Edge operations
    def add_edge(self, from_id: str, to_id: str, edge_type: str, properties: Dict[str, Any]) -> None:
        with self._get_session() as session:
            allowed_types = {"CONTAINS", "CALLS", "IMPORTS", "BELONGS_TO", "DEPENDS"}
            clean_type = edge_type if edge_type in allowed_types else "RELATIONSHIP"
            
            query = f"""
            MATCH (a:Node {{id: $from_id}}), (b:Node {{id: $to_id}})
            MERGE (a)-[r:{clean_type}]->(b)
            SET r += $properties
            """
            session.run(query, from_id=from_id, to_id=to_id, properties=properties)

    def remove_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        with self._get_session() as session:
            allowed_types = {"CONTAINS", "CALLS", "IMPORTS", "BELONGS_TO", "DEPENDS"}
            clean_type = edge_type if edge_type in allowed_types else "RELATIONSHIP"
            
            query = f"""
            MATCH (a:Node {{id: $from_id}})-[r:{clean_type}]->(b:Node {{id: $to_id}})
            DELETE r
            """
            session.run(query, from_id=from_id, to_id=to_id)

    def get_outbound_edges(self, node_id: str) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            query = """
            MATCH (a:Node {id: $node_id})-[r]->(b:Node)
            RETURN b.id AS target_node, type(r) AS relationship_type, r AS properties
            """
            records = session.run(query, node_id=node_id)
            return [
                {
                    "source_node": node_id,
                    "target_node": record["target_node"],
                    "relationship_type": record["relationship_type"],
                    **dict(record["properties"] or {})
                }
                for record in records
            ]

    def get_inbound_edges(self, node_id: str) -> List[Dict[str, Any]]:
        with self._get_session() as session:
            query = """
            MATCH (a:Node)-[r]->(b:Node {id: $node_id})
            RETURN a.id AS source_node, type(r) AS relationship_type, r AS properties
            """
            records = session.run(query, node_id=node_id)
            return [
                {
                    "source_node": record["source_node"],
                    "target_node": node_id,
                    "relationship_type": record["relationship_type"],
                    **dict(record["properties"] or {})
                }
                for record in records
            ]

    # Traversal operations
    def traverse_bfs(self, start_id: str, edge_types: List[str]) -> List[str]:
        visited = {start_id}
        queue = [start_id]
        order = []
        while queue:
            curr = queue.pop(0)
            order.append(curr)
            outbound = self.get_outbound_edges(curr)
            for edge in outbound:
                target = edge["target_node"]
                if edge_types and edge["relationship_type"] not in edge_types:
                    continue
                if target not in visited:
                    visited.add(target)
                    queue.append(target)
        return order

    def traverse_dfs(self, start_id: str, edge_types: List[str]) -> List[str]:
        visited = set()
        order = []
        def dfs(node_id):
            visited.add(node_id)
            order.append(node_id)
            outbound = self.get_outbound_edges(node_id)
            for edge in outbound:
                target = edge["target_node"]
                if edge_types and edge["relationship_type"] not in edge_types:
                    continue
                if target not in visited:
                    dfs(target)
        dfs(start_id)
        return order

    def get_shortest_path(self, start_id: str, end_id: str) -> List[str]:
        if start_id == end_id:
            return [start_id]
        visited = {start_id}
        queue = [[start_id]]
        while queue:
            path = queue.pop(0)
            node = path[-1]
            outbound = self.get_outbound_edges(node)
            for edge in outbound:
                target = edge["target_node"]
                if target == end_id:
                    return path + [end_id]
                if target not in visited:
                    visited.add(target)
                    queue.append(path + [target])
        return []
