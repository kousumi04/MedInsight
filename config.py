"""Central configuration for MedInsight backend services."""

from __future__ import annotations

import os
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"


def _load_environment() -> None:
    """Load environment variables from project-level env files."""

    for env_path in (BASE_DIR / ".env", BACKEND_DIR / ".env"):
        if env_path.exists():
            _load_simple_env_file(env_path)


def _load_simple_env_file(env_path: Path) -> None:
    """Load simple KEY=value lines while ignoring copied code snippets."""

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            continue

        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)


_load_environment()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
MAX_KEYWORDS = int(os.getenv("MAX_KEYWORDS", "8"))

GEMINI_GENERATION_CONFIG = {
    "temperature": 0.2,
    "top_p": 0.8,
    "top_k": 20,
    "max_output_tokens": 128,
    "response_mime_type": "application/json",
}

PUBMED_EMAIL = os.getenv("PUBMED_EMAIL", "")
PUBMED_TOOL_NAME = os.getenv("PUBMED_TOOL_NAME", "medinsight")
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
PUBMED_TIMEOUT_SECONDS = int(os.getenv("PUBMED_TIMEOUT_SECONDS", "20"))
PUBMED_SEARCH_BUFFER = int(os.getenv("PUBMED_SEARCH_BUFFER", "30"))

CHROMA_API_KEY = os.getenv("CHROMA_API_KEY", "")
CHROMA_TENANT = os.getenv("CHROMA_TENANT", "")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "")
CHROMA_COLLECTION_NAME = os.getenv(
    "CHROMA_COLLECTION_NAME",
    "medinsight_temp_pubmed_chunks",
)
CHROMA_LOCAL_PATH = os.getenv("CHROMA_LOCAL_PATH", "chroma")
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME",
    "models/gemini-embedding-001",
)


def _load_chroma_cloud_snippet() -> None:
    """Support the Chroma CloudClient snippet currently stored in .env.

    Preferred .env keys are CHROMA_API_KEY, CHROMA_TENANT, and CHROMA_DATABASE.
    This parser keeps the app working if the .env contains the copied
    ``chromadb.CloudClient(...)`` snippet instead.
    """

    global CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE

    if CHROMA_API_KEY and CHROMA_TENANT and CHROMA_DATABASE:
        return

    for env_path in (BASE_DIR / ".env", BACKEND_DIR / ".env"):
        if not env_path.exists():
            continue

        env_text = env_path.read_text(encoding="utf-8-sig")
        CHROMA_API_KEY = CHROMA_API_KEY or _extract_snippet_value(
            env_text,
            "api_key",
        )
        CHROMA_TENANT = CHROMA_TENANT or _extract_snippet_value(env_text, "tenant")
        CHROMA_DATABASE = CHROMA_DATABASE or _extract_snippet_value(
            env_text,
            "database",
        )


def _extract_snippet_value(text: str, key: str) -> str:
    """Extract a quoted value from a copied Chroma CloudClient snippet."""

    match = re.search(rf"{key}\s*=\s*['\"]([^'\"]+)['\"]", text)
    return match.group(1) if match else ""


_load_chroma_cloud_snippet()

GEMINI_SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
]

STOP_WORDS = {
    "a",
    "about",
    "and",
    "are",
    "article",
    "articles",
    "for",
    "from",
    "give",
    "how",
    "in",
    "is",
    "latest",
    "me",
    "new",
    "of",
    "on",
    "paper",
    "papers",
    "please",
    "research",
    "show",
    "study",
    "studies",
    "tell",
    "the",
    "to",
    "using",
    "what",
    "with",
}

GENERIC_KEYWORDS = {
    "clinical trial",
    "clinical trials",
    "current research",
    "latest research",
    "latest treatment",
    "latest treatments",
    "medical research",
    "new treatment",
    "new treatments",
    "recent advances",
    "research paper",
    "research papers",
    "treatment",
    "treatments",
}
