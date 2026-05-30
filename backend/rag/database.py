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
    MAX_STORED_CHUNKS,
)

from backend.rag.chunking import chunk_pubmed_papers
from backend.rag.embedding import EmbeddingError, MedInsightEmbeddings

try:
    import chromadb
except ImportError:  # pragma: no cover - only reached before dependency install.
    chromadb = None  # type: ignore[assignment]

try:
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
except ImportError:  # pragma: no cover - only reached before dependency install.
    Chroma = None  # type: ignore[assignment]
    Document = None  # type: ignore[assignment]


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

    chunks = chunk_pubmed_papers(pubmed_result)[:MAX_STORED_CHUNKS]

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
        vector_store = _get_vector_store(client)
        vector_store.add_documents(
            documents=[
                Document(
                    page_content=str(chunk["text"]),
                    metadata={
                        **_prepare_metadata(chunk.get("metadata", {})),
                        "id": str(chunk["chunk_id"]),
                    },
                )
                for chunk in chunks
            ],
            ids=[str(chunk["chunk_id"]) for chunk in chunks],
        )
    except EmbeddingError as exc:
        raise RagStorageError("Failed to embed PubMed chunks.") from exc
    except Exception:
        try:
            _delete_collection_if_exists(client, CHROMA_COLLECTION_NAME)
            vector_store = _get_vector_store(client)
            vector_store.add_documents(
                documents=[
                    Document(
                        page_content=str(chunk["text"]),
                        metadata={
                            **_prepare_metadata(chunk.get("metadata", {})),
                            "id": str(chunk["chunk_id"]),
                        },
                    )
                    for chunk in chunks
                ],
                ids=[str(chunk["chunk_id"]) for chunk in chunks],
            )
        except Exception as retry_exc:
            raise RagStorageError("Failed to save chunks in ChromaDB.") from retry_exc

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


def retrieve_similar_chunks(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Return nearest chunks using LangChain's Chroma vector store retriever."""

    if not query.strip():
        raise RagStorageError("Query cannot be empty.")

    try:
        vector_store = _get_vector_store(_get_chroma_client())
        results = vector_store.similarity_search_with_score(query, k=top_k)
    except Exception as exc:
        raise RagStorageError("Failed to retrieve ChromaDB chunks.") from exc

    chunks: list[dict[str, Any]] = []
    for document, score in results:
        chunks.append(
            {
                "id": str(document.metadata.get("id", "")),
                "text": document.page_content,
                "metadata": dict(document.metadata),
                "distance": float(score) if score is not None else None,
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


def _get_vector_store(client: Any) -> Any:
    """Create a LangChain Chroma vector store over the MedInsight collection."""

    if Chroma is None or Document is None:
        raise RagStorageError(
            "LangChain Chroma dependencies are not installed. Install requirements first."
        )

    return Chroma(
        client=client,
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=MedInsightEmbeddings(),
    )


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
