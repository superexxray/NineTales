"""
test_classifier.py
==================
Unit tests for the financial document classifier package.

All tests use mocks to avoid:
  - Downloading the sentence-transformers model (~80 MB)
  - Needing any real PDF / Excel files on disk
  - Requiring Tesseract or Poppler binaries

Run with:
    python -m pytest doc_classifier/tests/test_classifier.py -v
"""

from __future__ import annotations

import os
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

# ── Make sure the project root is on sys.path when running tests directly ──
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ===========================================================================
# test_text_cleaner.py
# ===========================================================================

class TestTextCleaner(unittest.TestCase):
    """Tests for doc_classifier.text_cleaner."""

    def setUp(self):
        from doc_classifier.text_cleaner import clean_text
        self.clean = clean_text

    def test_empty_string_returns_empty(self):
        self.assertEqual(self.clean(""), "")

    def test_whitespace_only_returns_empty(self):
        self.assertEqual(self.clean("   \n\t  "), "")

    def test_lowercases_output(self):
        result = self.clean("TOTAL ASSETS Rs. 500 Crore")
        self.assertEqual(result, result.lower())

    def test_removes_page_numbers(self):
        text = "Some content Page 3 of 42 more content"
        result = self.clean(text)
        self.assertNotIn("page 3 of 42", result)

    def test_collapses_whitespace(self):
        text = "hello    world\n\n\nfoo"
        result = self.clean(text)
        self.assertEqual(result, "hello world foo")

    def test_truncates_to_max_words(self):
        text = " ".join(["word"] * 600)
        result = self.clean(text, max_words=100)
        self.assertLessEqual(len(result.split()), 100)

    def test_preserves_financial_symbols(self):
        text = "Net profit margin: 12.5% EBITDA Rs.500Cr"
        result = self.clean(text)
        # % and . should survive
        self.assertIn("%", result)
        self.assertIn(".", result)

    def test_removes_separator_lines(self):
        text = "Header\n---\nContent\n===\nFooter"
        result = self.clean(text)
        self.assertNotIn("---", result)
        self.assertNotIn("===", result)


# ===========================================================================
# test_category_definitions.py
# ===========================================================================

class TestCategoryDefinitions(unittest.TestCase):
    """Tests for doc_classifier.category_definitions."""

    def setUp(self):
        from doc_classifier.category_definitions import CATEGORY_DESCRIPTIONS, CATEGORY_NAMES
        self.descriptions = CATEGORY_DESCRIPTIONS
        self.names = CATEGORY_NAMES

    def test_all_five_categories_present(self):
        expected = {
            "ALM",
            "Shareholding Pattern",
            "Borrowing Profile",
            "Annual Report",
            "Portfolio Performance",
        }
        self.assertEqual(set(self.names), expected)

    def test_descriptions_are_non_empty(self):
        for name, desc in self.descriptions.items():
            with self.subTest(category=name):
                self.assertIsInstance(desc, str)
                self.assertGreater(len(desc.strip()), 100, f"{name} description too short")

    def test_names_match_descriptions(self):
        self.assertEqual(set(self.names), set(self.descriptions.keys()))

    def test_alm_description_contains_key_terms(self):
        desc = self.descriptions["ALM"].lower()
        for term in ["liquidity", "interest rate", "gap"]:
            self.assertIn(term, desc, f"'{term}' missing from ALM description")

    def test_annual_report_description_contains_key_terms(self):
        desc = self.descriptions["Annual Report"].lower()
        for term in ["balance sheet", "profit", "cash flow"]:
            self.assertIn(term, desc, f"'{term}' missing from Annual Report description")

    def test_portfolio_description_contains_key_terms(self):
        desc = self.descriptions["Portfolio Performance"].lower()
        for term in ["nav", "aum", "return"]:
            self.assertIn(term, desc, f"'{term}' missing from Portfolio Performance description")


# ===========================================================================
# test_embedder.py
# ===========================================================================

class TestDocumentEmbedder(unittest.TestCase):
    """Tests for doc_classifier.embedder (model calls are mocked)."""

    def _make_embedder(self, dim: int = 384):
        """Return a DocumentEmbedder with a mocked SentenceTransformer."""
        with patch("doc_classifier.embedder.SentenceTransformer") as MockST:
            instance = MockST.return_value
            instance.get_sentence_embedding_dimension.return_value = dim

            def fake_encode(texts, **kwargs):
                n = len(texts)
                vecs = np.random.randn(n, dim).astype(np.float32)
                # Normalise each row
                norms = np.linalg.norm(vecs, axis=1, keepdims=True)
                return vecs / norms

            instance.encode.side_effect = fake_encode

            from doc_classifier.embedder import DocumentEmbedder
            embedder = DocumentEmbedder.__new__(DocumentEmbedder)
            embedder.model = instance
            embedder.embedding_dim = dim
        return embedder

    def test_embed_texts_returns_correct_shape(self):
        embedder = self._make_embedder(dim=384)
        texts = ["hello world", "financial report"]
        result = embedder.embed_texts(texts)
        self.assertEqual(result.shape, (2, 384))

    def test_embed_texts_raises_on_empty_list(self):
        embedder = self._make_embedder()
        with self.assertRaises(ValueError):
            embedder.embed_texts([])

    def test_embed_document_returns_1d_vector(self):
        embedder = self._make_embedder(dim=384)
        result = embedder.embed_document("some cleaned financial text about balance sheet")
        self.assertEqual(result.shape, (384,))

    def test_embed_document_empty_text_returns_zero_vector(self):
        embedder = self._make_embedder(dim=384)
        result = embedder.embed_document("")
        self.assertTrue(np.all(result == 0))

    def test_chunk_text_logic(self):
        from doc_classifier.embedder import _chunk_text
        words = ["word"] * 500
        text = " ".join(words)
        chunks = _chunk_text(text, chunk_size=200, overlap=40)
        self.assertGreater(len(chunks), 1)
        # Each chunk should not exceed chunk_size words
        for chunk in chunks:
            self.assertLessEqual(len(chunk.split()), 200)

    def test_chunk_text_short_text_single_chunk(self):
        from doc_classifier.embedder import _chunk_text
        text = "This is a short text."
        chunks = _chunk_text(text, chunk_size=200)
        self.assertEqual(len(chunks), 1)


# ===========================================================================
# test_classifier.py
# ===========================================================================

class TestDocumentClassifier(unittest.TestCase):
    """Tests for doc_classifier.classifier (embedder is mocked)."""

    DIM = 384
    NUM_CATS = 5

    def _make_classifier(self):
        """Build a DocumentClassifier with a deterministic fake embedder."""
        from doc_classifier.category_definitions import CATEGORY_NAMES
        from doc_classifier.classifier import DocumentClassifier

        mock_embedder = MagicMock()
        mock_embedder.embedding_dim = self.DIM

        # Category embeddings: identity-like orthogonal-ish matrix
        cat_embeddings = np.eye(self.NUM_CATS, self.DIM, dtype=np.float32)

        def fake_embed_texts(texts):
            return cat_embeddings[: len(texts)]

        mock_embedder.embed_texts.side_effect = fake_embed_texts

        clf = DocumentClassifier.__new__(DocumentClassifier)
        clf.embedder = mock_embedder
        clf._category_names = CATEGORY_NAMES
        clf._category_embeddings = cat_embeddings
        return clf

    def test_classify_returns_expected_keys(self):
        clf = self._make_classifier()

        # Embed document returns a unit vector toward first category
        clf.embedder.embed_document = MagicMock(
            return_value=np.eye(self.NUM_CATS, self.DIM, dtype=np.float32)[0]
        )
        result = clf.classify("some text", filename="test.pdf")
        self.assertIn("filename", result.to_dict())
        self.assertIn("predicted_category", result.to_dict())
        self.assertIn("confidence", result.to_dict())

    def test_classify_selects_highest_similarity_category(self):
        from doc_classifier.category_definitions import CATEGORY_NAMES
        clf = self._make_classifier()

        # Make doc embedding point toward the 3rd category ("Borrowing Profile")
        target_idx = 2  # "Borrowing Profile"
        doc_vec = np.zeros(self.DIM, dtype=np.float32)
        doc_vec[target_idx] = 1.0
        clf.embedder.embed_document = MagicMock(return_value=doc_vec)

        result = clf.classify("debt maturity profile term loans", filename="borrow.pdf")
        self.assertEqual(result.predicted_category, CATEGORY_NAMES[target_idx])

    def test_classify_confidence_between_0_and_1(self):
        clf = self._make_classifier()
        doc_vec = np.random.randn(self.DIM).astype(np.float32)
        doc_vec /= np.linalg.norm(doc_vec)
        clf.embedder.embed_document = MagicMock(return_value=doc_vec)

        result = clf.classify("some financial text", filename="report.pdf")
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_all_scores_sum_to_one(self):
        clf = self._make_classifier()
        doc_vec = np.random.randn(self.DIM).astype(np.float32)
        doc_vec /= np.linalg.norm(doc_vec)
        clf.embedder.embed_document = MagicMock(return_value=doc_vec)

        result = clf.classify("text", filename="f.pdf")
        total = sum(result.all_scores.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_empty_text_returns_unknown(self):
        clf = self._make_classifier()
        result = clf.classify("", filename="empty.pdf")
        self.assertEqual(result.predicted_category, "Unknown")
        self.assertEqual(result.confidence, 0.0)

    def test_to_dict_excludes_all_scores(self):
        clf = self._make_classifier()
        doc_vec = np.zeros(self.DIM, dtype=np.float32)
        doc_vec[0] = 1.0
        clf.embedder.embed_document = MagicMock(return_value=doc_vec)
        result = clf.classify("text", filename="f.pdf")
        self.assertNotIn("category_scores", result.to_dict())

    def test_to_dict_full_includes_all_scores(self):
        clf = self._make_classifier()
        doc_vec = np.zeros(self.DIM, dtype=np.float32)
        doc_vec[0] = 1.0
        clf.embedder.embed_document = MagicMock(return_value=doc_vec)
        result = clf.classify("text", filename="f.pdf")
        self.assertIn("category_scores", result.to_dict_full())
        self.assertEqual(len(result.to_dict_full()["category_scores"]), self.NUM_CATS)


# ===========================================================================
# test_pipeline.py
# ===========================================================================

class TestPipeline(unittest.TestCase):
    """Integration-style tests for doc_classifier.pipeline (all IO mocked)."""

    def setUp(self):
        """Reset the classifier singleton before each test."""
        from doc_classifier import pipeline
        pipeline._classifier = None

    @patch("doc_classifier.pipeline.load_document")
    @patch("doc_classifier.pipeline.DocumentClassifier")
    @patch("doc_classifier.pipeline.create_metadata")
    def test_classify_document_returns_correct_schema(self, mock_create_meta, MockClf, mock_load):
        mock_load.return_value = "net interest margin liquidity coverage ratio repricing"

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "filename": "alm_report.pdf",
            "predicted_category": "ALM",
            "confidence": 0.89,
        }
        MockClf.return_value.classify.return_value = mock_result

        # create_metadata returns the full metadata schema
        mock_create_meta.return_value = {
            "document_id": "test-uuid",
            "filename": "alm_report.pdf",
            "model_prediction": "ALM",
            "confidence": 0.89,
            "final_category": None,
            "status": "awaiting_review",
        }

        from doc_classifier.pipeline import classify_document
        result = classify_document("alm_report.pdf")

        self.assertEqual(result["filename"], "alm_report.pdf")
        self.assertEqual(result["model_prediction"], "ALM")
        self.assertAlmostEqual(result["confidence"], 0.89)
        self.assertEqual(result["status"], "awaiting_review")
        self.assertIn("document_id", result)

    @patch("doc_classifier.pipeline.load_document")
    @patch("doc_classifier.pipeline.DocumentClassifier")
    @patch("doc_classifier.pipeline.create_metadata")
    def test_empty_document_returns_unknown(self, mock_create_meta, MockClf, mock_load):
        mock_load.return_value = "   "   # all whitespace

        mock_create_meta.return_value = {
            "document_id": "test-uuid",
            "filename": "blank.pdf",
            "model_prediction": "Unknown",
            "confidence": 0.0,
            "final_category": None,
            "status": "awaiting_review",
        }

        from doc_classifier.pipeline import classify_document
        result = classify_document("blank.pdf")

        self.assertEqual(result["model_prediction"], "Unknown")
        self.assertEqual(result["confidence"], 0.0)

    @patch("doc_classifier.pipeline.load_document")
    @patch("doc_classifier.pipeline.DocumentClassifier")
    def test_return_full_scores_flag(self, MockClf, mock_load):
        mock_load.return_value = "promoter holdings FII DII shareholding pattern"

        mock_result = MagicMock()
        mock_result.to_dict_full.return_value = {
            "filename": "shp.pdf",
            "predicted_category": "Shareholding Pattern",
            "confidence": 0.91,
            "category_scores": {
                "ALM": 0.05,
                "Shareholding Pattern": 0.91,
                "Borrowing Profile": 0.02,
                "Annual Report": 0.01,
                "Portfolio Performance": 0.01,
            },
        }
        MockClf.return_value.classify.return_value = mock_result

        from doc_classifier.pipeline import classify_document
        result = classify_document("shp.pdf", return_full_scores=True)

        self.assertIn("category_scores", result)
        self.assertEqual(len(result["category_scores"]), 5)

    @patch("doc_classifier.pipeline.load_document")
    def test_load_error_propagates(self, mock_load):
        mock_load.side_effect = FileNotFoundError("no such file")

        from doc_classifier.pipeline import classify_document
        with self.assertRaises(FileNotFoundError):
            classify_document("nonexistent.pdf")


# ===========================================================================
# test_document_loader.py  (IO mocked)
# ===========================================================================

class TestDocumentLoader(unittest.TestCase):
    """Tests for doc_classifier.document_loader dispatching logic."""

    def test_unsupported_extension_raises_value_error(self):
        from doc_classifier.document_loader import load_document
        with self.assertRaises(ValueError, msg="Should raise for .docx"):
            load_document("report.docx")

    @patch("doc_classifier.document_loader.os.path.isfile", return_value=False)
    def test_missing_pdf_raises_file_not_found(self, _):
        from doc_classifier.document_loader import extract_from_pdf
        with self.assertRaises(FileNotFoundError):
            extract_from_pdf("nonexistent.pdf")

    @patch("doc_classifier.document_loader.os.path.isfile", return_value=False)
    def test_missing_excel_raises_file_not_found(self, _):
        from doc_classifier.document_loader import extract_from_excel
        with self.assertRaises(FileNotFoundError):
            extract_from_excel("nonexistent.xlsx")

    @patch("doc_classifier.document_loader.os.path.isfile", return_value=True)
    @patch("doc_classifier.document_loader.pdfplumber.open")
    def test_pdf_native_text_used_when_sufficient(self, mock_pdf_open, _):
        """Should use native pdfplumber text when >= OCR_FALLBACK_THRESHOLD chars."""
        from doc_classifier.document_loader import extract_from_pdf

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "A" * 100   # 100 chars > 20 threshold
        mock_pdf_open.return_value.__enter__.return_value.pages = [mock_page]

        result = extract_from_pdf("fake.pdf")
        self.assertIn("A" * 100, result)

    @patch("doc_classifier.document_loader.os.path.isfile", return_value=True)
    @patch("doc_classifier.document_loader.pd.read_excel")
    def test_excel_reads_all_sheets(self, mock_read_excel, _):
        import pandas as pd
        from doc_classifier.document_loader import extract_from_excel

        mock_read_excel.return_value = {
            "Sheet1": pd.DataFrame({"col1": ["ALM report"], "col2": ["liquidity"]}),
            "Sheet2": pd.DataFrame({"col1": ["shareholding"], "col2": ["promoter"]}),
        }

        result = extract_from_excel("fake.xlsx")
        self.assertIn("Sheet1", result)
        self.assertIn("Sheet2", result)
        self.assertIn("alm report", result.lower())


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
