"""
document_loader.py
==================
Extracts raw text from PDF and Excel financial documents.

PDF strategy
------------
1. Try pdfplumber (native text layer) for each page.
2. If a page yields fewer than OCR_FALLBACK_THRESHOLD characters,
   convert that page to an image with pdf2image and run pytesseract OCR.
3. Combine all page texts.

Excel strategy
--------------
Read every sheet with pandas; stringify all cell values and concatenate.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)

# If a PDF page yields fewer than this many characters from pdfplumber,
# fall back to OCR for that page.
OCR_FALLBACK_THRESHOLD: int = 20

# Supported extensions
PDF_EXTENSIONS = {".pdf"}
EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb", ".ods", ".csv"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ocr_page(image: Image.Image) -> str:
    """Run Tesseract OCR on a single PIL Image and return extracted text."""
    try:
        return pytesseract.image_to_string(image, lang="eng")
    except pytesseract.TesseractNotFoundError:
        logger.error(
            "Tesseract is not installed or not found on PATH. "
            "Install it from https://github.com/UB-Mannheim/tesseract/wiki"
        )
        return ""
    except Exception as exc:
        logger.warning("OCR failed for a page: %s", exc)
        return ""


def _extract_pdf_page_text(
    page: "pdfplumber.page.Page",
    pdf_path: str,
    page_index: int,
) -> str:
    """
    Extract text from one PDF page.
    Falls back to OCR if native text is too sparse.
    """
    native_text: str = page.extract_text() or ""

    if len(native_text.strip()) >= OCR_FALLBACK_THRESHOLD:
        return native_text

    # --- OCR fallback ---
    logger.debug(
        "Page %d of '%s' has only %d native chars — using OCR.",
        page_index + 1,
        pdf_path,
        len(native_text.strip()),
    )
    try:
        images = convert_from_path(
            pdf_path,
            first_page=page_index + 1,
            last_page=page_index + 1,
            dpi=200,
        )
        if images:
            return _ocr_page(images[0])
    except Exception as exc:
        logger.warning(
            "pdf2image conversion failed for page %d of '%s': %s",
            page_index + 1,
            pdf_path,
            exc,
        )

    # If both methods fail, return whatever native text we got (may be empty)
    return native_text


def extract_from_pdf(filepath: str) -> str:
    """
    Extract all text from a PDF file.

    Parameters
    ----------
    filepath : str
        Absolute or relative path to the PDF file.

    Returns
    -------
    str
        Concatenated raw text from all pages.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file cannot be opened as a PDF.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    page_texts: list[str] = []

    try:
        with pdfplumber.open(filepath) as pdf:
            for idx, page in enumerate(pdf.pages):
                text = _extract_pdf_page_text(page, filepath, idx)
                if text:
                    page_texts.append(text)
    except Exception as exc:
        raise ValueError(f"Failed to open PDF '{filepath}': {exc}") from exc

    combined = "\n".join(page_texts)
    logger.info(
        "Extracted %d characters from PDF '%s' (%d pages).",
        len(combined),
        filepath,
        len(page_texts),
    )
    return combined


def extract_from_excel(filepath: str) -> str:
    """
    Extract all text from an Excel (or CSV) file.

    Reads every sheet; converts all cell values to strings and joins them.

    Parameters
    ----------
    filepath : str
        Absolute or relative path to the Excel/CSV file.

    Returns
    -------
    str
        Concatenated string representation of all cell values across all sheets.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file cannot be read by pandas.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = Path(filepath).suffix.lower()
    all_texts: list[str] = []

    try:
        if ext == ".csv":
            df = pd.read_csv(filepath, dtype=str, on_bad_lines="skip")
            all_texts.append(_df_to_text(df))
        else:
            sheets: dict[str, pd.DataFrame] = pd.read_excel(
                filepath,
                sheet_name=None,   # read all sheets
                dtype=str,
                engine=_infer_engine(ext),
            )
            for sheet_name, df in sheets.items():
                logger.debug("Processing sheet: %s", sheet_name)
                all_texts.append(f"[Sheet: {sheet_name}]")
                all_texts.append(_df_to_text(df))
    except Exception as exc:
        raise ValueError(f"Failed to read Excel file '{filepath}': {exc}") from exc

    combined = "\n".join(all_texts)
    logger.info(
        "Extracted %d characters from Excel file '%s'.",
        len(combined),
        filepath,
    )
    return combined


def _df_to_text(df: pd.DataFrame) -> str:
    """Convert a DataFrame to a single text string of all cell contents."""
    # Include column headers + all rows
    header = " ".join(str(c) for c in df.columns)
    rows = df.fillna("").apply(
        lambda row: " ".join(str(v) for v in row if str(v).strip()),
        axis=1,
    )
    return header + "\n" + "\n".join(rows.tolist())


def _infer_engine(ext: str) -> Optional[str]:
    """Return the appropriate pandas Excel engine for the file extension."""
    mapping = {
        ".xlsx": "openpyxl",
        ".xlsm": "openpyxl",
        ".xlsb": "pyxlsb",
        ".xls": "xlrd",
        ".ods": "odf",
    }
    return mapping.get(ext)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_document(filepath: str) -> str:
    """
    Load a document and return its raw extracted text.

    Dispatches to the appropriate extractor based on file extension.

    Parameters
    ----------
    filepath : str
        Path to the PDF, Excel, or CSV file.

    Returns
    -------
    str
        Raw text extracted from the document.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file type is not supported or cannot be read.
    """
    ext = Path(filepath).suffix.lower()

    if ext in PDF_EXTENSIONS:
        return extract_from_pdf(filepath)
    elif ext in EXCEL_EXTENSIONS:
        return extract_from_excel(filepath)
    else:
        raise ValueError(
            f"Unsupported file type: '{ext}'. "
            f"Supported types: PDF {sorted(PDF_EXTENSIONS)}, "
            f"Excel/CSV {sorted(EXCEL_EXTENSIONS)}"
        )
