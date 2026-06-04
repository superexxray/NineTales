"""
text_cleaner.py
===============
Utilities to normalize raw text extracted from financial documents
before it is passed to the embedding model.
"""

import re
import unicodedata


# Max words to keep.  all-MiniLM-L6-v2 has a 256-token limit (≈ 300 words)
# but we embed a description that may be long; for *document* text we allow
# more context by splitting into chunks (handled in the embedder).
MAX_WORDS: int = 512


def _normalize_unicode(text: str) -> str:
    """Normalize unicode characters to their ASCII equivalents where possible."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _remove_boilerplate(text: str) -> str:
    """Strip common PDF artefacts: page headers/footers, form-feed characters."""
    # Remove form-feed / vertical tab characters
    text = re.sub(r"[\x0c\x0b]", "\n", text)
    # Remove isolated page numbers (e.g. "Page 3 of 42", "3 | 42", "- 3 -")
    text = re.sub(r"(?i)\bpage\s+\d+\s+(of\s+\d+)?\b", "", text)
    text = re.sub(r"\b\d+\s*\|\s*\d+\b", "", text)
    text = re.sub(r"(?m)^\s*[-–]\s*\d+\s*[-–]\s*$", "", text)
    # Strip lines that are purely dashes / underscores (table separators)
    text = re.sub(r"(?m)^[\-_=|]{3,}\s*$", "", text)
    return text


def _collapse_whitespace(text: str) -> str:
    """Replace multiple whitespace/newlines with a single space."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _remove_special_chars(text: str) -> str:
    """Keep alphanumerics, basic punctuation, and financial symbols."""
    # Allow: letters, digits, whitespace, . , % ( ) / - : ; ' " &
    text = re.sub(r"[^\w\s.,%()\-/:;'\"&@#₹$€£]", " ", text)
    return text


def clean_text(raw_text: str, max_words: int = MAX_WORDS) -> str:
    """
    Full cleaning pipeline for a raw text blob.

    Steps
    -----
    1. Unicode normalisation
    2. Remove common PDF boilerplate (page numbers, separator lines)
    3. Strip non-essential special characters
    4. Collapse whitespace
    5. Truncate to *max_words* words

    Parameters
    ----------
    raw_text : str
        Unprocessed text from a document loader.
    max_words : int
        Maximum number of words to keep (excess is dropped).

    Returns
    -------
    str
        Cleaned, truncated text ready for embedding.
    """
    if not raw_text or not raw_text.strip():
        return ""

    text = _normalize_unicode(raw_text)
    text = _remove_boilerplate(text)
    text = _remove_special_chars(text)
    text = _collapse_whitespace(text)

    # Truncate
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])

    return text.lower()
