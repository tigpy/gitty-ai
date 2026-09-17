from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from libs.shared_kernel.validation import validate_repository_id
from libs.auth.models import User
from libs.auth.dependencies import get_current_user, require_session_owner
from libs.auth.repository import get_user_repository, UserRepository
from services.rag_service.application.services.chat_service import ChatService
from services.rag_service.infrastructure.persistence.sqlite_session_repository import SQLiteChatSessionRepository
from services.rag_service.domain.entities.chat_session import ChatSession, ChatMessage
from .search import get_search_service

router = APIRouter()

def get_chat_service(search_service=Depends(get_search_service)) -> ChatService:
    from libs.core.message_bus.rabbitmq.publisher import RabbitMQPublisher
    from libs.config import get_settings
    
    settings = get_settings()
    publisher = None
    try:
        publisher = RabbitMQPublisher(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT)
    except Exception:
        pass
        
    session_repo = SQLiteChatSessionRepository()
    return ChatService(
        search_service=search_service,
        session_repo=session_repo,
        publisher=publisher
    )

class CreateSessionRequest(BaseModel):
    repository_id: str

class SendMessageRequest(BaseModel):
    content: str
    include_code: bool = True
    include_docs: bool = True
    include_security: bool = True
    limit: int = 5
    min_score: float = 0.5

@router.post("/sessions", response_model=ChatSession)
def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    validate_repository_id(request.repository_id)
    if not user_repo.is_repository_owner(current_user.id, request.repository_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have access to repository '{request.repository_id}'."
        )

    try:
        session = service.create_session(request.repository_id)
        user_repo.assign_session_owner(current_user.id, session.session_id)
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}", response_model=ChatSession)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    if not user_repo.is_session_owner(current_user.id, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to view this chat session."
        )

    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session

@router.get("/sessions", response_model=List[ChatSession])
def list_sessions(
    repository_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    if repository_id:
        validate_repository_id(repository_id)
        if not user_repo.is_repository_owner(current_user.id, repository_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have access to this repository's sessions."
            )

    try:
        all_sessions = service.list_sessions(repository_id)
        # Filter to sessions owned by the authenticated user
        return [s for s in all_sessions if user_repo.is_session_owner(current_user.id, s.session_id)]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/messages", response_model=ChatMessage)
def send_message(
    session_id: str,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    if not user_repo.is_session_owner(current_user.id, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to send messages in this session."
        )

    try:
        return service.send_message(
            session_id=session_id,
            content=request.content,
            include_code=request.include_code,
            include_docs=request.include_docs,
            include_security=request.include_security,
            limit=request.limit,
            min_score=request.min_score
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    user_repo: UserRepository = Depends(get_user_repository)
):
    if not user_repo.is_session_owner(current_user.id, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to delete this session."
        )

    try:
        service.delete_session(session_id)
        return {"status": "success", "message": "Session deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

