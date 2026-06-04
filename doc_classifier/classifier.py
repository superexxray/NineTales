"""
classifier.py
=============
Core classification logic.

Computes cosine similarity between a document embedding and pre-computed
category embeddings, then returns the top-scoring category with a
normalised confidence score.

Notes
-----
* Category embeddings are computed **once at construction time** and cached.
* Since all embeddings are L2-normalised (unit vectors), cosine similarity
  reduces to a simple dot product — no extra division needed.
* The raw cosine similarity scores are further softmax-transformed to
  produce a calibrated confidence value in [0, 1] that reflects not just
  absolute similarity but *relative* confidence over all categories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from category_definitions import CATEGORY_DESCRIPTIONS, CATEGORY_NAMES
from embedder import DocumentEmbedder, get_default_embedder

logger = logging.getLogger(__name__)

# Temperature for softmax normalisation.
# Higher → sharper separation; lower → more uniform probabilities.
SOFTMAX_TEMPERATURE: float = 5.0


def _softmax(scores: np.ndarray, temperature: float = SOFTMAX_TEMPERATURE) -> np.ndarray:
    """Compute temperature-scaled softmax over a 1-D score array."""
    scaled = scores * temperature
    # Shift for numerical stability
    shifted = scaled - scaled.max()
    exp_scores = np.exp(shifted)
    return exp_scores / exp_scores.sum()


@dataclass
class ClassificationResult:
    """Typed result container for a single document classification."""

    filename: str
    predicted_category: str
    confidence: float
    all_scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return the public-facing output dict (excludes all_scores)."""
        return {
            "filename": self.filename,
            "predicted_category": self.predicted_category,
            "confidence": round(self.confidence, 4),
        }

    def to_dict_full(self) -> dict:
        """Return the full result including per-category scores."""
        return {
            **self.to_dict(),
            "category_scores": {k: round(v, 4) for k, v in self.all_scores.items()},
        }


class DocumentClassifier:
    """
    Classifies financial documents into one of five predefined categories
    using semantic similarity.

    Parameters
    ----------
    embedder : DocumentEmbedder, optional
        A pre-initialised embedder.  Defaults to the module-level singleton.

    Attributes
    ----------
    category_embeddings : np.ndarray
        Matrix of shape ``(num_categories, embedding_dim)`` containing
        pre-computed, L2-normalised category description embeddings.

    Examples
    --------
    >>> clf = DocumentClassifier()
    >>> result = clf.classify("your cleaned document text", filename="report.pdf")
    >>> print(result.to_dict())
    {'filename': 'report.pdf', 'predicted_category': 'Annual Report', 'confidence': 0.87}
    """

    def __init__(self, embedder: DocumentEmbedder | None = None) -> None:
        self.embedder: DocumentEmbedder = embedder or get_default_embedder()
        self._category_names: list[str] = CATEGORY_NAMES
        self._category_embeddings: np.ndarray = self._build_category_embeddings()

    def _build_category_embeddings(self) -> np.ndarray:
        """
        Pre-compute and cache category description embeddings.

        Returns
        -------
        np.ndarray
            Shape ``(num_categories, embedding_dim)``.
        """
        logger.info("Pre-computing embeddings for %d categories…", len(self._category_names))
        descriptions = [CATEGORY_DESCRIPTIONS[name] for name in self._category_names]
        embeddings = self.embedder.embed_texts(descriptions)
        logger.info("Category embeddings ready — shape: %s", embeddings.shape)
        return embeddings  # (num_categories, dim)

    def classify(
        self,
        cleaned_text: str,
        filename: str = "unknown",
        *,
        return_full: bool = False,
    ) -> ClassificationResult:
        """
        Classify a document given its cleaned text.

        Parameters
        ----------
        cleaned_text : str
            Pre-processed document text (from text_cleaner.clean_text).
        filename : str
            Original filename, included in the result for traceability.
        return_full : bool
            If True, the result includes per-category similarity scores.

        Returns
        -------
        ClassificationResult
            Contains ``filename``, ``predicted_category``, and ``confidence``.
        """
        if not cleaned_text or not cleaned_text.strip():
            logger.warning("Empty text supplied for '%s'. Returning low-confidence result.", filename)
            return ClassificationResult(
                filename=filename,
                predicted_category="Unknown",
                confidence=0.0,
                all_scores={name: 0.0 for name in self._category_names},
            )

        # Step 1 — Embed the document (chunk-average for long docs)
        doc_embedding = self.embedder.embed_document(cleaned_text)  # (dim,)

        # Step 2 — Cosine similarity (= dot product since both are unit-norm)
        cosine_scores: np.ndarray = self._category_embeddings @ doc_embedding  # (num_cats,)

        # Step 3 — Softmax-normalise for calibrated confidence
        probabilities: np.ndarray = _softmax(cosine_scores)

        # Step 4 — Select best category
        best_idx: int = int(np.argmax(probabilities))
        best_category: str = self._category_names[best_idx]
        confidence: float = float(probabilities[best_idx])

        all_scores = {
            name: float(probabilities[i])
            for i, name in enumerate(self._category_names)
        }

        logger.info(
            "Classified '%s' → '%s' (confidence: %.4f)",
            filename,
            best_category,
            confidence,
        )

        return ClassificationResult(
            filename=filename,
            predicted_category=best_category,
            confidence=confidence,
            all_scores=all_scores,
        )
