"""
api.py
======
FastAPI backend for financial document classification and extraction.

Endpoints
---------
Classification & Review
  POST  /classify             Upload a document, classify it, return metadata.
  POST  /review               Submit a human review decision.
  GET   /metadata/{doc_id}    Get current metadata for a document.
  GET   /metadata             List all metadata (optional ?status= filter).

Schema Management
  GET   /schemas              List all category schemas.
  GET   /schemas/{category}   Get the schema for a specific category.
  POST  /schemas              Create or update a category schema.
  DELETE /schemas/{category}  Delete a custom schema (reverts to default).

Extraction
  POST  /extract/{doc_id}     Run extraction for an approved document.
  GET   /extractions/{doc_id} Retrieve a saved extraction result.

Ops
  GET   /health               Health check.

Run locally
-----------
    uvicorn doc_classifier.api:app --reload --port 8000

Environment variables
---------------------
  DOC_CLASSIFIER_STORE_DIR   Storage directory for metadata/extraction JSONs.
  DOC_CLASSIFIER_SCHEMA_DIR  Storage directory for schema JSONs.
  DOC_CLASSIFIER_UPLOAD_DIR  Permanent storage for uploaded documents.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Annotated, Any, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, field_validator

from extraction_pipeline import load_extraction, run_extraction
from metadata_store import (
    VALID_CATEGORIES,
    apply_review,
    list_metadata,
    load_metadata,
)
from pipeline import classify_document
from schema_store import (
    _DEFAULT_SCHEMA_DIR,
    delete_schema,
    list_schemas,
    load_schema,
    save_schema,
)

logger = logging.getLogger(__name__)

STORE_DIR: str  = os.environ.get("DOC_CLASSIFIER_STORE_DIR",  "review_metadata")
SCHEMA_DIR: str = os.environ.get("DOC_CLASSIFIER_SCHEMA_DIR", str(_DEFAULT_SCHEMA_DIR))
UPLOAD_DIR: str = os.environ.get("DOC_CLASSIFIER_UPLOAD_DIR", "uploaded_docs")

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Financial Document Classifier API",
    description=(
        "Classifies financial documents, supports human-in-the-loop review, "
        "manages dynamic extraction schemas, and runs schema-based extraction "
        "after category approval."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class OnboardingRequest(BaseModel):
    companyName: str
    cin: str
    pan: str
    sector: str
    subsector: str
    annualTurnover: float
    netProfit: float
    totalDebt: float
    ebitda: float
    loanType: str
    loanAmount: float
    loanTenure: int
    expectedInterestRate: float

class ReviewRequest(BaseModel):
    document_id: str
    final_category: str

    @field_validator("final_category")
    @classmethod
    def category_must_be_valid(cls, value: str) -> str:
        if value not in VALID_CATEGORIES:
            raise ValueError(
                f"'{value}' is not a valid category. "
                f"Choose one of: {sorted(VALID_CATEGORIES)}"
            )
        return value


class ReviewResponse(BaseModel):
    document_id: str
    filename: str
    model_prediction: str
    confidence: float
    final_category: Optional[str]
    status: str


class MetadataResponse(BaseModel):
    document_id: str
    filename: str
    model_prediction: str
    confidence: float
    final_category: Optional[str]
    status: str
    stored_filepath: Optional[str] = None


class SchemaRequest(BaseModel):
    """Payload for creating/updating a category schema."""
    category: str
    fields: dict[str, str]

    @field_validator("fields")
    @classmethod
    def validate_field_types(cls, fields: dict[str, str]) -> dict[str, str]:
        valid = {"string", "number", "date", "boolean"}
        for fname, ftype in fields.items():
            if ftype not in valid:
                raise ValueError(
                    f"Field '{fname}' has unsupported type '{ftype}'. "
                    f"Valid types: {sorted(valid)}"
                )
        return fields


class ExtractionResponse(BaseModel):
    document_id: str
    category: str
    filename: str
    extracted_records: list[dict[str, Any]]


class ResearchRequest(BaseModel):
    """Payload to trigger secondary research analysis for a company."""
    company_name: str
    sector: str


# --- Recommendation Schemas ---

class RecommendationRequest(BaseModel):
    financial_metrics: dict[str, Any]
    external_signals: dict[str, Any]
    sector_context: dict[str, Any]


class RecommendationResponse(BaseModel):
    risk_score: float
    risk_level: str
    loan_recommendation: str
    key_risk_factors: list[str]
    key_strengths: list[str]


# --- Report Schemas ---

class ReportRequest(BaseModel):
    entity_name: str
    entity_details: dict[str, Any]
    financial_metrics: dict[str, Any]
    external_signals: dict[str, Any]
    risk_evaluation: dict[str, Any]


class SWOTAnalysis(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]


class ReportResponse(BaseModel):
    executive_summary: str
    financial_analysis: str
    external_risk_analysis: str
    swot: SWOTAnalysis
    final_recommendation: str
    pdf_download_url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_upload_path(document_id: str, suffix: str) -> Path:
    """Return permanent storage path for an uploaded file."""
    upload_dir = Path(UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir / f"{document_id}{suffix}"


def _http_err(exc: Exception, code: int) -> HTTPException:
    return HTTPException(status_code=code, detail=str(exc))


# ===========================================================================
# Onboarding Endpoint
# ===========================================================================

@app.post(
    "/onboarding",
    status_code=status.HTTP_201_CREATED,
    summary="Save entity onboarding data",
    tags=["Onboarding"],
)
def onboarding_endpoint(payload: OnboardingRequest) -> dict[str, Any]:
    import uuid
    import json
    
    entity_id = str(uuid.uuid4())
    data = payload.model_dump()
    data["entity_id"] = entity_id
    
    store_path = Path(STORE_DIR)
    store_path.mkdir(parents=True, exist_ok=True)
    file_path = store_path / f"{entity_id}_onboarding.json"
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    return {
        "status": "success",
        "entity_id": entity_id,
        "message": "Entity onboarding saved successfully."
    }


# ===========================================================================
# Classification & Review Endpoints
# ===========================================================================

@app.post(
    "/classify",
    response_model=MetadataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and classify a financial document",
    tags=["Classification"],
)
async def classify_endpoint(
    file: Annotated[UploadFile, File(description="PDF, XLSX, XLS, or CSV document")],
) -> dict[str, Any]:
    """
    Upload a document, classify it, and persist the metadata record.

    The file is saved **permanently** to ``UPLOAD_DIR`` so the extraction
    pipeline can re-read it later.  The returned ``document_id`` is needed
    for ``POST /review`` and ``POST /extract/{document_id}``.
    """
    filename: str = file.filename or "unknown"
    suffix = os.path.splitext(filename)[-1].lower()
    allowed = {".pdf", ".xlsx", ".xls", ".xlsm", ".xlsb", ".ods", ".csv"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(allowed)}",
        )

    # Generate a preliminary UUID just to name the upload file.
    # The real UUID is assigned inside classify_document → create_metadata.
    import uuid as _uuid
    preliminary_id = str(_uuid.uuid4())
    upload_path = _get_upload_path(preliminary_id, suffix)

    try:
        with open(upload_path, "wb") as dest:
            shutil.copyfileobj(file.file, dest)
    except Exception as exc:
        logger.error("Failed to save upload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file.",
        ) from exc

    try:
        metadata = classify_document(
            str(upload_path),
            original_filename=filename,
            stored_filepath=str(upload_path),
            store_dir=STORE_DIR,
        )
    except (FileNotFoundError, ValueError) as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        logger.exception("Classification failed for '%s'", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Classification failed due to an internal error.",
        ) from exc

    return metadata


@app.post(
    "/review",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a human review decision",
    tags=["Review"],
)
def review_endpoint(payload: ReviewRequest) -> dict[str, Any]:
    """
    Apply a human reviewer's category decision.

    * ``model_prediction`` is never overwritten.
    * ``status`` → ``"approved"`` or ``"corrected_by_user"``.
    """
    try:
        return apply_review(payload.document_id, payload.final_category, store_dir=STORE_DIR)
    except FileNotFoundError as exc:
        raise _http_err(exc, status.HTTP_404_NOT_FOUND) from exc
    except ValueError as exc:
        raise _http_err(exc, status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    except Exception as exc:
        logger.exception("review failed for document_id='%s'", payload.document_id)
        raise _http_err(exc, status.HTTP_500_INTERNAL_SERVER_ERROR) from exc


@app.get(
    "/metadata/{document_id}",
    response_model=MetadataResponse,
    summary="Get metadata for a document",
    tags=["Metadata"],
)
def get_metadata_endpoint(document_id: str) -> dict[str, Any]:
    try:
        return load_metadata(document_id, store_dir=STORE_DIR)
    except FileNotFoundError as exc:
        raise _http_err(exc, status.HTTP_404_NOT_FOUND) from exc
    except ValueError as exc:
        raise _http_err(exc, status.HTTP_422_UNPROCESSABLE_ENTITY) from exc


@app.get(
    "/metadata",
    response_model=list[MetadataResponse],
    summary="List all metadata records",
    tags=["Metadata"],
)
def list_metadata_endpoint(
    status_filter: Annotated[
        Optional[str],
        Query(alias="status", description="Filter: awaiting_review | approved | corrected_by_user | extraction_complete"),
    ] = None,
) -> list[dict[str, Any]]:
    valid_statuses = {"awaiting_review", "approved", "corrected_by_user", "extraction_complete"}
    if status_filter and status_filter not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(valid_statuses)}",
        )
    return list_metadata(store_dir=STORE_DIR, status_filter=status_filter)


# ===========================================================================
# Schema Management Endpoints
# ===========================================================================

@app.get(
    "/schemas",
    summary="List all available category schemas",
    tags=["Schemas"],
)
def list_schemas_endpoint() -> list[dict[str, Any]]:
    """Return all schemas (custom + built-in defaults for missing ones)."""
    return list_schemas(schema_dir=SCHEMA_DIR)


@app.get(
    "/schemas/{category}",
    summary="Get the schema for a specific category",
    tags=["Schemas"],
)
def get_schema_endpoint(category: str) -> dict[str, Any]:
    """
    Return the schema for *category*.  Falls back to the built-in default
    if no custom schema has been saved.
    """
    try:
        return load_schema(category, schema_dir=SCHEMA_DIR)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.post(
    "/schemas",
    status_code=status.HTTP_201_CREATED,
    summary="Create or update a category schema",
    tags=["Schemas"],
)
def upsert_schema_endpoint(payload: SchemaRequest) -> dict[str, Any]:
    """
    Save (create or overwrite) the extraction schema for a category.

    Any future extraction for that category will use the updated schema.
    """
    try:
        schema = {"category": payload.category, "fields": payload.fields}
        return save_schema(schema, schema_dir=SCHEMA_DIR)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@app.delete(
    "/schemas/{category}",
    status_code=status.HTTP_200_OK,
    summary="Delete a custom schema (reverts to built-in default)",
    tags=["Schemas"],
)
def delete_schema_endpoint(category: str) -> dict[str, Any]:
    deleted = delete_schema(category, schema_dir=SCHEMA_DIR)
    return {
        "category": category,
        "deleted": deleted,
        "message": (
            f"Custom schema for '{category}' deleted. Built-in default is now active."
            if deleted else
            f"No custom schema found for '{category}'. Built-in default was already active."
        ),
    }


# ===========================================================================
# Extraction Endpoints
# ===========================================================================

@app.post(
    "/extract/{document_id}",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Run schema-based extraction for an approved document",
    tags=["Extraction"],
)
def extract_endpoint(document_id: str) -> dict[str, Any]:
    """
    Trigger the extraction pipeline for a reviewed document.

    **Pre-conditions**
    * Document status must be ``"approved"`` or ``"corrected_by_user"``.
    * The source file must be available at ``metadata.stored_filepath``.

    The extraction result is persisted and the document status is updated
    to ``"extraction_complete"``.
    """
    try:
        return run_extraction(
            document_id,
            store_dir=STORE_DIR,
            schema_dir=SCHEMA_DIR,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Extraction failed for document_id='%s'", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {exc}",
        ) from exc


@app.get(
    "/extractions/{document_id}",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve the saved extraction result for a document",
    tags=["Extraction"],
)
def get_extraction_endpoint(document_id: str) -> dict[str, Any]:
    """
    Return a previously saved extraction result.

    Raises 404 if extraction has not yet been run for this document.
    """
    try:
        return load_extraction(document_id, store_dir=STORE_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.get(
    "/documents/{document_id}/extraction",
    status_code=status.HTTP_200_OK,
    summary="Get extracted data for the frontend extraction review page",
    tags=["Extraction"],
)
def get_document_extraction_endpoint(document_id: str) -> dict[str, Any]:
    """
    Retrieve the extracted data for a document, returning a unified JSON 
    structure compatible with the extraction review frontend table.
    """
    try:
        metadata = load_metadata(document_id, store_dir=STORE_DIR)
        category = metadata.get("final_category") or metadata.get("model_prediction")
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc)
        ) from exc

    try:
        extraction = load_extraction(document_id, store_dir=STORE_DIR)
        return {
            "document_id": document_id,
            "category": category,
            "extracted_records": extraction.get("extracted_records", []),
            "status": "awaiting_validation",
        }
    except FileNotFoundError:
        return {
            "document_id": document_id,
            "category": category,
            "extracted_records": [],
            "status": "pending_extraction",
        }



class UpdateExtractionRequest(BaseModel):
    extracted_records: list[dict[str, Any]]


@app.post(
    "/documents/{document_id}/update-extraction",
    status_code=status.HTTP_200_OK,
    summary="Save edited extraction records for a document",
    tags=["Extraction"],
)
def update_extraction_endpoint(
    document_id: str,
    payload: UpdateExtractionRequest,
) -> dict[str, Any]:
    """
    Overwrite the stored extraction result for a document with the
    records provided by the frontend (after human editing).

    Does not change the document status — call ``approve-extraction``
    to mark the extraction as complete.
    """
    try:
        metadata = load_metadata(document_id, store_dir=STORE_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        ) from exc

    category = metadata.get("final_category") or metadata.get("model_prediction", "")
    filename = metadata.get("filename", "unknown")

    updated_result: dict[str, Any] = {
        "document_id": document_id,
        "category": category,
        "filename": filename,
        "extracted_records": payload.extracted_records,
    }

    try:
        from extraction_pipeline import save_extraction
        save_extraction(updated_result, store_dir=STORE_DIR)
    except Exception as exc:
        logger.exception("Failed to save updated extraction for document_id='%s'", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save updated extraction records.",
        ) from exc

    logger.info(
        "Extraction records updated: document_id=%s  records=%d",
        document_id, len(payload.extracted_records),
    )
    return {
        "document_id": document_id,
        "status": "updated",
        "message": "Extraction records saved successfully",
        "record_count": len(payload.extracted_records),
    }


@app.post(
    "/documents/{document_id}/approve-extraction",
    status_code=status.HTTP_200_OK,
    summary="Approve the extraction result for a document",
    tags=["Extraction"],
)
def approve_extraction_endpoint(document_id: str) -> dict[str, Any]:
    """
    Mark the extraction for a document as approved.

    Locates the document in the metadata store, updates its status to
    ``"extraction_complete"``, persists the change (individual file + consolidated
    index), and returns a confirmation payload.
    """
    from metadata_store import _metadata_path, _write_json, _load_index, _save_index

    try:
        metadata = load_metadata(document_id, store_dir=STORE_DIR)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    metadata["status"] = "extraction_complete"

    # Update individual per-doc file
    filepath = _metadata_path(document_id, STORE_DIR)
    try:
        _write_json(metadata, filepath)
    except Exception as exc:
        logger.exception("Failed to save metadata for document_id='%s'", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save updated metadata.",
        ) from exc

    # Sync consolidated index
    index = _load_index(STORE_DIR)
    index[document_id] = metadata
    _save_index(index, STORE_DIR)

    logger.info(
        "Extraction approved: document_id=%s  status='extraction_complete'",
        document_id,
    )
    return {
        "document_id": document_id,
        "status": "extraction_complete",
        "message": "Extraction approved successfully",
    }


# ===========================================================================
# Secondary Research Endpoints
# ===========================================================================

@app.post(
    "/research",
    status_code=status.HTTP_200_OK,
    summary="Run secondary research analysis (News + FinBERT + SBERT)",
    tags=["Research"],
)
def research_endpoint(payload: ResearchRequest) -> dict[str, Any]:
    """
    Fetch recent news using NewsAPI, extract article text, classify sentiment
    (FinBERT), and predict semantic risk category (SBERT).
    """
    from research import analyze_company_news
    try:
        return analyze_company_news(payload.company_name, payload.sector)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Research analysis failed for company='%s'", payload.company_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research generation failed: {exc}"
        ) from exc


# ===========================================================================
# Credit Recommendation Engine
# ===========================================================================

@app.post(
    "/recommend",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a credit recommendation using OpenAI",
    tags=["Recommendation"],
)
def recommend_endpoint(payload: RecommendationRequest) -> Any:
    """
    Pass the financial factors and external news signals into the risk LLM 
    for a final loan recommendation.
    """
    from recommendation import generate_recommendation
    try:
        res = generate_recommendation(
            payload.financial_metrics,
            payload.external_signals,
            payload.sector_context,
        )
        return res
    except RuntimeError as exc:
        if "API_KEY" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        ) from exc


# ===========================================================================
# Report Generation
# ===========================================================================

@app.post(
    "/report",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate comprehensive investment report and PDF",
    tags=["Report"],
)
def report_endpoint(payload: ReportRequest) -> Any:
    """
    Produce a JSON report containing a SWOT analysis and save a downloadable PDF.
    """
    from report_generator import generate_report_content, generate_pdf_report
    import uuid
    import os
    
    try:
        # LLM JSON Generation
        report_data = generate_report_content(
            payload.entity_details,
            payload.financial_metrics,
            payload.external_signals,
            payload.risk_evaluation,
        )
        
        # PDF Formatting
        report_id = str(uuid.uuid4())
        filename = f"{payload.entity_name.replace(' ', '_')}_{report_id}.pdf"
        output_path = str(STORE_DIR / filename)
        
        generate_pdf_report(report_data, payload.entity_name, output_path)
        
        # Attach URL to JSON response
        report_data["pdf_download_url"] = f"/reports/{filename}"
        
        return report_data
        
    except RuntimeError as exc:
        if "API_KEY" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        ) from exc


@app.get(
    "/reports/{filename}",
    status_code=status.HTTP_200_OK,
    summary="Download generated PDF report",
    tags=["Report"],
)
def download_report_endpoint(filename: str):
    """Retrieve the generated PDF report from disk."""
    file_path = STORE_DIR / filename
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found."
        )
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/pdf"
    )


# ===========================================================================
# Credit Decision Dashboard (Analysis)
# ===========================================================================

@app.get(
    "/analysis/{entity_id}",
    status_code=status.HTTP_200_OK,
    summary="Generate comprehensive credit analysis for an entity",
    tags=["Analysis"],
)
def get_analysis_endpoint(entity_id: str) -> dict[str, Any]:
    """
    1. Load entity onboarding data
    2. Load extracted financial data 
    3. Load secondary research results
    4. Run risk evaluation model
    """
    import json
    
    # 1. Load onboarding data
    onboarding_path = Path(STORE_DIR) / f"{entity_id}_onboarding.json"
    if not onboarding_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding data not found for entity '{entity_id}'"
        )
        
    with open(onboarding_path, "r", encoding="utf-8") as f:
        onboarding_data = json.load(f)
        
    company_name = onboarding_data.get("companyName", "Unknown Company")
    sector = onboarding_data.get("sector", "Unknown Sector")
    
    # Baseline financial summary from onboarding
    financial_summary = {
        "revenue": onboarding_data.get("annualTurnover", 0),
        "ebitda": onboarding_data.get("ebitda", 0),
        "net_profit": onboarding_data.get("netProfit", 0),
        "total_debt": onboarding_data.get("totalDebt", 0),
    }

    # 2. Load extracted structured data across all documents
    extracted_records = []
    store_path = Path(STORE_DIR)
    for ext_file in store_path.glob("*_extraction.json"):
        try:
            with open(ext_file, "r", encoding="utf-8") as f:
                ext_data = json.load(f)
                if "extracted_records" in ext_data:
                    extracted_records.extend(ext_data["extracted_records"])
        except Exception as e:
            logger.warning("Failed to load extraction file %s: %s", ext_file, e)

    # Overwrite financial summary with extracted data if available
    for record in extracted_records:
        if "revenue" in record or "total_revenue" in record:
            financial_summary["revenue"] = record.get("revenue") or record.get("total_revenue", financial_summary["revenue"])
        if "ebitda" in record:
            financial_summary["ebitda"] = record.get("ebitda", financial_summary["ebitda"])
        if "net_profit" in record or "pat" in record:
            financial_summary["net_profit"] = record.get("net_profit") or record.get("pat", financial_summary["net_profit"])
        if "total_debt" in record or "borrowings" in record:
            financial_summary["total_debt"] = record.get("total_debt") or record.get("borrowings", financial_summary["total_debt"])

    # 3. Load secondary research results (FinBERT & news)
    try:
        from research import analyze_company_news
        external_signals = analyze_company_news(company_name, sector)
    except Exception as e:
        logger.warning("Failed to fetch secondary research: %s", e)
        external_signals = {
            "top_news": [],
            "average_sentiment": 0.0,
            "overall_sentiment_label": "Neutral",
            "semantic_risk_category": "Unknown",
            "finbert_distribution": {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 1.0}
        }

    # 4. Run risk evaluation model
    sector_context = {
        "sector": sector,
        "subsector": onboarding_data.get("subsector", ""),
        "loan_type": onboarding_data.get("loanType", "")
    }
    
    try:
        from recommendation import generate_recommendation
        from report_generator import generate_report_content
        
        recommendation = generate_recommendation(
            financial_metrics=financial_summary,
            external_signals=external_signals,
            sector_context=sector_context
        )
        
        report = generate_report_content(
            entity_details=onboarding_data,
            financial_metrics=financial_summary,
            external_signals=external_signals,
            risk_evaluation=recommendation
        )
        swot = report.get("swot", {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []})
        
    except Exception as e:
        logger.error("Failed to generate recommendation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate credit recommendation. Ensure OPENAI_API_KEY is active."
        )

    return {
        "entity_id": entity_id,
        "risk_score": recommendation.get("risk_score", 50.0),
        "risk_level": recommendation.get("risk_level", "Unknown"),
        "loan_recommendation": recommendation.get("loan_recommendation", "Unknown"),
        "recommended_amount": onboarding_data.get("loanAmount", 0),
        "swot_analysis": swot,
        "financial_summary": financial_summary
    }


@app.get(
    "/analysis/{entity_id}/report",
    status_code=status.HTTP_200_OK,
    summary="Download credit analysis report as PDF",
    tags=["Analysis"],
)
def download_analysis_report_endpoint(entity_id: str):
    import uuid
    import json
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    
    # 1. Load the analysis results
    analysis_data = get_analysis_endpoint(entity_id)
    
    # 2. Load entity information
    onboarding_path = Path(STORE_DIR) / f"{entity_id}_onboarding.json"
    with open(onboarding_path, "r", encoding="utf-8") as f:
        onboarding_data = json.load(f)
        
    company_name = onboarding_data.get("companyName", "Unknown Company")
    cin = onboarding_data.get("cin", "N/A")
    sector = onboarding_data.get("sector", "N/A")
    subsector = onboarding_data.get("subsector", "N/A")
    
    financials = analysis_data["financial_summary"]
    risk_score = analysis_data["risk_score"]
    risk_level = analysis_data["risk_level"]
    loan_rec = analysis_data["loan_recommendation"]
    rec_amount = analysis_data["recommended_amount"]
    swot = analysis_data["swot_analysis"]

    # 3. Generate PDF
    report_id = str(uuid.uuid4())
    filename = f"{company_name.replace(' ', '_')}_{report_id}_analysis.pdf"
    output_path = str(Path(STORE_DIR) / filename)
    
    doc = SimpleDocTemplate(
        output_path, 
        pagesize=letter,
        rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50
    )
    styles = getSampleStyleSheet()
    heading_style = styles["Heading1"]
    subheading_style = styles["Heading2"]
    normal_style = styles["Normal"]
    
    flowables = []
    
    # Header
    flowables.append(Paragraph("<b>NineTales</b>", heading_style))
    flowables.append(Paragraph("Enterprise Credit Underwriting System", normal_style))
    flowables.append(Paragraph("<b>Credit Risk Assessment Report</b>", subheading_style))
    flowables.append(Spacer(1, 12))
    
    # Entity Information
    flowables.append(Paragraph("<b>Entity Information</b>", subheading_style))
    flowables.append(Paragraph(f"<b>Company Name:</b> {company_name}", normal_style))
    flowables.append(Paragraph(f"<b>CIN:</b> {cin}", normal_style))
    flowables.append(Paragraph(f"<b>Sector:</b> {sector}", normal_style))
    flowables.append(Paragraph(f"<b>Subsector:</b> {subsector}", normal_style))
    flowables.append(Spacer(1, 12))
    
    # Financial Summary
    flowables.append(Paragraph("<b>Financial Summary</b>", subheading_style))
    flowables.append(Paragraph(f"<b>Revenue:</b> {financials.get('revenue', 0)}", normal_style))
    flowables.append(Paragraph(f"<b>EBITDA:</b> {financials.get('ebitda', 0)}", normal_style))
    flowables.append(Paragraph(f"<b>Net Profit:</b> {financials.get('net_profit', 0)}", normal_style))
    flowables.append(Paragraph(f"<b>Total Debt:</b> {financials.get('total_debt', 0)}", normal_style))
    flowables.append(Spacer(1, 12))
    
    # Risk Assessment
    flowables.append(Paragraph("<b>Risk Assessment</b>", subheading_style))
    flowables.append(Paragraph(f"<b>Risk Score:</b> {risk_score}", normal_style))
    flowables.append(Paragraph(f"<b>Risk Level:</b> {risk_level}", normal_style))
    flowables.append(Spacer(1, 12))
    
    # Loan Recommendation
    flowables.append(Paragraph("<b>Loan Recommendation</b>", subheading_style))
    flowables.append(Paragraph(f"<b>Recommendation:</b> {loan_rec}", normal_style))
    flowables.append(Paragraph(f"<b>Recommended Loan Amount:</b> {rec_amount}", normal_style))
    flowables.append(Spacer(1, 12))
    
    # SWOT Analysis
    flowables.append(Paragraph("<b>SWOT Analysis</b>", subheading_style))
    
    flowables.append(Paragraph("<b>Strengths:</b>", normal_style))
    for item in swot.get("strengths", []):
        flowables.append(Paragraph(f"• {item}", normal_style))
        
    flowables.append(Paragraph("<b>Weaknesses:</b>", normal_style))
    for item in swot.get("weaknesses", []):
        flowables.append(Paragraph(f"• {item}", normal_style))
        
    flowables.append(Paragraph("<b>Opportunities:</b>", normal_style))
    for item in swot.get("opportunities", []):
        flowables.append(Paragraph(f"• {item}", normal_style))
        
    flowables.append(Paragraph("<b>Threats:</b>", normal_style))
    for item in swot.get("threats", []):
        flowables.append(Paragraph(f"• {item}", normal_style))
        
    doc.build(flowables)
    
    return FileResponse(
        path=output_path,
        filename=filename,
        media_type="application/pdf"
    )

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Ops"], summary="Health check")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
