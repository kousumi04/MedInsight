"""PubMed research paper retrieval pipeline for MedInsight.

The functions in this module convert extracted medical keywords into a PubMed
query, retrieve candidate papers through NCBI Entrez, and return structured
metadata ready for future RAG ingestion.
"""

from __future__ import annotations

import logging
import re
import socket
import xml.etree.ElementTree as ET
from typing import Any

from config import (
    PUBMED_API_KEY,
    PUBMED_EMAIL,
    PUBMED_SEARCH_BUFFER,
    PUBMED_TIMEOUT_SECONDS,
    PUBMED_TOOL_NAME,
)

try:
    from Bio import Entrez
except ImportError:  # pragma: no cover - only reached before dependency install.
    Entrez = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

PUBMED_BASE_URL = "https://pubmed.ncbi.nlm.nih.gov"
PMC_BASE_URL = "https://pmc.ncbi.nlm.nih.gov/articles"
DEFAULT_MAX_RESULTS = 10
EXCLUDED_PUBLICATION_TYPES = {
    "comment",
    "editorial",
    "letter",
    "news",
    "newspaper article",
}


class PubMedFetchError(RuntimeError):
    """Raised when PubMed retrieval cannot continue."""


def build_pubmed_query(keywords: list[str]) -> str:
    """Build a relevance-oriented PubMed query from extracted keywords.

    The first keyword is treated as the primary concept. Remaining keywords are
    grouped with OR so a query like ``["GLP-1 agonists", "obesity",
    "diabetes"]`` becomes ``("GLP-1 agonists") AND ("obesity" OR
    "diabetes")``. A has-abstract filter is added because abstracts are the
    immediate ingestion target for the RAG pipeline.
    """

    cleaned_keywords = _clean_keyword_list(keywords)
    if not cleaned_keywords:
        raise ValueError("At least one keyword is required for PubMed search.")

    primary = _format_pubmed_term(cleaned_keywords[0])
    if len(cleaned_keywords) == 1:
        keyword_query = primary
    else:
        secondary_terms = " OR ".join(
            _format_pubmed_term(keyword) for keyword in cleaned_keywords[1:]
        )
        keyword_query = f"{primary} AND ({secondary_terms})"

    publication_type_boost = (
        "(clinical trial[Publication Type] OR review[Publication Type] OR "
        "meta-analysis[Publication Type] OR randomized controlled trial"
        "[Publication Type] OR journal article[Publication Type])"
    )
    return f"({keyword_query}) AND hasabstract[text] AND {publication_type_boost}"


def search_pubmed(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[str]:
    """Search PubMed and return candidate PMIDs ordered by relevance."""

    if not query.strip():
        raise ValueError("PubMed query cannot be empty.")

    _configure_entrez()
    retmax = max(max_results, PUBMED_SEARCH_BUFFER)

    try:
        with Entrez.esearch(
            db="pubmed",
            term=query,
            retmax=retmax,
            sort="relevance",
            retmode="xml",
        ) as handle:
            search_result = Entrez.read(handle)
    except Exception as exc:
        raise PubMedFetchError("PubMed search request failed.") from exc

    id_list = search_result.get("IdList", [])
    return _deduplicate_pmids([str(pmid) for pmid in id_list])


def fetch_paper_details(pmids: list[str]) -> list[dict[str, Any]]:
    """Fetch PubMed article metadata for a batch of PMIDs."""

    unique_pmids = _deduplicate_pmids(pmids)
    if not unique_pmids:
        return []

    _configure_entrez()

    try:
        with Entrez.efetch(
            db="pubmed",
            id=",".join(unique_pmids),
            rettype="abstract",
            retmode="xml",
        ) as handle:
            fetch_result = Entrez.read(handle)
    except Exception as exc:
        raise PubMedFetchError("PubMed metadata fetch request failed.") from exc

    articles = fetch_result.get("PubmedArticle", [])
    papers = [parse_paper_data(article) for article in articles]
    _attach_full_text_paragraphs(papers)
    return papers


def parse_paper_data(article: dict[str, Any]) -> dict[str, Any]:
    """Parse one PubMed XML article record into clean metadata."""

    medline = article.get("MedlineCitation", {})
    pubmed_data = article.get("PubmedData", {})
    article_data = medline.get("Article", {})
    journal = article_data.get("Journal", {})

    pmid = str(medline.get("PMID", ""))
    title = _stringify(article_data.get("ArticleTitle", ""))
    abstract = _parse_abstract(article_data.get("Abstract", {}))
    authors = _parse_authors(article_data.get("AuthorList", []))
    journal_title = _stringify(journal.get("Title", ""))
    publication_date = _parse_publication_date(journal.get("JournalIssue", {}))
    doi = _parse_doi(article_data, pubmed_data)
    pmcid = _parse_pmcid(pubmed_data)

    return {
        "pmid": pmid,
        "pmcid": pmcid,
        "title": title,
        "abstract": abstract,
        "full_text_paragraphs": [],
        "authors": authors,
        "journal": journal_title,
        "publication_date": publication_date,
        "doi": doi,
        "pubmed_url": f"{PUBMED_BASE_URL}/{pmid}/" if pmid else "",
        "pmc_url": f"{PMC_BASE_URL}/{pmcid}/" if pmcid else "",
        "keywords_used": [],
        "publication_types": _parse_publication_types(article_data),
    }


def fetch_pubmed_papers(
    keywords: list[str],
    max_results: int = DEFAULT_MAX_RESULTS,
) -> list[dict[str, Any]]:
    """Fetch structured PubMed paper metadata for extracted keywords.

    Failures are logged and return an empty list so upstream API routes can
    respond gracefully while preserving the error trail for debugging.
    """

    cleaned_keywords = _clean_keyword_list(keywords)
    if not cleaned_keywords:
        logger.warning("PubMed fetch skipped because no keywords were provided.")
        return []

    try:
        query = build_pubmed_query(cleaned_keywords)
        pmids = search_pubmed(query, max_results=max_results)
        papers = fetch_paper_details(pmids)
    except (ValueError, PubMedFetchError) as exc:
        logger.warning("PubMed fetch failed: %s", exc)
        return []

    filtered_papers = [
        paper for paper in papers if _is_relevant_paper(paper)
    ][:max_results]

    for paper in filtered_papers:
        paper["keywords_used"] = _keywords_present_in_paper(cleaned_keywords, paper)
        paper.pop("publication_types", None)

    return filtered_papers


def _configure_entrez() -> None:
    """Configure Bio.Entrez using project-level PubMed settings."""

    if Entrez is None:
        raise PubMedFetchError(
            "biopython is not installed. Install requirements first."
        )

    if not PUBMED_EMAIL:
        logger.warning(
            "PUBMED_EMAIL is not configured. NCBI recommends setting a real "
            "email address for Entrez API usage."
        )

    Entrez.email = PUBMED_EMAIL or "anonymous@example.com"
    Entrez.tool = PUBMED_TOOL_NAME
    if PUBMED_API_KEY:
        Entrez.api_key = PUBMED_API_KEY

    Entrez.max_tries = 3
    Entrez.sleep_between_tries = 2
    socket.setdefaulttimeout(PUBMED_TIMEOUT_SECONDS)


def _clean_keyword_list(keywords: list[str]) -> list[str]:
    """Normalize keyword inputs while preserving multi-word medical phrases."""

    cleaned: list[str] = []
    seen: set[str] = set()

    for keyword in keywords:
        if not isinstance(keyword, str):
            continue

        normalized = re.sub(r"\s+", " ", keyword).strip(" \t\n\r\"'`.,;:?!")
        if not normalized:
            continue

        comparable = normalized.casefold()
        if comparable in seen:
            continue

        cleaned.append(normalized)
        seen.add(comparable)

    return cleaned


def _format_pubmed_term(keyword: str) -> str:
    """Quote a PubMed term safely while preserving phrase matching."""

    safe_keyword = keyword.replace('"', "").strip()
    return f'"{safe_keyword}"'


def _deduplicate_pmids(pmids: list[str]) -> list[str]:
    """Return PMIDs in original order without duplicates."""

    unique_pmids: list[str] = []
    seen: set[str] = set()

    for pmid in pmids:
        if pmid and pmid not in seen:
            unique_pmids.append(pmid)
            seen.add(pmid)

    return unique_pmids


def _parse_abstract(abstract_data: dict[str, Any]) -> str:
    """Extract and join abstract sections from PubMed XML."""

    abstract_parts = abstract_data.get("AbstractText", [])
    sections: list[str] = []

    for part in abstract_parts:
        text = _stringify(part)
        label = getattr(part, "attributes", {}).get("Label", "")
        if label and text:
            sections.append(f"{label}: {text}")
        elif text:
            sections.append(text)

    return " ".join(sections).strip()


def _parse_authors(author_list: list[dict[str, Any]]) -> list[str]:
    """Parse PubMed author names into readable strings."""

    authors: list[str] = []

    for author in author_list:
        collective_name = author.get("CollectiveName")
        if collective_name:
            authors.append(_stringify(collective_name))
            continue

        last_name = _stringify(author.get("LastName", ""))
        initials = _stringify(author.get("Initials", ""))
        full_name = " ".join(part for part in (last_name, initials) if part)
        if full_name:
            authors.append(full_name)

    return authors


def _parse_publication_date(journal_issue: dict[str, Any]) -> str:
    """Parse a compact publication date from JournalIssue/PubDate."""

    pub_date = journal_issue.get("PubDate", {})
    year = _stringify(pub_date.get("Year", ""))
    month = _stringify(pub_date.get("Month", ""))
    day = _stringify(pub_date.get("Day", ""))
    medline_date = _stringify(pub_date.get("MedlineDate", ""))

    date_parts = [part for part in (year, month, day) if part]
    if date_parts:
        return " ".join(date_parts)

    return medline_date


def _parse_doi(article_data: dict[str, Any], pubmed_data: dict[str, Any]) -> str:
    """Find a DOI in PubMed ArticleIdList or ELocationID fields."""

    article_ids = pubmed_data.get("ArticleIdList", [])
    for article_id in article_ids:
        if getattr(article_id, "attributes", {}).get("IdType") == "doi":
            return _stringify(article_id)

    electronic_ids = article_data.get("ELocationID", [])
    for electronic_id in electronic_ids:
        if getattr(electronic_id, "attributes", {}).get("EIdType") == "doi":
            return _stringify(electronic_id)

    return ""


def _parse_pmcid(pubmed_data: dict[str, Any]) -> str:
    """Find a PMCID in PubMed ArticleIdList."""

    article_ids = pubmed_data.get("ArticleIdList", [])
    for article_id in article_ids:
        if getattr(article_id, "attributes", {}).get("IdType") == "pmc":
            return _normalize_pmcid(_stringify(article_id))

    return ""


def _attach_full_text_paragraphs(papers: list[dict[str, Any]]) -> None:
    """Fetch open-access PMC full text paragraphs for papers with a PMCID."""

    pmcids = [paper["pmcid"] for paper in papers if paper.get("pmcid")]
    if not pmcids:
        return

    try:
        paragraphs_by_pmcid = fetch_pmc_full_text_paragraphs(pmcids)
    except PubMedFetchError as exc:
        logger.warning("PMC full-text fetch failed: %s", exc)
        return

    for paper in papers:
        pmcid = paper.get("pmcid", "")
        paper["full_text_paragraphs"] = paragraphs_by_pmcid.get(pmcid, [])


def fetch_pmc_full_text_paragraphs(pmcids: list[str]) -> dict[str, list[str]]:
    """Fetch paragraph text from PMC XML for open-access articles."""

    normalized_pmcids = [
        pmcid for pmcid in (_normalize_pmcid(pmcid) for pmcid in pmcids) if pmcid
    ]
    if not normalized_pmcids:
        return {}

    _configure_entrez()

    try:
        with Entrez.efetch(
            db="pmc",
            id=",".join(pmcid.removeprefix("PMC") for pmcid in normalized_pmcids),
            rettype="full",
            retmode="xml",
        ) as handle:
            xml_payload = handle.read()
    except Exception as exc:
        raise PubMedFetchError("PMC full-text request failed.") from exc

    if isinstance(xml_payload, bytes):
        xml_text = xml_payload.decode("utf-8", errors="replace")
    else:
        xml_text = str(xml_payload)

    return _parse_pmc_xml_paragraphs(xml_text)


def _parse_pmc_xml_paragraphs(xml_text: str) -> dict[str, list[str]]:
    """Parse PMC article XML into paragraph lists keyed by PMCID."""

    if not xml_text.strip():
        return {}

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise PubMedFetchError("PMC full-text XML could not be parsed.") from exc

    articles = [
        element for element in root.iter() if _local_tag(element.tag) == "article"
    ]
    if _local_tag(root.tag) == "article":
        articles = [root]

    paragraphs_by_pmcid: dict[str, list[str]] = {}
    for article in articles:
        pmcid = _extract_pmcid_from_article(article)
        if not pmcid:
            continue

        paragraphs = _extract_article_body_paragraphs(article)
        if paragraphs:
            paragraphs_by_pmcid[pmcid] = paragraphs

    return paragraphs_by_pmcid


def _extract_pmcid_from_article(article: ET.Element) -> str:
    """Extract PMCID from one PMC article XML node."""

    for article_id in article.iter():
        if _local_tag(article_id.tag) != "article-id":
            continue
        if article_id.attrib.get("pub-id-type") in {"pmc", "pmcid"}:
            return _normalize_pmcid("".join(article_id.itertext()))

    return ""


def _extract_article_body_paragraphs(article: ET.Element) -> list[str]:
    """Extract readable body paragraphs from one PMC article XML node."""

    body = next(
        (element for element in article.iter() if _local_tag(element.tag) == "body"),
        None,
    )
    if body is None:
        return []

    paragraphs: list[str] = []
    for paragraph in body.iter():
        if _local_tag(paragraph.tag) != "p":
            continue
        paragraph_text = _stringify(" ".join(paragraph.itertext()))
        if _is_useful_full_text_paragraph(paragraph_text):
            paragraphs.append(paragraph_text)

    return _deduplicate_paragraphs(paragraphs)


def _is_useful_full_text_paragraph(text: str) -> bool:
    """Filter tiny or boilerplate-ish full-text fragments."""

    if len(text) < 80:
        return False

    lowered = text.casefold()
    boilerplate_starts = (
        "copyright",
        "funding:",
        "competing interests:",
        "conflict of interest",
        "data availability",
        "publisher's note",
    )
    return not lowered.startswith(boilerplate_starts)


def _deduplicate_paragraphs(paragraphs: list[str]) -> list[str]:
    """Remove duplicate paragraphs while preserving order."""

    unique_paragraphs: list[str] = []
    seen: set[str] = set()

    for paragraph in paragraphs:
        comparable = paragraph.casefold()
        if comparable in seen:
            continue

        unique_paragraphs.append(paragraph)
        seen.add(comparable)

    return unique_paragraphs


def _normalize_pmcid(pmcid: str) -> str:
    """Normalize PMCID values to the PMC123 shape."""

    normalized = _stringify(pmcid).upper()
    if not normalized:
        return ""
    if normalized.startswith("PMC"):
        return normalized
    if normalized.isdigit():
        return f"PMC{normalized}"

    return normalized


def _local_tag(tag: str) -> str:
    """Return an XML tag name without its namespace."""

    return tag.rsplit("}", 1)[-1]


def _parse_publication_types(article_data: dict[str, Any]) -> list[str]:
    """Return lower-cased publication types for filtering."""

    publication_type_list = article_data.get("PublicationTypeList", [])
    return [_stringify(pub_type).casefold() for pub_type in publication_type_list]


def _is_relevant_paper(paper: dict[str, Any]) -> bool:
    """Filter out records that are not useful for research retrieval."""

    if not paper.get("pmid") or not paper.get("title") or not paper.get("abstract"):
        return False

    publication_types = set(paper.get("publication_types", []))
    if publication_types & EXCLUDED_PUBLICATION_TYPES:
        return False

    return True


def _keywords_present_in_paper(
    keywords: list[str],
    paper: dict[str, Any],
) -> list[str]:
    """Return query keywords found in the title or abstract."""

    searchable_text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
    searchable_text = searchable_text.casefold()

    matched_keywords = [
        keyword
        for keyword in keywords
        if keyword.casefold() in searchable_text
    ]

    return matched_keywords or keywords


def _stringify(value: Any) -> str:
    """Convert BioPython XML string-like values into plain strings."""

    if value is None:
        return ""

    text = str(value)
    return re.sub(r"\s+", " ", text).strip()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample_keywords = ["GLP-1 agonists", "obesity", "diabetes"]
    sample_papers = fetch_pubmed_papers(sample_keywords)
    for sample_paper in sample_papers:
        print(sample_paper)
