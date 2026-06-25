import pytest
from services.vector_service.domain.entities.vector_document import VectorDocument
from services.vector_service.infrastructure.vector_store.qdrant_repository import QdrantRepository

def test_qdrant_repository_in_memory_operations():
    # Initialize repository in memory
    repo = QdrantRepository(in_memory=True, vector_size=4)
    
    # Assert collections created
    assert "repository_code_chunks" in repo.collections
    assert "repository_document_chunks" in repo.collections
    assert "repository_security_chunks" in repo.collections
    
    # Create mock VectorDocuments
    documents = [
        VectorDocument(
            id="00000000-0000-0000-0000-000000000001",
            vector=[0.1, 0.2, 0.3, 0.4],
            payload={
                "repository_id": "r1",
                "file_path": "a.py",
                "chunk_type": "FUNCTION",
                "text_content": "def auth(): pass"
            }
        ),
        VectorDocument(
            id="00000000-0000-0000-0000-000000000002",
            vector=[0.5, 0.6, 0.7, 0.8],
            payload={
                "repository_id": "r1",
                "file_path": "b.py",
                "chunk_type": "FUNCTION",
                "text_content": "def helper(): pass"
            }
        ),
        VectorDocument(
            id="00000000-0000-0000-0000-000000000003",
            vector=[0.9, 1.0, 1.1, 1.2],
            payload={
                "repository_id": "r2",
                "file_path": "c.py",
                "chunk_type": "FUNCTION",
                "text_content": "def other(): pass"
            }
        )
    ]
    
    # 1. Upsert
    repo.upsert_documents(documents, "repository_code_chunks")
    
    # 2. Search similarity with repository filter
    results = repo.search_similarity(
        query_vector=[0.1, 0.2, 0.3, 0.4],
        collection_name="repository_code_chunks",
        limit=10,
        min_score=0.1,
        filter_dict={"repository_id": "r1"}
    )
    
    # Results should be filtered to only repository "r1"
    assert len(results) == 2
    assert results[0].id in ("00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002")
    assert results[0].payload["file_path"] in ("a.py", "b.py")
    assert "_score" in results[0].payload
    
    # 3. Test thresholding
    results_threshold = repo.search_similarity(
        query_vector=[0.1, 0.2, 0.3, 0.4],
        collection_name="repository_code_chunks",
        limit=10,
        min_score=1.05, # very high threshold above 1.0
        filter_dict={"repository_id": "r1"}
    )
    assert len(results_threshold) == 0
    
    # 4. Delete
    repo.delete_repository_vectors("r1", "repository_code_chunks")
    
    results_after_delete = repo.search_similarity(
        query_vector=[0.1, 0.2, 0.3, 0.4],
        collection_name="repository_code_chunks",
        limit=10,
        min_score=0.1,
        filter_dict={"repository_id": "r1"}
    )
    assert len(results_after_delete) == 0
    
    # Repository "r2" should still be intact
    results_r2 = repo.search_similarity(
        query_vector=[0.1, 0.2, 0.3, 0.4],
        collection_name="repository_code_chunks",
        limit=10,
        min_score=0.1,
        filter_dict={"repository_id": "r2"}
    )
    assert len(results_r2) == 1
    assert results_r2[0].id == "00000000-0000-0000-0000-000000000003"

def test_qdrant_repository_invalid_collection():
    repo = QdrantRepository(in_memory=True, vector_size=4)
    
    with pytest.raises(ValueError, match="Unknown Qdrant collection"):
        repo.upsert_documents([], "invalid_collection")
        
    with pytest.raises(ValueError, match="Unknown Qdrant collection"):
        repo.search_similarity([0.1, 0.2, 0.3, 0.4], "invalid_collection")
        
    with pytest.raises(ValueError, match="Unknown Qdrant collection"):
        repo.delete_repository_vectors("r1", "invalid_collection")

