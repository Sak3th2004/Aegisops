"""Slack delivery for the Comms agent.

Real webhook when SLACK_WEBHOOK_URL is set; clean console fallback otherwise
(spec §9 allows this). The fallback is explicit — it returns delivered=False and
the exact payload, so the UI can show "would have posted" rather than pretend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from backend.config import get_settings


@dataclass
class SlackResult:
    delivered: bool
    channel: str          # "slack" | "console"
    detail: str
    payload: dict[str, Any]


async def post_incident(blocks_text: str, *, summary: str) -> SlackResult:
    """Post a Slack message. `blocks_text` is pre-rendered markdown; `summary`
    is the notification fallback text."""
    settings = get_settings()
    payload: dict[str, Any] = {
        "text": summary,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": blocks_text}},
        ],
    }

    if not settings.has_slack:
        # Explicit fallback — not a silent no-op.
        return SlackResult(
            delivered=False,
            channel="console",
            detail="SLACK_WEBHOOK_URL not set; printed to console instead.",
            payload=payload,
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(settings.slack_webhook_url, json=payload)
        resp.raise_for_status()
        return SlackResult(
            delivered=True,
            channel="slack",
            detail=f"Slack responded {resp.status_code}",
            payload=payload,
        )
