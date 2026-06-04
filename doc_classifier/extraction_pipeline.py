"""
extraction_pipeline.py
=======================
Orchestrates the full schema-based extraction workflow.

This is the only module a caller needs to invoke after a document has
been reviewed and approved.

Workflow
--------
1. Load document metadata (validate that status is approved/corrected).
2. Resolve the document's ``stored_filepath`` from metadata.
3. Load the schema for the document's ``final_category``.
4. Extract raw content (text + tables) via ``extractor.extract_raw()``.
5. Map raw content to schema fields via ``schema_mapper.map_to_schema()``.
6. Persist the extraction result as JSON (``<store_dir>/<doc_id>_extraction.json``).
7. Update the metadata status to ``"extraction_complete"``.
8. Return the extraction result dict.

Extraction result format
------------------------
{
  "document_id":      "...",
  "category":         "Borrowing Profile",
  "filename":         "...",
  "extracted_records": [
    {"lender_name": "HDFC Bank", "loan_amount": 500.0, ...},
    ...
  ]
}
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from extractor import extract_raw
from metadata_store import _DEFAULT_STORE_DIR, _ensure_dir, _write_json, load_metadata
from schema_mapper import map_to_schema
from schema_store import _DEFAULT_SCHEMA_DIR, load_schema

logger = logging.getLogger(__name__)

# Statuses that permit extraction to proceed
EXTRACTABLE_STATUSES = {"approved", "corrected_by_user"}

# New status written to metadata after successful extraction
STATUS_EXTRACTION_COMPLETE = "extraction_complete"


# ---------------------------------------------------------------------------
# Extraction result persistence
# ---------------------------------------------------------------------------

def _extraction_path(document_id: str, store_dir: str) -> Path:
    """Return the Path for a document's extraction result JSON."""
    return _ensure_dir(store_dir) / f"{document_id}_extraction.json"


def save_extraction(
    result: dict[str, Any],
    *,
    store_dir: str = _DEFAULT_STORE_DIR,
) -> None:
    """Persist an extraction result to ``<store_dir>/<doc_id>_extraction.json``."""
    doc_id = result["document_id"]
    filepath = _extraction_path(doc_id, store_dir)
    _write_json(result, filepath)
    logger.info("Extraction result saved for document_id=%s", doc_id)


def load_extraction(
    document_id: str,
    *,
    store_dir: str = _DEFAULT_STORE_DIR,
) -> dict[str, Any]:
    """
    Load a previously saved extraction result.

    Raises
    ------
    FileNotFoundError
        If no extraction has been run for this document_id.
    """
    filepath = _extraction_path(document_id, store_dir)
    if not filepath.exists():
        raise FileNotFoundError(
            f"No extraction result found for document_id='{document_id}'. "
            f"Run POST /extract/{document_id} first."
        )
    with open(filepath, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Metadata update helper
# ---------------------------------------------------------------------------

def _mark_extraction_complete(
    document_id: str,
    store_dir: str,
) -> None:
    """
    Update the document's metadata status to 'extraction_complete'.
    Reuses the existing metadata store helpers without breaking immutability
    of model_prediction.  Also syncs the consolidated metadata_store.json index.
    """
    from metadata_store import _metadata_path, _load_index, _save_index

    meta_path = _metadata_path(document_id, store_dir)

    # Load -> mutate status only -> save individual file
    with open(meta_path, "r", encoding="utf-8") as fh:
        metadata = json.load(fh)

    metadata["status"] = STATUS_EXTRACTION_COMPLETE
    _write_json(metadata, meta_path)

    # Sync consolidated index
    index = _load_index(store_dir)
    index[document_id] = metadata
    _save_index(index, store_dir)

    logger.info("Metadata status updated to 'extraction_complete' for document_id=%s", document_id)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_extraction(
    document_id: str,
    *,
    store_dir: str = _DEFAULT_STORE_DIR,
    schema_dir: str = _DEFAULT_SCHEMA_DIR,
) -> dict[str, Any]:
    """
    Run the full schema-based extraction pipeline for an approved document.

    The document file path is read from the ``stored_filepath`` field in
    the metadata record.  Files must have been saved permanently during
    classification (see ``api.py`` upload handling).

    Parameters
    ----------
    document_id : str
        UUID of the document to extract.
    store_dir : str
        Directory containing metadata and extraction JSON files.
    schema_dir : str
        Directory containing schema definition JSON files.

    Returns
    -------
    dict
        Extraction result with ``document_id``, ``category``,
        ``filename``, and ``extracted_records``.

    Raises
    ------
    FileNotFoundError
        If metadata or the source document file cannot be found.
    PermissionError
        If the document has not yet been reviewed/approved.
    KeyError
        If no schema exists for the document's final category.
    """
    # ------------------------------------------------------------------
    # Step 1: Load and validate metadata
    # ------------------------------------------------------------------
    metadata = load_metadata(document_id, store_dir=store_dir)
    doc_status = metadata.get("status", "")

    if doc_status not in EXTRACTABLE_STATUSES:
        raise PermissionError(
            f"Extraction is only allowed for documents with status "
            f"{sorted(EXTRACTABLE_STATUSES)}. "
            f"Document '{document_id}' has status='{doc_status}'. "
            f"Please complete the human review first via POST /review."
        )

    category = metadata.get("final_category") or metadata.get("model_prediction", "")
    filename = metadata.get("filename", "unknown")

    # ------------------------------------------------------------------
    # Step 2: Resolve the stored file path
    # ------------------------------------------------------------------
    stored_filepath: str | None = metadata.get("stored_filepath")
    if not stored_filepath or not Path(stored_filepath).is_file():
        raise FileNotFoundError(
            f"Source document file not found at '{stored_filepath}' "
            f"for document_id='{document_id}'. "
            f"Ensure files are saved permanently during upload (POST /classify)."
        )

    # ------------------------------------------------------------------
    # Step 3: Load schema
    # ------------------------------------------------------------------
    schema = load_schema(category, schema_dir=schema_dir)
    logger.info(
        "Extraction started: document_id=%s  category='%s'  schema_fields=%d",
        document_id, category, len(schema.get("fields", {}))
    )

    # ------------------------------------------------------------------
    # Step 4: Extract raw content
    # ------------------------------------------------------------------
    raw_content = extract_raw(stored_filepath)

    # ------------------------------------------------------------------
    # Step 5: Map to schema
    # ------------------------------------------------------------------
    records = map_to_schema(raw_content, schema)

    # ------------------------------------------------------------------
    # Step 6: Build and persist result
    # ------------------------------------------------------------------
    result: dict[str, Any] = {
        "document_id":       document_id,
        "category":          category,
        "filename":          filename,
        "extracted_records": records,
    }

    save_extraction(result, store_dir=store_dir)

    # ------------------------------------------------------------------
    # Step 7: Update metadata status
    # ------------------------------------------------------------------
    _mark_extraction_complete(document_id, store_dir)

    logger.info(
        "Extraction complete: document_id=%s  records=%d",
        document_id, len(records)
    )
    return result
