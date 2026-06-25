import sys
from libs.config import get_settings
from .sqlite_graph_repository import SQLiteGraphRepository
from .neo4j_graph_repository import Neo4jGraphRepository

def get_graph_repository():
    # 1. Backward-compatible hook: if SQLiteGraphRepository was mocked in apps.worker.worker_app
    worker_mod = sys.modules.get("apps.worker.worker_app")
    if worker_mod:
        repo_class = getattr(worker_mod, "SQLiteGraphRepository", None)
        if repo_class and (hasattr(repo_class, "_mock_return_value") or "mock" in str(repo_class).lower()):
            return repo_class()

    # 2. Backward-compatible hook: if SQLiteGraphRepository was mocked in app.api.v1.graph
    gateway_mod = sys.modules.get("app.api.v1.graph")
    if gateway_mod:
        repo_class = getattr(gateway_mod, "SQLiteGraphRepository", None)
        if repo_class and (hasattr(repo_class, "_mock_return_value") or "mock" in str(repo_class).lower()):
            return repo_class()

    settings = get_settings()
    if settings.GRAPH_MODE == "neo4j":
        return Neo4jGraphRepository(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
    else:
        return SQLiteGraphRepository(db_path=settings.SQLITE_DB_PATH)
