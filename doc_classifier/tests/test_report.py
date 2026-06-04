"""
test_report.py
==============
Mocked tests for the Report Generation engine (LLM text + ReportLab PDF).
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env_patcher = patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
        self.env_patcher.start()

        from doc_classifier import report_generator
        self.rep = report_generator
        self.rep._CLIENT = None

    def tearDown(self):
        self.env_patcher.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                self.rep._get_openai_client()
            self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    @patch("doc_classifier.report_generator.OpenAI")
    def test_generate_report_content_success(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '''
        {
          "executive_summary": "Top notch company.",
          "financial_analysis": "Good numbers.",
          "external_risk_analysis": "No lawsuits.",
          "swot": {
            "strengths": ["Cash"],
            "weaknesses": ["None"],
            "opportunities": ["Growth"],
            "threats": ["Rivals"]
          },
          "final_recommendation": "Fund them."
        }
        '''
        mock_client.chat.completions.create.return_value = mock_response

        res = self.rep.generate_report_content({}, {}, {}, {})

        self.assertEqual(res["executive_summary"], "Top notch company.")
        self.assertIn("swot", res)
        self.assertEqual(res["swot"]["strengths"], ["Cash"])
        
        mock_client.chat.completions.create.assert_called_once()
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-4o-mini")

    def test_generate_pdf_report_success(self):
        report_data = {
          "executive_summary": "Summary text",
          "financial_analysis": "Financial text",
          "external_risk_analysis": "Risk text",
          "swot": {
            "strengths": ["S1"],
            "weaknesses": ["W1"],
            "opportunities": ["O1"],
            "threats": ["T1"]
          },
          "final_recommendation": "Approve."
        }
        
        out_path = str(Path(self.tmp) / "report.pdf")
        path = self.rep.generate_pdf_report(report_data, "Test Corp", out_path)
        
        self.assertEqual(path, out_path)
        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(os.path.getsize(out_path), 0)


class TestAPIReportEndpoint(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        import doc_classifier.api as api_module
        api_module.STORE_DIR = Path(self.tmp)
        from fastapi.testclient import TestClient
        self.client = TestClient(api_module.app)
        
        # Write a fake PDF file for HTTP GET testing
        self.fake_pdf = Path(self.tmp) / "fake.pdf"
        self.fake_pdf.write_bytes(b"%PDF-1.4 mock content")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    @patch("doc_classifier.report_generator.generate_pdf_report")
    @patch("doc_classifier.report_generator.generate_report_content")
    def test_post_report_endpoint_success(self, mock_gen_content, mock_gen_pdf):
        mock_gen_content.return_value = {
          "executive_summary": "Sum",
          "financial_analysis": "Fin",
          "external_risk_analysis": "Ext",
          "swot": {
            "strengths": [], "weaknesses": [],
            "opportunities": [], "threats": []
          },
          "final_recommendation": "Rec"
        }
        
        payload = {
            "entity_name": "Testing Inc",
            "entity_details": {},
            "financial_metrics": {},
            "external_signals": {},
            "risk_evaluation": {}
        }
        resp = self.client.post("/report", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("swot", data)
        self.assertTrue(data["pdf_download_url"].startswith("/reports/Testing_Inc"))

    def test_get_report_download_success(self):
        resp = self.client.get("/reports/fake.pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")
        self.assertEqual(resp.content, b"%PDF-1.4 mock content")

    def test_get_report_download_404(self):
        resp = self.client.get("/reports/ghost.pdf")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
