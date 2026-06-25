import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from libs.config import get_settings
from libs.events.schemas import (
    RepositoryQuestionAskedV1,
    RepositoryAnswerGeneratedV1,
    RepositoryAnswerFailedV1
)
from libs.core.message_bus.interfaces.event_bus import IEventBus
from libs.ai.llms import BaseLLM, get_llm_provider
from services.vector_service.application.services.semantic_search_service import SemanticSearchService
from services.vector_service.domain.value_objects.chunk import Chunk
from ...domain.entities.rag_query import RAGQuery
from ...domain.entities.rag_response import RAGResponse
from ...domain.entities.retrieved_chunk import RetrievedChunk
from .prompt_builder import PromptBuilder

class RAGService:
    def __init__(
        self,
        search_service: SemanticSearchService,
        llm_provider: Optional[BaseLLM] = None,
        publisher: Optional[IEventBus] = None
    ):
        self.settings = get_settings()
        self.search_service = search_service
        self.llm_provider = llm_provider or get_llm_provider(
            self.settings.LLM_PROVIDER,
            self.settings.LLM_MODEL
        )
        self.publisher = publisher
        self.prompt_builder = PromptBuilder()

    def query_repository(self, query: RAGQuery) -> RAGResponse:
        start_time = time.perf_counter()
        
        # 1. Publish RepositoryQuestionAskedV1 event
        if self.publisher:
            try:
                asked_event = RepositoryQuestionAskedV1(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    repository_id=query.repository_id,
                    question=query.question,
                    provider=self.llm_provider.provider_name,
                    model=self.llm_provider.model_name
                )
                self.publisher.publish("rag.question_asked", asked_event)
            except Exception:
                pass

        try:
            retrieved_chunks: List[Chunk] = []

            # 2. Retrieve Code & Documentation Chunks
            if query.include_code or query.include_docs:
                chunks = self.search_service.retrieve_context(
                    repository_id=query.repository_id,
                    query=query.question,
                    limit=query.limit
                )
                # Filter based on flags
                for c in chunks:
                    is_code = c.chunk_type in ("FUNCTION", "CLASS", "FILE")
                    is_doc = c.chunk_type == "DOCUMENTATION"
                    if (query.include_code and is_code) or (query.include_docs and is_doc):
                        retrieved_chunks.append(c)

            # 3. Retrieve Security Finding Chunks
            if query.include_security:
                sec_results = self.search_service.search_security_findings(
                    repo_id=query.repository_id,
                    query=query.question,
                    limit=query.limit,
                    min_score=query.min_score
                )
                for res in sec_results:
                    # Map SearchResult to Chunk
                    retrieved_chunks.append(Chunk(
                        id=str(uuid.uuid4()),
                        text=res.snippet,
                        chunk_type="SECURITY_FINDING",
                        metadata={
                            "file_path": res.file_path,
                            "symbol_name": res.symbol_name,
                            "chunk_type": "SECURITY_FINDING"
                        },
                        content_hash="",
                        version=1
                    ))

            # Sort combined chunks by score (if score exists in search metadata, or keep search order)
            # Limit the final retrieved chunk list to keep context tight
            retrieved_chunks = retrieved_chunks[:query.limit]

            if not retrieved_chunks:
                # Fallback context if nothing matches
                pass

            # 4. Construct prompt via PromptBuilder
            prompt = self.prompt_builder.build_rag_prompt(
                question=query.question,
                retrieved_chunks=retrieved_chunks
            )

            # 5. Generate Answer via LLM
            answer = self.llm_provider.generate(
                prompt=prompt,
                system_prompt=self.prompt_builder.DEFAULT_SYSTEM_PROMPT
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # 6. Publish RepositoryAnswerGeneratedV1 event
            if self.publisher:
                try:
                    generated_event = RepositoryAnswerGeneratedV1(
                        event_id=str(uuid.uuid4()),
                        timestamp=datetime.now(timezone.utc),
                        repository_id=query.repository_id,
                        question=query.question,
                        answer=answer,
                        provider=self.llm_provider.provider_name,
                        model=self.llm_provider.model_name,
                        latency_ms=latency_ms
                    )
                    self.publisher.publish("rag.answer_generated", generated_event)
                except Exception:
                    pass

            # Map retrieved chunks to output DTOs
            citations = []
            for c in retrieved_chunks:
                meta = c.metadata or {}
                citations.append(RetrievedChunk(
                    score=0.99,  # Default mock score since SearchResult to Chunk mapping doesn't hold raw float score
                    file_path=meta.get("file_path", "unknown"),
                    symbol_name=meta.get("symbol_name"),
                    start_line=c.start_line,
                    end_line=c.end_line,
                    chunk_type=c.chunk_type
                ))

            return RAGResponse(
                answer=answer,
                retrieved_chunks=citations,
                provider=self.llm_provider.provider_name,
                model=self.llm_provider.model_name,
                latency_ms=latency_ms
            )

        except Exception as e:
            # 7. Publish RepositoryAnswerFailedV1 event on error
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            if self.publisher:
                try:
                    failed_event = RepositoryAnswerFailedV1(
                        event_id=str(uuid.uuid4()),
                        timestamp=datetime.now(timezone.utc),
                        repository_id=query.repository_id,
                        question=query.question,
                        reason=str(e)
                    )
                    self.publisher.publish("rag.answer_failed", failed_event)
                except Exception:
                    pass
            raise e
