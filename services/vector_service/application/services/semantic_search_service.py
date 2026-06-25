import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from libs.events.schemas import SemanticSearchCompletedV1
from libs.core.message_bus.interfaces.event_bus import IEventBus
from ...domain.entities.vector_document import VectorDocument
from ...domain.entities.search_result import SearchResult
from ...domain.value_objects.chunk import Chunk
from ...domain.repositories.vector_repository import IVectorRepository
from .embedding_service import EmbeddingService

class SemanticSearchService:
    def __init__(
        self,
        vector_repo: IVectorRepository,
        embedding_service: EmbeddingService,
        publisher: Optional[IEventBus] = None
    ):
        self.vector_repo = vector_repo
        self.embedding_service = embedding_service
        self.publisher = publisher

    def _to_search_result(self, doc: VectorDocument) -> SearchResult:
        payload = doc.payload
        return SearchResult(
            score=payload.get("_score", 0.0),
            file_path=payload.get("file_path", ""),
            symbol_name=payload.get("symbol_name"),
            chunk_type=payload.get("chunk_type", "UNKNOWN"),
            snippet=payload.get("text_content", "")
        )

    def search_semantic(
        self, 
        repo_id: str, 
        query: str, 
        limit: int = 10, 
        min_score: float = 0.65
    ) -> List[SearchResult]:
        """Performs semantic search (text-to-code) across code and documentation collections."""
        query_vector = self.embedding_service.embed_query(query)
        
        # Search code collection
        code_docs = self.vector_repo.search_similarity(
            query_vector=query_vector,
            collection_name="repository_code_chunks",
            limit=limit,
            min_score=min_score,
            filter_dict={"repository_id": repo_id}
        )

        # Search document collection
        doc_docs = self.vector_repo.search_similarity(
            query_vector=query_vector,
            collection_name="repository_document_chunks",
            limit=limit,
            min_score=min_score,
            filter_dict={"repository_id": repo_id}
        )

        # Merge and sort by score descending
        merged = code_docs + doc_docs
        merged.sort(key=lambda x: x.payload.get("_score", 0.0), reverse=True)
        results = [self._to_search_result(d) for d in merged[:limit]]

        # Emit SemanticSearchCompletedV1
        if self.publisher:
            search_done = SemanticSearchCompletedV1(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                repository_id=repo_id,
                query=query,
                result_count=len(results)
            )
            self.publisher.publish("vector.search_completed", search_done)

        return results

    def search_similar_code(
        self, 
        repo_id: str, 
        code: str, 
        limit: int = 10, 
        min_score: float = 0.65
    ) -> List[SearchResult]:
        """Finds code snippets semantically similar to the provided code query."""
        query_vector = self.embedding_service.embed_query(code)
        docs = self.vector_repo.search_similarity(
            query_vector=query_vector,
            collection_name="repository_code_chunks",
            limit=limit,
            min_score=min_score,
            filter_dict={"repository_id": repo_id}
        )
        return [self._to_search_result(d) for d in docs]

    def search_security_findings(
        self, 
        repo_id: str, 
        query: str, 
        limit: int = 10, 
        min_score: float = 0.65
    ) -> List[SearchResult]:
        """Searches security findings semantically matching the query."""
        query_vector = self.embedding_service.embed_query(query)
        docs = self.vector_repo.search_similarity(
            query_vector=query_vector,
            collection_name="repository_security_chunks",
            limit=limit,
            min_score=min_score,
            filter_dict={"repository_id": repo_id}
        )
        return [self._to_search_result(d) for d in docs]

    def retrieve_context(
        self,
        repository_id: str,
        query: str,
        limit: int = 10
    ) -> List[Chunk]:
        """Retrieves matching code/doc chunks to construct context for Phase 7 RAG."""
        query_vector = self.embedding_service.embed_query(query)
        
        code_docs = self.vector_repo.search_similarity(
            query_vector=query_vector,
            collection_name="repository_code_chunks",
            limit=limit,
            min_score=0.60,  # slightly lower threshold to gather sufficient context
            filter_dict={"repository_id": repository_id}
        )

        doc_docs = self.vector_repo.search_similarity(
            query_vector=query_vector,
            collection_name="repository_document_chunks",
            limit=limit,
            min_score=0.60,
            filter_dict={"repository_id": repository_id}
        )

        merged = code_docs + doc_docs
        merged.sort(key=lambda x: x.payload.get("_score", 0.0), reverse=True)
        
        chunks = []
        for doc in merged[:limit]:
            payload = doc.payload
            meta = {k: v for k, v in payload.items() if k not in ("text_content", "_score")}
            chunks.append(Chunk(
                id=doc.id,
                text=payload.get("text_content", ""),
                chunk_type=payload.get("chunk_type", "UNKNOWN"),
                metadata=meta,
                content_hash=payload.get("content_hash", ""),
                version=payload.get("version", 1),
                start_line=payload.get("start_line"),
                end_line=payload.get("end_line")
            ))
        return chunks
