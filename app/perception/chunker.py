"""Smart text chunker — split documents into overlapping chunks for embedding.

Strategies:
- RecursiveCharacter: split by paragraphs → sentences → characters (default)
- Fixed: fixed-size with overlap (fallback for very long flat text)

Chunk size tuning:
- 512 tokens ≈ 350-700 Chinese chars depending on content
- We use char count as proxy: chunk_size=500 chars, overlap=80 chars
- These defaults work well with BGE-large-zh (max 512 tokens)
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class Chunk:
    """A text chunk with metadata."""
    index: int
    text: str
    char_count: int


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    min_chunk_size: int = 50,
) -> list[Chunk]:
    """Split text into overlapping chunks using recursive character splitting.

    Args:
        text: Full document text
        chunk_size: Target chunk size in characters
        chunk_overlap: Overlap between consecutive chunks
        min_chunk_size: Discard chunks shorter than this

    Returns:
        List of Chunk objects
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # If text is short enough, return as single chunk
    if len(text) <= chunk_size:
        return [Chunk(index=0, text=text, char_count=len(text))]

    # Recursive split separators (try in order)
    separators = [
        "\n\n",     # paragraph break
        "\n",       # line break
        "。",       # Chinese period
        "；",       # Chinese semicolon
        "！",       # Chinese exclamation
        "？",       # Chinese question mark
        ". ",       # English period
        "; ",       # English semicolon
        "，",       # Chinese comma
        ", ",       # English comma
        " ",        # space
        "",         # character-level (last resort)
    ]

    raw_chunks = _recursive_split(text, separators, chunk_size)

    # Apply overlap
    chunks = _apply_overlap(raw_chunks, chunk_overlap)

    # Filter out tiny chunks
    result = []
    for i, c in enumerate(chunks):
        c = c.strip()
        if len(c) >= min_chunk_size:
            result.append(Chunk(index=len(result), text=c, char_count=len(c)))

    logger.info("Chunked {} chars → {} chunks (size={}, overlap={})", len(text), len(result), chunk_size, chunk_overlap)
    return result


def _recursive_split(text: str, separators: list[str], chunk_size: int) -> list[str]:
    """Recursively split text using the best available separator."""
    if len(text) <= chunk_size:
        return [text]

    # Find the best separator that actually exists in the text
    best_sep = ""
    for sep in separators:
        if sep == "":
            best_sep = ""
            break
        if sep in text:
            best_sep = sep
            break

    if best_sep == "":
        # Character-level split as last resort
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i : i + chunk_size])
        return chunks

    # Split by the chosen separator
    parts = text.split(best_sep)
    result = []
    current = ""

    for part in parts:
        candidate = current + best_sep + part if current else part

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                result.append(current)
            # If single part is still too long, recurse with next separator
            if len(part) > chunk_size:
                remaining_seps = separators[separators.index(best_sep) + 1 :]
                result.extend(_recursive_split(part, remaining_seps, chunk_size))
                current = ""
            else:
                current = part

    if current:
        result.append(current)

    return result


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    """Add overlap from previous chunk to the beginning of each chunk."""
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        prefix = prev[-overlap:] if len(prev) > overlap else prev
        result.append(prefix + chunks[i])

    return result
