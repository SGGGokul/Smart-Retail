"""SQLAlchemy ORM Models for Persistent RAG Knowledge Base Documents and Chunks."""

import datetime
from typing import List
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

try:
    from pgvector.sqlalchemy import Vector
    EmbeddingType = Vector(384).with_variant(JSON(), "sqlite")
except ImportError:
    EmbeddingType = JSONB().with_variant(JSON(), "sqlite")


class RAGDocumentModel(Base):
    """Uploaded knowledge base document."""

    __tablename__ = "rag_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    chunks: Mapped[List["RAGChunkModel"]] = relationship(
        "RAGChunkModel",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="RAGChunkModel.chunk_index",
    )


class RAGChunkModel(Base):
    """Text chunk with BGE-small dense embeddings and metadata."""

    __tablename__ = "rag_document_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("rag_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(EmbeddingType, nullable=False)
    embedding_model: Mapped[str] = mapped_column(
        String(128),
        default="BAAI/bge-small-en-v1.5",
        nullable=False,
    )
    embedding_dimension: Mapped[int] = mapped_column(
        Integer,
        default=384,
        nullable=False,
    )
    citation: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped["RAGDocumentModel"] = relationship(
        "RAGDocumentModel",
        back_populates="chunks",
    )

