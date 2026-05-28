"""FastAPI entrypoint for MedInsight."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.query_engine.userquery import process_user_query
from backend.rag.database import RagStorageError, refresh_pubmed_collection
from backend.search.fetch import build_pubmed_query, fetch_pubmed_papers


app = FastAPI(title="MedInsight API", version="0.1.0")
logger = logging.getLogger(__name__)


class KeywordRequest(BaseModel):
    """Request body for keyword extraction testing."""

    query: str = Field(..., min_length=1, description="Medical research query")


class KeywordResponse(BaseModel):
    """Structured keyword extraction response."""

    original_query: str
    extracted_keywords: list[str]
    cleaned_keywords: list[str]


class PubMedSearchRequest(BaseModel):
    """Request body for PubMed fetch testing."""

    keywords: list[str] = Field(
        ...,
        min_length=1,
        description="Extracted medical keywords to search in PubMed",
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of PubMed papers to return",
    )


class PubMedPaper(BaseModel):
    """Structured PubMed paper metadata."""

    pmid: str
    pmcid: str
    title: str
    abstract: str
    full_text_paragraphs: list[str]
    authors: list[str]
    journal: str
    publication_date: str
    doi: str
    pubmed_url: str
    pmc_url: str
    keywords_used: list[str]


class PubMedSearchResponse(BaseModel):
    """Response body for PubMed fetch testing."""

    keywords: list[str]
    pubmed_query: str
    count: int
    papers: list[PubMedPaper]


@app.get("/health")
def health_check() -> dict[str, str]:
    """Confirm that the API is running."""

    return {"status": "ok"}


@app.post("/query/keywords", response_model=KeywordResponse)
def extract_query_keywords(request: KeywordRequest) -> dict[str, object]:
    """Extract medical research keywords from a user query."""

    try:
        return process_user_query(request.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/search/pubmed", response_model=PubMedSearchResponse)
def search_pubmed_papers(request: PubMedSearchRequest) -> dict[str, object]:
    """Fetch PubMed papers for extracted medical keywords."""

    cleaned_keywords = [
        keyword.strip()
        for keyword in request.keywords
        if isinstance(keyword, str) and keyword.strip()
    ]
    if not cleaned_keywords:
        raise HTTPException(
            status_code=400,
            detail="At least one non-empty keyword is required.",
        )

    try:
        pubmed_query = build_pubmed_query(cleaned_keywords)
        papers = fetch_pubmed_papers(
            cleaned_keywords,
            max_results=request.max_results,
        )
        refresh_pubmed_collection({"papers": papers})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RagStorageError as exc:
        logger.exception("Failed to refresh temporary RAG collection.")
        raise HTTPException(
            status_code=500,
            detail="PubMed search succeeded, but temporary RAG storage failed.",
        ) from exc

    return {
        "keywords": cleaned_keywords,
        "pubmed_query": pubmed_query,
        "count": len(papers),
        "papers": papers,
    }
