import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from libs.events.schemas import (
    EmbeddingCreatedV1, 
    VectorIndexBuiltV1
)
from libs.core.message_bus.interfaces.event_bus import IEventBus
from ...domain.repositories.vector_repository import IVectorRepository
from .chunking_service import ChunkingService
from .embedding_service import EmbeddingService
from services.security_service.application.security_analysis_service import SecurityAnalysisService

class IndexingService:
    def __init__(
        self,
        sqlite_repo: Any,
        vector_repo: IVectorRepository,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        publisher: Optional[IEventBus] = None
    ):
        self.sqlite_repo = sqlite_repo
        self.vector_repo = vector_repo
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.publisher = publisher

    def index_repository(self, repository_id: str) -> Dict[str, Any]:
        """Orchestrates chunk generation, cached embedding, purging old indexes, and saving to Qdrant."""
        nodes = self.sqlite_repo.get_nodes_by_repository(repository_id)
        
        # 1. Locate repository node to extract metadata
        repo_node = next((n for n in nodes if n["type"] == "Repository"), None)
        repo_path = repo_node.get("path", "") if repo_node else ""
        repo_name = repo_node.get("name", "unknown") if repo_node else "unknown"

        # 2. Run security analysis to fetch the findings list for chunking
        sec_service = SecurityAnalysisService(self.sqlite_repo)
        try:
            report = sec_service.run_security_scan(repository_id)
            # Serialize findings to dicts for chunking service
            findings = [f.model_dump() for f in report.findings]
        except Exception:
            findings = []

        # 3. Generate versioned chunks
        chunks = self.chunking_service.generate_chunks(
            nodes=nodes,
            repo_id=repository_id,
            repo_name=repo_name,
            repo_path=repo_path,
            security_findings=findings
        )

        # Emit EmbeddingCreatedV1
        if self.publisher and chunks:
            embed_created = EmbeddingCreatedV1(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                repository_id=repository_id,
                chunk_count=len(chunks)
            )
            self.publisher.publish("vector.embedding_created", embed_created)

        # 4. Generate embeddings (using SQLite cache)
        documents = self.embedding_service.embed_chunks(chunks)

        # 5. Purge old indexing points for this repository in all collections
        for col in self.vector_repo.collections:
            self.vector_repo.delete_repository_vectors(repository_id, col)

        # 6. Route and upsert points to separate collections
        code_docs = [d for d in documents if d.payload.get("chunk_type") in ("FUNCTION", "CLASS", "FILE")]
        doc_docs = [d for d in documents if d.payload.get("chunk_type") == "DOCUMENTATION"]
        sec_docs = [d for d in documents if d.payload.get("chunk_type") == "SECURITY_FINDING"]

        self.vector_repo.upsert_documents(code_docs, "repository_code_chunks")
        self.vector_repo.upsert_documents(doc_docs, "repository_document_chunks")
        self.vector_repo.upsert_documents(sec_docs, "repository_security_chunks")

        # 7. Collect statistics
        func_chunks = sum(1 for c in chunks if c.chunk_type == "FUNCTION")
        cls_chunks = sum(1 for c in chunks if c.chunk_type == "CLASS")
        file_chunks = sum(1 for c in chunks if c.chunk_type == "FILE")
        doc_chunks = sum(1 for c in chunks if c.chunk_type == "DOCUMENTATION")
        sec_chunks = sum(1 for c in chunks if c.chunk_type == "SECURITY_FINDING")

        # Emit VectorIndexBuiltV1
        if self.publisher:
            index_built = VectorIndexBuiltV1(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                repository_id=repository_id,
                vector_count=len(documents),
                function_chunks=func_chunks,
                class_chunks=cls_chunks,
                file_chunks=file_chunks,
                documentation_chunks=doc_chunks,
                security_chunks=sec_chunks
            )
            self.publisher.publish("vector.index_built", index_built)

        return {
            "repository_id": repository_id,
            "vector_count": len(documents),
            "function_chunks": func_chunks,
            "class_chunks": cls_chunks,
            "file_chunks": file_chunks,
            "documentation_chunks": doc_chunks,
            "security_chunks": sec_chunks
        }
