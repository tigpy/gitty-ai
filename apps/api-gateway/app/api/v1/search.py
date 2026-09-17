from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from libs.shared_kernel.validation import validate_repository_id
from libs.auth.models import User
from libs.auth.dependencies import get_current_user, require_repository_owner
from libs.auth.repository import get_user_repository, UserRepository
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.vector_service.infrastructure.vector_store.qdrant_repository import QdrantRepository
from services.vector_service.infrastructure.embeddings.sentence_transformer_provider import SentenceTransformerProvider
from services.vector_service.infrastructure.embeddings.sqlite_embedding_cache import SQLiteEmbeddingCache
from services.vector_service.application.services.embedding_service import EmbeddingService
from services.vector_service.application.services.semantic_search_service import SemanticSearchService
from services.vector_service.domain.entities.search_result import SearchResult

router = APIRouter()

class SemanticSearchRequest(BaseModel):
    repository_id: str
    query: str
    limit: int = 10

class SimilarSearchRequest(BaseModel):
    repository_id: str
    code: str
    limit: int = 10

class SecuritySearchRequest(BaseModel):
    repository_id: str
    query: str
    limit: int = 10

def get_search_service() -> SemanticSearchService:
    sqlite_repo = SQLiteGraphRepository()
    vector_repo = QdrantRepository()
    provider = SentenceTransformerProvider()
    cache = SQLiteEmbeddingCache()
    embed_service = EmbeddingService(provider, cache)
    return SemanticSearchService(vector_repo, embed_service)

@router.post("/search/semantic", response_model=List[SearchResult])
def search_semantic(
    request: SemanticSearchRequest,
    current_user: User = Depends(get_current_user),
    service: SemanticSearchService = Depends(get_search_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    validate_repository_id(request.repository_id)
    if not user_repo.is_repository_owner(current_user.id, request.repository_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have access to repository '{request.repository_id}'."
        )
    try:
        return service.search_semantic(
            repo_id=request.repository_id,
            query=request.query,
            limit=request.limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search/similar", response_model=List[SearchResult])
def search_similar(
    request: SimilarSearchRequest,
    current_user: User = Depends(get_current_user),
    service: SemanticSearchService = Depends(get_search_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    validate_repository_id(request.repository_id)
    if not user_repo.is_repository_owner(current_user.id, request.repository_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have access to repository '{request.repository_id}'."
        )
    try:
        return service.search_similar_code(
            repo_id=request.repository_id,
            code=request.code,
            limit=request.limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search/security", response_model=List[SearchResult])
def search_security(
    request: SecuritySearchRequest,
    current_user: User = Depends(get_current_user),
    service: SemanticSearchService = Depends(get_search_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    validate_repository_id(request.repository_id)
    if not user_repo.is_repository_owner(current_user.id, request.repository_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have access to repository '{request.repository_id}'."
        )
    try:
        return service.search_security_findings(
            repo_id=request.repository_id,
            query=request.query,
            limit=request.limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

