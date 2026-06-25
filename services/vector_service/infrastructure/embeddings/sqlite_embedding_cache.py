import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Optional
from contextlib import contextmanager
from libs.config import get_settings

class SQLiteEmbeddingCache:
    def __init__(self, db_path: Optional[str] = None):
        self.settings = get_settings()
        self.db_path = db_path or self.settings.SQLITE_DB_PATH
        self.create_table()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_table(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    content_hash TEXT,
                    model_name TEXT,
                    embedding TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (content_hash, model_name)
                )
            """)
            conn.commit()

    def get_embedding(self, content_hash: str, model_name: str) -> Optional[List[float]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT embedding FROM embedding_cache WHERE content_hash = ? AND model_name = ?",
                (content_hash, model_name)
            )
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["embedding"])
                except Exception:
                    pass
            return None

    def set_embedding(self, content_hash: str, model_name: str, embedding: List[float]) -> None:
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        embedding_json = json.dumps(embedding)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO embedding_cache (content_hash, model_name, embedding, created_at)
                VALUES (?, ?, ?, ?)
            """, (content_hash, model_name, embedding_json, created_at))
            conn.commit()
