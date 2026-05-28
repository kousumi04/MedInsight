"""Create an embedding for a validated user query."""

from __future__ import annotations

import re
from typing import Any

try:
    from backend.rag.embedding import EmbeddingError, embed_texts
except ImportError:  # Allows direct execution from inside backend/query_engine.
    from rag.embedding import EmbeddingError, embed_texts


MAX_QUERY_WORDS = 15


def create_user_query_embedding(query: str) -> dict[str, Any]:
    """Validate one user query and return its embedding."""

    normalized_query = validate_single_query(query)

    try:
        embedding = embed_texts(
            [normalized_query],
            task_type="retrieval_query",
        )[0]
    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError("Failed to create user query embedding.") from exc

    return {
        "original_query": normalized_query,
        "embedding": embedding,
        "embedding_dimensions": len(embedding),
    }


def validate_single_query(query: str) -> str:
    """Allow exactly one short query per prompt."""

    if not isinstance(query, str):
        raise ValueError("Query must be a string.")

    if re.search(r"[;\n\r]", query):
        raise ValueError("Please ask only one query per prompt.")

    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("Query cannot be empty.")

    words = re.findall(r"\b[\w'-]+\b", normalized_query)
    if len(words) > MAX_QUERY_WORDS:
        raise ValueError(f"Please ask only one query within {MAX_QUERY_WORDS} words.")

    if normalized_query.count("?") > 1:
        raise ValueError("Please ask only one question per prompt.")

    return normalized_query


def main() -> None:
    """Prompt for one query and print embedding metadata."""

    query = input("Enter one medical query: ")
    result = create_user_query_embedding(query)
    print(f"Query: {result['original_query']}")
    print(f"Embedding dimensions: {result['embedding_dimensions']}")
    print(result["embedding"])


if __name__ == "__main__":
    main()
