import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "False")  # Gemini API key only


@dataclass
class AgentConfig:
    # Reads model from environment GEMINI_MODEL.
    # Default: gemini-2.5-flash (gemini-1.5-* is retired and returns 404).
    # Use gemini-2.5-flash-lite for tighter free-tier quota.
    model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    mcp_server_port: int = 8090
    max_iterations: int = 3
    pii_redaction_enabled: bool = True
    injection_detection_enabled: bool = True

    # Research-specific settings
    max_papers_per_query: int = 5
    max_web_results: int = 10
    citation_style: str = "APA"
    report_sections: tuple = (
        "abstract",
        "introduction",
        "methodology",
        "findings",
        "contradictions",
        "conclusion",
        "references",
    )


config = AgentConfig()
