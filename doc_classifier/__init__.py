"""
doc_classifier
==============
Financial document classification package.

Public API
----------
>>> from doc_classifier.pipeline import classify_document
>>> result = classify_document("path/to/file.pdf")
"""

from pipeline import classify_document

__all__ = ["classify_document"]
