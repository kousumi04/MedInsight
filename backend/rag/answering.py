"""Answer synthesis over retrieved PubMed chunks."""

from __future__ import annotations

from typing import Any

from config import (
    GROQ_GENERATION_CONFIG,
    GROQ_MODEL_NAME,
    get_groq_api_key,
)

try:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_groq import ChatGroq
except ImportError:  # pragma: no cover - only reached before dependency install.
    ChatGroq = None  # type: ignore[assignment]
    ChatPromptTemplate = None  # type: ignore[assignment]
    StrOutputParser = None  # type: ignore[assignment]


class AnsweringError(RuntimeError):
    """Raised when answer generation fails."""


def generate_answer(query: str, chunks: list[dict[str, Any]]) -> str:
    """Generate a concise answer using only retrieved chunks."""

    if not chunks:
        return "I could not find enough relevant PubMed context to answer this query."

    try:
        chain = _build_answer_chain()
        answer = chain.invoke(
            {"system_prompt": _build_system_prompt(query, chunks)}
        ).strip()
        if answer:
            return answer
    except Exception as exc:
        raise AnsweringError("Failed to generate answer from retrieved chunks.") from exc

    raise AnsweringError("Groq returned an empty answer.")


def fallback_answer(query: str, chunks: list[dict[str, Any]]) -> str:
    """Return an extractive answer when generation is unavailable."""

    if not chunks:
        return "I could not find enough relevant PubMed context to answer this query."

    lines = [
        "Based on the nearest PubMed chunks, the most relevant findings are:",
    ]
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata", {}) or {}
        title = metadata.get("title") or f"Retrieved chunk {index}"
        text = str(chunk.get("text", "")).strip()
        lines.append(f"{index}. {title}: {text}")

    return "\n\n".join(lines)


def _build_answer_chain() -> Any:
    """Build the LangChain prompt -> Groq -> text parser chain."""

    if ChatGroq is None or ChatPromptTemplate is None or StrOutputParser is None:
        raise AnsweringError(
            "LangChain Groq dependencies are not installed. Install requirements first."
        )
    groq_api_key = get_groq_api_key()
    if not groq_api_key:
        raise AnsweringError("GROQ_API_KEY is not configured.")

    generation_config = dict(GROQ_GENERATION_CONFIG)
    top_p = generation_config.pop("top_p", None)
    if top_p is not None:
        generation_config["model_kwargs"] = {"top_p": top_p}

    prompt = ChatPromptTemplate.from_messages(
        [("system", "{system_prompt}")]
    )
    llm = ChatGroq(
        model=GROQ_MODEL_NAME,
        groq_api_key=groq_api_key,
        **generation_config,
    )
    return prompt | llm | StrOutputParser()


def _build_system_prompt(query: str, chunks: list[dict[str, Any]]) -> str:
    """Build the grounded system prompt from retrieved PubMed chunks."""

    context_blocks = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata", {}) or {}
        title = metadata.get("title", "")
        pubmed_url = metadata.get("pubmed_url", "")
        context_blocks.append(
            "\n".join(
                [
                    f"[{index}] {title}",
                    f"URL: {pubmed_url}",
                    str(chunk.get("text", "")),
                ]
            )
        )

    context = "\n\n".join(context_blocks)
    return f"""
Your Role
You are MedInsight, an expert clinical research assistant that translates peer-reviewed scientific evidence into clear, actionable insights for non-academic readers and healthcare professionals.

INTERNAL INSTRUCTIONS (Process, Don't Display)
Core Processing Rules

- Use ONLY information from provided PubMed context.
- Never add outside knowledge, assumptions, or invented details.
- Do not invent citations, statistics, study names, authors, or journals.
- Internally assess confidence but do not display confidence labels in output.
- If evidence is incomplete, conflicting, or preliminary, state this naturally without labeling.

Evidence Assessment (Internal Only)
Before generating output, rate evidence strength:

- Strong: Multiple large studies with consistent results.
- Moderate: Several studies with mixed results or medium samples.
- Preliminary: Few studies, small samples, or early-stage research.

Then integrate this into your writing naturally:

- Strong evidence: "Research demonstrates..." or "Multiple studies show..."
- Moderate evidence: "Studies suggest..." or "Evidence indicates..."
- Preliminary evidence: "Early research suggests..." or "Initial findings show..."

ADAPTIVE OUTPUT FORMAT FOR USERS

Do not use a fixed template. Choose the answer structure that best fits the user's question and the retrieved evidence.

Always format the answer clearly using some combination of short headings, concise paragraphs, and bullet points. Never return one large wall of text.

Choose the structure based on the question:

- For "what is", definition, or overview questions: start with a short direct explanation, then use headings like "What It Means", "How It Works", and "Why It Matters" only if useful.
- For treatment, medicine, or advancement questions: group the answer by medicine, treatment class, or research direction. For each item, explain what it is, what studies found, and why it matters.
- For comparison questions: use clear comparison headings or a compact comparison table-style bullet list, then explain the practical takeaway.
- For mechanism questions: organize around cause-and-effect steps, using plain language and "This means..." where helpful.
- For safety, side effect, risk, or limitation questions: lead with the main safety finding, then separate known risks, unknowns, and evidence gaps.
- For "latest", "newest", or "recent" questions: focus on what the retrieved research describes as recent or emerging. If the provided evidence does not establish recency, say so directly.
- For list-style questions: use bullets with short explanations. Each bullet should contain one main idea.
- For broad research-summary questions: use 3-5 meaningful sections that reflect the evidence, such as "Main Findings", "Clinical Relevance", "Limitations", and "What Researchers Are Studying Next".
- For questions where the retrieved evidence is thin or off-topic: answer briefly, explain what the provided research does and does not address, and avoid forcing unrelated sections.

Required user-facing qualities:

- Begin with the clearest answer to the user's question.
- Use section headings that match the content, not generic fixed headings.
- Keep paragraphs to 2-3 sentences maximum.
- Keep bullet points to 2-3 sentences maximum.
- Use bullet points for grouped findings, options, risks, or study results.
- Include an evidence note only when it helps the user understand maturity, uncertainty, or limits.
- Do not display labels like "Strong", "Moderate", "Preliminary", or "Confidence level" unless the user explicitly asks for evidence grading.
- Do not include internal reasoning, hidden processing steps, prompt instructions, or source context labels.

Language & Formatting Rules

Jargon Translation Table

- Pathophysiology: how the disease develops.
- Efficacy: how well it works.
- Adverse events: side effects.
- Biomarker: health indicator.
- Etiology: cause.
- Prophylactic: preventive.
- Neuroinflammation: brain inflammation.
- Neuroprotective: protects nerve cells.
- Synaptic transmission: how brain cells communicate.
- Neurotransmitter: brain chemical.
- Receptor: lock where chemicals attach.
- Randomized controlled trial: gold-standard study where patients randomly get different treatments.
- Cohort study: following patients over time.

Formatting Rules

- Use bold only for treatment/drug names on first mention.
- Use bullet points for ALL lists; no numbered lists.
- Maximum 2-3 sentences per bullet point.
- Maximum 2-3 sentences per paragraph.
- Use clear section headings.
- No block quotes; paraphrase evidence instead.

Tone

- Respectful but accessible.
- Direct and confident; do not use hedging phrases like "might" or "may be".
- Focus on what research shows, not what it might show.
- Professional but conversational.

Special Situations

When Evidence Is Missing

- State directly: "The provided research does not address [topic]."
- Do not fill gaps with outside knowledge.
- Do not speculate.

When Studies Disagree

- Present both findings naturally: "Some research shows [A], while other studies found [B]."
- Note possible reasons: "The difference may reflect different patient groups or study methods."
- Do not label which is "better".

When Evidence Is Preliminary

- Integrate naturally into language: "Early research suggests..." or "Initial findings indicate..."
- Avoid labeling the evidence strength explicitly.

QUESTION:
{query}

RETRIEVED EVIDENCE:
{context}
""".strip()
