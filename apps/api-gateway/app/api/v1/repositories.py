import os
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
from libs.auth.models import User
from libs.auth.dependencies import get_current_user, require_repository_owner
from libs.auth.repository import get_user_repository, UserRepository
from libs.auth.security import decode_access_token
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
    overwrite: bool = Query(True),
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """
    Triggers asynchronous repository cloning, AST parsing, and knowledge graph construction.
    Protected by user authentication and URL sanitization against argument injection and SSRF.
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
                    # Verify current user owns this repository before overwriting
                    if user_repo.is_repository_owner(current_user.id, r["id"]):
                        logger.info(f"Overwriting old scan for repository name {repo_name} (ID: {r['id']})")
                        cleanup_service.cleanup(r["id"])
        except Exception as e:
            logger.warning(f"Failed to run overwrite cleanup for {repo_name}", error=str(e))

    # Assign repository ownership to authenticated user
    user_repo.assign_repository_owner(current_user.id, repository_id, role="owner")

    # Dispatch Celery indexing task
    try:
        celery_app.send_task(
            "gitty.tasks.index_repository",
            args=[repository_id, url]
        )
    except Exception as e:
        logger.error("Failed to queue indexing task in Celery", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to queue analysis task: {str(e)}")

    logger.info("Queued repository analysis task", repository_id=repository_id, user_id=current_user.id)
    return {
        "repository_id": repository_id,
        "status": "queued"
    }

@router.delete("/repositories/{repo_id}")
def delete_repository(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
):
    """
    Deletes repository, associated graph nodes/edges, and vector representations.
    Protected against IDOR: only the owning user may delete the repository.
    """
    validate_repository_id(repo_id)
    if not user_repo.is_repository_owner(current_user.id, repo_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have permission to delete repository '{repo_id}'."
        )

    try:
        cleanup_service = RepositoryCleanupService(settings.SQLITE_DB_PATH)
        cleanup_service.cleanup(repo_id)
        return {"status": "success", "message": f"Repository {repo_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete repository {repo_id}", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/repositories/{repo_id}/progress")
async def progress_stream(
    repo_id: str,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = None,
    user_repo: UserRepository = Depends(get_user_repository)
):
    """
    Server-Sent Events (SSE) stream for live repository ingestion progress.
    Uses async Redis to prevent thread-blocking of FastAPI event loop.
    Protected by token verification and repository authorization.
    """
    validate_repository_id(repo_id)

    # Resolve token from query param or header (EventSource compatibility)
    auth_token = token
    if not auth_token and authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split(" ")[1]

    if not auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication token required for progress stream")
    try:
        payload = decode_access_token(auth_token)
        user_id = payload.get("sub")
        if not user_id or not user_repo.is_repository_owner(user_id, repo_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view progress for this repository")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")

    async def event_generator():
        r = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"repo_progress:{repo_id}")
        
        try:
            # Initial SSE event
            yield f"data: {json.dumps({'status': 'queued', 'message': 'Connecting live log stream...'})}\n\n"
            
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("data"):
                    data = message['data'].decode('utf-8')
                    yield f"data: {data}\n\n"
                    
                    try:
                        msg_obj = json.loads(data)
                        if msg_obj.get("status") in ("completed", "failed"):
                            break
                    except Exception:
                        pass
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

