"""Hybrid Retrieval Engine: Semantic Vector Search + Keyword FTS + RRF + Optional Reranker.

Combines dense semantic retrieval and sparse lexical retrieval using Reciprocal
Rank Fusion (RRF), with optional cross-encoder reranking on top candidates.
"""

from collections import defaultdict
from dataclasses import dataclass
import logging
import math
import re
from typing import Dict, List, Optional, Set, Tuple

from app.services.rag.document_loader import DocumentChunk
from app.services.rag.embedding_service import EmbeddingService, get_embedding_service

logger = logging.getLogger("retailiq.rag.hybrid_retriever")


STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
}


@dataclass
class RetrievalResult:
    """Retrieved document chunk with ranking signals and source attribution."""
    chunk: DocumentChunk
    rrf_score: float
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: Optional[float] = None
    rank: int = 1


class CrossEncoderReranker:
    """Lightweight cross-encoder reranker using ms-marco-MiniLM-L-6-v2."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model_name = model_name
        self._tokenizer = None
        self._model = None
        self._initialized = False

    def _lazy_init(self) -> None:
        if self._initialized:
            return
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            logger.info(f"Loading cross-encoder reranker '{self.model_name}' on CPU...")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self._model.eval()
            self._initialized = True
            logger.info("Cross-encoder reranker successfully loaded.")
        except Exception as err:
            logger.warning(f"Could not load cross-encoder '{self.model_name}': {err}")
            self._initialized = True

    def rerank(self, query: str, chunks: List[DocumentChunk]) -> List[Tuple[DocumentChunk, float]]:
        """Score (query, chunk) pairs and return chunks sorted by cross-encoder score descending."""
        if not chunks:
            return []

        self._lazy_init()
        if self._model is None or self._tokenizer is None:
            # Fallback: keep original order with dummy score
            return [(c, 0.0) for c in chunks]

        import torch

        pairs = [(query, c.content) for c in chunks]
        with torch.no_grad():
            inputs = self._tokenizer(
                pairs,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            scores = self._model(**inputs).logits.squeeze(-1).cpu().tolist()

        if isinstance(scores, float):
            scores = [scores]

        scored_chunks = list(zip(chunks, scores))
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks


class HybridRetriever:
    """Performs dual-channel retrieval (Dense Semantic + Sparse Keyword) fused via RRF."""

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        rrf_k: int = 60,
        enable_reranker: bool = False,
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ) -> None:
        self.embedding_service = embedding_service or get_embedding_service()
        self.rrf_k = rrf_k
        self.enable_reranker = enable_reranker
        self._reranker = CrossEncoderReranker(model_name=reranker_model) if enable_reranker else None

    @staticmethod
    def _bm25_tokenize(text: str, filter_stopwords: bool = True) -> List[str]:
        """Simple tokenizer for keyword search, filtering stop words for queries."""
        tokens = re.findall(r"\w+", text.lower())
        if filter_stopwords:
            return [t for t in tokens if t not in STOPWORDS and len(t) > 1]
        return [t for t in tokens if len(t) > 1]

    def _keyword_search(
        self,
        query: str,
        corpus: List[DocumentChunk],
        top_k: int = 20,
    ) -> List[Tuple[DocumentChunk, float]]:
        """BM25-style lexical keyword search scoring over candidate chunks."""
        q_tokens = self._bm25_tokenize(query)
        if not q_tokens or not corpus:
            return []

        # Calculate document frequencies
        doc_count = len(corpus)
        df: Dict[str, int] = defaultdict(int)
        for chunk in corpus:
            tokens_in_chunk = set(self._bm25_tokenize(chunk.content))
            for t in tokens_in_chunk:
                df[t] += 1

        # BM25 parameters
        k1 = 1.5
        b = 0.75
        avg_doc_len = sum(len(self._bm25_tokenize(c.content)) for c in corpus) / max(1, doc_count)

        scored_docs: List[Tuple[DocumentChunk, float]] = []

        for chunk in corpus:
            chunk_tokens = self._bm25_tokenize(chunk.content)
            doc_len = len(chunk_tokens)
            tf_map: Dict[str, int] = defaultdict(int)
            for t in chunk_tokens:
                tf_map[t] += 1

            score = 0.0
            for t in q_tokens:
                if t not in tf_map:
                    continue
                # IDF
                doc_freq = df.get(t, 0)
                idf = math.log((doc_count - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                # TF with length normalization
                tf = tf_map[t]
                tf_norm = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (doc_len / avg_doc_len)))
                score += idf * tf_norm

            if score > 0:
                scored_docs.append((chunk, score))

        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return scored_docs[:top_k]

    def _semantic_search(
        self,
        query: str,
        corpus: List[DocumentChunk],
        top_k: int = 20,
    ) -> List[Tuple[DocumentChunk, float]]:
        """Dense semantic search using cosine similarity of embeddings."""
        if not corpus:
            return []

        q_vec = self.embedding_service.embed_query(query)
        scored: List[Tuple[DocumentChunk, float]] = []

        for chunk in corpus:
            if chunk.embedding is not None:
                sim = self.embedding_service.cosine_similarity(q_vec, chunk.embedding)
                scored.append((chunk, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def reciprocal_rank_fusion(
        self,
        semantic_ranked: List[Tuple[DocumentChunk, float]],
        keyword_ranked: List[Tuple[DocumentChunk, float]],
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Combine two ranked lists using Reciprocal Rank Fusion: RRF = 1 / (k + rank)."""
        rrf_scores: Dict[str, float] = defaultdict(float)
        chunk_map: Dict[str, DocumentChunk] = {}
        sem_scores: Dict[str, float] = {}
        kw_scores: Dict[str, float] = {}

        # 1. Score semantic results
        for rank, (chunk, score) in enumerate(semantic_ranked, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            sem_scores[cid] = score
            rrf_scores[cid] += 1.0 / (self.rrf_k + rank)

        # 2. Score keyword results
        for rank, (chunk, score) in enumerate(keyword_ranked, start=1):
            cid = chunk.chunk_id
            chunk_map[cid] = chunk
            kw_scores[cid] = score
            rrf_scores[cid] += 1.0 / (self.rrf_k + rank)

        # Sort by combined RRF score descending
        fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        results: List[RetrievalResult] = []
        for rank, (cid, score) in enumerate(fused[:top_k], start=1):
            results.append(
                RetrievalResult(
                    chunk=chunk_map[cid],
                    rrf_score=score,
                    semantic_score=sem_scores.get(cid, 0.0),
                    keyword_score=kw_scores.get(cid, 0.0),
                    rank=rank,
                )
            )

        return results

    def retrieve(
        self,
        query: str,
        corpus: List[DocumentChunk],
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Execute complete Hybrid Retrieval pipeline: Semantic + BM25 -> RRF -> (Optional Reranker)."""
        if not corpus or not query.strip():
            return []

        # 1. Dual-channel retrieval
        semantic_candidates = self._semantic_search(query, corpus, top_k=top_k * 3)
        keyword_candidates = self._keyword_search(query, corpus, top_k=top_k * 3)

        # 2. Reciprocal Rank Fusion
        fused_results = self.reciprocal_rank_fusion(
            semantic_candidates,
            keyword_candidates,
            top_k=top_k * 2 if self.enable_reranker else top_k,
        )

        # 3. Optional Cross-Encoder Reranker
        if self.enable_reranker and self._reranker is not None and fused_results:
            top_chunks = [r.chunk for r in fused_results]
            reranked = self._reranker.rerank(query, top_chunks)

            reranked_results: List[RetrievalResult] = []
            for rank, (chunk, r_score) in enumerate(reranked[:top_k], start=1):
                # Locate original fusion score
                orig_rrf = next((r.rrf_score for r in fused_results if r.chunk.chunk_id == chunk.chunk_id), 0.0)
                reranked_results.append(
                    RetrievalResult(
                        chunk=chunk,
                        rrf_score=orig_rrf,
                        rerank_score=r_score,
                        rank=rank,
                    )
                )
            return reranked_results

        return fused_results[:top_k]
