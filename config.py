"""Central configuration for MedInsight backend services."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"


def _load_environment() -> None:
    """Load environment variables from project-level env files."""

    for env_path in (BASE_DIR / ".env", BACKEND_DIR / ".env"):
        if env_path.exists():
            load_dotenv(env_path)

    load_dotenv()


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
