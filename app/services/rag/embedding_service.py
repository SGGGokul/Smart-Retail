"""Embedding Generation Service for Hybrid RAG.

Provides batch embedding inference using BAAI/bge-small-en-v1.5 (384-dimensional
L2-normalized vectors) on CPU, with fallback deterministic vector generation for
isolated test environments.
"""

import hashlib
import logging
import math
from typing import List, Optional
import numpy as np

logger = logging.getLogger("retailiq.rag.embedding_service")

EMBEDDING_DIM = 384
DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"


class EmbeddingService:
    """Generates L2-normalized semantic dense embeddings for text queries and chunks."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        batch_size: int = 16,
        prefer_local_fallback: bool = False,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self._tokenizer = None
        self._model = None
        self._initialized = False
        self._use_fallback = prefer_local_fallback

    def _lazy_init(self) -> None:
        """Load tokenizer and model onto CPU on first request."""
        if self._initialized:
            return

        if self._use_fallback:
            self._initialized = True
            return

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            logger.info(f"Loading dense embedding model '{self.model_name}' on CPU...")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name)
            self._model.eval()
            self._initialized = True
            logger.info(f"Successfully loaded '{self.model_name}'.")
        except Exception as err:
            logger.warning(
                f"Could not load HuggingFace model '{self.model_name}' ({err}). "
                "Enabling deterministic fallback embedding engine."
            )
            self._use_fallback = True
            self._initialized = True

    def _fallback_embed(self, text: str) -> List[float]:
        """Deterministic 384-dimensional feature vector based on token n-grams and hashing."""
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        tokens = text.lower().split()
        if not tokens:
            return vec.tolist()

        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % EMBEDDING_DIM
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign

        # L2-normalize
        norm = np.linalg.norm(vec)
        if norm > 1e-12:
            vec = vec / norm
        return vec.tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Compute L2-normalized embeddings for a list of strings in batches."""
        if not texts:
            return []

        self._lazy_init()

        if self._use_fallback or self._model is None or self._tokenizer is None:
            return [self._fallback_embed(t) for t in texts]

        import torch

        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            with torch.no_grad():
                inputs = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                )
                outputs = self._model(**inputs)
                # BGE models use [CLS] token representation (index 0)
                cls_rep = outputs.last_hidden_state[:, 0]
                normalized = torch.nn.functional.normalize(cls_rep, p=2, dim=1)
                batch_vecs = normalized.cpu().numpy().tolist()
                all_embeddings.extend(batch_vecs)

        return all_embeddings

    def embed_query(self, query: str) -> List[float]:
        """Compute embedding for a single user query."""
        # For BGE retrieval, queries can include a task prefix, but bare queries work reliably
        results = self.embed_texts([query])
        return results[0] if results else [0.0] * EMBEDDING_DIM

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two float vectors."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom < 1e-12:
            return 0.0
        return float(np.dot(a, b) / denom)


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
