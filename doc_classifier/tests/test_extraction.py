"""
test_extraction.py
==================
Unit tests for the dynamic schema and extraction pipeline extension.

Covers:
  - schema_store: save, load, delete, list, default schemas, validation
  - extractor:    table normalisation, RawContent dataclass, dispatch
  - schema_mapper: table matching, text matching, type coercion, full mapping
  - extraction_pipeline: status gate, run_extraction end-to-end (mocked IO)
  - api (new endpoints): /schemas, /extract, /extractions

All tests are fully mocked — no real files, model downloads, or network
needed.

Run with:
    python -m pytest doc_classifier/tests/test_extraction.py -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ===========================================================================
# TestSchemaStore
# ===========================================================================

class TestSchemaStore(unittest.TestCase):
    """Tests for doc_classifier.schema_store."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from doc_classifier import schema_store
        self.store = schema_store

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _valid_schema(self, category: str = "Borrowing Profile") -> dict:
        return {
            "category": category,
            "fields": {
                "lender_name":  "string",
                "loan_amount":  "number",
                "interest_rate": "number",
            },
        }

    # --- save / load ---

    def test_save_and_load_roundtrip(self):
        schema = self._valid_schema()
        self.store.save_schema(schema, schema_dir=self.tmp)
        loaded = self.store.load_schema("Borrowing Profile", schema_dir=self.tmp)
        self.assertEqual(loaded["category"], "Borrowing Profile")
        self.assertIn("lender_name", loaded["fields"])

    def test_save_creates_json_file(self):
        schema = self._valid_schema()
        self.store.save_schema(schema, schema_dir=self.tmp)
        files = list(Path(self.tmp).glob("*.json"))
        self.assertEqual(len(files), 1)

    def test_save_invalid_field_type_raises(self):
        schema = {"category": "ALM", "fields": {"gap": "integer"}}
        with self.assertRaises(ValueError):
            self.store.save_schema(schema, schema_dir=self.tmp)

    def test_save_missing_category_raises(self):
        with self.assertRaises(ValueError):
            self.store.save_schema({"fields": {"a": "string"}}, schema_dir=self.tmp)

    def test_save_overwrites_existing(self):
        schema = self._valid_schema()
        self.store.save_schema(schema, schema_dir=self.tmp)
        schema["fields"]["new_field"] = "string"
        self.store.save_schema(schema, schema_dir=self.tmp)
        loaded = self.store.load_schema("Borrowing Profile", schema_dir=self.tmp)
        self.assertIn("new_field", loaded["fields"])

    # --- default fallback ---

    def test_load_falls_back_to_default_when_no_file(self):
        # No file exists in tmp_dir for "ALM"
        schema = self.store.load_schema("ALM", schema_dir=self.tmp)
        self.assertEqual(schema["category"], "ALM")
        self.assertIn("time_bucket", schema["fields"])

    def test_load_raises_for_unknown_category_no_default(self):
        with self.assertRaises(KeyError):
            self.store.load_schema("NonExistentCategory", schema_dir=self.tmp)

    # --- delete ---

    def test_delete_removes_file(self):
        schema = self._valid_schema()
        self.store.save_schema(schema, schema_dir=self.tmp)
        deleted = self.store.delete_schema("Borrowing Profile", schema_dir=self.tmp)
        self.assertTrue(deleted)
        files = list(Path(self.tmp).glob("*.json"))
        self.assertEqual(len(files), 0)

    def test_delete_nonexistent_returns_false(self):
        deleted = self.store.delete_schema("ALM", schema_dir=self.tmp)
        self.assertFalse(deleted)

    # --- list ---

    def test_list_returns_all_defaults_when_empty_dir(self):
        schemas = self.store.list_schemas(schema_dir=self.tmp)
        categories = {s["category"] for s in schemas}
        self.assertEqual(categories, {
            "ALM", "Shareholding Pattern", "Borrowing Profile",
            "Annual Report", "Portfolio Performance"
        })

    def test_custom_schema_overrides_default_in_list(self):
        schema = {"category": "ALM", "fields": {"custom_field": "string"}}
        self.store.save_schema(schema, schema_dir=self.tmp)
        schemas = self.store.list_schemas(schema_dir=self.tmp)
        alm = next(s for s in schemas if s["category"] == "ALM")
        self.assertIn("custom_field", alm["fields"])
        self.assertNotIn("time_bucket", alm["fields"])

    # --- seed ---

    def test_seed_creates_all_default_files(self):
        seeded = self.store.seed_default_schemas(schema_dir=self.tmp)
        self.assertEqual(len(seeded), 5)
        files = list(Path(self.tmp).glob("*.json"))
        self.assertEqual(len(files), 5)

    def test_seed_skips_existing_by_default(self):
        schema = self._valid_schema()
        self.store.save_schema(schema, schema_dir=self.tmp)
        seeded = self.store.seed_default_schemas(schema_dir=self.tmp)
        # Borrowing Profile already exists, so 4 others are seeded
        self.assertEqual(len(seeded), 4)


# ===========================================================================
# TestExtractor
# ===========================================================================

class TestExtractor(unittest.TestCase):
    """Tests for doc_classifier.extractor."""

    def setUp(self):
        from doc_classifier import extractor
        self.extractor = extractor

    def test_raw_content_dataclass_defaults(self):
        from doc_classifier.extractor import RawContent
        rc = RawContent()
        self.assertEqual(rc.text, "")
        self.assertEqual(rc.tables, [])

    def test_raw_content_to_dict_shape(self):
        from doc_classifier.extractor import RawContent
        rc = RawContent(
            text="hello world",
            tables=[pd.DataFrame({"a": [1, 2]})],
            source_path="test.pdf",
        )
        d = rc.to_dict()
        self.assertEqual(d["num_tables"], 1)
        self.assertEqual(d["text_length"], len("hello world"))

    def test_normalise_columns(self):
        from doc_classifier.extractor import _normalise_columns
        df = pd.DataFrame({"Lender Name": ["HDFC"], "Loan Amount (Cr)": [500]})
        normalised = _normalise_columns(df)
        self.assertIn("lender_name", normalised.columns)
        self.assertIn("loan_amount_(cr)", normalised.columns)

    def test_table_to_df_valid(self):
        from doc_classifier.extractor import _table_to_df
        raw = [["lender", "amount"], ["HDFC", "500"], ["ICICI", "200"]]
        df = _table_to_df(raw)
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)
        self.assertIn("lender", df.columns)

    def test_table_to_df_too_few_rows_returns_none(self):
        from doc_classifier.extractor import _table_to_df
        raw = [["header_only"]]   # only header, no data
        df = _table_to_df(raw)
        self.assertIsNone(df)

    def test_table_to_df_empty_returns_none(self):
        from doc_classifier.extractor import _table_to_df
        self.assertIsNone(_table_to_df([]))

    def test_extract_raw_raises_for_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            self.extractor.extract_raw("nonexistent.pdf")

    def test_extract_raw_raises_for_unsupported_type(self):
        with self.assertRaises(ValueError):
            self.extractor.extract_raw("report.docx")

    @patch("doc_classifier.extractor.Path.is_file", return_value=True)
    @patch("doc_classifier.extractor.pdfplumber.open")
    def test_extract_pdf_text_collected(self, mock_open, _is_file):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Net Interest Margin 5.2%"
        mock_page.extract_tables.return_value = []
        mock_open.return_value.__enter__.return_value.pages = [mock_page]

        from doc_classifier.extractor import _extract_pdf
        result = _extract_pdf("fake.pdf")
        self.assertIn("Net Interest Margin", result.text)
        self.assertEqual(len(result.tables), 0)

    @patch("doc_classifier.extractor.Path.is_file", return_value=True)
    @patch("doc_classifier.extractor.pdfplumber.open")
    def test_extract_pdf_tables_collected(self, mock_open, _is_file):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_page.extract_tables.return_value = [
            [["lender", "amount"], ["HDFC", "500"], ["ICICI", "300"]]
        ]
        mock_open.return_value.__enter__.return_value.pages = [mock_page]

        from doc_classifier.extractor import _extract_pdf
        result = _extract_pdf("fake.pdf")
        self.assertEqual(len(result.tables), 1)
        self.assertIn("lender", result.tables[0].columns)


# ===========================================================================
# TestSchemaMapper
# ===========================================================================

class TestSchemaMapper(unittest.TestCase):
    """Tests for doc_classifier.schema_mapper."""

    def setUp(self):
        from doc_classifier import schema_mapper
        self.mapper = schema_mapper

    def _make_raw(self, text: str = "", tables: list = None):
        from doc_classifier.extractor import RawContent
        return RawContent(text=text, tables=tables or [])

    def test_coerce_number_strips_currency(self):
        from doc_classifier.schema_mapper import _coerce
        self.assertAlmostEqual(_coerce("Rs. 500.5 Cr", "number"), 500.5)
        self.assertAlmostEqual(_coerce("1,234.56", "number"), 1234.56)

    def test_coerce_number_returns_none_for_empty(self):
        from doc_classifier.schema_mapper import _coerce
        self.assertIsNone(_coerce("", "number"))
        self.assertIsNone(_coerce("N/A", "number"))

    def test_coerce_string_truncates(self):
        from doc_classifier.schema_mapper import _coerce
        long_val = "x" * 300
        result = _coerce(long_val, "string")
        self.assertLessEqual(len(result), 200)

    def test_coerce_boolean_true_values(self):
        from doc_classifier.schema_mapper import _coerce
        for v in ["yes", "true", "1", "Y", "✓"]:
            self.assertTrue(_coerce(v, "boolean"), f"'{v}' should be True")

    def test_coerce_boolean_false_values(self):
        from doc_classifier.schema_mapper import _coerce
        self.assertFalse(_coerce("no", "boolean"))
        self.assertFalse(_coerce("false", "boolean"))

    def test_column_matches_field_exact(self):
        from doc_classifier.schema_mapper import _column_matches_field
        self.assertTrue(_column_matches_field("lender_name", "lender_name"))

    def test_column_matches_field_substring(self):
        from doc_classifier.schema_mapper import _column_matches_field
        self.assertTrue(_column_matches_field("total_loan_amount_crore", "loan_amount"))

    def test_column_no_match(self):
        from doc_classifier.schema_mapper import _column_matches_field
        self.assertFalse(_column_matches_field("date_incorporated", "interest_rate"))

    def test_table_extraction_produces_records(self):
        df = pd.DataFrame({
            "lender_name": ["HDFC Bank", "ICICI"],
            "loan_amount": ["500", "300"],
            "interest_rate": ["8.5", "9.0"],
        })
        schema = {
            "category": "Borrowing Profile",
            "fields": {
                "lender_name":  "string",
                "loan_amount":  "number",
                "interest_rate": "number",
            },
        }
        raw = self._make_raw(tables=[df])
        records = self.mapper.map_to_schema(raw, schema)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["lender_name"], "HDFC Bank")
        self.assertAlmostEqual(records[0]["loan_amount"], 500.0)

    def test_text_fallback_when_no_matching_table(self):
        text = "The lender_name is HDFC Bank and interest_rate is 8.50%"
        schema = {
            "category": "Borrowing Profile",
            "fields": {
                "lender_name":  "string",
                "interest_rate": "number",
            },
        }
        raw = self._make_raw(text=text)
        records = self.mapper.map_to_schema(raw, schema)
        self.assertGreaterEqual(len(records), 1)

    def test_empty_schema_fields_returns_empty_list(self):
        schema = {"category": "Test", "fields": {}}
        raw = self._make_raw(text="some text")
        records = self.mapper.map_to_schema(raw, schema)
        self.assertEqual(records, [])

    def test_all_schema_fields_present_in_each_record(self):
        df = pd.DataFrame({
            "lender_name": ["SBI"],
            "loan_amount": ["100"],
        })
        schema = {
            "category": "Borrowing Profile",
            "fields": {
                "lender_name": "string",
                "loan_amount": "number",
                "tenure_months": "number",   # not in table
            },
        }
        raw = self._make_raw(tables=[df])
        records = self.mapper.map_to_schema(raw, schema)
        for rec in records:
            self.assertIn("tenure_months", rec)


# ===========================================================================
# TestExtractionPipeline
# ===========================================================================

class TestExtractionPipeline(unittest.TestCase):
    """Tests for doc_classifier.extraction_pipeline."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from doc_classifier import extraction_pipeline
        self.ep = extraction_pipeline

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_metadata(
        self,
        pred: str = "Borrowing Profile",
        status_val: str = "approved",
        filepath: str = "/fake/path/doc.pdf",
    ) -> str:
        from doc_classifier.metadata_store import create_metadata, apply_review, _metadata_path, _write_json
        import uuid, json
        doc_id = str(uuid.uuid4())
        meta = {
            "document_id": doc_id,
            "filename": "doc.pdf",
            "model_prediction": pred,
            "confidence": 0.9,
            "final_category": pred,
            "status": status_val,
            "stored_filepath": filepath,
        }
        from doc_classifier.metadata_store import _ensure_dir
        path = _ensure_dir(self.tmp) / f"{doc_id}.json"
        from doc_classifier.metadata_store import _write_json as wj
        wj(meta, path)
        return doc_id

    def test_status_gate_blocks_awaiting_review(self):
        doc_id = self._seed_metadata(status_val="awaiting_review")
        with self.assertRaises(PermissionError):
            self.ep.run_extraction(doc_id, store_dir=self.tmp)

    def test_missing_stored_filepath_raises(self):
        doc_id = self._seed_metadata(status_val="approved", filepath="")
        with self.assertRaises(FileNotFoundError):
            self.ep.run_extraction(doc_id, store_dir=self.tmp)

    @patch("doc_classifier.extraction_pipeline.extract_raw")
    @patch("doc_classifier.extraction_pipeline.map_to_schema")
    @patch("doc_classifier.extraction_pipeline.load_schema")
    def test_run_extraction_end_to_end(self, mock_schema, mock_map, mock_extract):
        """Full pipeline with mocked IO: validates output structure."""
        # Seed a real temp file so is_file() passes
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            fake_path = tf.name

        doc_id = self._seed_metadata(status_val="approved", filepath=fake_path)

        mock_schema.return_value = {
            "category": "Borrowing Profile",
            "fields": {"lender_name": "string", "loan_amount": "number"},
        }
        mock_extract.return_value = MagicMock(text="HDFC 500", tables=[])
        mock_map.return_value = [{"lender_name": "HDFC", "loan_amount": 500.0}]

        result = self.ep.run_extraction(doc_id, store_dir=self.tmp)

        self.assertEqual(result["document_id"], doc_id)
        self.assertEqual(result["category"], "Borrowing Profile")
        self.assertEqual(len(result["extracted_records"]), 1)
        self.assertEqual(result["extracted_records"][0]["lender_name"], "HDFC")

        import os
        os.unlink(fake_path)

    @patch("doc_classifier.extraction_pipeline.extract_raw")
    @patch("doc_classifier.extraction_pipeline.map_to_schema")
    @patch("doc_classifier.extraction_pipeline.load_schema")
    def test_extraction_result_saved_to_disk(self, mock_schema, mock_map, mock_extract):
        """Verify extraction result JSON file is created."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
            fake_path = tf.name

        doc_id = self._seed_metadata(
            status_val="corrected_by_user", filepath=fake_path
        )
        mock_schema.return_value = {"category": "ALM", "fields": {"gap": "number"}}
        mock_extract.return_value = MagicMock(text="gap 100", tables=[])
        mock_map.return_value = [{"gap": 100.0}]

        self.ep.run_extraction(doc_id, store_dir=self.tmp)

        extraction_file = Path(self.tmp) / f"{doc_id}_extraction.json"
        self.assertTrue(extraction_file.exists())

        import os
        os.unlink(fake_path)

    @patch("doc_classifier.extraction_pipeline.extract_raw")
    @patch("doc_classifier.extraction_pipeline.map_to_schema")
    @patch("doc_classifier.extraction_pipeline.load_schema")
    def test_metadata_status_updated_after_extraction(self, mock_schema, mock_map, mock_extract):
        """Metadata status should become 'extraction_complete' after successful extraction."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            fake_path = tf.name

        doc_id = self._seed_metadata(status_val="approved", filepath=fake_path)
        mock_schema.return_value = {"category": "ALM", "fields": {"gap": "number"}}
        mock_extract.return_value = MagicMock(text="", tables=[])
        mock_map.return_value = []

        self.ep.run_extraction(doc_id, store_dir=self.tmp)

        from doc_classifier.metadata_store import load_metadata
        meta = load_metadata(doc_id, store_dir=self.tmp)
        self.assertEqual(meta["status"], "extraction_complete")

        import os
        os.unlink(fake_path)

    def test_load_extraction_raises_when_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.ep.load_extraction("ghost-uuid", store_dir=self.tmp)


# ===========================================================================
# TestAPISchemaAndExtraction
# ===========================================================================

class TestAPISchemaAndExtraction(unittest.TestCase):
    """Tests for new schema and extraction endpoints in api.py."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.schema_tmp = tempfile.mkdtemp()

        import doc_classifier.api as api_module
        api_module.STORE_DIR  = self.tmp
        api_module.SCHEMA_DIR = self.schema_tmp

        from fastapi.testclient import TestClient
        self.client = TestClient(api_module.app)
        self.api = api_module

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.schema_tmp, ignore_errors=True)

    # --- Schema endpoints ---

    def test_get_schemas_returns_five_defaults(self):
        resp = self.client.get("/schemas")
        self.assertEqual(resp.status_code, 200)
        categories = {s["category"] for s in resp.json()}
        self.assertEqual(len(categories), 5)

    def test_get_schema_by_category_returns_default(self):
        resp = self.client.get("/schemas/ALM")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["category"], "ALM")
        self.assertIn("time_bucket", resp.json()["fields"])

    def test_get_schema_unknown_category_returns_404(self):
        resp = self.client.get("/schemas/UnknownCategory")
        self.assertEqual(resp.status_code, 404)

    def test_post_schema_creates_custom(self):
        payload = {
            "category": "Borrowing Profile",
            "fields": {"lender": "string", "rate": "number"},
        }
        resp = self.client.post("/schemas", json=payload)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["category"], "Borrowing Profile")

    def test_post_schema_invalid_type_returns_422(self):
        payload = {
            "category": "ALM",
            "fields": {"gap": "integer"},   # invalid type
        }
        resp = self.client.post("/schemas", json=payload)
        self.assertEqual(resp.status_code, 422)

    def test_delete_schema_returns_200(self):
        # First create, then delete
        self.client.post("/schemas", json={
            "category": "ALM",
            "fields": {"custom": "string"},
        })
        resp = self.client.delete("/schemas/ALM")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["deleted"])

    def test_delete_nonexistent_schema_returns_false(self):
        resp = self.client.delete("/schemas/ALM")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["deleted"])

    # --- Extraction endpoints ---

    def _seed_metadata(
        self,
        pred: str = "ALM",
        status_val: str = "approved",
        filepath: str = "",
    ) -> str:
        import uuid, json
        doc_id = str(uuid.uuid4())
        meta = {
            "document_id": doc_id,
            "filename": "doc.pdf",
            "model_prediction": pred,
            "confidence": 0.9,
            "final_category": pred,
            "status": status_val,
            "stored_filepath": filepath,
        }
        path = Path(self.tmp) / f"{doc_id}.json"
        with open(path, "w") as f:
            json.dump(meta, f)
        return doc_id

    def test_extract_endpoint_blocks_unapproved(self):
        doc_id = self._seed_metadata(status_val="awaiting_review")
        resp = self.client.post(f"/extract/{doc_id}")
        self.assertEqual(resp.status_code, 409)

    def test_extract_endpoint_404_for_missing_doc(self):
        resp = self.client.post("/extract/ghost-uuid")
        self.assertEqual(resp.status_code, 404)

    def test_get_extractions_404_when_not_run(self):
        doc_id = self._seed_metadata(status_val="approved")
        resp = self.client.get(f"/extractions/{doc_id}")
        self.assertEqual(resp.status_code, 404)

    @patch("doc_classifier.api.run_extraction")
    def test_extract_endpoint_success(self, mock_run):
        doc_id = self._seed_metadata(status_val="approved")
        mock_run.return_value = {
            "document_id": doc_id,
            "category": "ALM",
            "filename": "doc.pdf",
            "extracted_records": [{"time_bucket": "1-7 days", "gap": 200.0}],
        }
        resp = self.client.post(f"/extract/{doc_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["document_id"], doc_id)
        self.assertEqual(len(data["extracted_records"]), 1)

    @patch("doc_classifier.api.load_extraction")
    def test_get_extraction_success(self, mock_load):
        doc_id = "test-uuid"
        mock_load.return_value = {
            "document_id": doc_id,
            "category": "ALM",
            "filename": "alm.pdf",
            "extracted_records": [{"time_bucket": "1-7 days"}],
        }
        resp = self.client.get(f"/extractions/{doc_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["category"], "ALM")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
