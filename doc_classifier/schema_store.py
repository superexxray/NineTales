"""
schema_store.py
===============
Persistent JSON store for user-defined document extraction schemas.

Each schema defines which fields should be extracted from documents of a
given category, along with their expected data types.

Storage layout
--------------
  <SCHEMA_STORE_DIR>/
      Borrowing_Profile.json
      Annual_Report.json
      ...

Environment variable
--------------------
  DOC_CLASSIFIER_SCHEMA_DIR — override the storage directory at runtime.
  Defaults to ``./schema_definitions``.

Schema format
-------------
{
  "category": "Borrowing Profile",
  "fields": {
    "lender_name":    "string",
    "loan_amount":    "number",
    "interest_rate":  "number",
    "tenure_months":  "number"
  }
}
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_DIR: str = os.environ.get(
    "DOC_CLASSIFIER_SCHEMA_DIR",
    str(Path.cwd() / "schema_definitions"),
)

# Canonical set of valid field types
VALID_FIELD_TYPES: frozenset[str] = frozenset(["string", "number", "date", "boolean"])

# ---------------------------------------------------------------------------
# Bundled default schemas for all five categories
# ---------------------------------------------------------------------------

DEFAULT_SCHEMAS: dict[str, dict[str, Any]] = {
    "ALM": {
        "category": "ALM",
        "fields": {
            "time_bucket":          "string",
            "rate_sensitive_assets": "number",
            "rate_sensitive_liabilities": "number",
            "gap":                  "number",
            "cumulative_gap":       "number",
            "nim":                  "number",
            "lcr":                  "number",
            "nsfr":                 "number",
        },
    },
    "Shareholding Pattern": {
        "category": "Shareholding Pattern",
        "fields": {
            "shareholder_category": "string",
            "no_of_shareholders":   "number",
            "total_shares":         "number",
            "demat_shares":         "number",
            "percentage_holding":   "number",
            "pledged_shares":       "number",
        },
    },
    "Borrowing Profile": {
        "category": "Borrowing Profile",
        "fields": {
            "lender_name":    "string",
            "instrument_type": "string",
            "loan_amount":    "number",
            "interest_rate":  "number",
            "tenure_months":  "number",
            "outstanding":    "number",
            "credit_rating":  "string",
        },
    },
    "Annual Report": {
        "category": "Annual Report",
        "fields": {
            "line_item":      "string",
            "current_year":   "number",
            "previous_year":  "number",
            "unit":           "string",
            "ebitda":         "number",
            "pat":            "number",
            "eps":            "number",
            "total_assets":   "number",
            "total_equity":   "number",
        },
    },
    "Portfolio Performance": {
        "category": "Portfolio Performance",
        "fields": {
            "scheme_name":   "string",
            "aum":           "number",
            "nav":           "number",
            "returns_1y":    "number",
            "returns_3y":    "number",
            "returns_5y":    "number",
            "benchmark":     "string",
            "alpha":         "number",
            "sharpe_ratio":  "number",
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _category_to_filename(category: str) -> str:
    """Convert a category name to a safe filename slug."""
    return re.sub(r"[^\w]", "_", category) + ".json"


def _ensure_dir(schema_dir: str) -> Path:
    path = Path(schema_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _schema_path(category: str, schema_dir: str) -> Path:
    return _ensure_dir(schema_dir) / _category_to_filename(category)


def _write_json(data: dict[str, Any], filepath: Path) -> None:
    tmp = filepath.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        tmp.replace(filepath)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _validate_schema(schema: dict[str, Any]) -> None:
    """Raise ValueError if the schema dict is structurally invalid."""
    if "category" not in schema:
        raise ValueError("Schema must contain a 'category' key.")
    if "fields" not in schema or not isinstance(schema["fields"], dict):
        raise ValueError("Schema must contain a 'fields' dict.")
    for field_name, field_type in schema["fields"].items():
        if field_type not in VALID_FIELD_TYPES:
            raise ValueError(
                f"Field '{field_name}' has unsupported type '{field_type}'. "
                f"Supported types: {sorted(VALID_FIELD_TYPES)}"
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_schema(
    schema: dict[str, Any],
    *,
    schema_dir: str = _DEFAULT_SCHEMA_DIR,
) -> dict[str, Any]:
    """
    Save (create or overwrite) a schema for a document category.

    Parameters
    ----------
    schema : dict
        Schema dict with ``category`` and ``fields`` keys.
    schema_dir : str
        Directory to store schema JSON files.

    Returns
    -------
    dict
        The saved schema (unchanged).

    Raises
    ------
    ValueError
        If the schema structure is invalid.
    """
    _validate_schema(schema)
    filepath = _schema_path(schema["category"], schema_dir)
    _write_json(schema, filepath)
    logger.info("Schema saved for category='%s'", schema["category"])
    return schema


def load_schema(
    category: str,
    *,
    schema_dir: str = _DEFAULT_SCHEMA_DIR,
) -> dict[str, Any]:
    """
    Load the schema for a given category.

    Falls back to the built-in default schema if no user-defined one exists.

    Parameters
    ----------
    category : str
        Document category name.
    schema_dir : str
        Directory where schemas are stored.

    Returns
    -------
    dict
        The schema dict.

    Raises
    ------
    KeyError
        If no schema (custom or default) exists for the category.
    """
    filepath = _schema_path(category, schema_dir)

    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
        logger.debug("Loaded custom schema for category='%s'", category)
        return schema

    # Fall back to default
    if category in DEFAULT_SCHEMAS:
        logger.debug("Using default schema for category='%s'", category)
        return DEFAULT_SCHEMAS[category]

    raise KeyError(
        f"No schema defined for category='{category}'. "
        f"Available defaults: {sorted(DEFAULT_SCHEMAS)}"
    )


def delete_schema(
    category: str,
    *,
    schema_dir: str = _DEFAULT_SCHEMA_DIR,
) -> bool:
    """
    Delete the user-defined schema for a category (reverts to built-in default).

    Returns True if a file was deleted, False if none existed.
    """
    filepath = _schema_path(category, schema_dir)
    if filepath.exists():
        filepath.unlink()
        logger.info("Deleted custom schema for category='%s'", category)
        return True
    return False


def list_schemas(
    *,
    schema_dir: str = _DEFAULT_SCHEMA_DIR,
) -> list[dict[str, Any]]:
    """
    Return all available schemas (custom files + defaults for missing ones).

    Custom schemas override built-in defaults for the same category.
    """
    custom: dict[str, dict[str, Any]] = {}
    schema_path_obj = _ensure_dir(schema_dir)

    for json_file in schema_path_obj.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as fh:
                s = json.load(fh)
            custom[s.get("category", json_file.stem)] = s
        except Exception as exc:
            logger.warning("Skipping corrupt schema file '%s': %s", json_file, exc)

    # Merge: custom overrides defaults
    merged = {**DEFAULT_SCHEMAS, **custom}
    return list(merged.values())


def seed_default_schemas(
    *,
    schema_dir: str = _DEFAULT_SCHEMA_DIR,
    overwrite: bool = False,
) -> list[str]:
    """
    Write all built-in default schemas to disk.

    Parameters
    ----------
    overwrite : bool
        If False (default), skip categories that already have a file.

    Returns
    -------
    list[str]
        Categories that were seeded.
    """
    seeded: list[str] = []
    for category, schema in DEFAULT_SCHEMAS.items():
        filepath = _schema_path(category, schema_dir)
        if not filepath.exists() or overwrite:
            _write_json(schema, filepath)
            seeded.append(category)
            logger.info("Seeded default schema for category='%s'", category)
    return seeded
