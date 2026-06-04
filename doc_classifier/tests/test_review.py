"""
test_review.py
==============
Unit tests for the human-in-the-loop review mechanism.

Covers:
  - metadata_store: create, load, apply_review, list_metadata
  - api endpoints: POST /review, GET /metadata/{id}, GET /metadata

All tests use temporary directories (no real disk state persists between runs).
API tests use the FastAPI TestClient — no uvicorn process needed.

Run with:
    python -m pytest doc_classifier/tests/test_review.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Project root on sys.path ────────────────────────────────────────────────
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ===========================================================================
# TestMetadataStore
# ===========================================================================

class TestMetadataStore(unittest.TestCase):
    """Tests for doc_classifier.metadata_store."""

    def setUp(self):
        """Each test gets its own isolated temp directory."""
        self.tmp_dir = tempfile.mkdtemp()
        from doc_classifier import metadata_store
        self.store = metadata_store

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create(
        self,
        filename: str = "report.pdf",
        prediction: str = "Annual Report",
        confidence: float = 0.87,
    ) -> dict:
        return self.store.create_metadata(
            filename=filename,
            model_prediction=prediction,
            confidence=confidence,
            store_dir=self.tmp_dir,
        )

    # --- create_metadata ---

    def test_create_returns_correct_keys(self):
        meta = self._create()
        for key in ("document_id", "filename", "model_prediction",
                    "confidence", "final_category", "status"):
            self.assertIn(key, meta)

    def test_create_initial_status_awaiting(self):
        meta = self._create()
        self.assertEqual(meta["status"], "awaiting_review")

    def test_create_final_category_is_null(self):
        meta = self._create()
        self.assertIsNone(meta["final_category"])

    def test_create_model_prediction_preserved(self):
        meta = self._create(prediction="ALM")
        self.assertEqual(meta["model_prediction"], "ALM")

    def test_create_persists_json_file(self):
        meta = self._create()
        doc_id = meta["document_id"]
        json_path = Path(self.tmp_dir) / f"{doc_id}.json"
        self.assertTrue(json_path.exists(), "JSON file should exist on disk")

    def test_create_generates_unique_ids(self):
        ids = {self._create()["document_id"] for _ in range(5)}
        self.assertEqual(len(ids), 5, "All document_ids should be unique")

    def test_confidence_is_rounded(self):
        meta = self._create(confidence=0.123456789)
        self.assertLessEqual(len(str(meta["confidence"]).split(".")[-1]), 4)

    # --- load_metadata ---

    def test_load_returns_persisted_record(self):
        meta = self._create(filename="test.pdf", prediction="ALM")
        loaded = self.store.load_metadata(meta["document_id"], store_dir=self.tmp_dir)
        self.assertEqual(loaded["document_id"], meta["document_id"])
        self.assertEqual(loaded["model_prediction"], "ALM")

    def test_load_raises_for_missing_id(self):
        with self.assertRaises(FileNotFoundError):
            self.store.load_metadata("non-existent-uuid", store_dir=self.tmp_dir)

    def test_load_raises_for_corrupt_json(self):
        meta = self._create()
        corrupt_path = Path(self.tmp_dir) / f"{meta['document_id']}.json"
        corrupt_path.write_text("{{not valid json{{", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.load_metadata(meta["document_id"], store_dir=self.tmp_dir)

    # --- apply_review: approved ---

    def test_review_approved_when_category_matches_prediction(self):
        meta = self._create(prediction="Annual Report")
        updated = self.store.apply_review(
            meta["document_id"], "Annual Report", store_dir=self.tmp_dir
        )
        self.assertEqual(updated["status"], "approved")
        self.assertEqual(updated["final_category"], "Annual Report")

    def test_review_corrected_when_category_differs(self):
        meta = self._create(prediction="ALM")
        updated = self.store.apply_review(
            meta["document_id"], "Borrowing Profile", store_dir=self.tmp_dir
        )
        self.assertEqual(updated["status"], "corrected_by_user")
        self.assertEqual(updated["final_category"], "Borrowing Profile")

    def test_review_does_not_overwrite_model_prediction(self):
        meta = self._create(prediction="ALM")
        updated = self.store.apply_review(
            meta["document_id"], "Borrowing Profile", store_dir=self.tmp_dir
        )
        self.assertEqual(updated["model_prediction"], "ALM",
                         "model_prediction must never be overwritten")

    def test_review_persists_changes_to_disk(self):
        meta = self._create(prediction="ALM")
        doc_id = meta["document_id"]
        self.store.apply_review(doc_id, "Portfolio Performance", store_dir=self.tmp_dir)
        # Re-load from disk to confirm persistence
        reloaded = self.store.load_metadata(doc_id, store_dir=self.tmp_dir)
        self.assertEqual(reloaded["final_category"], "Portfolio Performance")
        self.assertEqual(reloaded["status"], "corrected_by_user")

    def test_review_raises_for_invalid_category(self):
        meta = self._create()
        with self.assertRaises(ValueError):
            self.store.apply_review(
                meta["document_id"], "NonExistentCategory", store_dir=self.tmp_dir
            )

    def test_review_raises_for_missing_document(self):
        with self.assertRaises(FileNotFoundError):
            self.store.apply_review(
                "ghost-uuid", "ALM", store_dir=self.tmp_dir
            )

    # --- list_metadata ---

    def test_list_returns_all_records(self):
        for i in range(3):
            self._create(filename=f"doc{i}.pdf")
        records = self.store.list_metadata(store_dir=self.tmp_dir)
        self.assertEqual(len(records), 3)

    def test_list_status_filter_awaiting(self):
        m1 = self._create(prediction="ALM")
        m2 = self._create(prediction="Annual Report")
        # Approve one
        self.store.apply_review(m1["document_id"], "ALM", store_dir=self.tmp_dir)

        awaiting = self.store.list_metadata(
            store_dir=self.tmp_dir, status_filter="awaiting_review"
        )
        approved = self.store.list_metadata(
            store_dir=self.tmp_dir, status_filter="approved"
        )
        self.assertEqual(len(awaiting), 1)
        self.assertEqual(len(approved), 1)
        self.assertEqual(awaiting[0]["document_id"], m2["document_id"])

    def test_list_empty_store_returns_empty_list(self):
        records = self.store.list_metadata(store_dir=self.tmp_dir)
        self.assertEqual(records, [])


# ===========================================================================
# TestAPIEndpoints
# ===========================================================================

class TestAPIEndpoints(unittest.TestCase):
    """
    Tests for doc_classifier.api using FastAPI TestClient.

    All file I/O and classification calls are mocked.
    """

    def setUp(self):
        """Each test gets a temp store dir and a fresh TestClient."""
        self.tmp_dir = tempfile.mkdtemp()

        # We patch the STORE_DIR used by the api module before importing
        import doc_classifier.api as api_module
        api_module.STORE_DIR = self.tmp_dir

        from fastapi.testclient import TestClient
        self.client = TestClient(api_module.app)
        self.api_module = api_module

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # --- POST /review ---

    def _seed_metadata(self, prediction: str = "ALM") -> str:
        """Directly create a metadata record and return its document_id."""
        from doc_classifier.metadata_store import create_metadata
        meta = create_metadata(
            filename="test.pdf",
            model_prediction=prediction,
            confidence=0.90,
            store_dir=self.tmp_dir,
        )
        return meta["document_id"]

    def test_review_approved(self):
        doc_id = self._seed_metadata(prediction="ALM")
        response = self.client.post(
            "/review",
            json={"document_id": doc_id, "final_category": "ALM"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "approved")
        self.assertEqual(data["final_category"], "ALM")
        self.assertEqual(data["model_prediction"], "ALM")

    def test_review_corrected(self):
        doc_id = self._seed_metadata(prediction="ALM")
        response = self.client.post(
            "/review",
            json={"document_id": doc_id, "final_category": "Borrowing Profile"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "corrected_by_user")

    def test_review_invalid_category_returns_422(self):
        doc_id = self._seed_metadata()
        response = self.client.post(
            "/review",
            json={"document_id": doc_id, "final_category": "Not A Real Category"},
        )
        self.assertEqual(response.status_code, 422)

    def test_review_missing_document_returns_404(self):
        response = self.client.post(
            "/review",
            json={"document_id": "ghost-uuid", "final_category": "ALM"},
        )
        self.assertEqual(response.status_code, 404)

    def test_review_does_not_mutate_model_prediction(self):
        doc_id = self._seed_metadata(prediction="Annual Report")
        self.client.post(
            "/review",
            json={"document_id": doc_id, "final_category": "ALM"},
        )
        # Reload and check
        get_resp = self.client.get(f"/metadata/{doc_id}")
        self.assertEqual(get_resp.json()["model_prediction"], "Annual Report")

    # --- GET /metadata/{document_id} ---

    def test_get_metadata_returns_record(self):
        doc_id = self._seed_metadata(prediction="Portfolio Performance")
        response = self.client.get(f"/metadata/{doc_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["document_id"], doc_id)
        self.assertEqual(data["model_prediction"], "Portfolio Performance")

    def test_get_metadata_missing_id_returns_404(self):
        response = self.client.get("/metadata/does-not-exist")
        self.assertEqual(response.status_code, 404)

    # --- GET /metadata ---

    def test_list_all_metadata(self):
        for pred in ["ALM", "Annual Report", "Borrowing Profile"]:
            self._seed_metadata(prediction=pred)
        response = self.client.get("/metadata")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)

    def test_list_with_status_filter(self):
        doc_id1 = self._seed_metadata(prediction="ALM")
        self._seed_metadata(prediction="Annual Report")

        # Approve doc1
        self.client.post(
            "/review",
            json={"document_id": doc_id1, "final_category": "ALM"},
        )

        approved = self.client.get("/metadata?status=approved").json()
        awaiting = self.client.get("/metadata?status=awaiting_review").json()
        self.assertEqual(len(approved), 1)
        self.assertEqual(len(awaiting), 1)

    def test_list_invalid_status_returns_422(self):
        response = self.client.get("/metadata?status=invalid_status")
        self.assertEqual(response.status_code, 422)

    # --- GET /health ---

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
