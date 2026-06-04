"""
metadata_store.py
=================
Persistent JSON metadata store for human-in-the-loop document review.

Responsibilities
----------------
* Generate a unique document_id (UUID4) per classified document.
* Create the initial metadata JSON object with immutable model_prediction.
* Save / load metadata as individual JSON files in a configurable directory.
* Maintain a consolidated ``metadata_store.json`` index that mirrors all
  records — this file is loaded on startup so that documents survive backend
  restarts regardless of the working directory.
* Apply human review updates (final_category, status) — the **only** place
  that is allowed to mutate the stored JSON.

Storage layout
--------------
  <METADATA_STORE_DIR>/
      metadata_store.json        <- consolidated index (all records)
      <document_id>.json         <- individual record (used by extraction pipeline)
      <document_id>.json
      ...

Environment variable
--------------------
  DOC_CLASSIFIER_STORE_DIR  -- override the storage directory at runtime.
  Defaults to ``review_metadata/`` next to this source file (absolute path).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Anchor the default store directory to this file's own location so the path
# is stable regardless of the working directory uvicorn is started from.
_DEFAULT_STORE_DIR: str = os.environ.get(
    "DOC_CLASSIFIER_STORE_DIR",
    str(Path(__file__).resolve().parent / "review_metadata"),
)

# Name of the consolidated index file inside the store directory
_INDEX_FILENAME = "metadata_store.json"

# Valid review statuses
STATUS_AWAITING = "awaiting_review"
STATUS_APPROVED = "approved"
STATUS_CORRECTED = "corrected_by_user"
STATUS_EXTRACTION_COMPLETE = "extraction_complete"

# Valid category names (mirrors category_definitions.CATEGORY_NAMES)
VALID_CATEGORIES: frozenset[str] = frozenset(
    [
        "ALM",
        "Shareholding Pattern",
        "Borrowing Profile",
        "Annual Report",
        "Portfolio Performance",
    ]
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_dir(store_dir: str) -> Path:
    """Create the store directory if it does not already exist."""
    path = Path(store_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _metadata_path(document_id: str, store_dir: str) -> Path:
    """Return the Path for a given document_id's individual JSON file."""
    return _ensure_dir(store_dir) / f"{document_id}.json"


def _index_path(store_dir: str) -> Path:
    """Return the Path for the consolidated metadata_store.json index."""
    return _ensure_dir(store_dir) / _INDEX_FILENAME


def _write_json(data: dict[str, Any], filepath: Path) -> None:
    """Atomically write *data* as pretty-printed JSON to *filepath*."""
    tmp_path = filepath.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        tmp_path.replace(filepath)   # atomic rename on same filesystem
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _load_index(store_dir: str) -> dict[str, dict[str, Any]]:
    """
    Load the consolidated index from ``metadata_store.json``.

    Returns a dict keyed by document_id.  If the file does not exist yet
    (first run), it is built by scanning the existing individual per-doc
    JSON files so that no previously uploaded data is lost.
    """
    idx_path = _index_path(store_dir)

    if idx_path.exists():
        try:
            with open(idx_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            # Support both list-of-records and dict-keyed-by-id formats
            if isinstance(raw, list):
                return {rec["document_id"]: rec for rec in raw if "document_id" in rec}
            if isinstance(raw, dict):
                return raw
        except Exception as exc:
            logger.warning(
                "Could not parse %s, rebuilding from per-doc files: %s", idx_path, exc
            )

    # Fallback: scan individual per-doc files and build the index
    index: dict[str, dict[str, Any]] = {}
    store_path = _ensure_dir(store_dir)
    for json_file in store_path.glob("*.json"):
        if json_file.name in (_INDEX_FILENAME,) or json_file.name.endswith(
            ("_onboarding.json", "_extraction.json")
        ):
            continue
        try:
            with open(json_file, "r", encoding="utf-8") as fh:
                rec = json.load(fh)
            if "document_id" in rec:
                index[rec["document_id"]] = rec
        except Exception as exc:
            logger.warning("Skipping unreadable file '%s': %s", json_file, exc)

    # Persist the rebuilt index so subsequent startups are fast
    _save_index(index, store_dir)
    return index


def _save_index(index: dict[str, dict[str, Any]], store_dir: str) -> None:
    """Persist the full in-memory index to ``metadata_store.json``."""
    records = list(index.values())
    idx_path = _index_path(store_dir)
    tmp_path = idx_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)
        tmp_path.replace(idx_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_metadata(
    filename: str,
    model_prediction: str,
    confidence: float,
    *,
    stored_filepath: str | None = None,
    store_dir: str = _DEFAULT_STORE_DIR,
) -> dict[str, Any]:
    """
    Create and persist an initial metadata record after classification.

    Parameters
    ----------
    filename : str
        Original filename of the uploaded document.
    model_prediction : str
        The category predicted by the ML model. **Never mutated after creation.**
    confidence : float
        Softmax confidence score (0.0 - 1.0).
    stored_filepath : str, optional
        Absolute path to the permanently stored copy of the uploaded file.
        Required for the extraction pipeline to re-read the document.
    store_dir : str
        Directory in which to persist the JSON files.

    Returns
    -------
    dict
        The freshly created metadata record:

        .. code-block:: json

            {
              "document_id": "<uuid4>",
              "filename": "...",
              "model_prediction": "...",
              "confidence": 0.87,
              "final_category": null,
              "status": "awaiting_review",
              "stored_filepath": "/abs/path/to/file.pdf"
            }
    """
    document_id = str(uuid.uuid4())

    metadata: dict[str, Any] = {
        "document_id": document_id,
        "filename": filename,
        "model_prediction": model_prediction,
        "confidence": round(float(confidence), 4),
        "final_category": None,
        "status": STATUS_AWAITING,
        "stored_filepath": stored_filepath,
    }

    # 1. Write individual file (required by extraction_pipeline.py)
    filepath = _metadata_path(document_id, store_dir)
    _write_json(metadata, filepath)

    # 2. Append to consolidated index
    index = _load_index(store_dir)
    index[document_id] = metadata
    _save_index(index, store_dir)

    logger.info(
        "Metadata created: document_id=%s  filename='%s'  prediction='%s'",
        document_id,
        filename,
        model_prediction,
    )
    return metadata


def load_metadata(
    document_id: str,
    *,
    store_dir: str = _DEFAULT_STORE_DIR,
) -> dict[str, Any]:
    """
    Load the metadata record for *document_id*.

    Checks the consolidated index first; falls back to the individual file
    if the record is not in the index (e.g. legacy data written before this
    version).

    Parameters
    ----------
    document_id : str
        UUID of the document.
    store_dir : str
        Directory where JSON files are stored.

    Returns
    -------
    dict
        The metadata record.

    Raises
    ------
    FileNotFoundError
        If no metadata exists for *document_id*.
    ValueError
        If the stored JSON is malformed.
    """
    # Primary: consolidated index
    index = _load_index(store_dir)
    if document_id in index:
        return index[document_id]

    # Fallback: individual file
    filepath = _metadata_path(document_id, store_dir)
    if not filepath.exists():
        raise FileNotFoundError(
            f"No metadata found for document_id='{document_id}'. "
            f"Expected file: {filepath}"
        )

    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Metadata file for document_id='{document_id}' is corrupt: {exc}"
        ) from exc


def apply_review(
    document_id: str,
    final_category: str,
    *,
    store_dir: str = _DEFAULT_STORE_DIR,
) -> dict[str, Any]:
    """
    Apply a human reviewer's decision to the stored metadata.

    Rules
    -----
    * ``model_prediction`` is **never** overwritten.
    * ``final_category`` is set to *final_category*.
    * ``status`` becomes ``"approved"`` when *final_category* matches the
      model prediction, or ``"corrected_by_user"`` when it differs.

    Parameters
    ----------
    document_id : str
        UUID of the document to update.
    final_category : str
        The human-assigned category. Must be one of the five valid categories.
    store_dir : str
        Directory where JSON files are stored.

    Returns
    -------
    dict
        The updated metadata record.

    Raises
    ------
    FileNotFoundError
        If no metadata file exists for *document_id*.
    ValueError
        If *final_category* is not a known category name.
    """
    if final_category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{final_category}'. "
            f"Must be one of: {sorted(VALID_CATEGORIES)}"
        )

    metadata = load_metadata(document_id, store_dir=store_dir)

    metadata["final_category"] = final_category
    metadata["status"] = (
        STATUS_APPROVED
        if final_category == metadata["model_prediction"]
        else STATUS_CORRECTED
    )

    # 1. Update individual file
    filepath = _metadata_path(document_id, store_dir)
    _write_json(metadata, filepath)

    # 2. Sync consolidated index
    index = _load_index(store_dir)
    index[document_id] = metadata
    _save_index(index, store_dir)

    logger.info(
        "Review applied: document_id=%s  final_category='%s'  status='%s'",
        document_id,
        final_category,
        metadata["status"],
    )
    return metadata


def list_metadata(
    *,
    store_dir: str = _DEFAULT_STORE_DIR,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return all stored metadata records, optionally filtered by status.

    Reads from the consolidated ``metadata_store.json`` index, which is
    populated on startup from disk, so results survive backend restarts.

    Parameters
    ----------
    store_dir : str
        Directory where JSON files are stored.
    status_filter : str, optional
        If provided, only records with this status are returned.
        One of: ``"awaiting_review"``, ``"approved"``, ``"corrected_by_user"``,
        ``"extraction_complete"``.

    Returns
    -------
    list[dict]
        Sorted by document_id for stable, deterministic ordering.
    """
    index = _load_index(store_dir)
    records = sorted(index.values(), key=lambda r: r.get("document_id", ""))

    if status_filter is not None:
        records = [r for r in records if r.get("status") == status_filter]

    return records
