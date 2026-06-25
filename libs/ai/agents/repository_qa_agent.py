from typing import Dict, Any, List
from .base_agent import BaseAgent, AgentResult

class RepositoryQAAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "RepositoryQAAgent"

    def analyze(self, repository_id: str, context: Dict[str, Any]) -> AgentResult:
        try:
            from services.rag_service.application.services.rag_service import RAGService
            from services.rag_service.domain.entities.rag_query import RAGQuery
            from services.vector_service.infrastructure.vector_store.qdrant_repository import QdrantRepository
            from services.vector_service.infrastructure.embeddings.sentence_transformer_provider import SentenceTransformerProvider
            from services.vector_service.infrastructure.embeddings.sqlite_embedding_cache import SQLiteEmbeddingCache
            from services.vector_service.application.services.embedding_service import EmbeddingService
            from services.vector_service.application.services.semantic_search_service import SemanticSearchService
            from libs.ai.llms import get_llm_provider
            from libs.config import get_settings

            settings = get_settings()
            vector_repo = QdrantRepository()
            provider = SentenceTransformerProvider()
            cache = SQLiteEmbeddingCache(db_path=settings.SQLITE_DB_PATH)
            embed_service = EmbeddingService(provider, cache)
            search_service = SemanticSearchService(vector_repo, embed_service)
            llm = get_llm_provider(settings.LLM_PROVIDER, settings.LLM_MODEL)
            
            rag = RAGService(search_service=search_service, llm_provider=llm)
            
            exec_prompt = (
                f"Generate an executive analyst report for repository {repository_id}. "
                "Outline: 1. Repository Summary, 2. Architecture Summary, 3. Key Components, 4. Potential Risks."
            )
            
            query_obj = RAGQuery(
                repository_id=repository_id,
                question=exec_prompt,
                limit=5,
                include_code=True,
                include_docs=True,
                include_security=True
            )
            
            response = rag.query_repository(query_obj)
            
            findings = [response.answer]
            recommendations = ["Review potential risk factors outlined in the RAG summary.", "Check documentation for architectural design principles."]
            
            return AgentResult(
                agent_name=self.agent_name,
                score=100.0,
                findings=findings,
                recommendations=recommendations,
                severity="INFO",
                metadata={
                    "provider": response.provider,
                    "model": response.model,
                    "latency_ms": response.latency_ms,
                    "citations": [c.model_dump() for c in response.retrieved_chunks]
                }
            )
        except Exception as e:
            fallback_answer = (
                f"Mock Executive Summary for {repository_id}:\n"
                "- Repository Summary: Local source files parsed into Gitty AI knowledge graph.\n"
                "- Architecture Summary: Layered DDD application architecture.\n"
                "- Key Components: Graph builder, vector indexing, scan workers, REST gateway.\n"
                "- Potential Risks: Outdated dependencies or lack of test coverage."
            )
            return AgentResult(
                agent_name=self.agent_name,
                score=100.0,
                findings=[fallback_answer],
                recommendations=["Configure local LLM provider or API keys to run real RAG summarization."],
                severity="INFO",
                metadata={"error": str(e), "status": "fallback"}
            )
