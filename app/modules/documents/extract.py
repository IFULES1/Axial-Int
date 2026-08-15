"""Text extraction and chunking — pure functions, no I/O beyond parsing bytes.

Chunking mirrors the legacy pipeline: ~1000-char windows with 200-char overlap,
split on whitespace so we don't cut words.
"""
from __future__ import annotations

import io

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def extract_pdf_text(data: bytes) -> str:
    """Extract text from a PDF byte string. Returns "" if nothing readable."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n\n".join(parts).strip()


def _sanitize(text: str) -> str:
    """Strip lone surrogates / un-encodable code points left by bad PDF glyph
    decoding, so downstream JSON + UTF-8 encoding (e.g. to Cohere) never fails."""
    return text.encode("utf-8", "ignore").decode("utf-8")


def extract_text(filename: str, data: bytes) -> str:
    """Dispatch on file type. PDF today; plain text otherwise (best-effort)."""
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return _sanitize(extract_pdf_text(data))
    # Fallback: decode as UTF-8 text.
    try:
        return _sanitize(data.decode("utf-8", errors="ignore").strip())
    except Exception:
        return ""


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping windows on word boundaries."""
    text = " ".join(text.split())  # normalize whitespace
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    step = max(1, size - overlap)
    while start < len(text):
        end = start + size
        window = text[start:end]
        # Avoid cutting mid-word: back off to the last space if we're not at the end.
        if end < len(text):
            last_space = window.rfind(" ")
            if last_space > size // 2:
                window = window[:last_space]
        chunks.append(window.strip())
        start += step
    return [c for c in chunks if c]
