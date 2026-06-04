"""
schema_mapper.py
================
Maps raw extracted content (text + tables) to user-defined schema fields.

Strategy
--------
For each field in the schema the mapper applies (in order):

1. **Table-column match** — look for DataFrame columns whose name closely
   matches the field name (fuzzy substring or token overlap).  If found,
   pull values from that column to form one record per row.

2. **Text-pattern match** — scan the raw text for the field keyword and
   extract the value that follows it using a contextual regex.

Type coercion
-------------
* ``"number"``  — strip currency symbols / commas, cast to float.
* ``"string"``  — keep as-is, truncated to 200 chars.
* ``"date"``    — basic ISO/common format capture.
* ``"boolean"`` — "yes"/"true"/"1" → True, else False.

The mapper is intentionally heuristic.  For production, replace or augment
the matching logic with an LLM or NLP-based extraction step.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from extractor import RawContent

logger = logging.getLogger(__name__)

# ─── Regex helpers ──────────────────────────────────────────────────────────

# Matches a numeric value (with commas, decimals, optional %, optional sign)
_NUM_RE = re.compile(
    r"[+-]?\s*(?:(?:Rs\.?|INR|USD|\$|€|£|₹)\s*)?([0-9,]+(?:\.[0-9]+)?)\s*(?:%|Cr\.?|Lakh|Mn|Bn)?"
)

# Loose date patterns: 31-Mar-2024, 2024-03-31, 31/03/2024, March 31, 2024
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[-/]\w{2,9}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\w{3,9}\s+\d{1,2},?\s+\d{4})\b"
)


# ─── Similarity helpers ─────────────────────────────────────────────────────

def _token_overlap(a: str, b: str) -> float:
    """
    Jaccard-like token overlap between two strings (normalised 0–1).
    Used to decide if a column header matches a schema field name.
    """
    tokens_a = set(re.sub(r"[^\w]", " ", a.lower()).split())
    tokens_b = set(re.sub(r"[^\w]", " ", b.lower()).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _column_matches_field(col: str, field: str, threshold: float = 0.3) -> bool:
    """
    Return True if a DataFrame column name is deemed to match a schema field name.
    Uses both substring containment and token overlap.
    """
    col_norm  = re.sub(r"[^\w]", " ", col.lower()).strip()
    field_norm = re.sub(r"[^\w]", " ", field.lower()).strip()

    # Direct containment
    if field_norm in col_norm or col_norm in field_norm:
        return True

    # Token overlap
    return _token_overlap(col_norm, field_norm) >= threshold


# ─── Type coercion ───────────────────────────────────────────────────────────

def _coerce(value: Any, field_type: str) -> Any:
    """Coerce *value* to the declared schema field type."""
    if value is None or str(value).strip() in ("", "nan", "None", "N/A", "-"):
        return None

    raw = str(value).strip()

    if field_type == "number":
        m = _NUM_RE.search(raw.replace(",", ""))
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
        return None

    elif field_type == "date":
        m = _DATE_RE.search(raw)
        return m.group(0) if m else raw[:50]

    elif field_type == "boolean":
        return raw.lower() in {"yes", "true", "1", "y", "✓"}

    else:  # "string"
        return raw[:200]


# ─── Table-based extraction ──────────────────────────────────────────────────

def _extract_from_tables(
    tables: list[pd.DataFrame],
    schema_fields: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Try to build records from DataFrames whose columns match schema fields.

    For each table, check which schema fields match a column.
    If at least one field is matched, produce one record per table row.
    """
    records: list[dict[str, Any]] = []

    for df_idx, df in enumerate(tables):
        # Map schema field → matched column name (or None)
        field_to_col: dict[str, str | None] = {}
        for field_name in schema_fields:
            matched_col = None
            for col in df.columns:
                if _column_matches_field(col, field_name):
                    matched_col = col
                    break
            field_to_col[field_name] = matched_col

        matched_fields = {f: c for f, c in field_to_col.items() if c is not None}
        if not matched_fields:
            logger.debug("Table %d: no schema field matched — skipping.", df_idx)
            continue

        logger.debug(
            "Table %d: matched fields %s",
            df_idx, list(matched_fields.keys())
        )

        for _, row in df.iterrows():
            record: dict[str, Any] = {}
            for field_name, col in matched_fields.items():
                raw_val = row.get(col, None)
                record[field_name] = _coerce(raw_val, schema_fields[field_name])

            # Only keep rows that have at least one non-null value
            if any(v is not None for v in record.values()):
                records.append(record)

    return records


# ─── Text-based extraction ───────────────────────────────────────────────────

def _build_keyword_pattern(field_name: str) -> re.Pattern:
    """
    Build a regex that finds a schema field keyword in text and captures
    the value that follows on the same line.
    """
    tokens = re.sub(r"[^\w]", "|", field_name.lower()).strip("|")
    # Allow any of the field name tokens to appear near the value
    pattern = (
        rf"(?i)(?:{tokens})"          # field keyword
        rf"[^:\n]{{0,30}}[:=]?\s*"   # optional separator
        rf"(.{{1,80}})"               # captured value
    )
    return re.compile(pattern)


def _extract_from_text(
    text: str,
    schema_fields: dict[str, str],
) -> dict[str, Any]:
    """
    Extract field values from raw text using keyword + contextual regex.

    Returns a single record dict (first match per field).
    """
    record: dict[str, Any] = {}

    for field_name, field_type in schema_fields.items():
        pattern = _build_keyword_pattern(field_name)
        m = pattern.search(text)
        if m:
            raw_val = m.group(1).strip()
            record[field_name] = _coerce(raw_val, field_type)

    return record


# ─── Public API ──────────────────────────────────────────────────────────────

def map_to_schema(
    raw_content: RawContent,
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Map extracted raw content to the defined schema fields.

    Algorithm
    ---------
    1. Try table-based extraction first (produces multiple row records).
    2. If no table records are found, fall back to text-based extraction
       (produces a single consolidated record).
    3. Fill missing fields in table records from the text record where possible.

    Parameters
    ----------
    raw_content : RawContent
        Output of ``extractor.extract_raw()``.
    schema : dict
        Schema dict from ``schema_store.load_schema()``.

    Returns
    -------
    list[dict]
        List of records, each matching the schema field set.
        Values for fields not found are ``null``.
    """
    schema_fields: dict[str, str] = schema.get("fields", {})

    if not schema_fields:
        logger.warning("Schema for '%s' has no fields defined.", schema.get("category"))
        return []

    # Step 1: Table extraction
    table_records = _extract_from_tables(raw_content.tables, schema_fields)

    # Step 2: Text extraction (single record as fallback / supplement)
    text_record = _extract_from_text(raw_content.text, schema_fields) if raw_content.text else {}

    if table_records:
        # Fill any null fields in table records from text extraction
        enriched: list[dict[str, Any]] = []
        for rec in table_records:
            merged = {
                field: (rec.get(field) if rec.get(field) is not None
                        else text_record.get(field))
                for field in schema_fields
            }
            enriched.append(merged)
        return enriched

    # Fallback: return single text-derived record (may be sparsely populated)
    if text_record:
        # Ensure all schema fields are present (set to None if missing)
        full_record = {field: text_record.get(field) for field in schema_fields}
        return [full_record]

    logger.warning(
        "No data could be extracted for category='%s'.",
        schema.get("category"),
    )
    return []
