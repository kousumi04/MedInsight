"""Answer synthesis over retrieved PubMed chunks."""

from __future__ import annotations

from typing import Any

from config import (
    GEMINI_API_KEY,
    GEMINI_GENERATION_CONFIG,
    GEMINI_MODEL_NAME,
    GEMINI_SAFETY_SETTINGS,
)

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - only reached before dependency install.
    genai = None  # type: ignore[assignment]


class AnsweringError(RuntimeError):
    """Raised when answer generation fails."""


def generate_answer(query: str, chunks: list[dict[str, Any]]) -> str:
    """Generate a concise answer using only retrieved chunks."""

    if not chunks:
        return "I could not find enough relevant PubMed context to answer this query."

    try:
        model = _build_model()
        response = model.generate_content(_build_prompt(query, chunks))
        answer = (getattr(response, "text", "") or "").strip()
        if answer:
            return answer
    except Exception as exc:
        raise AnsweringError("Failed to generate answer from retrieved chunks.") from exc

    raise AnsweringError("Gemini returned an empty answer.")


def fallback_answer(query: str, chunks: list[dict[str, Any]]) -> str:
    """Return an extractive answer when generation is unavailable."""

    if not chunks:
        return "I could not find enough relevant PubMed context to answer this query."

    lines = [
        "Based on the nearest PubMed chunks, the most relevant findings are:",
    ]
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata", {}) or {}
        title = metadata.get("title") or f"Retrieved chunk {index}"
        text = str(chunk.get("text", "")).strip()
        lines.append(f"{index}. {title}: {text}")

    return "\n\n".join(lines)


def _build_model() -> Any:
    """Configure and return the Gemini generation model."""

    if genai is None:
        raise AnsweringError(
            "google-generativeai is not installed. Install requirements first."
        )
    if not GEMINI_API_KEY:
        raise AnsweringError("GEMINI_API_KEY is not configured.")

    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL_NAME,
        generation_config={**GEMINI_GENERATION_CONFIG, "response_mime_type": "text/plain"},
        safety_settings=GEMINI_SAFETY_SETTINGS,
    )


def _build_prompt(query: str, chunks: list[dict[str, Any]]) -> str:
    """Build a grounded RAG prompt from retrieved chunks."""

    context_blocks = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata", {}) or {}
        title = metadata.get("title", "")
        pubmed_url = metadata.get("pubmed_url", "")
        context_blocks.append(
            "\n".join(
                [
                    f"[{index}] {title}",
                    f"URL: {pubmed_url}",
                    str(chunk.get("text", "")),
                ]
            )
        )

    context = "\n\n".join(context_blocks)
    return f"""
You are MedInsight, a clinical research assistant.

Answer the user query using only the retrieved PubMed context below.
Be concise, clinically careful, and mention uncertainty when the context is limited.
Do not invent citations or facts outside the context.

User query:
{query}

Retrieved PubMed context:
{context}
""".strip()
