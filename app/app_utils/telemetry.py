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

import logging
import os


def setup_telemetry() -> str | None:
    """Configure telemetry settings."""

    # Don't capture prompt/response content in traces.
    os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")

    # Disable Google Cloud Agent Engine telemetry by default.
    os.environ.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "false")

    bucket = os.environ.get("LOGS_BUCKET_NAME")
    capture_content = os.environ.get(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT",
        "false",
    )

    if bucket and capture_content != "false":
        logging.info(
            "Prompt-response logging enabled (metadata only)."
        )

        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "NO_CONTENT"
        os.environ.setdefault(
            "OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT",
            "jsonl",
        )
        os.environ.setdefault(
            "OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK",
            "upload",
        )
        os.environ.setdefault(
            "OTEL_SEMCONV_STABILITY_OPT_IN",
            "gen_ai_latest_experimental",
        )

        commit_sha = os.environ.get("COMMIT_SHA", "dev")

        os.environ.setdefault(
            "OTEL_RESOURCE_ATTRIBUTES",
            f"service.namespace=auto-research-scientist,service.version={commit_sha}",
        )

        path = os.environ.get("GENAI_TELEMETRY_PATH", "completions")

        os.environ.setdefault(
            "OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH",
            f"gs://{bucket}/{path}",
        )

    else:
        logging.info("Google Cloud telemetry disabled.")

    return bucket


def setup_agent_engine_telemetry() -> None:
    """
    Configure Google Cloud Agent Engine telemetry.

    This is disabled unless explicitly enabled by setting:

        GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true
    """

    enabled = os.getenv(
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY",
        "false",
    ).lower()

    if enabled not in ("true", "1"):
        print("Google Cloud Agent Engine telemetry is disabled.")
        return

    try:
        import google.auth
        from vertexai.agent_engines.templates.adk import (
            _default_instrumentor_builder,
        )

        _, project_id = google.auth.default()

        _default_instrumentor_builder(
            project_id,
            enable_tracing=True,
            enable_logging=True,
        )

        print(f"Google Cloud telemetry enabled for project: {project_id}")

    except Exception as e:
        print(f"Skipping Google Cloud telemetry: {e}")