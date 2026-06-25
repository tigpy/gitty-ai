from typing import List, Optional
from ...domain.entities.vector_document import VectorDocument
from ...domain.value_objects.chunk import Chunk
from ...infrastructure.embeddings.sentence_transformer_provider import EmbeddingProvider
from ...infrastructure.embeddings.sqlite_embedding_cache import SQLiteEmbeddingCache

class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider, cache: Optional[SQLiteEmbeddingCache] = None):
        self.provider = provider
        self.cache = cache
        # Use class name or configured model name for cache keying
        self.model_name = getattr(provider, "model_name", provider.__class__.__name__)

    def embed_chunks(self, chunks: List[Chunk]) -> List[VectorDocument]:
        """Translates a list of Chunk domain value objects into VectorDocument entities using caching."""
        documents = []
        for chunk in chunks:
            vector = None
            if self.cache:
                vector = self.cache.get_embedding(chunk.content_hash, self.model_name)
                
            if not vector:
                vector = self.provider.embed(chunk.text)
                if self.cache:
                    self.cache.set_embedding(chunk.content_hash, self.model_name, vector)

            # Build Qdrant payload mapping
            payload = dict(chunk.metadata or {})
            payload["text_content"] = chunk.text
            payload["start_line"] = chunk.start_line
            payload["end_line"] = chunk.end_line
            payload["content_hash"] = chunk.content_hash
            payload["version"] = chunk.version

            documents.append(VectorDocument(
                id=chunk.id,
                vector=vector,
                payload=payload
            ))
        return documents

    def embed_query(self, text: str) -> List[float]:
        """Directly embeds a text query (without cache check) for semantic retrieval."""
        return self.provider.embed(text)
