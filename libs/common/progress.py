import json
import redis
from libs.config import get_settings
from libs.logging import get_logger

logger = get_logger("progress_publisher")

# Module-level connection pool — created once, reused across all publish_progress()
# calls within the same process.  This avoids opening a new TCP socket on every
# single progress message (which is called ~8-10 times per indexing pipeline run).
_redis_pool: redis.ConnectionPool | None = None

def _get_redis_client() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            max_connections=10,
            socket_connect_timeout=2.0,
        )
    return redis.Redis(connection_pool=_redis_pool)


def publish_progress(repository_id: str, status: str, message: str) -> None:
    """
    Publishes a progress update message to the Redis pub/sub channel for a
    specific repository.  Uses a shared connection pool so that repeated calls
    within the same Celery task worker do not open a fresh TCP connection each
    time.
    """
    try:
        r = _get_redis_client()
        channel = f"repo_progress:{repository_id}"
        payload = json.dumps({"status": status, "message": message})
        r.publish(channel, payload)
        logger.info(
            f"Published progress: {message}",
            repository_id=repository_id,
            status=status,
        )
    except Exception as e:
        logger.warning(
            "Failed to publish progress to Redis",
            repository_id=repository_id,
            error=str(e),
        )
