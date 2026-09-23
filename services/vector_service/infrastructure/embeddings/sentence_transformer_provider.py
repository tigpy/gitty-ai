import hashlib
from abc import ABC, abstractmethod
from typing import List


class EmbeddingProviderError(RuntimeError):
    """The configured embedding provider could not produce a real vector."""


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimensions(self) -> int:
        pass

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Return one embedding. Must not substitute a hash vector on failure."""

    def ensure_ready(self) -> None:
        """Fail before indexing if this provider cannot actually embed."""


class SentenceTransformerProvider(EmbeddingProvider):
    """Local sentence-transformers model. Never falls back to hash vectors."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dimensions: int = 384):
        if dimensions < 1:
            raise EmbeddingProviderError("Embedding dimensions must be a positive integer.")
        self.model_name = model_name
        self.provider_name = "sentence-transformers"
        self._dimensions = dimensions
        self._model = None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def ensure_ready(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingProviderError(
                "EMBEDDING_PROVIDER=sentence-transformers but the sentence-transformers "
                "package is not installed. Mock embeddings are not used as a fallback."
            ) from exc
        try:
            model = SentenceTransformer(self.model_name)
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Failed to initialize embedding model '{self.model_name}': {exc}"
            ) from exc
        try:
            actual = int(model.get_sentence_embedding_dimension())
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Could not read the dimension of embedding model '{self.model_name}': {exc}"
            ) from exc
        if actual != self._dimensions:
            raise EmbeddingProviderError(
                f"Model '{self.model_name}' has dimension {actual}, "
                f"but EMBEDDING_DIMENSIONS is {self._dimensions}."
            )
        self._model = model

    def embed(self, text: str) -> List[float]:
        self.ensure_ready()
        try:
            encoded = self._model.encode(text)
            values = [float(value) for value in encoded.tolist()]
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Embedding model '{self.model_name}' failed to encode text: {exc}"
            ) from exc
        if len(values) != self._dimensions:
            raise EmbeddingProviderError(
                f"Model '{self.model_name}' returned {len(values)} dimensions; "
                f"expected {self._dimensions}."
            )
        return values


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic non-semantic vectors for tests.

    This provider is never selected automatically. Callers must construct it
    directly or set EMBEDDING_PROVIDER=mock outside production.
    """

    def __init__(self, dimensions: int = 384, model_name: str = "mock"):
        if dimensions < 1:
            raise EmbeddingProviderError("Embedding dimensions must be a positive integer.")
        self.model_name = model_name
        self.provider_name = "mock"
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def ensure_ready(self) -> None:
        return None

    def embed(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [1.0]
        for index in range(self._dimensions - 1):
            raw = ((digest[index % len(digest)] + index) * 17) % 256
            values.append(((raw / 128.0) - 1.0) * 0.05)
        magnitude = sum(value * value for value in values) ** 0.5
        return [round(value / magnitude, 4) for value in values]
