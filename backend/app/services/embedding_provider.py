import hashlib
import importlib.util
import logging
import re
import threading
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List

import numpy as np

from app.core.config import settings

logger = logging.getLogger("qpi.embeddings")


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generate a dense vector embedding for a single string."""
        pass

    @abstractmethod
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate dense vector embeddings for a batch of strings."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality."""
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Identifier persisted with each embedding; vectors from different models are never compared."""
        pass


def _stable_seed(text: str) -> int:
    # Python's hash() is salted per process, so derive the seed from a real digest instead.
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:4], "little")


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic random vectors for fast tests. Carries no semantic signal."""

    def __init__(self, dim: int = settings.EMBEDDING_DIMENSION):
        self._dim = dim

    def generate_embedding(self, text: str) -> List[float]:
        rng = np.random.default_rng(_stable_seed(text))
        vec = rng.standard_normal(self._dim)
        norm = np.linalg.norm(vec)
        return (vec / norm).tolist() if norm else vec.tolist()

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.generate_embedding(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_id(self) -> str:
        return f"mock-{self._dim}"


_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingEmbeddingProvider(BaseEmbeddingProvider):
    """Dependency-free lexical embedding (signed feature hashing of words, bigrams and char trigrams).

    Cosine similarity approximates surface-level overlap, so it detects verbatim and lightly reworded
    repetitions but not deep paraphrases. Used when sentence-transformers is unavailable.
    """

    def __init__(self, dim: int = settings.EMBEDDING_DIMENSION):
        self._dim = dim

    def _features(self, text: str) -> List[tuple[str, float]]:
        tokens = _TOKEN_RE.findall(text.lower())
        feats: List[tuple[str, float]] = [(f"w:{t}", 1.0) for t in tokens]
        feats += [(f"b:{a}_{b}", 0.7) for a, b in zip(tokens, tokens[1:])]
        for t in tokens:
            padded = f"#{t}#"
            feats += [(f"c:{padded[i:i + 3]}", 0.3) for i in range(len(padded) - 2)]
        return feats

    def generate_embedding(self, text: str) -> List[float]:
        vec = np.zeros(self._dim, dtype=np.float64)
        for feature, weight in self._features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self._dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[idx] += sign * weight
        norm = np.linalg.norm(vec)
        return (vec / norm).tolist() if norm else vec.tolist()

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.generate_embedding(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_id(self) -> str:
        return f"hashing-v1-{self._dim}"


class SentenceTransformersProvider(BaseEmbeddingProvider):
    """Production embedding provider using sentence-transformers (model loaded lazily, once per process)."""

    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    logger.info("Loading sentence-transformers model '%s' (first use may download it)...", self.model_name)
                    model = SentenceTransformer(self.model_name)
                    get_dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
                    dim = get_dim()
                    if dim != settings.EMBEDDING_DIMENSION:
                        raise RuntimeError(
                            f"Model '{self.model_name}' produces {dim}-d vectors but EMBEDDING_DIMENSION is "
                            f"{settings.EMBEDDING_DIMENSION}; the database column cannot store them."
                        )
                    self._model = model
        return self._model

    def generate_embedding(self, text: str) -> List[float]:
        return self.generate_embeddings_batch([text])[0]

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings = self._get_model().encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        return settings.EMBEDDING_DIMENSION

    @property
    def model_id(self) -> str:
        return f"st:{self.model_name}"


@lru_cache(maxsize=None)
def _provider_for(name: str) -> BaseEmbeddingProvider:
    if name == "mock":
        return MockEmbeddingProvider()
    if name == "hashing":
        return HashingEmbeddingProvider()
    if name == "sentence_transformers":
        if importlib.util.find_spec("sentence_transformers") is not None:
            return SentenceTransformersProvider()
        logger.warning(
            "sentence-transformers is not installed; falling back to the hashing embedding provider. "
            "Install backend/requirements-ml.txt for semantic embeddings."
        )
        return HashingEmbeddingProvider()
    raise ValueError(f"Unknown EMBEDDING_PROVIDER '{name}'")


def get_embedding_provider() -> BaseEmbeddingProvider:
    return _provider_for(settings.EMBEDDING_PROVIDER)
