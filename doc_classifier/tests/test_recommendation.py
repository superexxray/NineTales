"""
test_recommendation.py
======================
Mocked tests for the OpenAI LLM credit recommendation engine.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestRecommendation(unittest.TestCase):

    def setUp(self):
        self.env_patcher = patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
        self.env_patcher.start()

        from doc_classifier import recommendation
        self.rec = recommendation
        # Clear cached client
        self.rec._CLIENT = None

    def tearDown(self):
        self.env_patcher.stop()

    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                self.rec._get_openai_client()
            self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    @patch("doc_classifier.recommendation.OpenAI")
    def test_generate_recommendation_success(self, mock_openai_cls):
        # Setup mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '''
        {
          "risk_score": 85.5,
          "risk_level": "Low",
          "loan_recommendation": "Approve",
          "key_risk_factors": ["Slight sector headwind"],
          "key_strengths": ["Strong liquidity", "No negative news"]
        }
        '''
        mock_client.chat.completions.create.return_value = mock_response

        res = self.rec.generate_recommendation(
            {"debt_ratio": 0.5},
            {"sentiment": "neutral"},
            {"outlook": "stable"}
        )

        self.assertEqual(res["risk_score"], 85.5)
        self.assertEqual(res["risk_level"], "Low")
        self.assertEqual(res["loan_recommendation"], "Approve")
        
        # Verify call params
        mock_client.chat.completions.create.assert_called_once()
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-4o-mini")
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})


class TestAPIRecommendationEndpoint(unittest.TestCase):

    def setUp(self):
        import doc_classifier.api as api_module
        from fastapi.testclient import TestClient
        self.client = TestClient(api_module.app)

    @patch("doc_classifier.recommendation.generate_recommendation")
    def test_recommend_endpoint_success(self, mock_generate):
        mock_generate.return_value = {
            "risk_score": 90.0,
            "risk_level": "Low",
            "loan_recommendation": "Approve",
            "key_risk_factors": [],
            "key_strengths": ["High cash reserves"]
        }

        payload = {
            "financial_metrics": {"a": 1},
            "external_signals": {"b": 2},
            "sector_context": {"c": 3}
        }
        resp = self.client.post("/recommend", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["risk_level"], "Low")

    @patch("doc_classifier.recommendation.generate_recommendation")
    def test_recommend_endpoint_missing_api_key_503(self, mock_generate):
        mock_generate.side_effect = RuntimeError("OPENAI_API_KEY environment variable is missing")
        payload = {
            "financial_metrics": {},
            "external_signals": {},
            "sector_context": {}
        }
        resp = self.client.post("/recommend", json=payload)
        self.assertEqual(resp.status_code, 503)


if __name__ == "__main__":
    unittest.main(verbosity=2)
