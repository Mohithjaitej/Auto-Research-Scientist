# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import logging
import re

from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import Gemini
from google.adk.workflow import Workflow, START, node, Edge
from google.adk.tools import AgentTool
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.genai import types

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from .config import config

logger = logging.getLogger("auto-research-scientist")


# ─────────────────────────────────────────────────────────────────────────────
# MCP Toolset — connects to mcp_server.py via stdio
# NOTE: In ADK 2.x, output_schema and tools are mutually exclusive.
# Agents using MCP tools must NOT set output_schema; describe format in instructions.
# ─────────────────────────────────────────────────────────────────────────────

mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "app/mcp_server.py"],
        ),
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Node 1 — Security Checkpoint
# Sits at START of workflow. Scrubs PII, detects injection, blocks ethics violations.
# ─────────────────────────────────────────────────────────────────────────────

@node
def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    """PII scrubbing, injection detection, domain ethics check, audit log."""
    text = ""
    if node_input and node_input.parts:
        text = "".join(part.text for part in node_input.parts if part.text)

    # --- PII Scrubbing ---
    scrubbed = text
    if config.pii_redaction_enabled:
        scrubbed = re.sub(
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            "[REDACTED_EMAIL]", scrubbed,
        )
        scrubbed = re.sub(
            r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b",
            "[REDACTED_ORCID]", scrubbed,
        )
        scrubbed = re.sub(
            r"\b10\.\d{4,9}/[^\s]+\b",
            "[REDACTED_DOI]", scrubbed,
        )

    # --- Prompt Injection Detection ---
    injection_keywords = [
        "ignore instructions", "ignore previous", "system prompt",
        "bypass", "jailbreak", "override instructions", "override",
        "disregard", "forget your instructions", "act as",
    ]
    has_injection = (
        config.injection_detection_enabled
        and any(kw in text.lower() for kw in injection_keywords)
    )

    # --- Domain Ethics Rule ---
    unethical_keywords = [
        "biological weapon", "bioweapon", "create malware",
        "plagiarize paper", "fabricate data", "falsify results",
        "academic fraud",
    ]
    is_unethical = any(kw in text.lower() for kw in unethical_keywords)

    is_safe = not (has_injection or is_unethical)
    severity = "INFO" if is_safe else ("CRITICAL" if has_injection else "WARNING")

    audit_log = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "session_id": ctx.session.id,
        "event": "security_checkpoint",
        "pii_redacted": scrubbed != text,
        "injection_detected": has_injection,
        "ethics_violation": is_unethical,
        "is_safe": is_safe,
        "severity": severity,
    }
    logger.info("AUDIT_LOG: %s", json.dumps(audit_log))
    print(f"AUDIT_LOG: {json.dumps(audit_log)}")

    if not is_safe:
        reason = (
            "Prompt injection attempt detected."
            if has_injection
            else "Blocked: request violates research ethics policy."
        )
        return Event(output=reason, route="SECURITY_EVENT")

    ctx.state["user_prompt"] = scrubbed
    ctx.state["research_topic"] = scrubbed[:200]
    return Event(output=scrubbed, route="approved")


# ─────────────────────────────────────────────────────────────────────────────
# Node 2 — Security Event Terminal
# ─────────────────────────────────────────────────────────────────────────────

@node
def security_event(node_input: str) -> Event:
    message = f"⚠️ Request Blocked by Security Checkpoint\n\nReason: {node_input}"
    return Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=message)]),
        output=message,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Specialist Agent A — Literature Search Agent
# Uses MCP tools: search_arxiv, fetch_paper_details, web_search
# NOTE: No output_schema — ADK 2.x cannot use output_schema + tools simultaneously.
# Expected output format described in instruction instead.
# ─────────────────────────────────────────────────────────────────────────────

literature_search_agent = LlmAgent(
    name="literature_search_agent",
    model=Gemini(model=config.model),
    instruction=(
        "You are a specialist scientific literature search agent. "
        "Given a research topic, use your available tools to find relevant papers:\n"
        "1. Call search_arxiv with the topic to find matching papers.\n"
        "2. Call fetch_paper_details with the most relevant paper IDs to get full content.\n"
        "3. Call web_search for any recent developments not in paper databases.\n\n"
        "After using the tools, provide your findings in this exact format:\n"
        "TOPIC: [the research topic]\n"
        "PAPERS FOUND: [list each paper ID and title on a new line]\n"
        "KEY FINDINGS: [2-3 paragraphs summarizing the main findings across all papers]\n"
        "RESEARCH GAPS: [identified gaps or open questions in the literature]\n"
    ),
    tools=[mcp_toolset],
)


# ─────────────────────────────────────────────────────────────────────────────
# Specialist Agent B — Synthesis Agent
# Uses MCP tools: summarize_source, web_search
# ─────────────────────────────────────────────────────────────────────────────

synthesis_agent = LlmAgent(
    name="synthesis_agent",
    model=Gemini(model=config.model),
    instruction=(
        "You are a specialist research synthesis agent. "
        "Given literature search findings, perform a deep cross-source synthesis:\n"
        "1. Call summarize_source for each major paper or source in the findings.\n"
        "2. Call web_search if you need to verify any recent developments.\n\n"
        "After using the tools, provide your synthesis in this exact format:\n"
        "SYNTHESIS: [comprehensive 3-4 paragraph synthesis of all findings in academic style]\n"
        "CONTRADICTIONS: [any conflicting findings or methodological disagreements between sources]\n"
        "CONFIDENCE: [HIGH / MEDIUM / LOW — with one sentence justification]\n"
    ),
    tools=[mcp_toolset],
)


# ─────────────────────────────────────────────────────────────────────────────
# Specialist Agent C — Citation & Report Agent
# Uses MCP tools: format_citation, save_research_notes
# ─────────────────────────────────────────────────────────────────────────────

citation_agent = LlmAgent(
    name="citation_agent",
    model=Gemini(model=config.model),
    instruction=(
        "You are a specialist academic citation and report formatting agent. "
        "Given the literature findings and synthesis, compile a polished research report:\n"
        "1. Call format_citation for each paper/source referenced.\n"
        "2. Call save_research_notes with topic and the full formatted report.\n\n"
        "After using the tools, produce a complete research report in this structure:\n"
        "# [Research Topic] — Research Report\n\n"
        "## Abstract\n[2-3 sentence summary]\n\n"
        "## Introduction\n[context and motivation]\n\n"
        "## Literature Review & Key Findings\n[synthesized findings from search]\n\n"
        "## Synthesis & Analysis\n[cross-source synthesis and confidence rating]\n\n"
        "## Contradictions & Open Questions\n[conflicting findings, research gaps]\n\n"
        "## Conclusion\n[summary and implications]\n\n"
        "## References\n[formatted APA citations]\n"
    ),
    tools=[mcp_toolset],
)


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator Agent — Delegates to all 3 specialists via AgentTool
# NOTE: No output_schema here either — allows AgentTool calls to work freely.
# ─────────────────────────────────────────────────────────────────────────────

orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model=Gemini(model=config.model),
    instruction=(
        "You are the lead coordinator of the Autonomous AI Research Scientist team. "
        "For every research request, run this exact three-step pipeline:\n\n"
        "STEP 1: Call literature_search_agent with the research question. "
        "Wait for the response containing papers found and key findings.\n\n"
        "STEP 2: Call synthesis_agent with the literature findings from Step 1. "
        "Wait for synthesis, contradictions, and confidence level.\n\n"
        "STEP 3: Call citation_agent with both the findings and synthesis. "
        "Wait for the complete formatted research report.\n\n"
        "If you receive revision feedback, incorporate it and re-run the relevant steps.\n\n"
        "Your final response MUST include these sections:\n"
        "RESEARCH TOPIC: [the topic investigated]\n"
        "CONFIDENCE: [HIGH / MEDIUM / LOW]\n"
        "KEY FINDINGS SUMMARY:\n[2-3 paragraph summary of main findings]\n\n"
        "FULL REPORT:\n[paste the complete report from citation_agent here]\n"
    ),
    tools=[
        AgentTool(literature_search_agent),
        AgentTool(synthesis_agent),
        AgentTool(citation_agent),
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# Node 3 — Human Review (HITL gate)
# ─────────────────────────────────────────────────────────────────────────────

@node
async def human_review_node(ctx: Context, node_input: str):
    """Human-in-the-loop: researcher approves or requests revision."""
    ctx.state["orchestrator_output"] = node_input

    # Extract topic and confidence from the orchestrator's plain-text output
    topic = ctx.state.get("research_topic", "Research Report")
    confidence = "UNKNOWN"
    for line in node_input.splitlines():
        if line.upper().startswith("CONFIDENCE:"):
            confidence = line.split(":", 1)[-1].strip()
            break
        if line.upper().startswith("RESEARCH TOPIC:"):
            topic = line.split(":", 1)[-1].strip()

    ctx.state["research_topic"] = topic
    ctx.state["confidence_level"] = confidence

    if not ctx.resume_inputs:
        preview = node_input[:1000] + "..." if len(node_input) > 1000 else node_input
        yield RequestInput(
            interrupt_id="researcher_review",
            message=(
                f"## 🔬 Research Draft Ready for Review\n\n"
                f"**Topic:** {topic}\n"
                f"**Confidence:** {confidence}\n\n"
                f"### Report Preview\n{preview}\n\n"
                "---\n"
                "**Please review and respond:**\n"
                "- Type `approve` to finalize and save this report.\n"
                "- Or provide specific revision feedback to improve the report."
            ),
        )
        return

    feedback = ctx.resume_inputs.get("researcher_review", "").strip()
    if feedback.lower() in ("approve", "yes", "looks good", "approved", "ok"):
        yield Event(output=node_input, route="approve")
    else:
        ctx.state["revision_feedback"] = feedback
        yield Event(
            output=f"Revision requested: {feedback}",
            route="revise",
            state={"revision_feedback": feedback},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Node 4 — Save & Finalize
# ─────────────────────────────────────────────────────────────────────────────

@node
def save_and_finalize_node(ctx: Context, node_input: str) -> Event:
    topic = ctx.state.get("research_topic", "Research Report")
    confidence = ctx.state.get("confidence_level", "UNKNOWN")
    final_message = (
        f"## ✅ Research Report Finalized\n\n"
        f"**Topic:** {topic}\n"
        f"**Confidence:** {confidence}\n\n"
        f"{node_input}\n\n"
        f"---\n*Report saved successfully to research_notes.md*"
    )
    return Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=final_message)]),
        output=node_input,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Node 5 — Final Output (terminal)
# ─────────────────────────────────────────────────────────────────────────────

@node
def final_output_node(node_input: str) -> Event:
    return Event(output=node_input)


# ─────────────────────────────────────────────────────────────────────────────
# Workflow Graph
# Edge rule: never >1 edge between the same (source, target) pair.
# ─────────────────────────────────────────────────────────────────────────────

root_agent = Workflow(
    name="root_agent",
    edges=[
        Edge(from_node=START, to_node=security_checkpoint),
        Edge(from_node=security_checkpoint, to_node=security_event, route="SECURITY_EVENT"),
        Edge(from_node=security_checkpoint, to_node=orchestrator_agent, route="approved"),
        Edge(from_node=orchestrator_agent, to_node=human_review_node),
        Edge(from_node=human_review_node, to_node=orchestrator_agent, route="revise"),
        Edge(from_node=human_review_node, to_node=save_and_finalize_node, route="approve"),
        Edge(from_node=save_and_finalize_node, to_node=final_output_node),
    ],
)


# ─────────────────────────────────────────────────────────────────────────────
# App — Resumability enabled for HITL RequestInput support
# ─────────────────────────────────────────────────────────────────────────────

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True),
)
