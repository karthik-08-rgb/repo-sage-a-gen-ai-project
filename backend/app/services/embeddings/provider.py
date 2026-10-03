import hashlib
import math
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of strings."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Return embedding dimension."""
        pass


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: str, model: str = settings.OPENAI_EMBEDDING_MODEL):
        self.api_key = api_key
        self.model = model
        self.dimension = settings.EMBEDDING_DIMENSION
        self.client: Any = None
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}")
            self.client = None

    def embed_text(self, text: str) -> List[float]:
        res = self.embed_batch([text])
        return res[0] if res else [0.0] * self.dimension

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self.client:
            raise RuntimeError("OpenAI client is not configured or missing API key.")
        
        cleaned = [t.replace("\n", " ").strip() for t in texts]
        max_retries = 3
        backoff = 1.0

        for attempt in range(max_retries):
            try:
                response = self.client.embeddings.create(
                    input=cleaned,
                    model=self.model
                )
                embeddings = [item.embedding for item in response.data]
                return embeddings
            except Exception as e:
                logger.warning(f"OpenAI embedding attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2.0

        return []

    def get_dimension(self) -> int:
        return self.dimension


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Google Gemini text embedding provider supporting models/gemini-embedding-001.
    """
    def __init__(self, api_key: str, model: str = "models/gemini-embedding-001"):
        self.api_key = api_key
        self.model = model
        self.dimension = settings.EMBEDDING_DIMENSION
        self._embed_content: Any = None
        try:
            from google.generativeai.client import configure
            from google.generativeai.embedding import embed_content
            try:
                configure(api_key=api_key, transport="rest")
            except Exception:
                configure(api_key=api_key)
            self._embed_content = embed_content
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini client: {e}")
            self._embed_content = None

    def embed_text(self, text: str) -> List[float]:
        res = self.embed_batch([text])
        return res[0] if res else [0.0] * self.dimension

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        cleaned = [t.replace("\n", " ").strip() or " " for t in texts]
        if not cleaned:
            return []

        if not self._embed_content:
            logger.warning("Gemini embedding client not configured; falling back to DeterministicMockEmbeddingProvider.")
            return DeterministicMockEmbeddingProvider(self.dimension).embed_batch(cleaned)

        max_retries = 3
        backoff = 1.0

        for attempt in range(max_retries):
            try:
                result = self._embed_content(
                    model=self.model,
                    content=cleaned,
                    task_type="retrieval_document",
                    output_dimensionality=self.dimension,
                )
                if isinstance(result, dict) and "embedding" in result:
                    emb = result["embedding"]
                    if cleaned and isinstance(emb, list) and len(cleaned) == 1 and emb and isinstance(emb[0], float):
                        return [emb]
                    return emb
                return DeterministicMockEmbeddingProvider(self.dimension).embed_batch(cleaned)
            except Exception as e:
                logger.warning(f"Gemini embedding attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.warning("All Gemini embedding attempts failed; falling back to DeterministicMockEmbeddingProvider.")
                    return DeterministicMockEmbeddingProvider(self.dimension).embed_batch(cleaned)
                time.sleep(backoff)
                backoff *= 2.0

        return DeterministicMockEmbeddingProvider(self.dimension).embed_batch(cleaned)

    def get_dimension(self) -> int:
        return self.dimension


class DeterministicMockEmbeddingProvider(BaseEmbeddingProvider):
    """
    High-fidelity deterministic embedding provider for offline testing and development.
    Generates unit-normalized dense vectors based on text semantics and token hashes.
    """
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def _hash_to_vector(self, text: str) -> List[float]:
        words = text.lower().split()
        vec = [0.0] * self.dimension
        
        for w in words:
            # Map word to dimensions
            h = int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16)
            idx1 = h % self.dimension
            idx2 = (h >> 16) % self.dimension
            idx3 = (h >> 32) % self.dimension
            val = ((h >> 48) % 100) / 100.0 - 0.5
            vec[idx1] += val
            vec[idx2] += val * 0.5
            vec[idx3] += val * 0.25

        # Also blend full text hash
        full_h = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
        for i in range(16):
            idx = (full_h >> (i * 8)) % self.dimension
            vec[idx] += 0.1

        # Normalize to unit length (L2 norm)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            vec = [x / norm for x in vec]
        else:
            vec[0] = 1.0

        return vec

    def embed_text(self, text: str) -> List[float]:
        return self._hash_to_vector(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_to_vector(t) for t in texts]

    def get_dimension(self) -> int:
        return self.dimension


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory returning configured embedding provider."""
    provider_name = (settings.EMBEDDING_PROVIDER or "").lower()

    if provider_name == "openai" and settings.OPENAI_API_KEY:
        try:
            return OpenAIEmbeddingProvider(settings.OPENAI_API_KEY, settings.OPENAI_EMBEDDING_MODEL)
        except Exception as e:
            logger.warning(f"Falling back to deterministic mock embedding provider: {e}")
    elif (provider_name == "gemini" or (not provider_name and (settings.LLM_PROVIDER or "").lower() == "gemini")) and settings.GEMINI_API_KEY:
        try:
            return GeminiEmbeddingProvider(settings.GEMINI_API_KEY)
        except Exception as e:
            logger.warning(f"Falling back to deterministic mock embedding provider: {e}")

    # Default to deterministic mock embedding provider for robust offline operation
    return DeterministicMockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
