from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import uuid
from typing import List, Optional, Dict, Any
from libs.config import get_settings
from ...domain.entities.vector_document import VectorDocument
from ...domain.repositories.vector_repository import IVectorRepository

class QdrantRepository(IVectorRepository):
    def __init__(
        self, 
        host: Optional[str] = None, 
        port: Optional[int] = None, 
        in_memory: bool = False,
        vector_size: int = 384
    ):
        self.settings = get_settings()
        self.vector_size = self.settings.EMBEDDING_DIMENSIONS if vector_size is None else vector_size
        self._unavailable_reason: Optional[BaseException] = None
        
        if in_memory:
            self.client = QdrantClient(":memory:")
        else:
            q_host = host or self.settings.QDRANT_HOST
            q_port = port or self.settings.QDRANT_PORT
            self.client = QdrantClient(host=q_host, port=q_port)

        self.collections = [
            "repository_code_chunks",
            "repository_document_chunks",
            "repository_security_chunks"
        ]
        self._ensure_collections()

    def _collection_vector_size(self, collection_name: str) -> int:
        info = self.client.get_collection(collection_name)
        vectors = info.config.params.vectors
        if isinstance(vectors, dict):
            if not vectors:
                raise ValueError(f"Qdrant collection '{collection_name}' has no vector configuration.")
            vectors = next(iter(vectors.values()))
        size = getattr(vectors, "size", None)
        if size is None:
            raise ValueError(f"Could not read the vector size for Qdrant collection '{collection_name}'.")
        return int(size)

    def _ensure_collections(self):
        try:
            existing = {c.name for c in self.client.get_collections().collections}
        except Exception as exc:
            # Construction stays lazy so repository cleanup can run without Qdrant.
            # Upsert and search retry, then fail if the dimension still cannot be verified.
            self._unavailable_reason = exc
            return

        self._unavailable_reason = None
        for col in self.collections:
            if col not in existing:
                self.client.create_collection(
                    collection_name=col,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
            actual = self._collection_vector_size(col)
            if actual != self.vector_size:
                raise ValueError(
                    f"Qdrant collection '{col}' dimension {actual} does not match "
                    f"embedding dimension {self.vector_size}."
                )

    def _require_verified_dimensions(self) -> None:
        if self._unavailable_reason is not None:
            self._ensure_collections()
        if self._unavailable_reason is not None:
            raise RuntimeError(
                f"Qdrant is unavailable, so embedding dimension {self.vector_size} "
                f"could not be verified: {self._unavailable_reason}"
            ) from self._unavailable_reason

    def upsert_documents(self, documents: List[VectorDocument], collection_name: str) -> None:
        if collection_name not in self.collections:
            raise ValueError(f"Unknown Qdrant collection: {collection_name}")
        self._require_verified_dimensions()
        points = []
        for doc in documents:
            if len(doc.vector) != self.vector_size:
                raise ValueError(
                    f"Embedding dimension {len(doc.vector)} does not match "
                    f"Qdrant collection dimension {self.vector_size}."
                )
            point_id = doc.id
            try:
                point_id = str(uuid.UUID(doc.id))
            except ValueError:
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc.id))

            points.append(PointStruct(
                id=point_id,
                vector=doc.vector,
                payload=doc.payload
            ))
            
        if points:
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )

    def search_similarity(
        self, 
        query_vector: List[float], 
        collection_name: str, 
        limit: int = 10, 
        min_score: float = 0.65, 
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[VectorDocument]:
        if collection_name not in self.collections:
            raise ValueError(f"Unknown Qdrant collection: {collection_name}")
        self._require_verified_dimensions()
        if len(query_vector) != self.vector_size:
            raise ValueError(
                f"Query embedding dimension {len(query_vector)} does not match "
                f"Qdrant collection dimension {self.vector_size}."
            )

        query_filter = None
        if filter_dict:
            conditions = []
            for k, v in filter_dict.items():
                conditions.append(FieldCondition(key=k, match=MatchValue(value=v)))
            query_filter = Filter(must=conditions)

        search_results = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            score_threshold=min_score,
            query_filter=query_filter
        ).points


        documents = []
        for res in search_results:
            payload = dict(res.payload or {})
            payload["_score"] = res.score  # Attach score to payload
            documents.append(VectorDocument(
                id=str(res.id),
                vector=[],  # Don't return massive vectors
                payload=payload
            ))
        return documents

    def delete_repository_vectors(self, repository_id: str, collection_name: str) -> None:
        if collection_name not in self.collections:
            raise ValueError(f"Unknown Qdrant collection: {collection_name}")

        self.client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="repository_id", match=MatchValue(value=repository_id))]
            )
        )
