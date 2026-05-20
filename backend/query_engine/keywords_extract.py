"""Medical keyword extraction for MedInsight.

This module owns all Gemini-specific behavior for the query pipeline. The
public ``extract_keywords`` function returns a compact list of medical and
research concepts that downstream PubMed search can consume directly.
"""

from __future__ import annotations

import json
import re
from typing import Any

from config import (
    GEMINI_API_KEY,
    GEMINI_GENERATION_CONFIG,
    GEMINI_MODEL_NAME,
    GEMINI_SAFETY_SETTINGS,
    GENERIC_KEYWORDS,
    MAX_KEYWORDS,
    STOP_WORDS,
)

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - exercised only before install.
    genai = None  # type: ignore[assignment]


class KeywordExtractionError(RuntimeError):
    """Raised when Gemini returns no usable keyword payload."""


def extract_keywords(query: str) -> list[str]:
    """Extract concise medical/research keywords from a user query.

    Gemini is attempted first. If configuration, dependency, API, or response
    parsing fails, the function falls back to deterministic regex extraction so
    the rest of the RAG pipeline can still proceed.
    """

    normalized_query = _validate_query(query)

    try:
        model = _build_gemini_model()
        response_text = _call_gemini(model, normalized_query)
        parsed_keywords = _parse_keyword_response(response_text)
        cleaned_keywords = clean_keywords(parsed_keywords)
        if cleaned_keywords:
            return cleaned_keywords
        raise KeywordExtractionError("Gemini returned no usable keywords.")
    except Exception:
        return fallback_extract_keywords(normalized_query)


def clean_keywords(keywords: list[str]) -> list[str]:
    """Normalize, deduplicate, and remove generic/filler keyword candidates."""

    cleaned: list[str] = []
    seen: set[str] = set()

    for keyword in keywords:
        normalized = _normalize_keyword(keyword)
        if not normalized:
            continue

        comparable = normalized.casefold()
        if comparable in seen or comparable in GENERIC_KEYWORDS:
            continue

        # Keep multi-word medical terms intact, but drop standalone filler.
        if comparable in STOP_WORDS:
            continue

        cleaned.append(normalized)
        seen.add(comparable)

        if len(cleaned) >= MAX_KEYWORDS:
            break

    return cleaned


def fallback_extract_keywords(query: str) -> list[str]:
    """Extract keywords locally when Gemini is unavailable.

    This is intentionally conservative. It keeps medically useful phrases such
    as drug names, biomarkers, and condition/treatment pairs while filtering
    common conversational wording.
    """

    normalized_query = re.sub(r"[?!.;:,]", " ", query)
    candidates = re.split(
        r"\b(?:and|or|for|with|using|about|on|in|to|from)\b",
        normalized_query,
        flags=re.IGNORECASE,
    )
    keywords: list[str] = []

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue

        words = [
            word
            for word in candidate.split()
            if word.casefold().strip("?:,.") not in STOP_WORDS
        ]
        if not words:
            continue

        phrase = " ".join(words)
        phrase = re.sub(r"\s+", " ", phrase).strip(" ,.;:?!")
        if len(phrase) < 3:
            continue

        keywords.append(phrase)

    return clean_keywords(keywords)


def _build_gemini_model() -> Any:
    """Configure and return a Gemini model instance."""

    if genai is None:
        raise KeywordExtractionError(
            "google-generativeai is not installed. Install requirements first."
        )

    if not GEMINI_API_KEY:
        raise KeywordExtractionError("GEMINI_API_KEY is not configured.")

    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL_NAME,
        generation_config=GEMINI_GENERATION_CONFIG,
        safety_settings=GEMINI_SAFETY_SETTINGS,
    )


def _call_gemini(model: Any, query: str) -> str:
    """Send the extraction prompt to Gemini and return raw response text."""

    prompt = f"""
You extract medical research keywords for PubMed search.

Return ONLY valid JSON in this exact shape:
{{"keywords": ["keyword 1", "keyword 2"]}}

Extract important concepts only:
- diseases
- drugs
- treatments
- biomarkers
- clinical concepts
- medical conditions
- therapies
- study topics


Ignore question words, stop words, conversational text, and generic phrases.
Preserve multi-word medical terms exactly when useful.
Limit the list to {MAX_KEYWORDS} concise keywords.

User query:
{query}
""".strip()

    response = model.generate_content(prompt)
    response_text = getattr(response, "text", "") or ""
    if not response_text.strip():
        raise KeywordExtractionError("Gemini returned an empty response.")

    return response_text


def _parse_keyword_response(response_text: str) -> list[str]:
    """Parse Gemini JSON, accepting fenced JSON if the model adds it."""

    json_text = _strip_markdown_fence(response_text)

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise KeywordExtractionError("Gemini returned invalid JSON.") from exc

    keywords = payload.get("keywords")
    if not isinstance(keywords, list):
        raise KeywordExtractionError("Gemini response is missing keywords list.")

    return [str(keyword) for keyword in keywords if isinstance(keyword, str)]


def _validate_query(query: str) -> str:
    """Validate and normalize user input before extraction."""

    if not isinstance(query, str):
        raise ValueError("Query must be a string.")

    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Query cannot be empty.")

    return normalized_query


def _normalize_keyword(keyword: str) -> str:
    """Trim punctuation and whitespace without damaging medical phrases."""

    keyword = re.sub(r"\s+", " ", keyword).strip()
    keyword = keyword.strip(" \t\n\r\"'`[]{}()<>.,;:?!")
    return keyword


def _strip_markdown_fence(text: str) -> str:
    """Remove common ```json fences before JSON parsing."""

    stripped = text.strip()
    fenced_match = re.fullmatch(
        r"```(?:json)?\s*(?P<body>.*?)\s*```",
        stripped,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced_match:
        return fenced_match.group("body").strip()

    return stripped

