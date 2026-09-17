from fastapi import APIRouter, HTTPException, Depends, status
from services.rag_service.domain.entities.rag_query import RAGQuery
from services.rag_service.domain.entities.rag_response import RAGResponse
from libs.shared_kernel.validation import validate_repository_id
from libs.auth.models import User
from libs.auth.dependencies import get_current_user, require_repository_owner
from libs.auth.repository import get_user_repository, UserRepository
from services.rag_service.application.services.rag_service import RAGService
from .search import get_search_service

router = APIRouter()

def get_rag_service(search_service=Depends(get_search_service)) -> RAGService:
    from libs.core.message_bus.rabbitmq.publisher import RabbitMQPublisher
    from libs.config import get_settings
    
    settings = get_settings()
    publisher = None
    try:
        publisher = RabbitMQPublisher(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT)
    except Exception:
        pass
        
    return RAGService(
        search_service=search_service,
        publisher=publisher
    )

@router.post("/rag/query", response_model=RAGResponse)
def query_rag(
    query: RAGQuery,
    current_user: User = Depends(get_current_user),
    service: RAGService = Depends(get_rag_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    validate_repository_id(query.repository_id)
    if not user_repo.is_repository_owner(current_user.id, query.repository_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have access to repository '{query.repository_id}'."
        )
    try:
        return service.query_repository(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query execution failed: {e}")

