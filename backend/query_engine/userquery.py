"""User query orchestration for MedInsight keyword extraction."""

from __future__ import annotations

from typing import Any

try:
    from .keywords_extract import clean_keywords, extract_keywords
except ImportError:  # Allows direct execution during local smoke tests.
    from keywords_extract import clean_keywords, extract_keywords


def process_user_query(query: str) -> dict[str, Any]:
    """Process a medical research query into structured keyword data.

    This function is intentionally framework-agnostic so a future FastAPI route
    can call it directly without mixing HTTP concerns into extraction logic.
    """

    normalized_query = _validate_query(query)

    try:
        extracted_keywords = extract_keywords(normalized_query)
        cleaned_keywords = clean_keywords(extracted_keywords)
    except Exception as exc:
        raise RuntimeError("Failed to process user query.") from exc

    return {
        "original_query": normalized_query,
        "extracted_keywords": extracted_keywords,
        "cleaned_keywords": cleaned_keywords,
    }


def _validate_query(query: str) -> str:
    """Validate user query input before sending it downstream."""

    if not isinstance(query, str):
        raise ValueError("Query must be a string.")

    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Query cannot be empty.")

    return normalized_query
