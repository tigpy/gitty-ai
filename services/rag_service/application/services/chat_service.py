import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from libs.config import get_settings
from libs.events.schemas import (
    ConversationStartedV1,
    ConversationMessageAddedV1,
    ConversationEndedV1,
    ConversationContextRetrievedV1
)
from libs.core.message_bus.interfaces.event_bus import IEventBus
from libs.ai.llms import BaseLLM, get_llm_provider
from services.vector_service.application.services.semantic_search_service import SemanticSearchService
from services.vector_service.domain.value_objects.chunk import Chunk
from ...domain.entities.chat_session import ChatSession, ChatMessage
from ...domain.entities.retrieved_chunk import RetrievedChunk
from ...domain.repositories.chat_session_repository import IChatSessionRepository
from .prompt_builder import PromptBuilder

class ChatService:
    def __init__(
        self,
        search_service: SemanticSearchService,
        session_repo: IChatSessionRepository,
        llm_provider: Optional[BaseLLM] = None,
        publisher: Optional[IEventBus] = None
    ):
        self.settings = get_settings()
        self.search_service = search_service
        self.session_repo = session_repo
        self.llm_provider = llm_provider or get_llm_provider(
            self.settings.LLM_PROVIDER,
            self.settings.LLM_MODEL
        )
        self.publisher = publisher
        self.prompt_builder = PromptBuilder()

    def create_session(self, repository_id: str) -> ChatSession:
        session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=session_id,
            repository_id=repository_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            messages=[]
        )
        self.session_repo.create_session(session)
        
        if self.publisher:
            try:
                event = ConversationStartedV1(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    session_id=session_id,
                    repository_id=repository_id
                )
                self.publisher.publish("chat.started", event)
            except Exception:
                pass
                
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.session_repo.get_session(session_id)

    def list_sessions(self, repository_id: Optional[str] = None) -> List[ChatSession]:
        return self.session_repo.list_sessions(repository_id)

    def delete_session(self, session_id: str) -> None:
        self.session_repo.delete_session(session_id)
        
        if self.publisher:
            try:
                event = ConversationEndedV1(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    session_id=session_id
                )
                self.publisher.publish("chat.ended", event)
            except Exception:
                pass

    def send_message(
        self,
        session_id: str,
        content: str,
        include_code: bool = True,
        include_docs: bool = True,
        include_security: bool = True,
        limit: int = 5,
        min_score: float = 0.5
    ) -> ChatMessage:
        session = self.session_repo.get_session(session_id)
        if not session:
            raise ValueError(f"Chat session not found: {session_id}")

        # 1. Load conversation history (N turns) *before* saving user message
        history = self.session_repo.load_recent_history(
            session_id=session_id,
            limit=self.settings.CHAT_HISTORY_LIMIT
        )

        # 2. Save user message
        user_message_id = str(uuid.uuid4())
        user_msg = ChatMessage(
            message_id=user_message_id,
            session_id=session_id,
            role="user",
            content=content,
            timestamp=datetime.now(timezone.utc)
        )
        self.session_repo.add_message(user_msg)

        if self.publisher:
            try:
                event = ConversationMessageAddedV1(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    session_id=session_id,
                    message_id=user_message_id,
                    role="user",
                    content=content
                )
                self.publisher.publish("chat.message_added", event)
            except Exception:
                pass

        start_time = time.perf_counter()

        # 3. Retrieve code, documentation, and security chunks.
        # Use (Chunk, score) pairs so the real Qdrant cosine score is preserved
        # all the way to the citation output instead of being discarded.
        retrieved_pairs: List[tuple] = []  # (Chunk, float score)

        if include_code or include_docs:
            chunks = self.search_service.retrieve_context(
                repository_id=session.repository_id,
                query=content,
                limit=limit
            )
            for c in chunks:
                is_code = c.chunk_type in ("FUNCTION", "CLASS", "FILE")
                is_doc = c.chunk_type == "DOCUMENTATION"
                if (include_code and is_code) or (include_docs and is_doc):
                    score = c.metadata.get("_score", 0.0) if c.metadata else 0.0
                    retrieved_pairs.append((c, score))

        if include_security:
            sec_results = self.search_service.search_security_findings(
                repo_id=session.repository_id,
                query=content,
                limit=limit,
                min_score=min_score
            )
            for res in sec_results:
                chunk = Chunk(
                    id=str(uuid.uuid4()),
                    text=res.snippet,
                    chunk_type="SECURITY_FINDING",
                    metadata={
                        "file_path": res.file_path,
                        "symbol_name": res.symbol_name,
                        "chunk_type": "SECURITY_FINDING",
                        "_score": res.score,
                    },
                    content_hash="",
                    version=1
                )
                retrieved_pairs.append((chunk, res.score))

        # Sort by score descending, cap to limit
        retrieved_pairs.sort(key=lambda x: x[1], reverse=True)
        retrieved_pairs = retrieved_pairs[:limit]
        retrieved_chunks = [pair[0] for pair in retrieved_pairs]

        if self.publisher:
            try:
                ctx_event = ConversationContextRetrievedV1(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    session_id=session_id,
                    chunk_count=len(retrieved_chunks)
                )
                self.publisher.publish("chat.context_retrieved", ctx_event)
            except Exception:
                pass

        # 4. Construct prompt via PromptBuilder
        prompt = self.prompt_builder.build_chat_prompt(
            question=content,
            retrieved_chunks=retrieved_chunks,
            history=history,
            repository_id=session.repository_id
        )

        # 5. Generate Answer via LLM
        answer = self.llm_provider.generate(
            prompt=prompt,
            system_prompt=self.prompt_builder.DEFAULT_SYSTEM_PROMPT
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # 6. Map retrieved chunks to citations DTO using real similarity scores
        citations = []
        for chunk, score in retrieved_pairs:
            meta = chunk.metadata or {}
            citations.append(RetrievedChunk(
                score=round(score, 4),
                file_path=meta.get("file_path", "unknown"),
                symbol_name=meta.get("symbol_name"),
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                chunk_type=chunk.chunk_type
            ))

        # 7. Create metadata dict
        meta_dict = {
            "provider": self.llm_provider.provider_name,
            "model": self.llm_provider.model_name,
            "latency_ms": latency_ms,
            "prompt_version": self.prompt_builder.PROMPT_VERSION
        }

        # 8. Save assistant message
        assistant_message_id = str(uuid.uuid4())
        assistant_msg = ChatMessage(
            message_id=assistant_message_id,
            session_id=session_id,
            role="assistant",
            content=answer,
            timestamp=datetime.now(timezone.utc),
            citations=citations,
            metadata=meta_dict
        )
        self.session_repo.add_message(assistant_msg)

        if self.publisher:
            try:
                event = ConversationMessageAddedV1(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    session_id=session_id,
                    message_id=assistant_message_id,
                    role="assistant",
                    content=answer
                )
                self.publisher.publish("chat.message_added", event)
            except Exception:
                pass

        return assistant_msg
