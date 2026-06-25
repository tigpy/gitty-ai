from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from libs.shared_kernel.validation import validate_repository_id
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
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
):
    validate_repository_id(request.repository_id)
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
