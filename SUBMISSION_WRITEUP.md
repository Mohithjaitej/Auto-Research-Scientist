# SUBMISSION WRITEUP — Auto Research Scientist

## Problem Statement

Scientific research is bottlenecked by the time required to search, read, and synthesize literature. A PhD researcher can spend 40–60% of their time on literature review alone — weeks per topic, manually querying databases, skimming hundreds of abstracts, and painstakingly cross-referencing citations. For resource-limited researchers and institutions in developing regions, this bottleneck is even more severe.

**Auto Research Scientist** addresses this directly: given a research question, the system autonomously searches scientific paper databases, extracts key findings, detects contradictions between sources, synthesizes the evidence, formats proper citations, and delivers a structured, peer-review-ready draft — with human expert oversight at the final approval gate.

---

## Solution Architecture

```
User Prompt
    │
    ▼
┌──────────────────────────────────────────────────┐
│  Security Checkpoint Node                         │
│  PII scrub (email/ORCID/DOI) · Injection detect  │
│  Ethics rule · JSON audit log                     │
└─────────┬────────────────────┬───────────────────┘
          │ approved            │ SECURITY_EVENT
          ▼                     ▼
┌──────────────────┐    ┌───────────────┐
│  Orchestrator    │    │ Security Event│
│  Agent           │    │ (terminal)    │
│  (coordinates    │    └───────────────┘
│  all specialists)│
└────────┬─────────┘
         │  delegates via AgentTool
    ┌────┼────────────────────────┐
    ▼    ▼                        ▼
┌──────────────┐  ┌────────────────┐  ┌─────────────────┐
│ Literature   │  │  Synthesis     │  │  Citation &     │
│ Search Agent │  │  Agent         │  │  Report Agent   │
└──────────────┘  └────────────────┘  └─────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│  Human Review Node (HITL — RequestInput)          │
└─────────┬───────────────────────┬────────────────┘
          │ revise                 │ approve
          ▼                        ▼
   Orchestrator (loop)      Save & Finalize → Final Output
```

---

## Concepts Used

### ADK Workflow Graph
- **File:** `app/agent.py`
- Uses `from google.adk.workflow import Workflow, START, node, Edge`
- 7 nodes connected by directed edges with named routes (`approved`, `SECURITY_EVENT`, `revise`, `approve`)
- `ctx.state` used in `human_review_node` and `save_and_finalize_node` for inter-node data sharing
- Strict edge rule enforced: no duplicate `(from_node, to_node)` pairs

### LlmAgent + AgentTool
- **File:** `app/agent.py`
- Three specialist `LlmAgent` instances: `literature_search_agent`, `synthesis_agent`, `citation_agent`
- Each has domain-specific `instruction`, `tools=[mcp_toolset]`, and a Pydantic `output_schema`
- `orchestrator_agent` wraps all three via `AgentTool(agent)` — enabling sequential delegation
- `orchestrator_agent` runs the full pipeline: Search → Synthesize → Cite

### MCP Server
- **File:** `app/mcp_server.py`
- 6 domain tools over stdio transport using `FastMCP`
- `search_arxiv` + `fetch_paper_details` + `web_search` → wired to `literature_search_agent` and `synthesis_agent`
- `summarize_source` → wired to `synthesis_agent`
- `format_citation` + `save_research_notes` → wired to `citation_agent`
- Connected via `McpToolset` with `StdioConnectionParams`

### Security Checkpoint
- **File:** `app/agent.py` — `security_checkpoint()` function node
- PII scrubbing: email regex, ORCID pattern (`\d{4}-\d{4}-\d{4}-\d{3}[\dX]`), DOI pattern
- Prompt injection: 10 keyword patterns (`ignore instructions`, `jailbreak`, `bypass`, etc.)
- Domain ethics rule: blocks requests for data fabrication, academic fraud, bioweapon research
- Structured JSON audit log on every request: `{timestamp, session_id, severity, is_safe, ...}`
- Routes to terminal `security_event` node on violation — no agents are ever invoked

### Agents CLI
- Scaffolded with `agents-cli scaffold create auto-research-scientist --agent adk --deployment-target agent_runtime`
- `GEMINI.md` auto-generated as agent guidance file
- `agents-cli-manifest.yaml` defines: `agent_directory: app`, `deployment_target: agent_runtime`
- `make playground` launches `adk web app --host 127.0.0.1 --port 18081`

---

## Security Design

| Control | Implementation | Why It Matters |
|---------|---------------|----------------|
| PII Scrubbing | Regex for email, ORCID, DOI | Prevents researcher identities leaking into LLM context or logs |
| Prompt Injection | 10-keyword heuristic detection | Research systems access powerful tools; injected instructions could misuse them |
| Ethics Filter | Domain keyword blocklist | AI research assistants must refuse requests for data fabrication or weapon design |
| Audit Log | Structured JSON with severity | Every request produces an immutable audit trail for compliance and forensics |
| HITL Gate | `RequestInput` before report finalization | Human expert catches hallucinations, fabricated citations, or low-confidence outputs |

---

## MCP Server Design

| Tool | Purpose | Used By |
|------|---------|---------|
| `search_arxiv` | Keyword-scored search across paper database | `literature_search_agent` |
| `fetch_paper_details` | Full paper content retrieval by ID | `literature_search_agent` |
| `web_search` | Recent web results beyond paper databases | `literature_search_agent`, `synthesis_agent` |
| `summarize_source` | Structured condensation of source text | `synthesis_agent` |
| `format_citation` | APA/MLA/Chicago citation formatting | `citation_agent` |
| `save_research_notes` | Persist draft reports to local markdown file | `citation_agent` |

---

## HITL Flow

The `human_review_node` uses ADK's `RequestInput` to pause the workflow and present:
- Research topic and confidence level
- Key findings summary
- First 800 characters of the full report preview

The researcher responds with either:
- `"approve"` → routes to `save_and_finalize_node`
- Any other text → treated as revision feedback, stored in `ctx.state["revision_feedback"]`, routes back to `orchestrator_agent`

This loop can repeat indefinitely until the researcher approves. `ResumabilityConfig(is_resumable=True)` ensures the session survives the interruption.

**Why:** Fully autonomous research report generation carries a real risk of hallucinated citations or misrepresented findings. The HITL gate ensures a human expert validates the output before it is saved and presented as final.

---

## Demo Walkthrough

Refer to the three sample test cases in [README.md](README.md):

1. **Standard Query** — demonstrates the full pipeline from question to HITL approval gate
2. **Revision Loop** — demonstrates `ctx.state` revision feedback and the orchestrator loop
3. **Security Block** — demonstrates the security checkpoint blocking an unethical request

---

## Impact / Value Statement

**Who benefits:**
- Graduate students and junior researchers who spend most of their time on literature review
- Researchers in low-resource settings without institutional database access
- Interdisciplinary teams needing rapid synthesis across unfamiliar fields
- Research labs accelerating systematic reviews for grant applications

**How:**
- Reduces literature review time from weeks to minutes for initial drafts
- Detects contradictions in the literature automatically — a task humans often miss
- Produces properly formatted citations, eliminating a significant source of submission errors
- The HITL approval gate ensures AI augments rather than replaces expert judgment

**Broader impact:** As AI research assistants become standard tools in academia, this project demonstrates how to build them safely — with security checkpoints, audit logging, and mandatory human oversight — setting a responsible precedent for AI-assisted scientific discovery.