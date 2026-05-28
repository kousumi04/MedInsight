"""Chunk PubMed/PMC article paragraphs for the MedInsight RAG pipeline.

PubMed search returns the top 10 papers, but only the first five are ingested
for RAG context. For each paper, PMC full-text paragraphs are preferred when
available. If full text is not available, the PubMed abstract is used as a
fallback.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_TOP_PAPERS = 5


def chunk_pubmed_papers(
    pubmed_result: dict[str, Any] | list[dict[str, Any]],
    top_n: int = DEFAULT_TOP_PAPERS,
) -> list[dict[str, Any]]:
    """Return one text chunk per paragraph for the top PubMed papers.

    Args:
        pubmed_result: Either the complete API response containing a ``papers``
            key, or the paper list returned by ``fetch_pubmed_papers``.
        top_n: Number of top-ranked papers to chunk. Defaults to five.

    Returns:
        A flat list of chunk dictionaries ready for embedding.
    """

    papers = _extract_papers(pubmed_result)[:top_n]
    chunks: list[dict[str, Any]] = []

    for paper_index, paper in enumerate(papers, start=1):
        paragraphs, source = _paper_paragraphs(paper)
        if not paragraphs:
            continue

        for paragraph_index, paragraph in enumerate(paragraphs, start=1):
            chunks.append(
                {
                    "chunk_id": _build_chunk_id(
                        paper=paper,
                        paper_index=paper_index,
                        chunk_index=paragraph_index,
                    ),
                    "text": paragraph,
                    "metadata": {
                        "pmid": str(paper.get("pmid", "")),
                        "pmcid": str(paper.get("pmcid", "")),
                        "title": str(paper.get("title", "")),
                        "authors": paper.get("authors", []),
                        "journal": str(paper.get("journal", "")),
                        "publication_date": str(
                            paper.get("publication_date", "")
                        ),
                        "doi": str(paper.get("doi", "")),
                        "pubmed_url": str(paper.get("pubmed_url", "")),
                        "pmc_url": str(paper.get("pmc_url", "")),
                        "keywords_used": paper.get("keywords_used", []),
                        "paper_rank": paper_index,
                        "paragraph_index": paragraph_index,
                        "chunk_index": paragraph_index,
                        "content_source": source,
                    },
                }
            )

    return chunks


def _paper_paragraphs(paper: dict[str, Any]) -> tuple[list[str], str]:
    """Return full-text paragraphs when available, otherwise abstract chunks."""

    full_text_paragraphs = [
        _clean_text(str(paragraph))
        for paragraph in paper.get("full_text_paragraphs", [])
        if _clean_text(str(paragraph))
    ]
    if full_text_paragraphs:
        return full_text_paragraphs, "pmc_full_text"

    abstract = _clean_text(str(paper.get("abstract", "")))
    if not abstract:
        return [], "none"

    return split_abstract_into_paragraphs(abstract), "pubmed_abstract"


def split_abstract_into_paragraphs(abstract: str) -> list[str]:
    """Split a PubMed abstract into readable paragraph-like sections.

    PubMed often returns structured abstracts as a single string, for example
    ``OBJECTIVE: ... METHODS: ... CONCLUSION: ...``. This function respects
    explicit blank lines first, then falls back to common structured abstract
    labels.
    """

    cleaned_abstract = _clean_text(abstract)
    if not cleaned_abstract:
        return []

    explicit_paragraphs = [
        _clean_text(paragraph)
        for paragraph in re.split(r"\n\s*\n+", cleaned_abstract)
        if _clean_text(paragraph)
    ]
    if len(explicit_paragraphs) > 1:
        return explicit_paragraphs

    labelled_sections = _split_labelled_sections(cleaned_abstract)
    if len(labelled_sections) > 1:
        return labelled_sections

    return [cleaned_abstract]


def _extract_papers(
    pubmed_result: dict[str, Any] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize supported PubMed result shapes into a paper list."""

    if isinstance(pubmed_result, list):
        return [paper for paper in pubmed_result if isinstance(paper, dict)]

    papers = pubmed_result.get("papers", [])
    if not isinstance(papers, list):
        return []

    return [paper for paper in papers if isinstance(paper, dict)]


def _split_labelled_sections(text: str) -> list[str]:
    """Split one-line structured abstracts by common section labels."""

    labels = (
        "PATIENTS AND METHODS",
        "MATERIALS AND METHODS",
        "INTRODUCTION",
        "CONCLUSIONS",
        "CONCLUSION",
        "SIGNIFICANCE",
        "BACKGROUND",
        "OBJECTIVES",
        "OBJECTIVE",
        "DISCUSSION",
        "ABSTRACT",
        "METHODS",
        "RESULTS",
        "CASE",
        "AIM",
    )
    label_expression = "|".join(re.escape(label) for label in labels)
    section_pattern = re.compile(rf"(?i)(?:^|(?<=[.!?])\s+)(?:{label_expression}):\s")
    matches = list(section_pattern.finditer(text))
    if len(matches) <= 1:
        return [text]

    sections: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append(_clean_text(text[match.start() : end]))

    return sections


def _build_chunk_id(
    paper: dict[str, Any],
    paper_index: int,
    chunk_index: int,
) -> str:
    """Build a stable chunk identifier."""

    pmid = str(paper.get("pmid", "")).strip()
    paper_key = pmid or f"paper-{paper_index}"
    return f"pubmed-{paper_key}-chunk-{chunk_index}"


def _clean_text(text: str) -> str:
    """Normalize whitespace without changing the article wording."""

    return re.sub(r"\s+", " ", text).strip()


if __name__ == "__main__":
    sample = {
        "papers": [
            {
                "pmid": "38220551",
                "title": "Rabies: Epidemiological update and pre- and post-exposure management.",
                "abstract": (
                    "Rabies is a deadly neurotropic viral infection but is "
                    "preventable through vaccination. Its impact on human and "
                    "animal health is often devastating."
                ),
                "authors": ["Arsuaga M", "de Miguel Buckley R", "Díaz-Menéndez M"],
                "journal": "Medicina clinica",
                "publication_date": "2024 Jun 14",
                "doi": "10.1016/j.medcli.2023.11.017",
                "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/38220551/",
                "keywords_used": ["advancements"],
            }
        ]
    }
    print(chunk_pubmed_papers(sample))
