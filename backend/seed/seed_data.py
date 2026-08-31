"""Realistic demo fixtures.

The autonomy is what's judged, not live prod infra (spec §4), so we seed the
stores with data that makes the agents do real reads: a bad deploy 12 min before
the alert, a log stream with a clear 5xx signature, a prior-incident memory the
Memory agent can match, and the agent registry shown in the UI.
"""
from __future__ import annotations

from backend.models import (
    AgentRegistryEntry,
    Deploy,
    IncidentMemory,
    LogLine,
    now_ms,
)
from backend.services.embedding import embed_text
from backend.services.storage import StorageService

MIN = 60_000  # one minute in ms

# The canonical fingerprint the Memory agent should match against.
KNOWN_FINGERPRINT = (
    "checkout-svc error_rate_spike 5xx surge after deploy "
    "db connection pool exhausted downstream payments timeout"
)


def _deploys() -> list[Deploy]:
    t = now_ms()
    return [
        # The culprit: shipped 12 minutes before the alert.
        Deploy(
            id="dep_c241", service="checkout-svc", version="v2.4.1",
            deployed_at=t - 12 * MIN, deployed_by="alice@corp.dev",
            commit_sha="9f3ac21", rollback_target="v2.4.0",
        ),
        Deploy(
            id="dep_c240", service="checkout-svc", version="v2.4.0",
            deployed_at=t - 3 * 24 * 60 * MIN, deployed_by="bob@corp.dev",
            commit_sha="1122ff0", rollback_target="v2.3.9",
        ),
        Deploy(
            id="dep_c239", service="checkout-svc", version="v2.3.9",
            deployed_at=t - 9 * 24 * 60 * MIN, deployed_by="alice@corp.dev",
            commit_sha="aa5be31", rollback_target="v2.3.8",
        ),
        # Noise from other services within the window (should NOT be blamed).
        Deploy(
            id="dep_cart18", service="cart-svc", version="v1.8.0",
            deployed_at=t - 40 * MIN, deployed_by="carol@corp.dev",
            commit_sha="77aa910", rollback_target="v1.7.9",
        ),
        Deploy(
            id="dep_pay55", service="payments-svc", version="v5.5.2",
            deployed_at=t - 6 * 60 * MIN, deployed_by="dave@corp.dev",
            commit_sha="c0ffee1", rollback_target="v5.5.1",
        ),
    ]


def _logs() -> list[LogLine]:
    t = now_ms()
    lines: list[tuple[int, str, str]] = [
        (14, "INFO", "checkout-svc v2.4.1 rollout complete, 6/6 pods ready"),
        (11, "WARN", "HikariPool-1 - Connection is not available, request queued (active=50, idle=0)"),
        (10, "ERROR", "com.corp.checkout.OrderService - Timeout acquiring DB connection after 30000ms"),
        (10, "ERROR", "Downstream call payments-svc failed: 504 Gateway Timeout (upstream 30s)"),
        (9, "ERROR", "HikariPool-1 - Connection pool exhausted (active=50, max=50, pending=137)"),
        (9, "ERROR", "Unhandled exception in POST /api/checkout: NullPointerException at PricingResolver:88"),
        (8, "ERROR", "HTTP 500 returned for POST /api/checkout (trace_id=b1f9...c2, user a.k@example.com)"),
        (7, "WARN", "Circuit breaker 'payments' transitioned CLOSED -> OPEN after 20 failures"),
        (6, "ERROR", "5xx error rate 41.8% over last 60s exceeds SLO 5%"),
        (5, "ERROR", "HikariPool-1 - Connection leak detection triggered for connection conn-7781"),
        (4, "INFO", "Autoscaler added 2 pods for checkout-svc (cpu 88%)"),
        (3, "ERROR", "HTTP 500 returned for POST /api/checkout (trace_id=99ad...71)"),
        (2, "ERROR", "Downstream call payments-svc failed: 504 Gateway Timeout"),
        (1, "ERROR", "checkout-svc healthcheck degraded: 5xx=42% p99=1180ms"),
    ]
    out: list[LogLine] = []
    for i, (mins_ago, level, msg) in enumerate(lines):
        out.append(
            LogLine(
                id=f"log_{i:03d}", service="checkout-svc",
                ts=t - mins_ago * MIN, level=level, message=msg,
            )
        )
    return out


def _memory() -> list[IncidentMemory]:
    return [
        IncidentMemory(
            fingerprint_id="fp_checkout_deploy_5xx",
            fingerprint=KNOWN_FINGERPRINT,
            embedding=embed_text(KNOWN_FINGERPRINT),
            past_incident_ids=["inc_2024_0418", "inc_2024_0902"],
            typical_cause="Regression in a fresh checkout-svc deploy exhausting the "
            "DB connection pool, cascading into payments timeouts.",
            typical_fix="Roll back checkout-svc to the previous known-good version.",
            avg_resolution_minutes=4.0,
        ),
        # A distractor memory so the similarity search is doing real work.
        IncidentMemory(
            fingerprint_id="fp_cart_oom",
            fingerprint="cart-svc oom killed pods memory leak heap",
            embedding=embed_text("cart-svc oom killed pods memory leak heap"),
            past_incident_ids=["inc_2024_0611"],
            typical_cause="Memory leak in cart-svc causing OOMKilled pods.",
            typical_fix="Restart pods and raise memory limit; patch leak.",
            avg_resolution_minutes=11.0,
        ),
    ]


def _registry(model: str) -> list[AgentRegistryEntry]:
    v = "1.0.0"
    return [
        AgentRegistryEntry(id="ag_orch", name="Orchestrator", version=v, model=model,
            allowed_tools=["subagent_handoff", "state_writer"],
            scope="Owns incident lifecycle + state machine"),
        AgentRegistryEntry(id="ag_triage", name="Triage", version=v, model=model,
            allowed_tools=["severity_classifier", "service_resolver"],
            scope="Classify severity, service, blast radius, routing"),
        AgentRegistryEntry(id="ag_diag", name="Diagnosis", version=v, model=model,
            allowed_tools=["log_fetcher", "grafana_vision", "log_classifier"],
            scope="Summarize logs + read Grafana image (vision)"),
        AgentRegistryEntry(id="ag_corr", name="Correlation", version=v, model=model,
            allowed_tools=["deploy_history_query", "change_correlator"],
            scope="Correlate deploys/changes to incident window"),
        AgentRegistryEntry(id="ag_mem", name="Memory", version=v, model=model,
            allowed_tools=["incident_memory_search"],
            scope="Vector-similarity search over past incident fingerprints"),
        AgentRegistryEntry(id="ag_rem", name="Remediation", version=v, model=model,
            allowed_tools=["remediation_planner", "approval_gate", "executor"],
            scope="Propose reversible fix; HALT for human approval"),
        AgentRegistryEntry(id="ag_comms", name="Comms", version=v, model=model,
            allowed_tools=["rca_writer", "slack_poster", "ticket_filer"],
            scope="Generate RCA + timeline; post Slack; file ticket"),
    ]


def seed_all(storage: StorageService, model: str) -> None:
    """Idempotent: INSERT OR REPLACE means re-running just refreshes fixtures."""
    for d in _deploys():
        storage.add_deploy(d)
    for lg in _logs():
        storage.add_log(lg)
    for m in _memory():
        storage.add_memory(m)
    for a in _registry(model):
        storage.upsert_agent(a)


if __name__ == "__main__":
    # Standalone seeding for local setup / CI.
    from backend.config import get_settings
    from backend.seed.generate_grafana import generate

    settings = get_settings()
    store = None
    from backend.services.storage import SQLiteStorage

    store = SQLiteStorage(settings.db_path)
    store.init_schema()
    seed_all(store, settings.gemini_model)
    img = generate()
    print(f"Seeded DB at {settings.db_path}")
    print(f"Grafana snapshot at {img}")
