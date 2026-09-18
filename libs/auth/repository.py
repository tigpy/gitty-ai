import os
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from libs.config import get_settings
from .models import User
from .security import hash_password

class UserRepository:
    def __init__(self, db_path: Optional[str] = None):
        settings = get_settings()
        self.db_path = db_path or getattr(settings, "SQLITE_DB_PATH", "gitty_graph.db")
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_repositories (
                    user_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'owner',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, repository_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_repos_user ON user_repositories(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_repos_repo ON user_repositories(repository_id)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, session_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_session ON user_sessions(session_id)")

    def create_user(self, username: str, email: str, password: str, user_id: Optional[str] = None) -> User:
        user_id = user_id or str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        pwd_hash, salt = hash_password(password)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, username, email, password_hash, salt, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (user_id, username.lower(), email.lower(), pwd_hash, salt, created_at))

        return User(
            id=user_id,
            username=username.lower(),
            email=email.lower(),
            created_at=created_at,
            is_active=True
        )

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, created_at, is_active FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return User(
                    id=row["id"],
                    username=row["username"],
                    email=row["email"],
                    created_at=row["created_at"],
                    is_active=bool(row["is_active"])
                )
            return None

    def get_user_record_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username.lower(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_record_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def _ensure_dev_user(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (id, username, email, password_hash, salt, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, ("dev-user-local", "developer", "dev@gitty.local", "dev_bypass", "salt", datetime.now(timezone.utc).isoformat()))

    def assign_repository_owner(self, user_id: str, repository_id: str, role: str = "owner") -> None:
        if user_id == "dev-user-local":
            self._ensure_dev_user()
        created_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_repositories (user_id, repository_id, role, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, repository_id) DO UPDATE SET role = excluded.role
            """, (user_id, repository_id, role, created_at))

    def is_repository_owner(self, user_id: str, repository_id: str) -> bool:
        if os.getenv("DEV_AUTH_BYPASS", "true").lower() in ("true", "1", "yes"):
            return True
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM user_repositories 
                WHERE user_id = ? AND repository_id = ?
            """, (user_id, repository_id))
            if cursor.fetchone():
                return True
            
            # Check if repo has no registered owners (e.g. legacy/seed repo)
            cursor.execute("SELECT 1 FROM user_repositories WHERE repository_id = ?", (repository_id,))
            has_any_owner = cursor.fetchone() is not None
            # If no owner has been claimed at all, allow initial access, but if owners exist, require match
            return not has_any_owner

    def list_user_repositories(self, user_id: str) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT repository_id FROM user_repositories WHERE user_id = ?", (user_id,))
            return [row["repository_id"] for row in cursor.fetchall()]

    def assign_session_owner(self, user_id: str, session_id: str) -> None:
        if user_id == "dev-user-local":
            self._ensure_dev_user()
        created_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_sessions (user_id, session_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, session_id) DO NOTHING
            """, (user_id, session_id, created_at))

    def is_session_owner(self, user_id: str, session_id: str) -> bool:
        if os.getenv("DEV_AUTH_BYPASS", "true").lower() in ("true", "1", "yes"):
            return True
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM user_sessions 
                WHERE user_id = ? AND session_id = ?
            """, (user_id, session_id))
            if cursor.fetchone():
                return True
            # Check if session has any registered owner
            cursor.execute("SELECT 1 FROM user_sessions WHERE session_id = ?", (session_id,))
            has_any_owner = cursor.fetchone() is not None
            return not has_any_owner

_user_repo: Optional[UserRepository] = None

def get_user_repository() -> UserRepository:
    global _user_repo
    if _user_repo is None:
        _user_repo = UserRepository()
    return _user_repo
