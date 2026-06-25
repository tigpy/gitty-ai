from fastapi import APIRouter
from .health import router as health_router
from .search import router as search_router
from .rag import router as rag_router
from .chat import router as chat_router
from .graph import router as graph_router
from .agents import router as agents_router
from .repositories import router as repositories_router

router = APIRouter()

router.include_router(health_router, tags=["Health"])
router.include_router(search_router, tags=["Search"])
router.include_router(rag_router, tags=["RAG"])
router.include_router(chat_router, prefix="/chat", tags=["Chat"])
router.include_router(graph_router, prefix="/graph", tags=["Graph"])
router.include_router(agents_router, prefix="/agents", tags=["Agents"])
router.include_router(repositories_router, tags=["Repositories"])


