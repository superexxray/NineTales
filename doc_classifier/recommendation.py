"""
recommendation.py
=================
Credit recommendation engine bridging structured financial data, 
external research signals, and sector context.

Uses OpenAI's gpt-4o-mini as a credit risk analyst to output a deterministic, 
explainable JSON recommendation.

Environment variables
---------------------
  OPENAI_API_KEY — Required to use the OpenAI API.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI Client handling
# ---------------------------------------------------------------------------

_CLIENT = None

def _get_openai_client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is missing. "
                "Cannot generate credit recommendation."
            )
        _CLIENT = OpenAI(api_key=api_key)
    return _CLIENT


# ---------------------------------------------------------------------------
# Prompt Definition
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert Credit Risk Analyst.
You will be provided with three sets of data about a candidate company:
1. "financial_metrics": Extracted financial ratios and metrics.
2. "external_signals": Summary of sentiment and risk from recent news.
3. "sector_context": Brief sector-specific information.

Your task is to evaluate this information and output a final credit recommendation.
Evaluate their financial health, leverage and liquidity, negative news signals, 
and sector outlook.

You MUST respond in strictly valid JSON format matching exactly this schema:
{
  "risk_score": <float between 0.0 (highest risk) and 100.0 (safest)>,
  "risk_level": "<one of: Low, Medium, High>",
  "loan_recommendation": "<one of: Approve, Approve with conditions, Reject>",
  "key_risk_factors": ["<string>", ...],
  "key_strengths": ["<string>", ...]
}

Do not include any text outside of the JSON block. Do not use markdown backticks around the JSON.
"""

def _build_user_message(
    financial_metrics: dict[str, Any],
    external_signals: dict[str, Any],
    sector_context: dict[str, Any],
) -> str:
    """Format the payload nicely for the LLM context."""
    return json.dumps({
        "financial_metrics": financial_metrics,
        "external_signals": external_signals,
        "sector_context": sector_context,
    }, indent=2)


# ---------------------------------------------------------------------------
# Public Entry Point
# ---------------------------------------------------------------------------

def generate_recommendation(
    financial_metrics: dict[str, Any],
    external_signals: dict[str, Any],
    sector_context: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate financial and external data using an LLM to produce a credit recommendation.

    Returns
    -------
    dict
        Structured recommendation mapping to the required schema:
        {
          "risk_score": float,
          "risk_level": str,
          "loan_recommendation": str,
          "key_risk_factors": list[str],
          "key_strengths": list[str]
        }
    """
    logger.info("Generating LLM credit recommendation...")
    client = _get_openai_client()

    user_msg = _build_user_message(
        financial_metrics, external_signals, sector_context
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2, # Low temperature for more deterministic/stable responses
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned empty content.")

        result = json.loads(content)
        
        # Enforce basic shape in case the model hallucinates keys
        expected_keys = {
            "risk_score", "risk_level", "loan_recommendation",
            "key_risk_factors", "key_strengths"
        }
        if not expected_keys.issubset(result.keys()):
            logger.warning("Agent returned unexpected schema keys: %s", list(result.keys()))
            
        return result

    except Exception as exc:
        logger.exception("Failed to generate credit recommendation.")
        raise RuntimeError(f"OpenAI completion failed: {exc}") from exc
