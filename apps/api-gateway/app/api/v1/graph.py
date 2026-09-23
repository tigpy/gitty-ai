from fastapi import APIRouter, HTTPException, Depends, status
from libs.shared_kernel.validation import validate_repository_id
from services.graph_service.application.graph_application_service import GraphApplicationService
from services.graph_service.infrastructure.repositories.graph_repository_factory import get_graph_repository
from services.graph_service.domain.entities.graph_entities import RepositoryGraphResponse, NodeDetailsResponse

router = APIRouter()

def get_graph_service() -> GraphApplicationService:
    repo = get_graph_repository()
    return GraphApplicationService(repo)

def _require_node_in_repository(service: GraphApplicationService, node_id: str, repo_id: str) -> None:
    """Validate that node belongs to the requested repository to preserve repository-bound isolation."""
    bound = service.repository_id_for_node(node_id)
    if not bound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node not found: {node_id}")
    if bound != repo_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Node does not belong to the requested repository."
        )

@router.get("/repositories")
def list_repositories(
    service: GraphApplicationService = Depends(get_graph_service)
):
    try:
        return service.get_repositories()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/repositories/{repo_id}/data", response_model=RepositoryGraphResponse)
def get_repository_graph(
    repo_id: str,
    service: GraphApplicationService = Depends(get_graph_service)
):
    validate_repository_id(repo_id)
    try:
        return service.get_repository_graph(repo_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/repositories/{repo_id}/expand/{node_id}", response_model=RepositoryGraphResponse)
def expand_node(
    repo_id: str,
    node_id: str,
    service: GraphApplicationService = Depends(get_graph_service)
):
    validate_repository_id(repo_id)
    _require_node_in_repository(service, node_id, repo_id)
    try:
        return service.expand_node(node_id, repo_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/nodes/{node_id}", response_model=NodeDetailsResponse)
def get_node_details(
    node_id: str,
    repo_id: str,
    service: GraphApplicationService = Depends(get_graph_service)
):
    validate_repository_id(repo_id)
    _require_node_in_repository(service, node_id, repo_id)
    try:
        return service.get_node_details(node_id, repo_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/nodes/{node_id}/traversal", response_model=RepositoryGraphResponse)
def traverse_node(
    node_id: str,
    service: GraphApplicationService = Depends(get_graph_service)
):
    """
    Call-graph traversal verified by checking repository bounding node existence.
    """
    bound_repo = service.repository_id_for_node(node_id)
    if not bound_repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node not found: {node_id}")
    try:
        return service.traverse_node(node_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

