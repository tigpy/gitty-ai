from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

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

    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    CLAUDE_API_KEY: Optional[str] = None
    OLLAMA_URI: str = "http://localhost:11434"
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "llama3"
    CHAT_HISTORY_LIMIT: int = 10


    # Authentication & JWT
    JWT_SECRET_KEY: str = "gitty-insecure-dev-secret-change-in-production-32bytesmin"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Architecture Smell Thresholds
    GITTY_SMELL_FAN_IN_THRESHOLD: int = 10
    GITTY_SMELL_FAN_OUT_THRESHOLD: int = 10
    GITTY_SMELL_MODULE_SIZE_THRESHOLD: int = 750

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def validate_production_security(self) -> None:
        """Enforces mandatory security configuration in production environments."""
        if self.ENV.lower() == "production":
            if self.JWT_SECRET_KEY == "gitty-insecure-dev-secret-change-in-production-32bytesmin" or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("SECURITY ERROR: In production, JWT_SECRET_KEY must be a unique, secure secret with >= 32 characters.")
            if self.NEO4J_PASSWORD == "gitty_password":
                raise ValueError("SECURITY ERROR: In production, default NEO4J_PASSWORD must be replaced.")


_settings: Optional[SystemSettings] = None

def get_settings() -> SystemSettings:
    global _settings
    if _settings is None:
        _settings = SystemSettings()
    return _settings
