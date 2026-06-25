from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
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
        self.vector_size = vector_size
        
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

    def _ensure_collections(self):
        try:
            existing = [c.name for c in self.client.get_collections().collections]
        except Exception:
            existing = []

        for col in self.collections:
            if col not in existing:
                try:
                    self.client.create_collection(
                        collection_name=col,
                        vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                    )
                except Exception:
                    pass

    def upsert_documents(self, documents: List[VectorDocument], collection_name: str) -> None:
        if collection_name not in self.collections:
            raise ValueError(f"Unknown Qdrant collection: {collection_name}")
            
        import uuid
        points = []
        for doc in documents:
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
