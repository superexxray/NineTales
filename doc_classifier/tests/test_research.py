"""
test_research.py
================
Unit tests for the new secondary research module using fully mocked components
for NewsClient, newspaper3k, and transformer pipelines so no live network/model
calls occur during CI.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestResearchModule(unittest.TestCase):
    """Tests for doc_classifier.research."""

    def setUp(self):
        # We need to test the module with an API key set, so we patch environ
        self.env_patcher = patch.dict("os.environ", {"NEWSAPI_KEY": "fake_key"})
        self.env_patcher.start()

        from doc_classifier import research
        self.research = research

        # Clean up global pipeline/embeddings caches if dirty
        self.research._FINBERT_PIPELINE = None
        self.research._RISK_EMBEDDINGS = []
        self.research._RISK_LABELS = []

    def tearDown(self):
        self.env_patcher.stop()

    def test_fetch_news_missing_key_raises(self):
        with patch.dict("os.environ", clear=True):
            # Without key set, it should raise RuntimeError
            import os
            # Manually reset module's private var just for this test
            old_key = self.research._NEWSAPI_KEY
            self.research._NEWSAPI_KEY = None
            try:
                with self.assertRaises(RuntimeError):
                    self.research._fetch_news("Test Corp")
            finally:
                self.research._NEWSAPI_KEY = old_key

    @patch("doc_classifier.research.NewsApiClient")
    def test_fetch_news_success_and_dedupes(self, MockClient):
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        # Return the same article twice over two queries to test deduplication
        mock_instance.get_everything.side_effect = [
            # query 1
            {"articles": [{"title": "A", "url": "http://same", "publishedAt": "2024-01-01", "source": {"name": "Test"}}]},
            # query 2 — exact same url
            {"articles": [{"title": "A", "url": "http://same", "publishedAt": "2024-01-01", "source": {"name": "Test"}}]},
        ] + [{"articles": []}] * 3  # Remaining 3 queries empty

        articles = self.research._fetch_news("Acme")
        
        self.assertEqual(len(articles), 1)  # Deduped by URL
        self.assertEqual(articles[0]["title"], "A")
        self.assertEqual(mock_instance.get_everything.call_count, 5)

    @patch("doc_classifier.research.Article")
    def test_extract_text_success(self, MockArticle):
        mock_instance = MagicMock()
        mock_instance.text = "Full article content written here."
        MockArticle.return_value = mock_instance

        text = self.research._extract_text("http://news.com/article")
        self.assertEqual(text, "Full article content written here.")
        mock_instance.download.assert_called_once()
        mock_instance.parse.assert_called_once()

    @patch("doc_classifier.research.Article")
    def test_extract_text_failure_returns_empty(self, MockArticle):
        mock_instance = MagicMock()
        mock_instance.download.side_effect = Exception("HTTP 404")
        MockArticle.return_value = mock_instance

        text = self.research._extract_text("http://bad-url.com")
        self.assertEqual(text, "")

    @patch("doc_classifier.research.pipeline")
    def test_analyze_sentiment_success(self, mock_pipeline):
        # Mock pipeline constructor
        mock_pipe_instance = MagicMock()
        mock_pipeline.return_value = mock_pipe_instance
        
        # Mock inference return shape: [{'label': 'positive', 'score': 0.99}]
        mock_pipe_instance.return_value = [{"label": "negative", "score": 0.852}]

        res = self.research._analyze_sentiment("Company is facing a massive lawsuit.")
        
        self.assertEqual(res["sentiment"], "negative")
        self.assertAlmostEqual(res["confidence"], 0.852)
        mock_pipeline.assert_called_once_with("sentiment-analysis", model="ProsusAI/finbert")

    def test_analyze_sentiment_empty_text_returns_neutral(self):
        res = self.research._analyze_sentiment("")
        self.assertEqual(res["sentiment"], "neutral")
        self.assertEqual(res["confidence"], 0.0)

    @patch("doc_classifier.research.get_default_embedder")
    def test_detect_risk_success(self, mock_get_embedder):
        import numpy as np
        
        mock_embedder = MagicMock()
        mock_get_embedder.return_value = mock_embedder
        
        # Setup: the risk labels are fraud, regulatory, default, funding, growth (5 items)
        # We will mock the embedding so that risk category 2 ("default") exactly matches the doc
        mock_embedder.embed.side_effect = [
            # Call 1: creating risk embeddings
            np.array([
                [1, 0, 0], # fraud
                [0, 1, 0], # regulatory
                [0, 0, 1], # default
                [0.1, 0, 0], # funding
                [0.2, 0, 0], # growth
            ]),
            # Call 2: creating doc embedding
            np.array([[0, 0, 1]])
        ]

        res = self.research._detect_risk("The company filed for bankruptcy.")
        
        self.assertEqual(res["risk_category"], "default")
        self.assertAlmostEqual(res["confidence"], 1.0)
        self.assertEqual(mock_embedder.embed.call_count, 2)

    @patch("doc_classifier.research.get_default_embedder")
    def test_detect_risk_low_confidence_returns_none(self, mock_get_embedder):
        import numpy as np
        mock_embedder = MagicMock()
        mock_get_embedder.return_value = mock_embedder
        
        # All embeddings are orthogonal (0 similarity)
        mock_embedder.embed.side_effect = [
            np.array([[1, 0], [1, 0], [1, 0], [1, 0], [1, 0]]),
            np.array([[0, 1]]) 
        ]

        res = self.research._detect_risk("Unrelated tech news.")
        
        # Falls below the 0.15 threshold
        self.assertEqual(res["risk_category"], "none")
        self.assertAlmostEqual(res["confidence"], 0.0)

    @patch("doc_classifier.research._fetch_news")
    @patch("doc_classifier.research._extract_text")
    @patch("doc_classifier.research._analyze_sentiment")
    @patch("doc_classifier.research._detect_risk")
    def test_analyze_company_news_orchestration(
        self, mock_risk, mock_sentiment, mock_extract, mock_fetch
    ):
        mock_fetch.return_value = [{
            "title": "Bad News",
            "url": "http://x",
            "date": "2024",
            "source": "News",
            "description": "fraud"
        }]
        mock_extract.return_value = "Long article text."
        mock_sentiment.return_value = {"sentiment": "negative", "confidence": 0.9}
        mock_risk.return_value = {"risk_category": "fraud", "confidence": 0.8}

        res = self.research.analyze_company_news("Acme Corp", "Tech")

        self.assertEqual(res["company"], "Acme Corp")
        self.assertEqual(res["sector"], "Tech")
        self.assertEqual(len(res["news_analysis"]), 1)
        
        item = res["news_analysis"][0]
        self.assertEqual(item["title"], "Bad News")
        self.assertEqual(item["sentiment"], "negative")
        self.assertEqual(item["risk_category"], "fraud")

        # Fallback assertion inside function
        mock_sentiment.assert_called_with("Long article text.")


class TestAPIResearchEndpoint(unittest.TestCase):

    def setUp(self):
        import doc_classifier.api as api_module
        from fastapi.testclient import TestClient
        self.client = TestClient(api_module.app)

    @patch("doc_classifier.research.analyze_company_news")
    def test_research_endpoint_success(self, mock_analyze):
        mock_analyze.return_value = {"company": "Test", "news_analysis": []}
        
        resp = self.client.post("/research", json={"company_name": "Test", "sector": "IT"})
        
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["company"], "Test")
        mock_analyze.assert_called_once_with("Test", "IT")

    @patch("doc_classifier.research.analyze_company_news")
    def test_research_endpoint_handles_missing_api_key(self, mock_analyze):
        mock_analyze.side_effect = RuntimeError("NEWSAPI_KEY missing")
        
        resp = self.client.post("/research", json={"company_name": "Test", "sector": "IT"})
        
        self.assertEqual(resp.status_code, 503)

if __name__ == "__main__":
    unittest.main(verbosity=2)
