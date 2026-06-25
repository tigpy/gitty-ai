import pytest
from services.vector_service.domain.value_objects.chunk import Chunk
from services.vector_service.infrastructure.embeddings.sentence_transformer_provider import SentenceTransformerProvider
from services.vector_service.infrastructure.embeddings.sqlite_embedding_cache import SQLiteEmbeddingCache
from services.vector_service.application.services.embedding_service import EmbeddingService

def test_embedding_provider_mock_dimensions():
    provider = SentenceTransformerProvider(force_mock=True)
    assert provider.dimensions == 384
    
    vec = provider.embed("hello world")
    assert len(vec) == 384
    assert all(isinstance(f, float) for f in vec)
    
    # Check determinism
    vec2 = provider.embed("hello world")
    assert vec == vec2

def test_sqlite_embedding_cache(tmp_path):
    db_path = str(tmp_path / "test_cache.db")
    cache = SQLiteEmbeddingCache(db_path=db_path)
    
    content_hash = "hash123"
    model_name = "test-model"
    embedding = [0.1, 0.2, 0.3]
    
    assert cache.get_embedding(content_hash, model_name) is None
    
    cache.set_embedding(content_hash, model_name, embedding)
    cached = cache.get_embedding(content_hash, model_name)
    assert cached == embedding

def test_embedding_service_with_cache(tmp_path):
    provider = SentenceTransformerProvider(force_mock=True)
    db_path = str(tmp_path / "test_cache.db")
    cache = SQLiteEmbeddingCache(db_path=db_path)
    
    service = EmbeddingService(provider, cache)
    
    chunk = Chunk(
        id="chunk-1",
        text="print('hello')",
        chunk_type="FUNCTION",
        metadata={"repository_id": "r1", "file_path": "a.py"},
        content_hash="h1",
        version=1,
        start_line=1,
        end_line=2
    )
    
    # 1. Embed first time (should compute and save to cache)
    docs = service.embed_chunks([chunk])
    assert len(docs) == 1
    doc = docs[0]
    assert doc.id == "chunk-1"
    assert len(doc.vector) == 384
    assert doc.payload["text_content"] == "print('hello')"
    assert doc.payload["start_line"] == 1
    
    # Verify cache has it
    cached_vec = cache.get_embedding("h1", provider.model_name)
    assert cached_vec == doc.vector
    
    # 2. Embed second time (should read from cache)
    docs2 = service.embed_chunks([chunk])
    assert docs2[0].vector == doc.vector

def test_sqlite_embedding_cache_invalid_json(tmp_path):
    import sqlite3
    db_path = str(tmp_path / "test_corrupt_cache.db")
    cache = SQLiteEmbeddingCache(db_path=db_path)
    
    # Manually insert invalid JSON into database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO embedding_cache (content_hash, model_name, embedding, created_at) VALUES (?, ?, ?, ?)",
        ("corrupt_hash", "test-model", "not-a-json-list", "2026-06-24T00:00:00Z")
    )
    conn.commit()
    conn.close()
    
    # Trying to get it should return None due to exception handling
    res = cache.get_embedding("corrupt_hash", "test-model")
    assert res is None

