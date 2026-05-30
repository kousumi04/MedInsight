"""Supabase-backed cache for MedInsight RAG chunks."""

from __future__ import annotations

import math
import re
import threading
from datetime import datetime, timezone
from typing import Any

import requests

from config import (
    MEDINSIGHT_CACHE_SIMILARITY_THRESHOLD,
    MEDINSIGHT_CACHE_TTL_SECONDS,
    MEDINSIGHT_RELATED_QUERY_FOLLOW_UP_THRESHOLD,
    MEDINSIGHT_RELATED_QUERY_LOOKBACK,
    MEDINSIGHT_RELATED_QUERY_SIMILARITY_THRESHOLD,
    SUPABASE_PUBLISHABLE_KEY,
    SUPABASE_URL,
)
from backend.rag.embedding import embed_texts


CACHE_TABLE = "medinsight_chat_cache"
CHAT_MEMORY_TABLE = "medinsight_chat_memory"
CACHE_TTL_SECONDS = MEDINSIGHT_CACHE_TTL_SECONDS
CACHE_SIMILARITY_THRESHOLD = MEDINSIGHT_CACHE_SIMILARITY_THRESHOLD
RELATED_QUERY_SIMILARITY_THRESHOLD = MEDINSIGHT_RELATED_QUERY_SIMILARITY_THRESHOLD
RELATED_QUERY_FOLLOW_UP_THRESHOLD = MEDINSIGHT_RELATED_QUERY_FOLLOW_UP_THRESHOLD
RELATED_QUERY_LOOKBACK = MEDINSIGHT_RELATED_QUERY_LOOKBACK

_LOCAL_CACHE_LOCK = threading.Lock()
_LOCAL_CACHE: dict[str, dict[str, Any]] = {}


class ChatCacheError(RuntimeError):
    """Raised when chat cache operations fail."""


def load_cache_record(
    session_id: str,
    *,
    prefer_local: bool = True,
) -> dict[str, Any] | None:
    """Load the cached RAG payload for a chat session, if available."""

    if not _cache_enabled() or not session_id:
        return None

    if prefer_local:
        local_record = _load_local_cache(session_id)
        if local_record and cache_is_fresh(local_record):
            return local_record

    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/{CACHE_TABLE}",
            params={"session_id": f"eq.{session_id}", "select": "*", "limit": 1},
            headers=_supabase_headers(),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None

    if isinstance(payload, list) and payload:
        record = payload[0]
        _store_local_cache(session_id, record)
        return record
    if isinstance(payload, dict):
        _store_local_cache(session_id, payload)
        return payload
    return None


def load_chat_history(session_id: str) -> list[dict[str, Any]]:
    """Load the stored chat transcript for a session from Supabase."""

    if not _cache_enabled() or not session_id:
        return []

    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/{CHAT_MEMORY_TABLE}",
            params={"session_id": f"eq.{session_id}", "select": "messages", "limit": 1},
            headers=_supabase_headers(),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    messages: list[dict[str, Any]] = []
    if isinstance(payload, list) and payload:
        raw_messages = payload[0].get("messages", [])
    elif isinstance(payload, dict):
        raw_messages = payload.get("messages", [])
    else:
        raw_messages = []

    if isinstance(raw_messages, list):
        messages = [message for message in raw_messages if isinstance(message, dict)]

    return messages


def cache_is_fresh(record: dict[str, Any] | None) -> bool:
    """Return whether a cache record is still within the TTL window."""

    if not record:
        return False

    cached_at = _parse_timestamp(str(record.get("cached_at", "")))
    if cached_at is None:
        cached_at = _parse_timestamp(str(record.get("updated_at", "")))
    if cached_at is None:
        return False

    age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
    return age_seconds <= CACHE_TTL_SECONDS


def should_use_cache(
    query: str,
    cleaned_keywords: list[str],
    record: dict[str, Any] | None,
) -> bool:
    """Decide whether the cached chunks should answer the new query."""

    if not cache_is_fresh(record):
        return False

    if not get_cached_chunks(record):
        return False

    cached_embedding = record.get("query_embedding") if record else None
    if not isinstance(cached_embedding, list) or not cached_embedding:
        return False

    query_terms = _extract_topic_terms(query, cleaned_keywords)
    cached_terms = _extract_cached_topic_terms(record)
    if _has_meaningful_topic_overlap(query_terms, cached_terms):
        return True

    try:
        query_embedding = embed_texts([query], task_type="retrieval_query")[0]
    except Exception:
        return False

    similarity = _cosine_similarity(query_embedding, cached_embedding)
    if similarity >= max(0.55, CACHE_SIMILARITY_THRESHOLD - 0.12):
        return True

    cached_keywords = record.get("cleaned_keywords", []) if record else []
    if isinstance(cached_keywords, list):
        overlap = _keyword_overlap_ratio(cleaned_keywords, cached_keywords)
        if overlap >= 0.34:
            return True

    if query_terms and cached_terms:
        token_overlap = len(query_terms & cached_terms) / min(
            len(query_terms),
            len(cached_terms),
        )
        return token_overlap >= 0.2

    return False


def should_extract_keywords(
    query: str,
    session_id: str | None,
    *,
    cache_record: dict[str, Any] | None = None,
    chat_messages: list[dict[str, Any]] | None = None,
) -> bool:
    """Decide whether Gemini keyword extraction is needed for this query."""

    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return True

    if not cache_is_fresh(cache_record):
        return True

    if not get_cached_chunks(cache_record):
        return True

    history_messages = chat_messages if chat_messages is not None else load_chat_history(
        normalized_session_id
    )
    previous_queries = extract_chat_queries(history_messages)
    if not previous_queries:
        source_query = str((cache_record or {}).get("source_query", "")).strip()
        if source_query:
            previous_queries = [source_query]
        else:
            return True

    return not is_related_query(query, previous_queries, cache_record)


def store_cache_record(
    session_id: str,
    query: str,
    cleaned_keywords: list[str],
    pubmed_query: str,
    papers: list[dict[str, Any]],
    retrieved_chunks: list[dict[str, Any]],
) -> None:
    """Store the latest RAG context for a chat session."""

    if not _cache_enabled() or not session_id:
        return

    try:
        query_embedding = embed_texts([query], task_type="retrieval_query")[0]
    except Exception:
        query_embedding = []

    record = {
        "session_id": session_id,
        "source_query": query,
        "query_embedding": query_embedding,
        "cleaned_keywords": cleaned_keywords,
        "topic_terms": sorted(_extract_topic_terms(query, cleaned_keywords)),
        "pubmed_query": pubmed_query,
        "papers": papers,
        "retrieved_chunks": retrieved_chunks,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _store_local_cache(session_id, record)

    try:
        _upsert_supabase_record(record)
    except Exception as exc:
        raise ChatCacheError("Failed to store the chat cache in Supabase.") from exc


def get_cached_chunks(record: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract cached chunks from a cache record."""

    if not record:
        return []

    chunks = record.get("retrieved_chunks", [])
    if isinstance(chunks, list):
        return [chunk for chunk in chunks if isinstance(chunk, dict)]

    return []


def extract_chat_queries(messages: list[dict[str, Any]] | None) -> list[str]:
    """Extract the conversational queries from stored chat messages."""

    if not messages:
        return []

    queries: list[str] = []
    seen: set[str] = set()

    for message in messages:
        if not isinstance(message, dict):
            continue

        candidates: list[str] = []
        result = message.get("result")
        if isinstance(result, dict):
            candidates.append(str(result.get("original_query", "")).strip())

        candidates.append(str(message.get("query", "")).strip())
        candidates.append(str(message.get("original_query", "")).strip())

        for candidate in candidates:
            if not candidate:
                continue
            comparable = candidate.casefold()
            if comparable in seen:
                continue
            seen.add(comparable)
            queries.append(candidate)

    return queries


def is_related_query(
    query: str,
    previous_queries: list[str],
    cache_record: dict[str, Any] | None = None,
) -> bool:
    """Return whether a new query is a follow-up on an existing topic."""

    normalized_query = _normalize_query_text(query)
    if not normalized_query or not previous_queries:
        return False

    previous_queries = previous_queries[-RELATED_QUERY_LOOKBACK:]
    current_terms = _extract_topic_terms(normalized_query, [])
    previous_terms = set()
    for previous_query in previous_queries:
        previous_terms |= _extract_topic_terms(previous_query, [])

    if _has_meaningful_topic_overlap(current_terms, previous_terms):
        return True

    candidate_queries = list(previous_queries)
    if cache_record:
        source_query = str(cache_record.get("source_query", "")).strip()
        if source_query and source_query.casefold() not in {
            query_text.casefold() for query_text in candidate_queries
        }:
            candidate_queries.append(source_query)

    if len(candidate_queries) == 1:
        return _query_similarity(normalized_query, candidate_queries[0]) >= (
            RELATED_QUERY_FOLLOW_UP_THRESHOLD
        )

    similarities = [_query_similarity(normalized_query, candidate) for candidate in candidate_queries]
    max_similarity = max(similarities) if similarities else 0.0
    if max_similarity >= RELATED_QUERY_SIMILARITY_THRESHOLD:
        return True

    if _looks_like_follow_up(normalized_query) and max_similarity >= RELATED_QUERY_FOLLOW_UP_THRESHOLD:
        return True

    return False


def _cache_enabled() -> bool:
    """Return whether Supabase credentials are available."""

    return bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY)


def _supabase_headers() -> dict[str, str]:
    """Return headers needed for Supabase REST requests."""

    return {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {SUPABASE_PUBLISHABLE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Profile": "public",
        "Content-Profile": "public",
    }


def _parse_timestamp(value: str) -> datetime | None:
    """Parse an ISO timestamp returned by Supabase."""

    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _normalize_query_text(query: str) -> str:
    """Normalize a user query for topic comparison."""

    return re.sub(r"\s+", " ", str(query or "")).strip()


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity between two vectors."""

    if len(left) != len(right) or not left:
        return 0.0

    numerator = sum(x * y for x, y in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(x * x for x in left))
    right_norm = math.sqrt(sum(y * y for y in right))
    if not left_norm or not right_norm:
        return 0.0

    return numerator / (left_norm * right_norm)


def _query_similarity(left_query: str, right_query: str) -> float:
    """Compare two queries with embeddings and basic token overlap fallback."""

    left = _normalize_query_text(left_query)
    right = _normalize_query_text(right_query)
    if not left or not right:
        return 0.0

    try:
        embeddings = embed_texts([left, right], task_type="retrieval_query")
    except Exception:
        embeddings = []

    if len(embeddings) >= 2:
        similarity = _cosine_similarity(embeddings[0], embeddings[1])
        if similarity:
            return similarity

    left_terms = _extract_topic_terms(left, [])
    right_terms = _extract_topic_terms(right, [])
    if left_terms and right_terms:
        return len(left_terms & right_terms) / min(len(left_terms), len(right_terms))

    return 0.0


def _keyword_overlap_ratio(left: list[str], right: list[str]) -> float:
    """Measure overlap between two cleaned keyword sets."""

    left_keywords = {str(keyword).casefold() for keyword in left if str(keyword).strip()}
    right_keywords = {str(keyword).casefold() for keyword in right if str(keyword).strip()}
    if not left_keywords or not right_keywords:
        return 0.0

    return len(left_keywords & right_keywords) / min(len(left_keywords), len(right_keywords))


def _has_meaningful_topic_overlap(left: set[str], right: set[str]) -> bool:
    """Return whether two topic-term sets share a specific enough concept."""

    shared_terms = left & right
    if not shared_terms:
        return False

    if any(_is_specific_topic_term(term) for term in shared_terms):
        return True

    denominator = min(len(left), len(right))
    if denominator <= 0:
        return False

    return len(shared_terms) / denominator >= 0.5


def _extract_topic_terms(query: str, cleaned_keywords: list[str]) -> set[str]:
    """Extract stable topic terms from the query and cleaned keywords."""

    terms = set()
    for keyword in cleaned_keywords:
        normalized = _normalize_term(str(keyword))
        if normalized:
            terms.add(normalized)

    for token in re.findall(r"[a-z0-9][a-z0-9+-]*", query.casefold()):
        normalized = _normalize_term(token)
        if normalized:
            terms.add(normalized)

    return terms


def _extract_cached_topic_terms(record: dict[str, Any] | None) -> set[str]:
    """Collect topic terms from cached query metadata and retrieved chunks."""

    if not record:
        return set()

    terms = set()

    for keyword in record.get("cleaned_keywords", []) or []:
        normalized = _normalize_term(str(keyword))
        if normalized:
            terms.add(normalized)

    for keyword in record.get("topic_terms", []) or []:
        normalized = _normalize_term(str(keyword))
        if normalized:
            terms.add(normalized)

    source_query = str(record.get("source_query", ""))
    for token in re.findall(r"[a-z0-9][a-z0-9+-]*", source_query.casefold()):
        normalized = _normalize_term(token)
        if normalized:
            terms.add(normalized)

    for chunk in record.get("retrieved_chunks", []) or []:
        if not isinstance(chunk, dict):
            continue
        metadata = chunk.get("metadata", {}) or {}
        title = str(metadata.get("title", ""))
        keywords_used = metadata.get("keywords_used", [])
        for token in re.findall(r"[a-z0-9][a-z0-9+-]*", title.casefold()):
            normalized = _normalize_term(token)
            if normalized:
                terms.add(normalized)
        if isinstance(keywords_used, list):
            for keyword in keywords_used:
                normalized = _normalize_term(str(keyword))
                if normalized:
                    terms.add(normalized)

    return terms


def _looks_like_follow_up(query: str) -> bool:
    """Heuristically detect conversational follow-up phrasing."""

    lowered = query.casefold()
    return lowered.startswith(
        (
            "what about",
            "and ",
            "also ",
            "how about",
            "tell me more",
            "what else",
            "is there",
            "do they",
            "does it",
            "what are the side effects",
            "what about side effects",
            "can you explain",
            "how does it",
            "what is the mechanism",
        )
    ) or any(
        phrase in lowered
        for phrase in (
            "side effects",
            "safety",
            "dosage",
            "dose",
            "mechanism",
            "efficacy",
            "compared with",
            "compared to",
            "in humans",
            "in people",
            "in patients",
            "long term",
        )
    )


def _normalize_term(term: str) -> str:
    """Normalize a medical topic term for reuse checks."""

    normalized = term.strip().casefold()
    if len(normalized) < 2:
        return ""
    if normalized in {
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "on",
        "the",
        "to",
        "what",
        "when",
        "why",
        "how",
        "about",
        "advance",
        "advancements",
        "advances",
        "article",
        "articles",
        "clinical",
        "current",
        "disease",
        "diseases",
        "drug",
        "drugs",
        "effect",
        "effects",
        "medicine",
        "medicines",
        "new",
        "latest",
        "paper",
        "papers",
        "patient",
        "patients",
        "recent",
        "research",
        "study",
        "studies",
        "tell",
        "me",
        "therapies",
        "therapy",
        "treatment",
        "treatments",
    }:
        return ""
    return normalized


def _is_specific_topic_term(term: str) -> bool:
    """Return whether a normalized term is specific enough to trust alone."""

    return (
        len(term) >= 5
        or any(character.isdigit() for character in term)
        or "-" in term
        or "+" in term
    )


def _load_local_cache(session_id: str) -> dict[str, Any] | None:
    """Return the last in-process cache record for a session, if present."""

    with _LOCAL_CACHE_LOCK:
        record = _LOCAL_CACHE.get(session_id)
        return dict(record) if isinstance(record, dict) else None


def _store_local_cache(session_id: str, record: dict[str, Any]) -> None:
    """Update the in-process cache for a session."""

    if not session_id or not isinstance(record, dict):
        return

    with _LOCAL_CACHE_LOCK:
        _LOCAL_CACHE[session_id] = dict(record)


def _upsert_supabase_record(record: dict[str, Any]) -> None:
    """Upsert a cache record into Supabase and verify it persisted."""

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{CACHE_TABLE}",
        params={"on_conflict": "session_id"},
        headers={
            **_supabase_headers(),
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        json=record,
        timeout=20,
    )
    response.raise_for_status()

    returned = response.json()
    if isinstance(returned, list) and returned:
        persisted = returned[0]
        if str(persisted.get("session_id", "")) == str(record.get("session_id", "")):
            _store_local_cache(str(record.get("session_id", "")), persisted)
            return

    persisted = load_cache_record(str(record.get("session_id", "")), prefer_local=False)
    if not persisted or str(persisted.get("source_query", "")) != str(record.get("source_query", "")):
        raise ChatCacheError("Supabase did not persist the cache record.")

    _store_local_cache(str(record.get("session_id", "")), persisted)
