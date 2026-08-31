"""Fire the demo incident: drop a real alert onto the running AegisOps bus.

Usage:
    python scripts/publish_alert.py                 # default checkout-svc SEV1
    python scripts/publish_alert.py --url http://localhost:8080

This posts to /api/alerts, which publishes onto the in-process event bus exactly
as a real Pub/Sub push would. The Orchestrator picks it up and the war room
lights up.
"""
from __future__ import annotations

import argparse
import sys

import httpx

DEFAULT_SNAPSHOT = "backend/seed/grafana_checkout_spike.png"


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish a demo alert to AegisOps")
    ap.add_argument("--url", default="http://localhost:8080", help="AegisOps base URL")
    ap.add_argument("--service", default="checkout-svc")
    ap.add_argument("--alert", default="HighErrorRate")
    ap.add_argument("--error-rate", default="42%")
    ap.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    args = ap.parse_args()

    payload = {
        "alert": args.alert,
        "service": args.service,
        "error_rate": args.error_rate,
        "grafana_snapshot": args.snapshot,
    }

    try:
        resp = httpx.post(f"{args.url}/api/alerts", json=payload, timeout=15.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"✗ Failed to publish alert: {exc}", file=sys.stderr)
        print("  Is the backend running?  uvicorn backend.main:app --port 8080", file=sys.stderr)
        return 1

    print("✓ Alert published to AegisOps event bus:")
    print(f"    {payload['alert']} on {payload['service']} @ {payload['error_rate']}")
    print(f"  Response: {resp.json()}")
    print("  Watch the war room — the agents are now working the incident.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
