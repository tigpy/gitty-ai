from libs.config import get_settings
from .sqlite_graph_repository import SQLiteGraphRepository
from .neo4j_graph_repository import Neo4jGraphRepository


def get_graph_repository():
    """
    Returns the configured graph repository implementation.

    Selects between SQLite (default, zero-dependency local mode) and Neo4j
    (production graph database) based on the GRAPH_MODE setting.

    Previous versions of this factory inspected sys.modules for unittest.mock
    objects as a test-isolation workaround.  That approach is fragile and
    pollutes production code with test concerns.  Tests should instead use
    pytest fixtures or monkeypatch to supply a mock/in-memory repository
    directly to the service under test.
    """
    settings = get_settings()
    if settings.GRAPH_MODE == "neo4j":
        return Neo4jGraphRepository(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
        )
    return SQLiteGraphRepository(db_path=settings.SQLITE_DB_PATH)
