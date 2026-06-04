"""
research.py
===========
Secondary research analysis module collecting external financial news about a 
company and analyzing it using FinBERT (sentiment) and SBERT (semantic risk).

Responsibilities
----------------
* Fetch recent news via NewsAPI (newsapi-python)
* Download full text via newspaper3k
* Classify sentiment via HuggingFace transformers (ProsusAI/finbert)
* Detect primary risk category via sentence-transformers (all-MiniLM-L6-v2)

Environment variables
---------------------
  NEWSAPI_KEY — Required to fetch live news. If missing, fetching will raise an Error.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from newsapi import NewsApiClient
from newspaper import Article

# HuggingFace
from transformers import pipeline

# Local embedder logic (reuses the already cached SBERT model instance)
from embedder import get_default_embedder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Globals / Constants
# ---------------------------------------------------------------------------

_NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")

_FINBERT_PIPELINE = None

# Risk categories we want to detect in articles
RISK_CATEGORIES = [
    "fraud",
    "regulatory",
    "default",
    "funding",
    "growth",
]

_RISK_EMBEDDINGS: list[Any] = []
_RISK_LABELS: list[str] = []


def _get_finbert():
    """Lazy load the ProsusAI/finbert sentiment pipeline."""
    global _FINBERT_PIPELINE
    if _FINBERT_PIPELINE is None:
        logger.info("Loading FinBERT sentiment model (ProsusAI/finbert)...")
        _FINBERT_PIPELINE = pipeline("sentiment-analysis", model="ProsusAI/finbert")
    return _FINBERT_PIPELINE


def _get_risk_embeddings():
    """Lazy-embed the risk category labels using the existing SBERT instance."""
    global _RISK_EMBEDDINGS, _RISK_LABELS
    if not _RISK_EMBEDDINGS:
        embedder = get_default_embedder()
        logger.info("Pre-computing risk category embeddings...")
        _RISK_LABELS = RISK_CATEGORIES
        _RISK_EMBEDDINGS = embedder.embed(RISK_CATEGORIES)
    return _RISK_EMBEDDINGS, _RISK_LABELS


# ---------------------------------------------------------------------------
# 1. News Collection
# ---------------------------------------------------------------------------

def _fetch_news(company_name: str) -> list[dict[str, str]]:
    """
    Search NewsAPI for recent articles mentioning the company with risk keywords.
    Deduplicates by URL.
    """
    if not _NEWSAPI_KEY:
        raise RuntimeError(
            "NEWSAPI_KEY environment variable is missing. "
            "Cannot fetch live news for secondary research."
        )

    client = NewsApiClient(api_key=_NEWSAPI_KEY)
    
    # 30 days lookback
    from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    queries = [
        f'"{company_name}"',
        f'"{company_name}" AND lawsuit',
        f'"{company_name}" AND regulatory',
        f'"{company_name}" AND funding',
        f'"{company_name}" AND default',
    ]

    seen_urls: set[str] = set()
    articles: list[dict[str, str]] = []

    for q in queries:
        try:
            res = client.get_everything(
                q=q,
                language="en",
                from_param=from_date,
                sort_by="relevancy",
                page_size=5,  # Top 5 per query to keep volume manageable
            )
            for item in res.get("articles", []):
                url = item.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Transform to our internal schema
                articles.append({
                    "title": item.get("title") or "Unknown Title",
                    "source": item.get("source", {}).get("name") or "Unknown Source",
                    "date": item.get("publishedAt") or "Unknown Date",
                    "url": url,
                    "description": item.get("description") or "",
                })
        except Exception as exc:
            logger.warning("NewsAPI fetch failed for query '%s': %s", q, exc)

    logger.info("Fetched %d unique news articles for '%s'", len(articles), company_name)
    return articles


# ---------------------------------------------------------------------------
# 2. Article Text Extraction
# ---------------------------------------------------------------------------

def _extract_text(url: str) -> str:
    """Download and parse full article text via newspaper3k."""
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text or ""
    except Exception as exc:
        logger.warning("Failed to extract text from %s: %s", url, exc)
        return ""


# ---------------------------------------------------------------------------
# 3. Sentiment Analysis (FinBERT)
# ---------------------------------------------------------------------------

def _analyze_sentiment(text: str) -> dict[str, Any]:
    """Run FinBERT on the text (truncated to model context window)."""
    if not text.strip():
        return {"sentiment": "neutral", "confidence": 0.0}

    # FinBERT max length is 512 tokens. We chunk by words roughly.
    words = text.split()[:400]
    short_text = " ".join(words)

    try:
        classifier = _get_finbert()
        # FinBERT returns e.g. [{'label': 'positive', 'score': 0.94}]
        res = classifier(short_text)[0] 
        return {
            "sentiment": res["label"].lower(),
            "confidence": round(float(res["score"]), 4),
        }
    except Exception as exc:
        logger.warning("Sentiment analysis failed: %s", exc)
        return {"sentiment": "neutral", "confidence": 0.0}


# ---------------------------------------------------------------------------
# 4. Semantic Risk Detection (SBERT)
# ---------------------------------------------------------------------------

def _detect_risk(text: str) -> dict[str, Any]:
    """
    Compare article text to predefined risk categories using cosine similarity.
    Returns the highest matching risk category.
    """
    if not text.strip():
        return {"risk_category": "unknown", "confidence": 0.0}

    from sklearn.metrics.pairwise import cosine_similarity
    
    try:
        embedder = get_default_embedder()
        risk_embeddings, labels = _get_risk_embeddings()
        
        # truncate text for embedding to avoid warning spam
        short_text = " ".join(text.split()[:500])
        doc_emb = embedder.embed([short_text])
        
        sims = cosine_similarity(doc_emb, risk_embeddings)[0]
        
        best_idx = int(sims.argmax())
        best_score = float(sims[best_idx])
        
        # If score is very low, maybe no risk is applicable
        if best_score < 0.15:
            return {"risk_category": "none", "confidence": round(best_score, 4)}
            
        return {
            "risk_category": labels[best_idx],
            "confidence": round(best_score, 4)
        }
    except Exception as exc:
        logger.warning("Risk detection failed: %s", exc)
        return {"risk_category": "unknown", "confidence": 0.0}


# ---------------------------------------------------------------------------
# 5. Public Orchestrator
# ---------------------------------------------------------------------------

def analyze_company_news(company_name: str, sector: str) -> dict[str, Any]:
    """
    Perform a complete secondary research cycle for a company.

    Returns
    -------
    dict
        Structured JSON representing the research output:
        {
          "company": "...",
          "sector": "...",
          "news_analysis": [ ... ]
        }
    """
    logger.info("Starting research analysis for company='%s', sector='%s'", company_name, sector)
    
    articles = _fetch_news(company_name)
    news_analysis = []

    for art in articles:
        # Download text
        full_text = _extract_text(art["url"])
        
        # Fallback to description if full text extraction fails
        analysis_text = full_text if full_text.strip() else art["description"]
        
        # ML Analysis
        sentiment = _analyze_sentiment(analysis_text)
        risk = _detect_risk(analysis_text)
        
        news_analysis.append({
            "title": art["title"],
            "date": art["date"],
            "url": art["url"],
            "source": art["source"],
            "sentiment": sentiment["sentiment"],
            "sentiment_confidence": sentiment["confidence"],
            "risk_category": risk["risk_category"],
            "risk_confidence": risk["confidence"],
        })

    logger.info("Completed research analysis. Processed %d articles.", len(news_analysis))

    return {
        "company": company_name,
        "sector": sector,
        "news_analysis": news_analysis
    }
