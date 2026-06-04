"""
extractor.py
============
Raw content extraction layer for the extraction pipeline.

Responsibilities
----------------
* Extract text (reuses document_loader strategies).
* Extract tables from PDFs (pdfplumber) and Excel files (pandas).
* Return a unified intermediate representation used by schema_mapper.

This module is intentionally stateless — all functions are pure transformations
with no side effects beyond reading the source file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber

logger = logging.getLogger(__name__)

# Minimum number of rows a table must have (header + data) to be kept
MIN_TABLE_ROWS: int = 2

# PDF extensions dispatched to pdfplumber
PDF_EXTENSIONS = {".pdf"}
EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb", ".ods", ".csv"}


# ---------------------------------------------------------------------------
# Intermediate representation
# ---------------------------------------------------------------------------

@dataclass
class RawContent:
    """
    Unified intermediate representation of raw document content.

    Attributes
    ----------
    text : str
        All textual content concatenated from pages / sheets.
    tables : list[pd.DataFrame]
        List of DataFrames extracted from tables in the document.
        Column headers are normalised (lowercase, underscores, stripped).
    source_path : str
        Original file path (for diagnostics).
    """
    text: str = ""
    tables: list[pd.DataFrame] = field(default_factory=list)
    source_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise (text + table summaries) for logging/debugging."""
        return {
            "source_path": self.source_path,
            "text_length": len(self.text),
            "num_tables": len(self.tables),
            "table_shapes": [list(t.shape) for t in self.tables],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise DataFrame column names.
    Strips whitespace, lowercases, replaces spaces/special chars with underscores.
    """
    df = df.copy()
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")
        for c in df.columns
    ]
    return df


def _table_to_df(raw_table: list[list[Any]]) -> pd.DataFrame | None:
    """
    Convert a pdfplumber raw table (list of lists) into a normalised DataFrame.
    Returns None if the table is empty or has fewer rows than MIN_TABLE_ROWS.
    """
    if not raw_table or len(raw_table) < MIN_TABLE_ROWS:
        return None

    # Assume first row is the header
    headers = [str(c).strip() if c else f"col_{i}" for i, c in enumerate(raw_table[0])]
    rows = raw_table[1:]

    # Guard: skip if no data rows
    if not rows:
        return None

    try:
        df = pd.DataFrame(rows, columns=headers)
        df = df.fillna("").map(lambda x: str(x).strip())
        df = _normalise_columns(df)
        return df
    except Exception as exc:
        logger.warning("Skipping malformed pdfplumber table: %s", exc)
        return None


def _infer_engine(ext: str) -> str | None:
    mapping = {
        ".xlsx": "openpyxl",
        ".xlsm": "openpyxl",
        ".xlsb": "pyxlsb",
        ".xls":  "xlrd",
        ".ods":  "odf",
    }
    return mapping.get(ext)


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def _extract_pdf(filepath: str) -> RawContent:
    """Extract text and tables from a PDF using pdfplumber."""
    page_texts: list[str] = []
    all_tables: list[pd.DataFrame] = []

    try:
        with pdfplumber.open(filepath) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                # --- Text ---
                text = page.extract_text() or ""
                if text.strip():
                    page_texts.append(text)

                # --- Tables ---
                try:
                    raw_tables = page.extract_tables() or []
                    for raw_table in raw_tables:
                        df = _table_to_df(raw_table)
                        if df is not None and not df.empty:
                            all_tables.append(df)
                            logger.debug(
                                "Page %d: extracted table with shape %s",
                                page_idx + 1, df.shape
                            )
                except Exception as exc:
                    logger.warning("Table extraction failed on page %d: %s", page_idx + 1, exc)

    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{filepath}': {exc}") from exc

    combined_text = "\n".join(page_texts)
    logger.info(
        "PDF '%s': %d chars text, %d tables extracted.",
        Path(filepath).name, len(combined_text), len(all_tables)
    )
    return RawContent(text=combined_text, tables=all_tables, source_path=filepath)


# ---------------------------------------------------------------------------
# Excel extraction
# ---------------------------------------------------------------------------

def _df_to_string(df: pd.DataFrame) -> str:
    """Convert a DataFrame to a plain-text representation."""
    header = " ".join(str(c) for c in df.columns)
    rows = df.fillna("").apply(
        lambda row: " ".join(str(v) for v in row if str(v).strip()),
        axis=1,
    )
    return header + "\n" + "\n".join(rows.tolist())


def _extract_excel(filepath: str) -> RawContent:
    """Extract text and structured DataFrames from an Excel / CSV file."""
    ext = Path(filepath).suffix.lower()
    all_texts: list[str] = []
    all_tables: list[pd.DataFrame] = []

    try:
        if ext == ".csv":
            df = pd.read_csv(filepath, dtype=str, on_bad_lines="skip")
            df = _normalise_columns(df.fillna(""))
            all_texts.append(_df_to_string(df))
            all_tables.append(df)
        else:
            sheets: dict[str, pd.DataFrame] = pd.read_excel(
                filepath,
                sheet_name=None,
                dtype=str,
                engine=_infer_engine(ext),
            )
            for sheet_name, df in sheets.items():
                df = _normalise_columns(df.fillna(""))
                all_texts.append(f"[Sheet: {sheet_name}]")
                all_texts.append(_df_to_string(df))
                if not df.empty:
                    all_tables.append(df)

    except Exception as exc:
        raise ValueError(f"Cannot read Excel file '{filepath}': {exc}") from exc

    combined_text = "\n".join(all_texts)
    logger.info(
        "Excel '%s': %d chars text, %d sheets as tables.",
        Path(filepath).name, len(combined_text), len(all_tables)
    )
    return RawContent(text=combined_text, tables=all_tables, source_path=filepath)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_raw(filepath: str) -> RawContent:
    """
    Extract all text and tables from a financial document.

    Dispatches to the appropriate extractor based on file extension.

    Parameters
    ----------
    filepath : str
        Absolute path to the document (PDF, Excel, or CSV).

    Returns
    -------
    RawContent
        Unified intermediate representation with ``.text`` and ``.tables``.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file type is unsupported or cannot be parsed.
    """
    ext = Path(filepath).suffix.lower()

    if ext not in PDF_EXTENSIONS and ext not in EXCEL_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {sorted(PDF_EXTENSIONS | EXCEL_EXTENSIONS)}"
        )

    if not Path(filepath).is_file():
        raise FileNotFoundError(f"Document not found: '{filepath}'")

    if ext in PDF_EXTENSIONS:
        return _extract_pdf(filepath)
    else:
        return _extract_excel(filepath)
