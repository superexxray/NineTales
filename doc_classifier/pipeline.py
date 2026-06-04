"""
pipeline.py
===========
Public-facing orchestration layer.

This module ties together document loading, text cleaning, classification,
and metadata persistence into a single ``classify_document`` function.

Usage
-----
    from doc_classifier.pipeline import classify_document

    result = classify_document("path/to/annual_report.pdf")
    # {
    #   "document_id": "<uuid>",
    #   "filename": "annual_report.pdf",
    #   "model_prediction": "Annual Report",
    #   "confidence": 0.8742,
    #   "final_category": null,
    #   "status": "awaiting_review"
    # }
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from classifier import DocumentClassifier
from document_loader import load_document
from metadata_store import _DEFAULT_STORE_DIR, create_metadata
from text_cleaner import clean_text

logger = logging.getLogger(__name__)

# Module-level classifier singleton — category embeddings are pre-computed once
_classifier: DocumentClassifier | None = None


def _get_classifier() -> DocumentClassifier:
    """Return the module-level DocumentClassifier, creating it if needed."""
    global _classifier
    if _classifier is None:
        _classifier = DocumentClassifier()
    return _classifier


def classify_document(
    filepath: str,
    *,
    max_words: int = 512,
    return_full_scores: bool = False,
    original_filename: str | None = None,
    store_dir: str = _DEFAULT_STORE_DIR,
    stored_filepath: str | None = None,
) -> dict[str, Any]:
    """
    Classify a financial document, persist metadata, and return the record.

    Pipeline steps
    --------------
    1. Load the document (PDF via pdfplumber/OCR, or Excel via pandas).
    2. Clean and normalise the extracted text.
    3. Embed using ``all-MiniLM-L6-v2``.
    4. Compute cosine similarity against category embeddings.
    5. Persist a metadata JSON record and return it.

    Parameters
    ----------
    filepath : str
        Absolute or relative path to the document (PDF / XLS / XLSX / CSV).
    max_words : int
        Maximum words to retain before embedding.  Default 512.
    return_full_scores : bool
        If ``True``, response also includes per-category softmax scores.
    original_filename : str, optional
        Override the filename stored in metadata (e.g., original upload name
        when the file was saved to a temp path by the API layer).
    store_dir : str
        Directory in which the metadata JSON file is persisted.
        Defaults to ``DOC_CLASSIFIER_STORE_DIR`` env var or ``./review_metadata``.

    Returns
    -------
    dict
        Metadata record::

            {
              "document_id": "<uuid4>",
              "filename": "...",
              "model_prediction": "...",
              "confidence": 0.87,
              "final_category": null,
              "status": "awaiting_review"
            }

        If *return_full_scores* is ``True``, also includes
        ``category_scores`` mapping each category to its softmax probability.

    Raises
    ------
    FileNotFoundError
        If the file at *filepath* does not exist.
    ValueError
        If the file type is unsupported or the file cannot be parsed.

    Examples
    --------
    >>> from doc_classifier.pipeline import classify_document
    >>> result = classify_document("reports/q4_alm.pdf")
    >>> print(result["model_prediction"])
    'ALM'
    """
    filepath = os.path.abspath(filepath)
    # Prefer the caller-supplied display name (e.g. original upload name)
    filename = original_filename or Path(filepath).name

    logger.info("classify_document called for: %s", filename)

    # ------------------------------------------------------------------
    # Step 1: Load
    # ------------------------------------------------------------------
    raw_text: str = load_document(filepath)

    if not raw_text.strip():
        logger.warning("No text could be extracted from '%s'.", filename)
        return create_metadata(
            filename=filename,
            model_prediction="Unknown",
            confidence=0.0,
            stored_filepath=stored_filepath or os.path.abspath(filepath),
            store_dir=store_dir,
        )

    # ------------------------------------------------------------------
    # Step 2: Clean
    # ------------------------------------------------------------------
    cleaned: str = clean_text(raw_text, max_words=max_words)

    if not cleaned.strip():
        logger.warning("Text from '%s' was empty after cleaning.", filename)
        return create_metadata(
            filename=filename,
            model_prediction="Unknown",
            confidence=0.0,
            stored_filepath=stored_filepath or os.path.abspath(filepath),
            store_dir=store_dir,
        )

    # ------------------------------------------------------------------
    # Step 3 & 4: Embed + Classify
    # ------------------------------------------------------------------
    clf = _get_classifier()
    result = clf.classify(cleaned, filename=filename)

    # ------------------------------------------------------------------
    # Step 5: Persist metadata and return
    # ------------------------------------------------------------------
    classification = result.to_dict_full() if return_full_scores else result.to_dict()

    metadata = create_metadata(
        filename=filename,
        model_prediction=classification["predicted_category"],
        confidence=classification["confidence"],
        stored_filepath=stored_filepath or os.path.abspath(filepath),
        store_dir=store_dir,
    )

    # Optionally attach full per-category scores alongside metadata
    if return_full_scores:
        metadata["category_scores"] = classification.get("category_scores", {})

    return metadata


def reset_classifier() -> None:
    """
    Reset the module-level classifier singleton.

    Useful in tests or when you want the model to be reloaded.
    """
    global _classifier
    _classifier = None
    logger.info("Classifier singleton has been reset.")
