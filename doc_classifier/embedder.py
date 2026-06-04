"""
embedder.py
===========
Wraps the sentence-transformers model to produce document embeddings.

Design decisions
----------------
* The SentenceTransformer model is loaded **once** per process via a
  module-level cached instance (lazy singleton pattern).  This avoids
  re-loading the ~80 MB model on every classification call.

* Long texts that exceed the model's token limit (256 tokens for
  all-MiniLM-L6-v2) are split into overlapping 200-word chunks and
  their embeddings are averaged.  This gives representative embeddings
  for multi-page financial reports without truncation artefacts.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Default model — fast, lightweight, good semantic quality
DEFAULT_MODEL_NAME: str = "all-MiniLM-L6-v2"

# Chunk settings for long documents
CHUNK_SIZE_WORDS: int = 200   # words per chunk
CHUNK_OVERLAP_WORDS: int = 40  # overlap between consecutive chunks


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """
    Split *text* into overlapping word-level chunks.

    Parameters
    ----------
    text : str
        The cleaned document text.
    chunk_size : int
        Number of words per chunk.
    overlap : int
        Number of words shared between consecutive chunks.

    Returns
    -------
    list[str]
        Non-empty chunks.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break

    return chunks if chunks else [text]


class DocumentEmbedder:
    """
    Generates sentence-level embeddings for text documents.

    Parameters
    ----------
    model_name : str
        A sentence-transformers model identifier.
        Defaults to ``all-MiniLM-L6-v2``.

    Attributes
    ----------
    model : SentenceTransformer
        The loaded embedding model.
    embedding_dim : int
        Dimensionality of the output embeddings.

    Examples
    --------
    >>> embedder = DocumentEmbedder()
    >>> vec = embedder.embed_document("Some financial text here")
    >>> vec.shape
    (384,)
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        logger.info("Loading sentence-transformers model: %s", model_name)
        self.model = SentenceTransformer(model_name)
        self.embedding_dim: int = self.model.get_sentence_embedding_dimension()
        logger.info("Model loaded. Embedding dimension: %d", self.embedding_dim)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Embed a list of text strings.

        Parameters
        ----------
        texts : list[str]
            Non-empty list of text strings.

        Returns
        -------
        np.ndarray
            Array of shape ``(len(texts), embedding_dim)`` with
            L2-normalised embeddings.
        """
        if not texts:
            raise ValueError("texts list must not be empty.")

        embeddings: np.ndarray = self.model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,   # unit vectors → cosine sim = dot product
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embeddings  # shape: (N, embedding_dim)

    def embed_document(self, text: str) -> np.ndarray:
        """
        Embed a (potentially long) document by chunking and averaging.

        Parameters
        ----------
        text : str
            Cleaned document text.

        Returns
        -------
        np.ndarray
            1-D array of shape ``(embedding_dim,)``, L2-normalised.
        """
        if not text or not text.strip():
            logger.warning("embed_document received empty text; returning zero vector.")
            return np.zeros(self.embedding_dim, dtype=np.float32)

        chunks = _chunk_text(text)
        chunk_embeddings = self.embed_texts(chunks)  # (num_chunks, dim)

        # Average chunk embeddings and re-normalise
        avg = chunk_embeddings.mean(axis=0)
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg = avg / norm

        return avg.astype(np.float32)


# ---------------------------------------------------------------------------
# Module-level lazy singleton
# ---------------------------------------------------------------------------

_default_embedder: Optional[DocumentEmbedder] = None


def get_default_embedder() -> DocumentEmbedder:
    """
    Return the shared default :class:`DocumentEmbedder` instance,
    creating it on first call.
    """
    global _default_embedder
    if _default_embedder is None:
        _default_embedder = DocumentEmbedder()
    return _default_embedder
