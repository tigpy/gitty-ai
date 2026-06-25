from fastapi import APIRouter, Depends
from dependency_injector.wiring import inject, Provide
from datetime import datetime, timezone
from ...core.container import ApplicationContainer
from ...core.providers import ConnectionChecker

router = APIRouter()

@router.get("/health")
@inject
def get_health(
    checker: ConnectionChecker = Depends(Provide[ApplicationContainer.connection_checker])
):
    redis_status = checker.check_redis()
    rabbitmq_status = checker.check_rabbitmq()
    neo4j_status = checker.check_neo4j()
    qdrant_status = checker.check_qdrant()

    # The API is healthy if critical connections are okay.
    # Note: Neo4j could be skipped or unhealthy if in SQLite mode, which is allowed.
    is_healthy = "unhealthy" not in redis_status and "unhealthy" not in rabbitmq_status and "unhealthy" not in qdrant_status

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "services": {
            "redis": redis_status,
            "rabbitmq": rabbitmq_status,
            "neo4j": neo4j_status,
            "qdrant": qdrant_status
        }
    }
