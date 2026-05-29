"""Temporary ChromaDB storage for PubMed RAG chunks."""

from __future__ import annotations

import json
from typing import Any

from config import (
    CHROMA_API_KEY,
    CHROMA_COLLECTION_NAME,
    CHROMA_DATABASE,
    CHROMA_LOCAL_PATH,
    CHROMA_TENANT,
)

from backend.rag.chunking import chunk_pubmed_papers
from backend.rag.embedding import EmbeddingError, embed_chunks

try:
    import chromadb
except ImportError:  # pragma: no cover - only reached before dependency install.
    chromadb = None  # type: ignore[assignment]


class RagStorageError(RuntimeError):
    """Raised when temporary RAG storage cannot be refreshed."""


def refresh_pubmed_collection(
    pubmed_result: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, int | str]:
    """Delete previous temporary chunks and store chunks for a new search.

    This function is intentionally destructive for the target collection:
    every new PubMed search replaces the previous temporary RAG context.
    """

    try:
        client = _get_chroma_client()
        _delete_collection_if_exists(client, CHROMA_COLLECTION_NAME)
    except RagStorageError:
        raise
    except Exception as exc:
        raise RagStorageError("Failed to connect to ChromaDB.") from exc

    return upsert_pubmed_collection(pubmed_result)


def upsert_pubmed_collection(
    pubmed_result: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, int | str]:
    """Embed PubMed chunks and upsert them into the RAG collection."""

    chunks = chunk_pubmed_papers(pubmed_result)

    try:
        client = _get_chroma_client()
        collection = client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)
    except RagStorageError:
        raise
    except Exception as exc:
        raise RagStorageError("Failed to connect to ChromaDB.") from exc

    if not chunks:
        return {
            "collection": CHROMA_COLLECTION_NAME,
            "papers_used": 0,
            "chunks_stored": 0,
        }

    try:
        embedded_chunks = embed_chunks(chunks)
        collection.upsert(
            ids=[str(chunk["chunk_id"]) for chunk in chunks],
            documents=[str(chunk["text"]) for chunk in chunks],
            embeddings=[
                chunk["embedding"]
                for chunk in embedded_chunks
            ],
            metadatas=[
                _prepare_metadata(chunk.get("metadata", {}))
                for chunk in chunks
            ],
        )
    except EmbeddingError as exc:
        raise RagStorageError("Failed to embed PubMed chunks.") from exc
    except Exception as exc:
        raise RagStorageError("Failed to save chunks in ChromaDB.") from exc

    paper_ids = {
        str(chunk.get("metadata", {}).get("pmid", ""))
        for chunk in chunks
        if chunk.get("metadata", {}).get("pmid")
    }

    return {
        "collection": CHROMA_COLLECTION_NAME,
        "papers_used": len(paper_ids),
        "chunks_stored": len(chunks),
    }


def query_similar_chunks(
    query_embedding: list[float],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Return the nearest stored chunks for a user query embedding."""

    if not query_embedding:
        raise RagStorageError("Query embedding cannot be empty.")

    try:
        client = _get_chroma_client()
        collection = client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        raise RagStorageError("Failed to query ChromaDB chunks.") from exc

    documents = _first_result_list(result.get("documents", []))
    metadatas = _first_result_list(result.get("metadatas", []))
    distances = _first_result_list(result.get("distances", []))
    ids = _first_result_list(result.get("ids", []))

    chunks: list[dict[str, Any]] = []
    for index, document in enumerate(documents):
        chunks.append(
            {
                "id": str(ids[index]) if index < len(ids) else "",
                "text": str(document),
                "metadata": metadatas[index] if index < len(metadatas) else {},
                "distance": float(distances[index]) if index < len(distances) else None,
            }
        )

    return chunks


def _get_chroma_client() -> Any:
    """Create a Chroma Cloud client when configured, otherwise local client."""

    if chromadb is None:
        raise RagStorageError("chromadb is not installed. Install requirements first.")

    if CHROMA_API_KEY and CHROMA_TENANT and CHROMA_DATABASE:
        return chromadb.CloudClient(
            api_key=CHROMA_API_KEY,
            tenant=CHROMA_TENANT,
            database=CHROMA_DATABASE,
        )

    return chromadb.PersistentClient(path=CHROMA_LOCAL_PATH)


def _delete_collection_if_exists(client: Any, collection_name: str) -> None:
    """Delete a collection if it exists."""

    try:
        client.delete_collection(name=collection_name)
    except Exception as exc:
        message = str(exc).lower()
        if "does not exist" in message or "not found" in message:
            return
        raise RagStorageError("Failed to clear previous ChromaDB data.") from exc


def _prepare_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Convert metadata into Chroma-supported scalar values."""

    prepared: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            prepared[key] = value
        elif value is None:
            prepared[key] = ""
        else:
            prepared[key] = json.dumps(value, ensure_ascii=False)

    return prepared


def _first_result_list(values: Any) -> list[Any]:
    """Normalize Chroma's one-query result lists."""

    if isinstance(values, list) and values and isinstance(values[0], list):
        return values[0]
    if isinstance(values, list):
        return values
    return []
