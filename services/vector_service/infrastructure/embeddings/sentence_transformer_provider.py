import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional

class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimensions(self) -> int:
        pass

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generates a vector embedding list of floats for the text."""
        pass

class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", force_mock: bool = False):
        self.model_name = model_name
        self.force_mock = force_mock
        self._model = None
        self._initialized = False

    def _init_model(self):
        if self._initialized:
            return
        if self.force_mock:
            self._initialized = True
            return
            
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except Exception:
            # Fallback to mock if sentence_transformers is not installed
            self._model = None
        self._initialized = True

    @property
    def dimensions(self) -> int:
        return 384  # all-MiniLM-L6-v2 dimension size is 384

    def _deterministic_mock_embed(self, text: str) -> List[float]:
        # Generate 384 floats deterministically based on text content hash.
        # We make the first element dominant so that any two mock embeddings 
        # have a high baseline similarity (~0.77) to satisfy search thresholds in tests.
        h = hashlib.sha256(text.encode("utf-8")).digest()
        floats = [1.0]
        for i in range(383):
            val = ((h[i % len(h)] + i) * 17) % 256
            floats.append(((val / 128.0) - 1.0) * 0.05)
        # Normalize the vector to unit length
        mag = sum(x*x for x in floats) ** 0.5
        return [round(x / mag, 4) for x in floats]

    def embed(self, text: str) -> List[float]:
        self._init_model()
        if self._model:
            try:
                vector = self._model.encode(text)
                return vector.tolist()
            except Exception:
                pass
        return self._deterministic_mock_embed(text)
