import importlib.util

import pytest
from libs.config.config_loader import SystemSettings
from services.vector_service.application.services.embedding_service import EmbeddingService
from services.vector_service.domain.entities.vector_document import VectorDocument
from services.vector_service.infrastructure.embeddings.provider_factory import (
    build_embedding_provider,
    describe_embedding_configuration,
)
from services.vector_service.infrastructure.embeddings.sentence_transformer_provider import (
    EmbeddingProviderError,
    MockEmbeddingProvider,
    SentenceTransformerProvider,
)
from services.vector_service.infrastructure.vector_store.qdrant_repository import QdrantRepository


def _settings(**overrides):
    values = {
        "ENV": "development",
        "EMBEDDING_PROVIDER": "sentence-transformers",
        "EMBEDDING_MODEL": "all-MiniLM-L6-v2",
        "EMBEDDING_DIMENSIONS": 384,
        "NEO4J_PASSWORD": "unique-production-password",
    }
    values.update(overrides)
    return SystemSettings(**values)


def test_default_provider_is_real_and_does_not_hash_on_failure():
    provider = build_embedding_provider(_settings())
    assert isinstance(provider, SentenceTransformerProvider)
    assert provider.provider_name == "sentence-transformers"
    assert provider.dimensions == 384
    if importlib.util.find_spec("sentence_transformers") is not None:
        vector = provider.embed("repository code that must not become a fake vector")
        assert len(vector) == 384
        assert any(v != 0.0 for v in vector)
    else:
        with pytest.raises(EmbeddingProviderError, match="not installed"):
            provider.embed("repository code that must not become a fake vector")


def test_mock_provider_is_explicit_and_isolated_from_the_real_provider():
    mock = build_embedding_provider(_settings(EMBEDDING_PROVIDER="mock", EMBEDDING_DIMENSIONS=32))
    assert isinstance(mock, MockEmbeddingProvider)
    assert mock.dimensions == 32
    vector = mock.embed("same")
    assert len(vector) == 32
    assert vector == mock.embed("same")
    assert vector != mock.embed("different")

    real = SentenceTransformerProvider(model_name="all-MiniLM-L6-v2", dimensions=384)
    if importlib.util.find_spec("sentence_transformers") is None:
        with pytest.raises(EmbeddingProviderError):
            real.ensure_ready()
    else:
        real.ensure_ready()
        assert real._model is not None


def test_production_rejects_mock_embedding_configuration():
    settings = _settings(ENV="production", EMBEDDING_PROVIDER="mock")
    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER"):
        settings.validate_production_security()
    with pytest.raises(EmbeddingProviderError, match="forbidden in production"):
        build_embedding_provider(settings)


def test_secure_production_settings_still_allow_the_real_provider():
    settings = _settings(ENV="production")
    settings.validate_production_security()
    provider = build_embedding_provider(settings)
    assert isinstance(provider, SentenceTransformerProvider)


def test_unknown_provider_and_dimension_mismatch_fail_clearly():
    with pytest.raises(EmbeddingProviderError, match="Unknown EMBEDDING_PROVIDER"):
        build_embedding_provider(_settings(EMBEDDING_PROVIDER="hash-vectors"))

    class ShortProvider(SentenceTransformerProvider):
        def embed(self, text):
            return [0.1, 0.2]

    service = EmbeddingService(ShortProvider(dimensions=384), cache=None)
    with pytest.raises(EmbeddingProviderError, match="dimensions"):
        service.embed_query("print('hello')")


def test_encode_errors_are_not_replaced_with_hash_vectors():
    provider = SentenceTransformerProvider(dimensions=4)

    class BrokenModel:
        def encode(self, _text):
            raise RuntimeError("model exploded")

    provider._model = BrokenModel()
    with pytest.raises(EmbeddingProviderError, match="failed to encode"):
        provider.embed("do not hash this")


def test_qdrant_rejects_vectors_with_the_wrong_dimension():
    repo = QdrantRepository(in_memory=True, vector_size=4)
    document = VectorDocument(id="chunk-1", vector=[0.1, 0.2], payload={"repository_id": "r1"})
    with pytest.raises(ValueError, match="dimension"):
        repo.upsert_documents([document], "repository_code_chunks")


def test_health_description_does_not_pretend_embeddings_are_live():
    info = describe_embedding_configuration(_settings())
    assert info["provider"] == "sentence-transformers"
    assert info["model"] == "all-MiniLM-L6-v2"
    assert info["dimensions"] == 384
    assert info["semantic"] is True
    assert "key" not in info
    assert "secret" not in info
    if importlib.util.find_spec("sentence_transformers") is None:
        assert info["status"] == "unavailable"
    else:
        assert info["status"] == "available"


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is None,
    reason="sentence-transformers is not installed in this environment; live inference was not executed",
)
def test_optional_live_minilm_inference():
    provider = SentenceTransformerProvider(model_name="all-MiniLM-L6-v2", dimensions=384)
    provider.ensure_ready()
    vector = provider.embed("def add(a, b):\n    return a + b")
    assert len(vector) == 384
    assert any(value != 0.0 for value in vector)
