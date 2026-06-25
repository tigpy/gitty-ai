import os
import re
import uuid
import redis
import json
import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.core.config import settings
from services.graph_service.application.repository_cleanup_service import RepositoryCleanupService
from services.graph_service.infrastructure.repositories.graph_repository_factory import get_graph_repository
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
    # Extract repo name from URL and suffix with an 8-char UUID segment
    name = url.rstrip("/").split("/")[-1].replace(".git", "")
    # Ensure ID matches REPO_ID_REGEX: ^[a-zA-Z0-9_-]+$
    clean_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name).lower()
    clean_name = re.sub(r"-+", "-", clean_name).strip("-")
    if not clean_name:
        clean_name = "repo"
    return f"{clean_name}-{uuid.uuid4().hex[:8]}"

@router.post("/repositories/analyze")
def analyze_repository(request: AnalyzeRequest, overwrite: bool = Query(True)):
    url = str(request.url).strip()
    if not url:
        raise HTTPException(status_code=400, detail="Repository URL is required")

    # Generate repository ID
    repository_id = generate_repo_id(url)
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")

    # Cleanup service for overwriting existing repo scans with the same base name
    cleanup_service = RepositoryCleanupService(settings.SQLITE_DB_PATH)
    
    if overwrite:
        try:
            # Look up repositories with the same name to clean them up
            repo_db = get_graph_repository()
            existing_repos = repo_db.list_repositories()
            for r in existing_repos:
                if r.get("name") == repo_name:
                    logger.info(f"Overwriting old scan for repository name {repo_name} (ID: {r['id']})")
                    cleanup_service.cleanup(r["id"])
        except Exception as e:
            logger.warning(f"Failed to run overwrite cleanup for {repo_name}", error=str(e))

    # Send the task to Celery
    try:
        celery_app.send_task(
            "gitty.tasks.index_repository",
            args=[repository_id, url]
        )
    except Exception as e:
        logger.error("Failed to queue indexing task in Celery", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to queue analysis task: {str(e)}")

    return {
        "repository_id": repository_id,
        "status": "queued"
    }

@router.delete("/repositories/{repo_id}")
def delete_repository(repo_id: str):
    try:
        cleanup_service = RepositoryCleanupService(settings.SQLITE_DB_PATH)
        cleanup_service.cleanup(repo_id)
        return {"status": "success", "message": f"Repository {repo_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete repository {repo_id}", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/repositories/{repo_id}/progress")
async def progress_stream(repo_id: str):
    async def event_generator():
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        pubsub = r.pubsub()
        pubsub.subscribe(f"repo_progress:{repo_id}")
        
        try:
            # Initial SSE event
            yield f"data: {json.dumps({'status': 'queued', 'message': 'Connecting live log stream...'})}\n\n"
            
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    data = message['data'].decode('utf-8')
                    yield f"data: {data}\n\n"
                    
                    try:
                        msg_obj = json.loads(data)
                        if msg_obj.get("status") in ("completed", "failed"):
                            break
                    except Exception:
                        pass
                await asyncio.sleep(0.1)
        except Exception as e:
            yield f"data: {json.dumps({'status': 'failed', 'message': f'Connection lost: {str(e)}'})}\n\n"
        finally:
            try:
                pubsub.unsubscribe(f"repo_progress:{repo_id}")
                pubsub.close()
            except Exception:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")
