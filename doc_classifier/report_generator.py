"""
report_generator.py
===================
Generates structured investment reports containing SWOT analysis 
and compiles them into downloadable PDFs using Jinja2 and ReportLab.

Environment variables
---------------------
  OPENAI_API_KEY — Required for LLM generation.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from pathlib import Path

from openai import OpenAI
from jinja2 import Template
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & Setup
# ---------------------------------------------------------------------------

_CLIENT = None

def _get_openai_client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is missing. "
                "Cannot generate investment report."
            )
        _CLIENT = OpenAI(api_key=api_key)
    return _CLIENT

# Jinja2 template for the PDF layout (using ReportLab-supported XML tags)
REPORT_TEMPLATE = """
<font size="18"><b>Investment Report: {{ entity_name }}</b></font>
<br/><br/>
<font size="14"><b>1. Executive Summary</b></font>
<br/>
{{ executive_summary }}
<br/><br/>
<font size="14"><b>2. Financial Analysis</b></font>
<br/>
{{ financial_analysis }}
<br/><br/>
<font size="14"><b>3. External Risk Analysis</b></font>
<br/>
{{ external_risk_analysis }}
<br/><br/>
<font size="14"><b>4. SWOT Analysis</b></font>
<br/>
<b>Strengths:</b>
{% for item in swot.strengths %}
<br/>&#8226; {{ item }}
{% endfor %}
<br/><br/>
<b>Weaknesses:</b>
{% for item in swot.weaknesses %}
<br/>&#8226; {{ item }}
{% endfor %}
<br/><br/>
<b>Opportunities:</b>
{% for item in swot.opportunities %}
<br/>&#8226; {{ item }}
{% endfor %}
<br/><br/>
<b>Threats:</b>
{% for item in swot.threats %}
<br/>&#8226; {{ item }}
{% endfor %}
<br/><br/>
<font size="14"><b>5. Final Recommendation</b></font>
<br/>
<i>{{ final_recommendation }}</i>
"""

SYSTEM_PROMPT = """You are a Senior Investment Analyst. 
You are provided with structured data containing entity details, financial metrics, external news signals, and a risk evaluation.

Your task is to synthesize this information into a comprehensive Investment Report.
You must return your output strictly in the following JSON format:
{
  "executive_summary": "<summary text>",
  "financial_analysis": "<analysis of metrics>",
  "external_risk_analysis": "<analysis of news and external signals>",
  "swot": {
    "strengths": ["...", "..."],
    "weaknesses": ["...", "..."],
    "opportunities": ["...", "..."],
    "threats": ["...", "..."]
  },
  "final_recommendation": "<final recommendation text>"
}
Do not return any text outside the JSON block. Do not use markdown backticks for the JSON.
"""

# ---------------------------------------------------------------------------
# Generation Logic
# ---------------------------------------------------------------------------

def generate_report_content(
    entity_details: dict[str, Any],
    financial_metrics: dict[str, Any],
    external_signals: dict[str, Any],
    risk_evaluation: dict[str, Any],
) -> dict[str, Any]:
    """Use OpenAI gpt-4o-mini to generate structured JSON report content."""
    logger.info("Generating LLM investment report...")
    client = _get_openai_client()

    payload = {
        "entity_details": entity_details,
        "financial_metrics": financial_metrics,
        "external_signals": external_signals,
        "risk_evaluation": risk_evaluation,
    }

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, indent=2)},
            ],
            temperature=0.3, 
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned empty content for report.")

        result = json.loads(content)
        return result

    except Exception as exc:
        logger.exception("Failed to generate report content.")
        raise RuntimeError(f"OpenAI completion failed: {exc}") from exc


def generate_pdf_report(report_data: dict[str, Any], entity_name: str, output_path: str) -> str:
    """
    Format the JSON report data using Jinja2 and export it as a PDF using ReportLab.
    
    Returns the absolute output_path of the generated PDF.
    """
    logger.info("Generating PDF report for '%s'...", entity_name)
    
    # 1. Jinja2 formatting
    template = Template(REPORT_TEMPLATE.strip())
    # Merge entity name directly into context
    context = {"entity_name": entity_name, **report_data}
    rendered_text = template.render(context)
    
    # 2. ReportLab PDF Generation
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        output_path, 
        pagesize=letter,
        rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    # We create a custom style permitting ReportLab's basic HTML-like tags
    base_style = ParagraphStyle(
        name="ReportBody",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,          # Line spacing
        spaceAfter=12,
    )
    
    # ReportLab Paragraph can sometimes struggle with massive single blocks, 
    # so we split the templated string by double-newlines into multiple Paragraphs.
    blocks = [b.strip() for b in rendered_text.split("\n\n") if b.strip()]
    
    flowables = []
    for block in blocks:
        # Paragraph supports tags like <b>, <i>, <font>
        p = Paragraph(block.replace("\n", ""), base_style)
        flowables.append(p)
        flowables.append(Spacer(1, 6))
        
    try:
        doc.build(flowables)
        logger.info("PDF report successfully generated at: %s", output_path)
        return output_path
    except Exception as exc:
        logger.exception("PDF generation failed.")
        raise RuntimeError(f"Failed to generate PDF: {exc}") from exc
