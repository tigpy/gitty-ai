import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

INSECURE_NEO4J_PASSWORDS = {
    "gitty_password",
    "change-me-to-a-secure-password",
    "neo4j",
    "password",
}


class SystemSettings(BaseSettings):
    ENV: str = "development"

    # Cache / Session Store
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Queue
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672

    # Graph modes & Neo4j
    GRAPH_MODE: str = "sqlite" # "sqlite" or "neo4j"
    SQLITE_DB_PATH: str = "gitty_graph.db"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "gitty_password"

    # Vector store
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # Embeddings. Mock is never the default and is rejected in production.
    EMBEDDING_PROVIDER: str = "sentence-transformers"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384

    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    OLLAMA_URI: str = "http://localhost:11434"
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "llama3"
    CHAT_HISTORY_LIMIT: int = 10

    # ── Local LLM (llama.cpp) ────────────────────────────────────────────
    # Set GITTY_LLM_ENABLED=true and start a llama.cpp server before use.
    # Example server command:
    #   llama-server --model "D:\...\Qwen3.5-9B-Q4_K_M.gguf" \
    #       --host 127.0.0.1 --port 8080 --ctx-size 8192
    # The GGUF path is NEVER stored here — it belongs only to the server CLI.
    GITTY_LLM_ENABLED: bool = False
    GITTY_LLM_BASE_URL: str = "http://127.0.0.1:8080"
    GITTY_LLM_MODEL: str = "qwen3.5-9b-q4"
    GITTY_LLM_TIMEOUT: float = 120.0

    # Hybrid RAG graph expansion. Vector hits stay the seeds. These caps stop
    # the property graph from dumping a whole repository into the prompt.
    # Depth 2 reaches a call (function -> call node -> callee) without a full walk.
    RAG_MAX_GRAPH_SEEDS: int = 5
    RAG_MAX_GRAPH_DEPTH: int = 2
    RAG_MAX_GRAPH_NODES: int = 24
    RAG_MAX_GRAPH_RELATIONSHIPS: int = 32

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"

    # Architecture Smell Thresholds
    GITTY_SMELL_FAN_IN_THRESHOLD: int = 10
    GITTY_SMELL_FAN_OUT_THRESHOLD: int = 10
    GITTY_SMELL_MODULE_SIZE_THRESHOLD: int = 750

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def model_post_init(self, __context) -> None:
        if self.SQLITE_DB_PATH and not os.path.isabs(self.SQLITE_DB_PATH):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.SQLITE_DB_PATH = os.path.normpath(os.path.join(project_root, self.SQLITE_DB_PATH))

    def validate_production_security(self) -> None:
        """Enforces mandatory security configuration in production environments."""
        if self.ENV.lower() != "production":
            return
        if not self.NEO4J_PASSWORD or self.NEO4J_PASSWORD.strip() in INSECURE_NEO4J_PASSWORDS:
            raise ValueError(
                "SECURITY ERROR: In production, NEO4J_PASSWORD must be replaced with a unique credential."
            )
        if (self.EMBEDDING_PROVIDER or "").strip().lower() in {"mock", "fake", "hash"}:
            raise ValueError(
                "SECURITY ERROR: EMBEDDING_PROVIDER=mock is not allowed in production. "
                "Production must use a real embedding model."
            )


_settings: Optional[SystemSettings] = None

def get_settings() -> SystemSettings:
    global _settings
    if _settings is None:
        _settings = SystemSettings()
    return _settings

def reset_settings_cache() -> None:
    """Test helper. Production startup reads settings once per process."""
    global _settings
    _settings = None
