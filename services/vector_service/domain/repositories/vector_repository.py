from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..entities.vector_document import VectorDocument

class IVectorRepository(ABC):
    @abstractmethod
    def upsert_documents(self, documents: List[VectorDocument], collection_name: str) -> None:
        """Upserts a list of vector documents into the specified collection."""
        pass

    @abstractmethod
    def search_similarity(
        self, 
        query_vector: List[float], 
        collection_name: str, 
        limit: int = 10, 
        min_score: float = 0.65, 
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[VectorDocument]:
        """Searches for similar vector documents inside the collection filtered by attributes."""
        pass

    @abstractmethod
    def delete_repository_vectors(self, repository_id: str, collection_name: str) -> None:
        """Deletes all vector documents belonging to a repository from the collection."""
        pass
