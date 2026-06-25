import json
import redis
from libs.config import get_settings
from libs.logging import get_logger

logger = get_logger("progress_publisher")

def publish_progress(repository_id: str, status: str, message: str):
    """
    Publishes a progress update message to the Redis pub/sub channel for a specific repository.
    """
    try:
        settings = get_settings()
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        channel = f"repo_progress:{repository_id}"
        payload = json.dumps({
            "status": status,
            "message": message
        })
        r.publish(channel, payload)
        logger.info(f"Published progress: {message}", repository_id=repository_id, status=status)
    except Exception as e:
        logger.warning("Failed to publish progress to Redis", repository_id=repository_id, error=str(e))
