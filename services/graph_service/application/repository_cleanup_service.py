import os
import shutil
import stat
import sqlite3
from libs.config import get_settings
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.vector_service.infrastructure.vector_store.qdrant_repository import QdrantRepository
from services.rag_service.infrastructure.persistence.sqlite_session_repository import SQLiteChatSessionRepository
from libs.logging import get_logger

logger = get_logger("cleanup_service")

class RepositoryCleanupService:
    def __init__(self, db_path: str = None):
        self.settings = get_settings()
        self.db_path = db_path or self.settings.SQLITE_DB_PATH
        self.sqlite_repo = SQLiteGraphRepository(self.db_path)
        self.vector_repo = QdrantRepository()
        self.session_repo = SQLiteChatSessionRepository(self.db_path)

    def cleanup(self, repository_id: str) -> None:
        logger.info("Starting cleanup for repository", repository_id=repository_id)
        
        # 1. Clean Qdrant vectors
        try:
            for col in self.vector_repo.collections:
                self.vector_repo.delete_repository_vectors(repository_id, col)
            logger.info("Deleted Qdrant vectors", repository_id=repository_id)
        except Exception as e:
            logger.warning("Failed to delete Qdrant vectors", repository_id=repository_id, error=str(e))

        # 2. Clean SQLite graph nodes, edges, and repository metadata
        try:
            self.sqlite_repo.delete_repository(repository_id)
            logger.info("Deleted SQLite graph records", repository_id=repository_id)
        except Exception as e:
            logger.warning("Failed to delete SQLite graph records", repository_id=repository_id, error=str(e))

        # 3. Clean Chat Sessions and Cascade Chat Messages
        try:
            with self.session_repo._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM chat_sessions WHERE repository_id = ?", (repository_id,))
                conn.commit()
            logger.info("Deleted chat sessions and messages", repository_id=repository_id)
        except Exception as e:
            logger.warning("Failed to delete chat sessions", repository_id=repository_id, error=str(e))

        # 4. Delete cloned repository files on disk
        dest_path = os.path.join("data", "repos", repository_id)
        if os.path.exists(dest_path):
            try:
                def remove_readonly(func, path, excinfo):
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                shutil.rmtree(dest_path, onerror=remove_readonly)
                logger.info("Deleted repository files on disk", path=dest_path)
            except Exception as e:
                logger.warning("Failed to delete repository files on disk", path=dest_path, error=str(e))
