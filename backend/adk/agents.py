"""The six specialized sub-agents as REAL google-adk `LlmAgent`s.

Each wraps its existing instruction prompt + real tools, runs on the
retry-wrapped `RetryGemini` (Flash), and streams every step via ADK callbacks.
Governance (approval gate, PII scrub, execution) stays in the orchestrator, so
the LLM plans but never executes a destructive action unilaterally.
"""
from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from backend.adk.callbacks import make_callbacks
from backend.adk.retry_llm import RetryGemini
from backend.adk import tools as TL
from backend.agents.base import RunContext
from backend.config import get_settings


def _model() -> RetryGemini:
    # Flash for every agent (hard rule); id from config (gemini-3.5-flash).
    return RetryGemini(model=get_settings().gemini_model)


def _agent(name: str, instruction: str, tools, rc: RunContext, capture: dict[str, Any]) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=_model(),
        instruction=instruction,
        tools=tools,
        **make_callbacks(rc, name, capture),
    )


def build_agents(rc: RunContext, capture: dict[str, Any]) -> dict[str, LlmAgent]:
    """Construct all six LlmAgents bound to this incident's context."""
    return {
        "Triage": _agent(
            "Triage",
            "You are the Triage agent of an autonomous SRE system. FIRST call "
            "resolve_service_and_severity to get hard signals. Then decide the "
            "severity (SEV1 highest..SEV4 lowest) — never rate a tier-0 service "
            "below the rubric_severity. Respond with ONLY JSON: "
            '{"severity":"SEV1|SEV2|SEV3|SEV4","blast_radius":"one sentence",'
            '"oncall":"channel","reasoning":"1-2 sentences"}.',
            TL.triage_tools(rc), rc, capture,
        ),
        "Diagnosis": _agent(
            "Diagnosis",
            "You are the Diagnosis agent. A Grafana dashboard screenshot for the "
            "affected service is attached to this message. FIRST call "
            "fetch_and_classify_logs to see the log signature. THEN read the "
            "Grafana image: identify the anomaly (which panel, the numbers, when "
            "it started). Respond with ONLY JSON: "
            '{"summary":"2-3 sentence technical diagnosis",'
            '"primary_symptom":"short phrase","vision_confirmed":true,'
            '"vision_observation":"what the panels show, with numbers",'
            '"vision_annotation":"short caption to overlay on the image",'
            '"reasoning":"1 sentence"}.',
            TL.diagnosis_tools(rc), rc, capture,
        ),
        "Correlation": _agent(
            "Correlation",
            "You are the Correlation agent. Call query_recent_deploys to get the "
            "ranked change suspects with temporal proximity scores. A high "
            "proximity score for a deploy just before detection is strong "
            "evidence of a bad-deploy regression; let your confidence track that "
            "score (do not exceed it by much). Respond with ONLY JSON: "
            '{"probable_cause":"one sentence naming the root cause",'
            '"confidence":0.0,"reasoning":"1-2 sentences"}.',
            TL.correlation_tools(rc), rc, capture,
        ),
        "Memory": _agent(
            "Memory",
            "You are the Memory agent. Call search_incident_memory to find the "
            "closest past incident by fingerprint similarity. If the best cosine "
            "similarity is >= 0.4, recommend the historically-effective fix; "
            "otherwise say there is no strong prior. Respond with ONLY JSON: "
            '{"recommendation":"e.g. Seen 2x, resolved in ~4m via rollback",'
            '"has_strong_prior":true,"reasoning":"1 sentence"}.',
            TL.memory_tools(rc), rc, capture,
        ),
        "Remediation": _agent(
            "Remediation",
            "You are the Remediation agent. The correlation and memory findings "
            "are in the message. Choose ONE reversible action and call "
            "propose_remediation(action, rollback_target, rationale). For a "
            "bad-deploy regression choose action='rollback' with the suspect's "
            "rollback_target; prefer the historically-effective fix if given. "
            "Respond with ONLY JSON: "
            '{"action":"rollback|scale_out|restart|flag_off",'
            '"rationale":"one sentence","reasoning":"1 sentence"}.',
            TL.remediation_tools(rc), rc, capture,
        ),
        # Comms writes prose, not JSON, and uses no tools (Slack + ticket are done
        # in the orchestrator so PII scrubbing is guaranteed before egress).
        "Comms": _agent(
            "Comms",
            "You are the Comms agent. Using all the incident findings in the "
            "message, write a clear, honest post-incident RCA in GitHub-flavored "
            "Markdown with sections: Summary, Impact, Root Cause, Detection & "
            "Diagnosis, Remediation, Timeline, Follow-ups. If remediation ran in "
            "simulation, say so. Output the Markdown document ONLY — no code "
            "fences, no JSON.",
            [], rc, capture,
        ),
    }
