import os
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from libs.shared_kernel.validation import validate_repository_id
from libs.auth.models import User
from libs.auth.dependencies import get_current_user, require_repository_owner
from libs.auth.repository import get_user_repository, UserRepository
from services.graph_service.application.graph_application_service import GraphApplicationService
from services.graph_service.infrastructure.repositories.graph_repository_factory import get_graph_repository
from services.graph_service.domain.entities.graph_entities import RepositoryGraphResponse, NodeDetailsResponse

router = APIRouter()

def get_graph_service() -> GraphApplicationService:
    repo = get_graph_repository()
    return GraphApplicationService(repo)

@router.get("/repositories")
def list_repositories(
    current_user: User = Depends(get_current_user),
    service: GraphApplicationService = Depends(get_graph_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    try:
        all_repos = service.get_repositories()
        # In DEV_AUTH_BYPASS mode, return all indexed repositories directly
        if os.getenv("DEV_AUTH_BYPASS", "true").lower() in ("true", "1", "yes"):
            return all_repos
        # Filter to repositories the user has access to
        return [r for r in all_repos if user_repo.is_repository_owner(current_user.id, r["id"])]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/repositories/{repo_id}/data", response_model=RepositoryGraphResponse)
def get_repository_graph(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    service: GraphApplicationService = Depends(get_graph_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    validate_repository_id(repo_id)
    if not user_repo.is_repository_owner(current_user.id, repo_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have access to repository '{repo_id}'."
        )
    try:
        return service.get_repository_graph(repo_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/repositories/{repo_id}/expand/{node_id}", response_model=RepositoryGraphResponse)
def expand_node(
    repo_id: str,
    node_id: str,
    current_user: User = Depends(get_current_user),
    service: GraphApplicationService = Depends(get_graph_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    validate_repository_id(repo_id)
    if not user_repo.is_repository_owner(current_user.id, repo_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have access to repository '{repo_id}'."
        )
    try:
        return service.expand_node(node_id, repo_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/nodes/{node_id}", response_model=NodeDetailsResponse)
def get_node_details(
    node_id: str,
    repo_id: str,
    current_user: User = Depends(get_current_user),
    service: GraphApplicationService = Depends(get_graph_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    validate_repository_id(repo_id)
    if not user_repo.is_repository_owner(current_user.id, repo_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have access to repository '{repo_id}'."
        )
    try:
        return service.get_node_details(node_id, repo_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/nodes/{node_id}/traversal", response_model=RepositoryGraphResponse)
def traverse_node(
    node_id: str,
    current_user: User = Depends(get_current_user),
    service: GraphApplicationService = Depends(get_graph_service)
):
    try:
        return service.traverse_node(node_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

