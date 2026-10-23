import math
import re
import hashlib
from typing import List, Optional
import numpy as np
from app.core.config import settings
from app.core.logging import logger
from app.retrieval.base import BaseEmbeddingProvider

class FallbackDeterministicVectorizer(BaseEmbeddingProvider):
    """
    Deterministic dense vectorizer (128-dim) utilizing hashed character n-grams
    and term frequency with L2 unit normalization.
    
    Guarantees 100% offline availability, zero model download delays,
    and mathematically sound cosine similarity for testing, offline air-gapped shops,
    and resource-constrained edge industrial controllers.
    """
    def __init__(self, dimension: int = 128):
        self._dim = dimension

    @property
    def provider_name(self) -> str:
        return "deterministic_fallback_vectorizer"

    @property
    def dimension(self) -> int:
        return self._dim

    def _tokenize_ngrams(self, text: str) -> List[str]:
        clean = re.sub(r"[^\w\s\.-]", " ", text.lower())
        tokens = [t for t in clean.split() if len(t) > 1]
        ngrams = list(tokens)
        # Add character 3-grams for typo resilience and parameter matching (e.g. 1200, cnc)
        for t in tokens:
            if len(t) >= 3:
                for i in range(len(t) - 2):
                    ngrams.append(t[i:i+3])
        return ngrams

    def embed_text(self, text: str) -> List[float]:
        vec = np.zeros(self._dim, dtype=np.float32)
        ngrams = self._tokenize_ngrams(text)
        if not ngrams:
            return vec.tolist()

        for ng in ngrams:
            # Deterministic hash to dimension index
            h = int(hashlib.md5(ng.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if (h // self._dim) % 2 == 0 else -1.0
            vec[idx] += sign

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class SentenceTransformersProvider(BaseEmbeddingProvider):
    """
    Sentence Transformers provider using modern dense embedding models
    (e.g., 'all-MiniLM-L6-v2').
    Includes lazy loading and graceful fallback if dependencies or network fail.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._fallback = FallbackDeterministicVectorizer(128)
        self._failed_init = False

    def _get_model(self):
        if self._model is not None:
            return self._model
        if self._failed_init:
            return None

        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            return self._model
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer '{self.model_name}': {e}. Switching to deterministic fallback vectorizer.")
            self._failed_init = True
            return None

    @property
    def provider_name(self) -> str:
        if self._model is not None:
            return f"sentence_transformers ({self.model_name})"
        return "deterministic_fallback_vectorizer (fallback)"

    @property
    def dimension(self) -> int:
        model = self._get_model()
        if model is not None:
            return model.get_sentence_embedding_dimension()
        return self._fallback.dimension

    def embed_text(self, text: str) -> List[float]:
        model = self._get_model()
        if model is not None:
            try:
                emb = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
                return emb.tolist()
            except Exception as e:
                logger.error(f"Error encoding with SentenceTransformer: {e}")
        return self._fallback.embed_text(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        if model is not None:
            try:
                embs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
                return embs.tolist()
            except Exception as e:
                logger.error(f"Error batch encoding with SentenceTransformer: {e}")
        return self._fallback.embed_batch(texts)


def get_embedding_provider() -> BaseEmbeddingProvider:
    """
    Factory returning configured embedding provider.
    """
    if settings.EMBEDDING_PROVIDER.lower() == "sentence-transformers":
        return SentenceTransformersProvider(settings.EMBEDDING_MODEL_NAME)
    return FallbackDeterministicVectorizer(128)

embedding_provider = get_embedding_provider()
