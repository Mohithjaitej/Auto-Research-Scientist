"""
MCP Server for Auto Research Scientist
Domain tools: search_arxiv, fetch_paper_details, web_search,
              summarize_source, format_citation, save_research_notes

Used by: literature_search_agent (search_arxiv, fetch_paper_details, web_search)
         synthesis_agent (summarize_source, web_search)
         citation_agent (format_citation, save_research_notes)
"""

import datetime
import os
import re
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AutoResearchScientistServer")


# ── Tool 1: search_arxiv ──────────────────────────────────────────────────────

@mcp.tool()
def search_arxiv(query: str, max_results: int = 5) -> str:
    """Searches a simulated arXiv/PubMed database for scientific papers.

    Args:
        query: Search keywords or research question.
        max_results: Maximum number of results to return (default 5).

    Returns:
        JSON-like string listing matching papers with IDs, titles, authors,
        year, and abstract snippets.
    """
    PAPER_DATABASE = [
        {
            "id": "arXiv:2401.00001",
            "title": "Autonomous LLM Agents in Scientific Discovery",
            "authors": "Smith, A., Patel, R., Kim, J.",
            "year": 2024,
            "keywords": ["autonomous agent", "llm", "scientific discovery", "ai research"],
            "abstract": (
                "We present a framework where autonomous LLM agents design experiments, "
                "search literature, and generate hypotheses, achieving a 3x speedup in "
                "research iteration cycles compared to human-only baselines."
            ),
        },
        {
            "id": "arXiv:2403.04210",
            "title": "Retrieval-Augmented Generation for Scientific Knowledge Synthesis",
            "authors": "Jones, M., Gupta, S., Chen, L.",
            "year": 2024,
            "keywords": ["rag", "retrieval", "synthesis", "knowledge", "science"],
            "abstract": (
                "This paper evaluates RAG architectures for synthesizing multi-domain "
                "scientific literature, showing domain-tuned embeddings outperform "
                "general-purpose models by 38% on retrieval precision benchmarks."
            ),
        },
        {
            "id": "arXiv:2311.12091",
            "title": "Security and Safety in Scientific LLM Assistants",
            "authors": "Brown, K., Alvarez, T., Zhao, W.",
            "year": 2023,
            "keywords": ["security", "safety", "prompt injection", "llm", "scientific"],
            "abstract": (
                "We evaluate prompt injection vulnerabilities in 10 scientific AI assistants. "
                "8/10 were susceptible to injected instructions embedded in paper abstracts. "
                "We propose layered input sanitization and security checkpoint architectures."
            ),
        },
        {
            "id": "arXiv:2405.07820",
            "title": "Multi-Agent Orchestration for Systematic Literature Reviews",
            "authors": "Wilson, E., Nakamura, H., Okonkwo, F.",
            "year": 2024,
            "keywords": ["multi-agent", "literature review", "orchestration", "systematic"],
            "abstract": (
                "Systematic literature reviews are time-intensive. We propose a multi-agent "
                "system with specialized sub-agents for search, screening, and synthesis, "
                "reducing review time from weeks to hours."
            ),
        },
        {
            "id": "arXiv:2406.11234",
            "title": "Hypothesis Generation via Chain-of-Thought Reasoning in Research Agents",
            "authors": "Lee, C., Martinez, P., Singh, V.",
            "year": 2024,
            "keywords": ["hypothesis", "chain of thought", "reasoning", "research agent"],
            "abstract": (
                "We introduce a hypothesis-generation module for research agents using "
                "chain-of-thought prompting over retrieved literature. Human expert evaluation "
                "rates 72% of generated hypotheses as 'novel and plausible'."
            ),
        },
        {
            "id": "arXiv:2312.09876",
            "title": "Contradiction Detection in Scientific Literature Using NLP",
            "authors": "Thompson, R., Dubois, A., Iyer, K.",
            "year": 2023,
            "keywords": ["contradiction", "detection", "nlp", "literature", "science"],
            "abstract": (
                "Scientific papers often present conflicting findings. We build an NLP pipeline "
                "that identifies contradictions across paper corpora with 84% F1, enabling "
                "researchers to focus on contested areas of knowledge."
            ),
        },
        {
            "id": "arXiv:2407.00555",
            "title": "Human-in-the-Loop Validation for AI-Generated Research Summaries",
            "authors": "Park, Y., Russo, G., Ahmed, Z.",
            "year": 2024,
            "keywords": ["human in the loop", "hitl", "validation", "research", "ai"],
            "abstract": (
                "We study how human expert checkpoints in AI research pipelines improve "
                "output quality. Agents with approval gates score 31% higher in expert "
                "evaluation compared to fully autonomous pipelines."
            ),
        },
    ]

    query_lower = query.lower()
    query_tokens = set(re.split(r"\W+", query_lower))

    # Score each paper by keyword/abstract overlap
    scored = []
    for paper in PAPER_DATABASE:
        score = 0
        for kw in paper["keywords"]:
            if kw in query_lower:
                score += 3
        if any(tok in paper["title"].lower() for tok in query_tokens if len(tok) > 3):
            score += 2
        if any(tok in paper["abstract"].lower() for tok in query_tokens if len(tok) > 3):
            score += 1
        scored.append((score, paper))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [p for _, p in scored if _ >= 0][:max_results]

    if not results:
        results = [p for _, p in scored[:max_results]]

    lines = [f"Found {len(results)} papers for query: '{query}'\n"]
    for p in results:
        lines.append(
            f"[{p['id']}] {p['title']} ({p['year']})\n"
            f"  Authors: {p['authors']}\n"
            f"  Abstract: {p['abstract']}\n"
        )
    return "\n".join(lines)


# ── Tool 2: fetch_paper_details ───────────────────────────────────────────────

@mcp.tool()
def fetch_paper_details(paper_id: str) -> str:
    """Fetches the full content of a specific scientific paper by ID.

    Args:
        paper_id: The arXiv or PubMed ID (e.g., 'arXiv:2401.00001').

    Returns:
        Full paper content including introduction, methodology, results,
        and conclusion sections.
    """
    FULL_PAPERS = {
        "arXiv:2401.00001": (
            "Title: Autonomous LLM Agents in Scientific Discovery\n"
            "Authors: Smith, A., Patel, R., Kim, J. (2024)\n\n"
            "Introduction: Modern scientific discovery requires synthesizing vast bodies of "
            "literature, designing experiments, and iterating on hypotheses — tasks well suited "
            "to autonomous AI agents.\n\n"
            "Methodology: We deploy a pipeline of specialized LLM agents: a Planner, a "
            "Literature Searcher, an Experiment Designer, and a Reviewer, each with domain-specific "
            "tools. Agents communicate via structured JSON schemas.\n\n"
            "Results: Across 50 biology research tasks, the agent pipeline completed 38 autonomously "
            "(76%), with the remaining 12 requiring minimal human correction. Average cycle time "
            "dropped from 14 days to 4.7 days.\n\n"
            "Conclusion: Autonomous agents can meaningfully accelerate scientific research when "
            "equipped with literature search, code execution, and structured output tools."
        ),
        "arXiv:2403.04210": (
            "Title: Retrieval-Augmented Generation for Scientific Knowledge Synthesis\n"
            "Authors: Jones, M., Gupta, S., Chen, L. (2024)\n\n"
            "Introduction: Scientific synthesis demands precision — incorrectly retrieved context "
            "leads to hallucinated claims in AI-generated summaries.\n\n"
            "Methodology: We compare three retrieval strategies (BM25, dense embeddings, "
            "domain-tuned embeddings) across 12 scientific domains using 2,400 query-answer pairs.\n\n"
            "Results: Domain-tuned embeddings achieve 91.2% retrieval precision vs 65.8% for BM25 "
            "and 72.1% for generic dense models. Synthesis quality (ROUGE-L) improves by 38%.\n\n"
            "Conclusion: Domain-specific fine-tuning of retrieval models is critical for high-quality "
            "scientific RAG pipelines."
        ),
        "arXiv:2311.12091": (
            "Title: Security and Safety in Scientific LLM Assistants\n"
            "Authors: Brown, K., Alvarez, T., Zhao, W. (2023)\n\n"
            "Introduction: Scientific AI assistants are granted broad tool access — web search, "
            "code execution, file writes — making them high-value targets for adversarial inputs.\n\n"
            "Methodology: We injected 47 unique payloads into paper abstracts, conference bios, "
            "and metadata fields, then submitted these to 10 production research AI systems.\n\n"
            "Results: 8/10 systems executed injected instructions. Only 2 had explicit input "
            "sanitization layers. Common payload success vectors: author bio fields, dataset "
            "metadata, reference list entries.\n\n"
            "Conclusion: Research AI systems require multi-layer defenses: input sanitization, "
            "semantic injection detection, and behavioral monitoring of tool calls."
        ),
        "arXiv:2405.07820": (
            "Title: Multi-Agent Orchestration for Systematic Literature Reviews\n"
            "Authors: Wilson, E., Nakamura, H., Okonkwo, F. (2024)\n\n"
            "Introduction: A full systematic literature review (SLR) takes expert researchers "
            "4–16 weeks. AI acceleration is urgently needed.\n\n"
            "Methodology: We build a 4-agent SLR pipeline: Search Agent, Screening Agent, "
            "Data Extraction Agent, Synthesis Agent. Each communicates via structured data schemas.\n\n"
            "Results: For a benchmarked SLR (500 papers, oncology domain), our system reduced "
            "time to draft from 6 weeks to 11 hours, with expert-rated quality scores of 4.1/5.\n\n"
            "Conclusion: Specialized multi-agent pipelines with human oversight checkpoints "
            "deliver near-human quality SLRs at a fraction of the time and cost."
        ),
    }
    return FULL_PAPERS.get(
        paper_id,
        f"Paper '{paper_id}' not found in database. "
        "Try search_arxiv to find valid paper IDs.",
    )


# ── Tool 3: web_search ────────────────────────────────────────────────────────

@mcp.tool()
def web_search(query: str, num_results: int = 5) -> str:
    """Simulates a web search for recent developments not yet in paper databases.

    Args:
        query: The search query string.
        num_results: Number of results to return (default 5).

    Returns:
        Simulated search results with title, source, date, and snippet.
    """
    WEB_RESULTS = [
        {
            "title": "Google DeepMind's AlphaFold 3 Expands to RNA and DNA Structures",
            "source": "Nature (2024)",
            "snippet": (
                "AlphaFold 3 generalizes protein structure prediction to RNA, DNA, and small "
                "molecules, dramatically expanding the tool's utility for multi-omics research."
            ),
        },
        {
            "title": "OpenAI o3 Achieves Expert-Level Performance on FrontierMath",
            "source": "OpenAI Blog (2024)",
            "snippet": (
                "The o3 reasoning model solves 25.2% of previously unsolved FrontierMath problems, "
                "surpassing human expert baselines for the first time."
            ),
        },
        {
            "title": "Autonomous AI Research: Current Capabilities and Limitations",
            "source": "MIT Technology Review (2024)",
            "snippet": (
                "A survey of AI research tools in 2024 finds growing adoption of autonomous "
                "literature review systems, but persistent issues with hallucinated citations "
                "and lack of reproducibility verification."
            ),
        },
        {
            "title": "Multi-Agent Systems for Drug Discovery Show Promise in Clinical Trials",
            "source": "Science (2024)",
            "snippet": (
                "A multi-agent AI pipeline accelerated lead compound identification by 4x "
                "in Phase I trials, with 3 compounds advancing to Phase II testing."
            ),
        },
        {
            "title": "EU AI Act Research Exemptions: What Scientists Need to Know",
            "source": "Science Policy Weekly (2024)",
            "snippet": (
                "The EU AI Act grants conditional exemptions for AI systems used purely for "
                "scientific research, though safety and transparency requirements still apply."
            ),
        },
    ]

    query_lower = query.lower()
    scored = []
    for r in WEB_RESULTS:
        score = sum(
            1 for w in query_lower.split()
            if len(w) > 3 and (w in r["title"].lower() or w in r["snippet"].lower())
        )
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [r for _, r in scored[:num_results]]

    lines = [f"Web search results for: '{query}'\n"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. {r['title']}\n"
            f"   Source: {r['source']}\n"
            f"   {r['snippet']}\n"
        )
    return "\n".join(lines)


# ── Tool 4: summarize_source ──────────────────────────────────────────────────

@mcp.tool()
def summarize_source(source_text: str, focus: str = "key findings") -> str:
    """Produces a structured summary of a given source text.

    Args:
        source_text: The full text or abstract of the source to summarize.
        focus: What to focus on in the summary (default: 'key findings').

    Returns:
        A structured summary with: core claim, methodology, evidence strength,
        and relevance note.
    """
    word_count = len(source_text.split())
    sentences = [s.strip() for s in source_text.replace("\n", ". ").split(".") if len(s.strip()) > 20]
    first_two = ". ".join(sentences[:2]) + "." if len(sentences) >= 2 else source_text[:300]
    last_one = sentences[-1] + "." if sentences else ""

    return (
        f"=== Source Summary (Focus: {focus}) ===\n\n"
        f"Core Claim: {first_two}\n\n"
        f"Methodology Hint: [Extracted from methodology section — "
        f"involves structured experimental or analytical design]\n\n"
        f"Conclusion: {last_one}\n\n"
        f"Evidence Strength: {'STRONG' if word_count > 200 else 'MODERATE'} "
        f"({word_count} words analyzed)\n\n"
        f"Relevance: Directly addresses '{focus}' — recommended for inclusion in synthesis."
    )


# ── Tool 5: format_citation ───────────────────────────────────────────────────

@mcp.tool()
def format_citation(
    paper_id: str,
    authors: str,
    title: str,
    year: int,
    journal: str = "arXiv preprint",
    style: str = "APA",
) -> str:
    """Formats a citation for a scientific paper in the specified citation style.

    Args:
        paper_id: The paper identifier (e.g., 'arXiv:2401.00001').
        authors: Author names (e.g., 'Smith, A., Patel, R.').
        title: The full title of the paper.
        year: Publication year.
        journal: Journal or preprint server name (default: 'arXiv preprint').
        style: Citation style — 'APA', 'MLA', or 'Chicago' (default: 'APA').

    Returns:
        Formatted citation string in the requested style.
    """
    if style.upper() == "APA":
        citation = f"{authors} ({year}). {title}. *{journal}*. {paper_id}"
    elif style.upper() == "MLA":
        author_mla = authors.split(",")[0].strip() if "," in authors else authors
        citation = f'{author_mla}. "{title}." {journal}, {year}. {paper_id}.'
    elif style.upper() == "CHICAGO":
        citation = f'{authors}. "{title}." {journal} ({year}). {paper_id}.'
    else:
        citation = f"{authors} ({year}). {title}. {journal}. {paper_id}"

    return f"Formatted Citation [{style}]:\n{citation}"


# ── Tool 6: save_research_notes ───────────────────────────────────────────────

@mcp.tool()
def save_research_notes(topic: str, content: str, section: str = "general") -> str:
    """Saves research notes or a draft report to a local markdown file.

    Args:
        topic: The research topic or report title.
        content: The full text content to save (markdown supported).
        section: Report section label (e.g., 'findings', 'synthesis', 'final').

    Returns:
        Confirmation message with file path and timestamp.
    """
    file_path = "research_notes.md"
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry = (
        f"\n---\n"
        f"# [{section.upper()}] {topic}\n"
        f"*Saved: {timestamp}*\n\n"
        f"{content}\n"
    )
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(entry)
        abs_path = os.path.abspath(file_path)
        return f"✅ Saved '{section}' notes for '{topic}' to {abs_path} at {timestamp}."
    except Exception as e:
        return f"❌ Error saving notes: {e}"


if __name__ == "__main__":
    mcp.run()
