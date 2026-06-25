from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from libs.shared_kernel.validation import validate_repository_id
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
def create_session(request: CreateSessionRequest, service: ChatService = Depends(get_chat_service)):
    validate_repository_id(request.repository_id)
    try:
        return service.create_session(request.repository_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}", response_model=ChatSession)
def get_session(session_id: str, service: ChatService = Depends(get_chat_service)):
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session

@router.get("/sessions", response_model=List[ChatSession])
def list_sessions(repository_id: Optional[str] = None, service: ChatService = Depends(get_chat_service)):
    if repository_id:
        validate_repository_id(repository_id)
    try:
        return service.list_sessions(repository_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/messages", response_model=ChatMessage)
def send_message(session_id: str, request: SendMessageRequest, service: ChatService = Depends(get_chat_service)):
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, service: ChatService = Depends(get_chat_service)):
    try:
        service.delete_session(session_id)
        return {"status": "success", "message": "Session deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
