from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from libs.shared_kernel.validation import validate_repository_id
from libs.auth.models import User
from libs.auth.dependencies import get_current_user, require_repository_owner
from libs.auth.repository import get_user_repository, UserRepository
from libs.ai.agents.orchestrator import AgentOrchestrator, RepositoryAnalysisReport

router = APIRouter()

def get_orchestrator() -> AgentOrchestrator:
    from libs.core.message_bus.rabbitmq.publisher import RabbitMQPublisher
    from libs.config import get_settings
    
    settings = get_settings()
    publisher = None
    try:
        publisher = RabbitMQPublisher(host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT)
    except Exception:
        pass
        
    return AgentOrchestrator(publisher=publisher)

class AnalyzeRequest(BaseModel):
    repository_id: str
    changed_component: Optional[str] = None
    timeout: Optional[float] = 30.0

@router.post("/analyze", response_model=RepositoryAnalysisReport)
def analyze_repository(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    user_repo: UserRepository = Depends(get_user_repository)
):
    validate_repository_id(request.repository_id)
    if not user_repo.is_repository_owner(current_user.id, request.repository_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have access to repository '{request.repository_id}'."
        )
    try:
        context = {}
        if request.changed_component:
            context["changed_component"] = request.changed_component
        
        return orchestrator.run_analysis(
            repository_id=request.repository_id,
            context=context,
            timeout=request.timeout
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Autonomous analysis orchestration failed: {str(e)}"
        )

