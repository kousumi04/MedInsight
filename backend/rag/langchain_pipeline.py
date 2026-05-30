"""LangChain orchestration for the MedInsight PubMed RAG pipeline."""

from __future__ import annotations

import logging
from typing import Any

try:
    from langchain_core.runnables import RunnableLambda
except ImportError:  # pragma: no cover - only reached before dependency install.
    RunnableLambda = None  # type: ignore[assignment]

from backend.query_engine.userquery import process_user_query
from backend.rag.cache import (
    ChatCacheError,
    cache_is_fresh,
    extract_chat_queries,
    get_cached_chunks,
    is_related_query,
    load_chat_history,
    load_cache_record,
    should_extract_keywords,
    store_cache_record,
)
from backend.rag.answering import generate_answer
from backend.rag.database import refresh_pubmed_collection, retrieve_similar_chunks
from backend.search.fetch import build_pubmed_query, fetch_pubmed_papers


class MedInsightChainError(RuntimeError):
    """Raised when the LangChain RAG pipeline cannot be built or executed."""


logger = logging.getLogger(__name__)


def run_medinsight_chain(
    query: str,
    max_results: int,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Run the end-to-end MedInsight flow through a LangChain runnable chain."""

    if RunnableLambda is None:
        raise MedInsightChainError(
            "LangChain core is not installed. Install requirements first."
        )

    chain = (
        RunnableLambda(lambda state: _prepare_query_context(state, session_id))
        | RunnableLambda(lambda state: _fetch_pubmed_papers(state, max_results))
        | RunnableLambda(_refresh_and_retrieve)
        | RunnableLambda(_generate_answer)
    )
    return chain.invoke({"query": query})


def _prepare_query_context(
    state: dict[str, Any],
    session_id: str | None,
) -> dict[str, Any]:
    """Load cache context and decide whether keyword extraction is needed."""

    normalized_session_id = str(session_id or "").strip()
    cache_record = load_cache_record(normalized_session_id) if normalized_session_id else None
    chat_messages = load_chat_history(normalized_session_id) if normalized_session_id else []
    previous_queries = extract_chat_queries(chat_messages)
    if not previous_queries and isinstance(cache_record, dict):
        source_query = str(cache_record.get("source_query", "")).strip()
        if source_query:
            previous_queries = [source_query]

    should_extract = should_extract_keywords(
        str(state["query"]),
        normalized_session_id,
        cache_record=cache_record,
        chat_messages=chat_messages,
    )
    related_to_history = is_related_query(
        str(state["query"]),
        previous_queries,
        cache_record,
    )

    if should_extract:
        keyword_result = process_user_query(str(state["query"]))
        cleaned_keywords = keyword_result["cleaned_keywords"]
        extracted_keywords = keyword_result["extracted_keywords"]
    else:
        cached_keywords = []
        if isinstance(cache_record, dict):
            cached_keywords = [
                str(keyword).strip()
                for keyword in cache_record.get("cleaned_keywords", [])
                if str(keyword).strip()
            ]
        keyword_result = {
            "original_query": str(state["query"]),
            "extracted_keywords": [],
            "cleaned_keywords": cached_keywords,
        }
        cleaned_keywords = cached_keywords
        extracted_keywords = []

    return {
        **state,
        "session_id": normalized_session_id,
        "cache_record": cache_record,
        "chat_messages": chat_messages,
        "previous_queries": previous_queries,
        "related_to_history": related_to_history,
        "should_extract_keywords": should_extract,
        "keyword_result": keyword_result,
        "extracted_keywords": extracted_keywords,
        "cleaned_keywords": cleaned_keywords,
        "use_cached_chunks": related_to_history and cache_is_fresh(cache_record),
    }


def _fetch_pubmed_papers(
    state: dict[str, Any],
    max_results: int,
) -> dict[str, Any]:
    """Fetch PubMed papers for the cleaned keyword set."""

    if state.get("use_cached_chunks") and cache_is_fresh(state.get("cache_record")):
        cache_record = state.get("cache_record") or {}
        return {
            **state,
            "pubmed_query": cache_record.get("pubmed_query", ""),
            "papers": cache_record.get("papers", []),
            "retrieved_chunks": get_cached_chunks(cache_record),
            "cache_source": "supabase_cache",
        }

    if not state.get("cleaned_keywords"):
        return {
            **state,
            "pubmed_query": "",
            "papers": [],
            "retrieved_chunks": [],
            "cache_source": "no_keywords",
        }

    cleaned_keywords = state["cleaned_keywords"]
    papers = fetch_pubmed_papers(cleaned_keywords, max_results=max_results)
    return {
        **state,
        "pubmed_query": build_pubmed_query(cleaned_keywords),
        "papers": papers,
        "cache_source": "rag_refresh",
    }


def _refresh_and_retrieve(state: dict[str, Any]) -> dict[str, Any]:
    """Load PubMed papers into LangChain Chroma and retrieve nearest chunks."""

    if state.get("cache_source") == "supabase_cache":
        return state

    refresh_pubmed_collection({"papers": state["papers"]})
    refreshed_state = {
        **state,
        "retrieved_chunks": retrieve_similar_chunks(str(state["query"]), top_k=3),
    }
    session_id = str(state.get("session_id") or "").strip()
    if session_id:
        try:
            store_cache_record(
                session_id=session_id,
                query=str(state["query"]),
                cleaned_keywords=list(state.get("cleaned_keywords", [])),
                pubmed_query=str(refreshed_state.get("pubmed_query", "")),
                papers=list(refreshed_state.get("papers", [])),
                retrieved_chunks=list(refreshed_state.get("retrieved_chunks", [])),
            )
        except ChatCacheError:
            logger.warning(
                "Supabase cache write failed; continuing without cache persistence."
            )
    return refreshed_state


def _generate_answer(state: dict[str, Any]) -> dict[str, Any]:
    """Generate the final grounded answer from retrieved chunks."""

    answer = generate_answer(str(state["query"]), state["retrieved_chunks"])
    keyword_result = state["keyword_result"]
    return {
        "original_query": keyword_result["original_query"],
        "extracted_keywords": state.get("extracted_keywords", keyword_result["extracted_keywords"]),
        "cleaned_keywords": state["cleaned_keywords"],
        "pubmed_query": state["pubmed_query"],
        "papers": state["papers"],
        "retrieved_chunks": state["retrieved_chunks"],
        "answer": answer,
    }
