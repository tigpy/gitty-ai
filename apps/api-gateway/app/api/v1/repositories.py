import re
import uuid
import json
import asyncio
import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.core.config import settings
from services.graph_service.application.repository_cleanup_service import RepositoryCleanupService
from services.graph_service.infrastructure.repositories.graph_repository_factory import get_graph_repository
from libs.shared_kernel.validation import validate_repository_id, validate_repository_url
from libs.logging import get_logger
from celery import Celery

logger = get_logger("repositories_api")
router = APIRouter()

# Configure Celery client
broker_url = f"amqp://guest:guest@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}//"
celery_app = Celery("gitty-worker", broker=broker_url)

class AnalyzeRequest(BaseModel):
    url: str

def generate_repo_id(url: str) -> str:
    name = url.rstrip("/").split("/")[-1].replace(".git", "")
    clean_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name).lower()
    clean_name = re.sub(r"-+", "-", clean_name).strip("-")
    if not clean_name:
        clean_name = "repo"
    return f"{clean_name}-{uuid.uuid4().hex[:8]}"

@router.post("/repositories/analyze")
def analyze_repository(
    request: AnalyzeRequest,
    overwrite: bool = Query(True)
):
    """
    Triggers asynchronous repository cloning, AST parsing, and knowledge graph construction.
    Protected by URL sanitization against argument injection and SSRF.
    """
    raw_url = str(request.url).strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Repository URL is required")

    # Validate against argument injection and SSRF
    try:
        url = validate_repository_url(raw_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Generate repository ID
    repository_id = generate_repo_id(url)
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")

    # Cleanup service for overwriting existing repo scans with the same base name
    cleanup_service = RepositoryCleanupService(settings.SQLITE_DB_PATH)
    
    if overwrite:
        try:
            repo_db = get_graph_repository()
            existing_repos = repo_db.list_repositories()
            for r in existing_repos:
                if r.get("name") == repo_name:
                    logger.info(f"Overwriting old scan for repository name {repo_name} (ID: {r['id']})")
                    cleanup_service.cleanup(r["id"])
        except Exception as e:
            logger.warning(f"Failed to run overwrite cleanup for {repo_name}", error=str(e))

    # Dispatch Celery indexing task
    try:
        celery_app.send_task(
            "gitty.tasks.index_repository",
            args=[repository_id, url]
        )
    except Exception as e:
        logger.error("Failed to queue indexing task in Celery", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to queue analysis task: {str(e)}")

    logger.info("Queued repository analysis task", repository_id=repository_id)
    return {
        "repository_id": repository_id,
        "status": "queued"
    }

@router.delete("/repositories/{repo_id}")
def delete_repository(
    repo_id: str
):
    """
    Deletes repository, associated graph nodes/edges, and vector representations.
    """
    validate_repository_id(repo_id)

    try:
        cleanup_service = RepositoryCleanupService(settings.SQLITE_DB_PATH)
        cleanup_service.cleanup(repo_id)
        return {"status": "success", "message": f"Repository {repo_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete repository {repo_id}", error=str(e))
@router.get("/repositories/{repo_id}/status")
async def get_repository_status(
    repo_id: str
):
    """
    Returns the authoritative repository status from Redis and SQLite.
    Status values: 'queued', 'processing', 'completed', 'failed', 'unknown'.
    """
    validate_repository_id(repo_id)

    # 1. Check Redis for active/cached status
    redis_status = None
    redis_message = None
    try:
        r = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        cached = await r.get(f"repo_status:{repo_id}")
        await r.aclose()
        if cached:
            d_str = cached.decode("utf-8") if isinstance(cached, bytes) else cached
            payload = json.loads(d_str)
            redis_status = payload.get("status")
            redis_message = payload.get("message")
    except Exception:
        pass

    # 2. Check SQLite repository record
    sqlite_status = None
    try:
        repo_db = get_graph_repository()
        repo_data = repo_db.get_repository(repo_id)
        if repo_data:
            sqlite_status = repo_data.get("status")
    except Exception:
        pass

    effective_status = redis_status or sqlite_status or "unknown"
    if sqlite_status in ("completed", "failed") and redis_status not in ("completed", "failed"):
        effective_status = sqlite_status

    return {
        "repository_id": repo_id,
        "status": effective_status,
        "message": redis_message,
        "sqlite_status": sqlite_status,
        "redis_status": redis_status
    }

@router.get("/repositories/{repo_id}/progress")
async def progress_stream(
    repo_id: str
):
    """
    Server-Sent Events (SSE) stream for live repository ingestion progress.
    Uses async Redis to prevent thread-blocking of FastAPI event loop.
    """
    validate_repository_id(repo_id)

    async def event_generator():
        r = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"repo_progress:{repo_id}")
        
        try:
            # Initial SSE event
            yield f"data: {json.dumps({'status': 'queued', 'message': 'Connecting live log stream...'})}\n\n"

            # Check if there is already a cached status in Redis (handles rapid failure/completion)
            cached_status = None
            try:
                get_res = r.get(f"repo_status:{repo_id}")
                if asyncio.iscoroutine(get_res) or hasattr(get_res, "__await__"):
                    cached_status = await get_res
                elif isinstance(get_res, (str, bytes)):
                    cached_status = get_res
            except Exception:
                pass

            if cached_status:
                try:
                    data_str = cached_status.decode('utf-8') if isinstance(cached_status, bytes) else cached_status
                    data_obj = json.loads(data_str)
                    yield f"data: {data_str}\n\n"
                    if data_obj.get("status") in ("completed", "failed"):
                        return
                except Exception:
                    pass
            
            idle_ticks = 0
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("data"):
                    idle_ticks = 0
                    data = message['data'].decode('utf-8')
                    yield f"data: {data}\n\n"
                    
                    try:
                        msg_obj = json.loads(data)
                        if msg_obj.get("status") in ("completed", "failed"):
                            break
                    except Exception:
                        pass
                else:
                    idle_ticks += 1
                    # Periodically check Redis status cache every 5 ticks in case a pubsub message was missed
                    if idle_ticks % 5 == 0:
                        cached = None
                        try:
                            get_res = r.get(f"repo_status:{repo_id}")
                            if asyncio.iscoroutine(get_res) or hasattr(get_res, "__await__"):
                                cached = await get_res
                            elif isinstance(get_res, (str, bytes)):
                                cached = get_res
                        except Exception:
                            pass

                        if cached:
                            try:
                                d_str = cached.decode('utf-8') if isinstance(cached, bytes) else cached
                                d_obj = json.loads(d_str)
                                if d_obj.get("status") in ("completed", "failed"):
                                    yield f"data: {d_str}\n\n"
                                    break
                            except Exception:
                                pass
                    # Safety timeout after 10 minutes of total inactivity
                    if idle_ticks > 600:
                        yield f"data: {json.dumps({'status': 'failed', 'message': 'Analysis timed out'})}\n\n"
                        break

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("SSE client disconnected from progress stream", repo_id=repo_id)
        except Exception as e:
            yield f"data: {json.dumps({'status': 'failed', 'message': f'Connection lost: {str(e)}'})}\n\n"
        finally:
            try:
                await pubsub.unsubscribe(f"repo_progress:{repo_id}")
                await pubsub.close()
                await r.close()
            except Exception:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")

