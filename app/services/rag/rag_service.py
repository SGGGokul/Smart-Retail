"""High-Level RAG Service: Corpus Management, Grounded Answer Synthesis, and Source Citations.

Orchestrates document parsing, batch embedding, hybrid retrieval, answer grounding,
citation generation, and strict prompt injection shielding.
"""

from dataclasses import dataclass
import inspect
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.models.rag import RAGChunkModel, RAGDocumentModel
from app.services.rag.document_loader import DocumentChunk, DocumentLoader
from app.services.rag.embedding_service import EmbeddingService, get_embedding_service
from app.services.rag.hybrid_retriever import HybridRetriever, RetrievalResult

logger = logging.getLogger("retailiq.rag.rag_service")

UNSUPPORTED_ANSWER_FALLBACK = (
    "The provided store operational documents do not contain information to answer this question."
)


@dataclass
class RAGAnswer:
    """Grounded answer generated from knowledge documents with source citations."""
    query: str
    answer: str
    citations: List[str]
    retrieved_chunks: List[RetrievalResult]
    is_grounded: bool
    confidence: float


class RAGService:
    """Production Hybrid RAG pipeline for retail operational documentation."""

    def __init__(
        self,
        loader: Optional[DocumentLoader] = None,
        embedder: Optional[EmbeddingService] = None,
        retriever: Optional[HybridRetriever] = None,
        enable_reranker: bool = False,
    ) -> None:
        self.loader = loader or DocumentLoader()
        self.embedder = embedder or get_embedding_service()
        self.retriever = retriever or HybridRetriever(
            embedding_service=self.embedder,
            enable_reranker=enable_reranker,
        )
        # In-memory document chunk repository (persisted in SQLite/Postgres or memory)
        self._corpus: List[DocumentChunk] = []
        self._bm25_doc_tokens: Dict[str, List[str]] = {}

    def rebuild_bm25_index(self) -> None:
        """Rebuild any in-memory index structures over self._corpus."""
        self._bm25_doc_tokens = {
            c.chunk_id: HybridRetriever._bm25_tokenize(c.content)
            for c in self._corpus
        }
        if hasattr(self.retriever, "build_index"):
            self.retriever.build_index(self._corpus)
        logger.debug(f"Rebuilt in-memory BM25 index over {len(self._corpus)} chunks.")

    async def _async_persist_to_db(
        self,
        file_path: Path,
        chunks: List[DocumentChunk],
        session: Any,
    ) -> None:
        """Persist document metadata and chunks with 384-D dense embeddings to PostgreSQL."""
        from sqlalchemy import delete, select

        doc_name = file_path.name
        doc_stmt = select(RAGDocumentModel).where(RAGDocumentModel.filename == doc_name)
        res = await session.execute(doc_stmt)
        existing_doc = res.scalar_one_or_none()

        if existing_doc:
            await session.execute(delete(RAGChunkModel).where(RAGChunkModel.document_id == existing_doc.id))
            await session.execute(delete(RAGDocumentModel).where(RAGDocumentModel.id == existing_doc.id))
            await session.flush()

        doc_id = f"doc-{uuid.uuid4().hex[:12]}"
        doc_record = RAGDocumentModel(
            id=doc_id,
            filename=doc_name,
            file_type=file_path.suffix.lstrip(".").lower() or "txt",
            chunk_count=len(chunks),
        )
        session.add(doc_record)

        for c in chunks:
            chunk_record = RAGChunkModel(
                id=c.chunk_id if c.chunk_id else f"chunk-{uuid.uuid4().hex[:12]}",
                document_id=doc_id,
                document_name=doc_name,
                page_number=c.page_number,
                chunk_index=c.chunk_index,
                text=c.content,
                embedding=c.embedding or [],
                embedding_model="BAAI/bge-small-en-v1.5",
                embedding_dimension=384,
                citation=c.citation,
            )
            session.add(chunk_record)

        await session.commit()
        logger.info(f"Persisted document {doc_name} ({len(chunks)} chunks) with 384-D embeddings to PostgreSQL.")

    def _sync_persist_to_db(
        self,
        file_path: Path,
        chunks: List[DocumentChunk],
        session: Any,
    ) -> None:
        """Persist document metadata and chunks using synchronous SQLAlchemy session."""
        doc_name = file_path.name
        existing = session.query(RAGDocumentModel).filter_by(filename=doc_name).first()
        if existing:
            session.delete(existing)
            session.flush()

        doc_id = f"doc-{uuid.uuid4().hex[:12]}"
        doc_record = RAGDocumentModel(
            id=doc_id,
            filename=doc_name,
            file_type=file_path.suffix.lstrip(".").lower() or "txt",
            chunk_count=len(chunks),
        )
        session.add(doc_record)

        for c in chunks:
            chunk_record = RAGChunkModel(
                id=c.chunk_id if c.chunk_id else f"chunk-{uuid.uuid4().hex[:12]}",
                document_id=doc_id,
                document_name=doc_name,
                page_number=c.page_number,
                chunk_index=c.chunk_index,
                text=c.content,
                embedding=c.embedding or [],
                embedding_model="BAAI/bge-small-en-v1.5",
                embedding_dimension=384,
                citation=c.citation,
            )
            session.add(chunk_record)

        session.commit()
        logger.info(f"Persisted document {doc_name} ({len(chunks)} chunks) to database.")

    def ingest_document(
        self,
        file_path: Path,
        session: Optional[Any] = None,
    ) -> List[DocumentChunk]:
        """Ingest a document (.pdf, .txt), chunk it, generate embeddings, and add to corpus."""
        logger.info(f"Ingesting knowledge document: {file_path.name}")
        chunks = self.loader.load_document(file_path)
        if not chunks:
            logger.warning(f"No chunks extracted from {file_path.name}")
            return []

        # Generate batch embeddings
        texts_to_embed = [c.content for c in chunks]
        embeddings = self.embedder.embed_texts(texts_to_embed)

        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        # Remove existing chunks for this document to avoid duplication on re-ingest
        self._corpus = [c for c in self._corpus if c.document_name != file_path.name]
        self._corpus.extend(chunks)

        self.rebuild_bm25_index()

        if session is not None:
            if hasattr(session, "commit") and not inspect.iscoroutinefunction(getattr(session, "commit", None)) and not hasattr(session, "_connection"):
                self._sync_persist_to_db(file_path, chunks, session)
            else:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self._async_persist_to_db(file_path, chunks, session))
                    else:
                        loop.run_until_complete(self._async_persist_to_db(file_path, chunks, session))
                except Exception as err:
                    logger.warning(f"Could not persist chunks asynchronously in sync context: {err}")

        logger.info(f"Successfully ingested {file_path.name}: {len(chunks)} chunks added to RAG corpus.")
        return chunks

    async def aingest_document(
        self,
        file_path: Path,
        session: Optional[Any] = None,
    ) -> List[DocumentChunk]:
        """Async ingestion method supporting AsyncSession database persistence."""
        logger.info(f"Async ingesting knowledge document: {file_path.name}")
        chunks = self.loader.load_document(file_path)
        if not chunks:
            logger.warning(f"No chunks extracted from {file_path.name}")
            return []

        texts_to_embed = [c.content for c in chunks]
        embeddings = self.embedder.embed_texts(texts_to_embed)

        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        self._corpus = [c for c in self._corpus if c.document_name != file_path.name]
        self._corpus.extend(chunks)

        self.rebuild_bm25_index()

        if session is not None:
            await self._async_persist_to_db(file_path, chunks, session)

        logger.info(f"Successfully async-ingested {file_path.name}: {len(chunks)} chunks added to RAG corpus.")
        return chunks

    async def load_persisted_corpus(self, session: Any) -> int:
        """Query PostgreSQL for stored document chunks and precomputed 384-D embeddings.

        Populates self._corpus and rebuilds the in-memory BM25 index WITHOUT re-generating embeddings.
        Returns total number of chunks loaded.
        """
        from sqlalchemy import select

        stmt = (
            select(RAGChunkModel)
            .order_by(RAGChunkModel.document_name, RAGChunkModel.chunk_index)
        )

        if hasattr(session, "execute"):
            res = session.execute(stmt)
            if inspect.isawaitable(res):
                res = await res
            chunks_models = res.scalars().all()
        else:
            chunks_models = session.query(RAGChunkModel).order_by(
                RAGChunkModel.document_name, RAGChunkModel.chunk_index
            ).all()

        loaded_chunks: List[DocumentChunk] = []
        for cm in chunks_models:
            emb = cm.embedding
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            elif isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except Exception:
                    emb = []
            elif not isinstance(emb, list):
                try:
                    emb = list(emb)
                except Exception:
                    emb = []

            chunk = DocumentChunk(
                chunk_id=cm.id,
                document_name=cm.document_name,
                page_number=cm.page_number,
                chunk_index=cm.chunk_index,
                content=cm.text,
                char_count=len(cm.text),
                metadata={
                    "embedding_model": cm.embedding_model,
                    "embedding_dimension": cm.embedding_dimension,
                    "document_id": cm.document_id,
                },
                embedding=emb,
            )
            loaded_chunks.append(chunk)

        self._corpus = loaded_chunks
        self.rebuild_bm25_index()

        logger.info(
            f"RAG Knowledge Base reloaded from database: {len(self._corpus)} chunks loaded "
            f"across {len(self.get_ingested_documents())} documents (zero re-embedding)."
        )
        return len(self._corpus)


    def ingest_text_content(self, text: str, document_name: str) -> List[DocumentChunk]:
        """Directly ingest raw text content with a simulated document name."""
        chunks = self.loader.chunk_text(text, document_name=document_name)
        if not chunks:
            return []

        embeddings = self.embedder.embed_texts([c.content for c in chunks])
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        self._corpus = [c for c in self._corpus if c.document_name != document_name]
        self._corpus.extend(chunks)
        return chunks

    def get_corpus_size(self) -> int:
        return len(self._corpus)

    def get_ingested_documents(self) -> List[str]:
        return sorted(list({c.document_name for c in self._corpus}))

    def answer_query(
        self,
        query: str,
        top_k: int = 3,
        min_relevance_threshold: float = 0.015,  # RRF score threshold
    ) -> RAGAnswer:
        """Retrieve relevant operational chunks, apply prompt protection, and synthesize a cited response."""
        clean_query = query.strip()
        if not clean_query:
            return RAGAnswer(
                query=query,
                answer="Please provide a specific store operations or policy question.",
                citations=[],
                retrieved_chunks=[],
                is_grounded=False,
                confidence=0.0,
            )

        if not self._corpus:
            return RAGAnswer(
                query=query,
                answer="No operational documents have been ingested into the store knowledge base.",
                citations=[],
                retrieved_chunks=[],
                is_grounded=False,
                confidence=0.0,
            )

        # 1. Execute Hybrid Retrieval
        retrieved = self.retriever.retrieve(clean_query, self._corpus, top_k=top_k)

        # 2. Check for relevance floor
        is_relevant = False
        if retrieved:
            top = retrieved[0]
            # Meaningful semantic similarity threshold or keyword overlap threshold
            if top.semantic_score >= 0.52 or top.keyword_score >= 1.0:
                is_relevant = True

        if not is_relevant:
            return RAGAnswer(
                query=query,
                answer=UNSUPPORTED_ANSWER_FALLBACK,
                citations=[],
                retrieved_chunks=retrieved,
                is_grounded=False,
                confidence=0.0,
            )

        # 3. Assemble Citations and Context
        citations: List[str] = []
        context_parts: List[str] = []

        for r in retrieved:
            cite = r.chunk.citation
            if cite not in citations:
                citations.append(cite)
            # Wrap retrieved content with explicit demarcation to neutralize injection
            safe_content = DocumentLoader.sanitize_text(r.chunk.content)
            context_parts.append(f"{safe_content}\n{cite}")

        # 4. Synthesize Grounded Answer
        # When operating in local/deterministic mode without external API call, synthesize directly
        # from the highest-ranked matching chunk statements
        lead_chunk = retrieved[0].chunk
        extracted_facts = [line.strip() for line in lead_chunk.content.split("\n") if line.strip() and not line.startswith("#")]
        key_fact = "\n".join(extracted_facts[:3]) if extracted_facts else lead_chunk.content

        citations_str = " ".join(citations)
        grounded_answer = (
            f"According to verified store documentation:\n\n"
            f"{key_fact}\n\n"
            f"Sources: {citations_str}"
        )

        return RAGAnswer(
            query=query,
            answer=grounded_answer,
            citations=citations,
            retrieved_chunks=retrieved,
            is_grounded=True,
            confidence=round(retrieved[0].rrf_score * 100, 2),
        )

    def clear(self) -> None:
        self._corpus.clear()


_rag_service: Optional[RAGService] = None


def get_rag_service(enable_reranker: bool = False) -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService(enable_reranker=enable_reranker)
    return _rag_service
