"""Document Ingestion and Chunking Service for Hybrid RAG.

Parses TXT and PDF documents, extracts clean text, partitions content into
semantically coherent chunks with sliding-window overlap, preserves document metadata
(filename, page number, chunk index), and defends against prompt injection attacks.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("retailiq.rag.document_loader")

# Prompt injection patterns to sanitize from retrieved external documents
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*\|\s*(im_start|im_end|system|user|assistant)\s*\|\s*>", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"disregard\s+the\s+above", re.IGNORECASE),
    re.compile(r"new\s+system\s+prompt\s*:", re.IGNORECASE),
]


@dataclass
class DocumentChunk:
    """A bounded text segment extracted from a knowledge document."""
    chunk_id: str
    document_name: str
    page_number: int
    chunk_index: int
    content: str
    char_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    @property
    def citation(self) -> str:
        """Standardized source citation string."""
        if self.page_number > 0:
            return f"[Source: {self.document_name}, Page {self.page_number}]"
        return f"[Source: {self.document_name}]"


class DocumentLoader:
    """Loads, cleans, sanitizes, and chunks TXT and PDF documents."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 80,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def sanitize_text(text: str) -> str:
        """Neutralize potential prompt injection delimiters and normalize whitespace."""
        # Replace common LLM instruction hijacking markers
        clean = text
        for pattern in INJECTION_PATTERNS:
            clean = pattern.sub("[REDACTED_INSTRUCTION]", clean)

        # Normalize linebreaks and whitespace
        clean = re.sub(r"\r\n", "\n", clean)
        clean = re.sub(r"[ \t]+", " ", clean)
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        return clean.strip()

    def chunk_text(
        self,
        text: str,
        document_name: str,
        page_number: int = 1,
    ) -> List[DocumentChunk]:
        """Split text into overlapping chunks while respecting sentence and paragraph boundaries."""
        sanitized = self.sanitize_text(text)
        if not sanitized:
            return []

        # Split into natural paragraphs / sentence blocks first
        paragraphs = [p.strip() for p in sanitized.split("\n\n") if p.strip()]
        chunks: List[DocumentChunk] = []

        current_text = ""
        chunk_idx = 1

        for para in paragraphs:
            if not current_text:
                current_text = para
            elif len(current_text) + len(para) + 2 <= self.chunk_size:
                current_text += "\n\n" + para
            else:
                # Emit current chunk
                c_id = f"{document_name}_p{page_number}_c{chunk_idx}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=c_id,
                        document_name=document_name,
                        page_number=page_number,
                        chunk_index=chunk_idx,
                        content=current_text,
                        char_count=len(current_text),
                    )
                )
                chunk_idx += 1

                # Start new chunk with overlap from end of previous
                overlap_text = current_text[-self.chunk_overlap:] if len(current_text) > self.chunk_overlap else ""
                current_text = (overlap_text + " " + para).strip() if overlap_text else para

        if current_text:
            c_id = f"{document_name}_p{page_number}_c{chunk_idx}"
            chunks.append(
                DocumentChunk(
                    chunk_id=c_id,
                    document_name=document_name,
                    page_number=page_number,
                    chunk_index=chunk_idx,
                    content=current_text,
                    char_count=len(current_text),
                )
            )

        return chunks

    def load_txt(self, file_path: Path) -> List[DocumentChunk]:
        """Load and chunk a UTF-8 or Latin-1 text file."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")

        return self.chunk_text(
            text=content,
            document_name=file_path.name,
            page_number=1,
        )

    def load_pdf(self, file_path: Path) -> List[DocumentChunk]:
        """Load and chunk a PDF document using pypdf, extracting text per page."""
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        import pypdf

        reader = pypdf.PdfReader(str(file_path))
        all_chunks: List[DocumentChunk] = []

        for page_idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                page_chunks = self.chunk_text(
                    text=page_text,
                    document_name=file_path.name,
                    page_number=page_idx,
                )
                all_chunks.extend(page_chunks)

        return all_chunks

    def load_document(self, file_path: Path) -> List[DocumentChunk]:
        """Auto-detect format and load document."""
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            return self.load_pdf(file_path)
        elif suffix in {".txt", ".md", ".csv"}:
            return self.load_txt(file_path)
        else:
            raise ValueError(f"Unsupported document format: {suffix}. Supported: .pdf, .txt, .md")
