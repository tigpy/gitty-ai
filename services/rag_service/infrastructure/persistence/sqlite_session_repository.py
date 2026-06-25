import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Optional
from contextlib import contextmanager
from libs.config import get_settings
from ...domain.entities.chat_session import ChatSession, ChatMessage
from ...domain.entities.retrieved_chunk import RetrievedChunk
from ...domain.repositories.chat_session_repository import IChatSessionRepository

class SQLiteChatSessionRepository(IChatSessionRepository):
    def __init__(self, db_path: Optional[str] = None):
        self.settings = get_settings()
        self.db_path = db_path or self.settings.SQLITE_DB_PATH
        self.create_tables()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_tables(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    repository_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citations TEXT,
                    metadata TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session 
                ON chat_messages(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_repository 
                ON chat_sessions(repository_id)
            """)

    def create_session(self, session: ChatSession) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_sessions (session_id, repository_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (
                    session.session_id,
                    session.repository_id,
                    session.created_at.isoformat().replace("+00:00", "Z"),
                    session.updated_at.isoformat().replace("+00:00", "Z")
                )
            )

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id, repository_id, created_at, updated_at FROM chat_sessions WHERE session_id = ?",
                (session_id,)
            )
            session_row = cursor.fetchone()
            if not session_row:
                return None
            
            cursor.execute(
                "SELECT message_id, session_id, role, content, citations, metadata, timestamp FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            message_rows = cursor.fetchall()
            messages = []
            for row in message_rows:
                citations = None
                if row["citations"]:
                    citations = [RetrievedChunk(**c) for c in json.loads(row["citations"])]
                metadata = {}
                if row["metadata"]:
                    metadata = json.loads(row["metadata"])
                    
                messages.append(ChatMessage(
                    message_id=row["message_id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                    citations=citations,
                    metadata=metadata
                ))
                
            return ChatSession(
                session_id=session_row["session_id"],
                repository_id=session_row["repository_id"],
                created_at=datetime.fromisoformat(session_row["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(session_row["updated_at"].replace("Z", "+00:00")),
                messages=messages
            )

    def add_message(self, message: ChatMessage) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            citations_str = None
            if message.citations is not None:
                citations_str = json.dumps([c.model_dump() for c in message.citations])
            metadata_str = json.dumps(message.metadata)
            
            cursor.execute(
                "INSERT INTO chat_messages (message_id, session_id, role, content, citations, metadata, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    message.message_id,
                    message.session_id,
                    message.role,
                    message.content,
                    citations_str,
                    metadata_str,
                    message.timestamp.isoformat().replace("+00:00", "Z")
                )
            )
            now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            cursor.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
                (now_str, message.session_id)
            )

    def list_sessions(self, repository_id: Optional[str] = None) -> List[ChatSession]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if repository_id:
                cursor.execute(
                    "SELECT session_id, repository_id, created_at, updated_at FROM chat_sessions WHERE repository_id = ? ORDER BY updated_at DESC",
                    (repository_id,)
                )
            else:
                cursor.execute(
                    "SELECT session_id, repository_id, created_at, updated_at FROM chat_sessions ORDER BY updated_at DESC"
                )
            rows = cursor.fetchall()
            sessions = []
            for row in rows:
                sessions.append(ChatSession(
                    session_id=row["session_id"],
                    repository_id=row["repository_id"],
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
                    messages=[]
                ))
            return sessions

    def delete_session(self, session_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))

    def load_recent_history(self, session_id: str, limit: int) -> List[ChatMessage]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT message_id, session_id, role, content, citations, metadata, timestamp 
                FROM (
                    SELECT message_id, session_id, role, content, citations, metadata, timestamp 
                    FROM chat_messages 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ) 
                ORDER BY timestamp ASC
                """,
                (session_id, limit)
            )
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                citations = None
                if row["citations"]:
                    citations = [RetrievedChunk(**c) for c in json.loads(row["citations"])]
                metadata = {}
                if row["metadata"]:
                    metadata = json.loads(row["metadata"])
                    
                messages.append(ChatMessage(
                    message_id=row["message_id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                    citations=citations,
                    metadata=metadata
                ))
            return messages
