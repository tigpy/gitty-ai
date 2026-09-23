from typing import Optional

from libs.config import SystemSettings, get_settings

from .sentence_transformer_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
    MockEmbeddingProvider,
    SentenceTransformerProvider,
)

MOCK_PROVIDER_NAMES = {"mock", "fake", "hash"}
REAL_PROVIDER_NAMES = {"sentence-transformers", "sentence_transformers", "minilm"}


def build_embedding_provider(settings: Optional[SystemSettings] = None) -> EmbeddingProvider:
    """
    Select the embedding provider from EMBEDDING_PROVIDER.

    sentence-transformers is the only default. mock/fake/hash are explicit and
    are rejected in production. A missing model raises; it does not hash text.
    """
    settings = settings or get_settings()
    selected = (settings.EMBEDDING_PROVIDER or "").strip().lower()
    dimensions = int(settings.EMBEDDING_DIMENSIONS)
    model_name = settings.EMBEDDING_MODEL

    if selected in MOCK_PROVIDER_NAMES:
        if settings.ENV.lower() == "production":
            raise EmbeddingProviderError(
                "Mock embeddings are forbidden in production. "
                "Set EMBEDDING_PROVIDER=sentence-transformers."
            )
        return MockEmbeddingProvider(dimensions=dimensions, model_name=model_name or "mock")

    if selected in REAL_PROVIDER_NAMES:
        return SentenceTransformerProvider(model_name=model_name, dimensions=dimensions)

    raise EmbeddingProviderError(
        f"Unknown EMBEDDING_PROVIDER '{settings.EMBEDDING_PROVIDER}'. "
        "Use 'sentence-transformers' or, outside production, 'mock'."
    )


def describe_embedding_configuration(settings: Optional[SystemSettings] = None) -> dict:
    """Health metadata. Does not load model weights and does not include secrets."""
    settings = settings or get_settings()
    selected = (settings.EMBEDDING_PROVIDER or "").strip().lower()
    info = {
        "provider": settings.EMBEDDING_PROVIDER,
        "model": settings.EMBEDDING_MODEL,
        "dimensions": settings.EMBEDDING_DIMENSIONS,
        "semantic": selected in REAL_PROVIDER_NAMES,
    }
    if selected in MOCK_PROVIDER_NAMES:
        info["status"] = "mock"
        info["detail"] = "Deterministic hash vectors are configured. These are not semantic embeddings."
        return info
    if selected not in REAL_PROVIDER_NAMES:
        info["status"] = "misconfigured"
        info["detail"] = "EMBEDDING_PROVIDER is not a known embedding backend."
        return info
    try:
        import sentence_transformers
    except ImportError:
        info["status"] = "unavailable"
        info["detail"] = "sentence-transformers is not installed, so real embeddings cannot be generated."
        return info
    info["status"] = "available"
    info["library_version"] = getattr(sentence_transformers, "__version__", "unknown")
    info["detail"] = "The embedding library can be imported. Weights load on first use, not in health checks."
    return info
