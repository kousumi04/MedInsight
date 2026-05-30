"""Embedding helpers for PubMed RAG chunks."""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any

from config import EMBEDDING_MODEL_NAME, GEMINI_API_KEY

try:
    from langchain_core.embeddings import Embeddings
except ImportError:  # pragma: no cover - only reached before dependency install.
    Embeddings = object  # type: ignore[assignment,misc]

EMBEDDING_BATCH_SIZE = 100
LOCAL_EMBEDDING_DIMENSIONS = 384

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - only reached before dependency install.
    genai = None  # type: ignore[assignment]


class EmbeddingError(RuntimeError):
    """Raised when chunk embedding cannot be completed."""


class MedInsightEmbeddings(Embeddings):
    """LangChain embedding adapter backed by MedInsight's embedding logic."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents for vector storage."""

        return embed_texts(texts, task_type="retrieval_document")

    def embed_query(self, text: str) -> list[float]:
        """Embed a query for vector retrieval."""

        return embed_texts([text], task_type="retrieval_query")[0]


def embed_texts(
    texts: list[str],
    task_type: str = "retrieval_document",
) -> list[list[float]]:
    """Embed texts, falling back locally when Gemini is unavailable or limited."""

    if not texts:
        return []

    if os.getenv("USE_GEMINI_EMBEDDINGS", "").casefold() not in {"1", "true", "yes"}:
        return [_embed_text_locally(text) for text in texts]

    try:
        _configure_gemini()
        model_name = _resolve_embedding_model()
        embeddings: list[list[float]] = []

        for batch in _batched(texts, EMBEDDING_BATCH_SIZE):
            response = genai.embed_content(
                model=model_name,
                content=batch,
                task_type=task_type,
            )

            batch_embeddings = _parse_embeddings(response)
            if len(batch_embeddings) != len(batch):
                raise EmbeddingError("Gemini returned an unexpected embedding count.")
            if not batch_embeddings:
                raise EmbeddingError("Gemini returned an empty embedding.")
            embeddings.extend(batch_embeddings)

        return embeddings
    except Exception:
        return [_embed_text_locally(text) for text in texts]


def embed_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return chunks with an ``embedding`` key added to each chunk."""

    texts = [str(chunk.get("text", "")) for chunk in chunks]
    embeddings = embed_texts(texts)

    embedded_chunks: list[dict[str, Any]] = []
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        embedded_chunk = dict(chunk)
        embedded_chunk["embedding"] = embedding
        embedded_chunks.append(embedded_chunk)

    return embedded_chunks


def _configure_gemini() -> None:
    """Configure Gemini for embeddings."""

    if genai is None:
        raise EmbeddingError(
            "google-generativeai is not installed. Install requirements first."
        )
    if not GEMINI_API_KEY:
        raise EmbeddingError("GEMINI_API_KEY is not configured.")

    genai.configure(api_key=GEMINI_API_KEY)


def _resolve_embedding_model() -> str:
    """Return a configured embedding model, falling back to an available one."""

    available_models = _list_embedding_models()
    if not available_models or EMBEDDING_MODEL_NAME in available_models:
        return EMBEDDING_MODEL_NAME

    preferred_models = [
        "models/gemini-embedding-001",
        "models/gemini-embedding-2",
        "models/gemini-embedding-2-preview",
    ]
    for model_name in preferred_models:
        if model_name in available_models:
            return model_name

    return available_models[0]


def _list_embedding_models() -> list[str]:
    """List Gemini models that support embedContent."""

    try:
        return [
            model.name
            for model in genai.list_models()
            if "embedContent"
            in (getattr(model, "supported_generation_methods", []) or [])
        ]
    except Exception:
        return []


def _parse_embeddings(response: Any) -> list[list[float]]:
    """Normalize Gemini embedding response formats into float vectors."""

    if isinstance(response, dict):
        values = response.get("embedding", [])
    else:
        values = getattr(response, "embedding", [])

    if not values:
        return []

    if isinstance(values[0], list):
        return [[float(value) for value in embedding] for embedding in values]

    return [[float(value) for value in values]]


def _batched(items: list[str], batch_size: int) -> list[list[str]]:
    """Split a list into API-sized batches."""

    return [
        items[start : start + batch_size]
        for start in range(0, len(items), batch_size)
    ]


def _embed_text_locally(text: str) -> list[float]:
    """Create a stable hashing-vector embedding as an offline fallback."""

    vector = [0.0] * LOCAL_EMBEDDING_DIMENSIONS
    tokens = re.findall(r"[a-z0-9][a-z0-9+-]*", text.casefold())
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % LOCAL_EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    magnitude = math.sqrt(sum(value * value for value in vector))
    if not magnitude:
        return vector

    return [value / magnitude for value in vector]
