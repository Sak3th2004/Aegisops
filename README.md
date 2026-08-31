# AegisOps

**Autonomous multi-agent SRE on-call.** When a production alert fires, AegisOps
triages it, diagnoses the logs *and reads the Grafana dashboard with Gemini
vision*, correlates against recent deploys, recalls similar past incidents,
proposes a remediation **gated by human approval**, executes it, and auto-writes
the RCA — then posts the timeline to Slack and files a ticket. The entire 3am
on-call loop, run by six specialized agents under one orchestrator.

Built on **Gemini 3.5 Flash** (Google AI Studio key) with an **ADK-style
orchestrator-with-sub-agents** topology. Runs end to end on the **zero-billing
free tier** — SQLite for state, an in-process event bus for ingestion — and
deploys to **Cloud Run** for the "runs on Google Cloud" proof.

---

## Features

- **Six specialized agents + orchestrator**, not one monolithic prompt. Each has
  its own instruction prompt, scoped tools, and model config.
- **Multimodal diagnosis** — the Diagnosis agent reads the actual Grafana
  snapshot with Gemini vision to confirm the anomaly.
- **503-safe by design** — *every* model call funnels through one
  `GeminiService` with exponential-backoff-and-jitter retry, so the free tier's
  throttling never crashes the live demo.
- **Human-in-the-loop approval gate** — destructive remediations physically
  cannot execute until a human clicks Approve (an asyncio handshake, not a
  polled flag).
- **Every decision observable** — every agent step (input, reasoning, tool call,
  output, tokens, latency) is persisted to an audit log *and* streamed live to
  the UI over Server-Sent Events.
- **Governance layer** — approval gate, PII scrubber ("Model Armor" concept),
  full audit trail, and an agent registry surfaced in the UI.
- **Cloud-portable** — `StorageService`/`EventBus` interfaces mean the same code
  swaps SQLite→Firestore and the in-process bus→Pub/Sub by changing two lines.

---

## Architecture summary

```
publish_alert.py ──▶ POST /api/alerts ──▶ EventBus (InProcessBus)
                                              │
                                              ▼
                                        Orchestrator ── state machine
                                              │
      ┌──────────┬──────────┬───────────┬─────┴─────┬─────────────┬──────────┐
      ▼          ▼          ▼           ▼           ▼             ▼          ▼
   Triage   Diagnosis  Correlation   Memory    Remediation     Comms
      │          │          │           │        (approval        │
      └──────────┴──────────┴───────────┴───────── gate) ─────────┘
                              │
                              ▼
                       GeminiService (503-safe retry) ──▶ Gemini 3.5 Flash
                              │
             StorageService (SQLite)   StreamHub ──▶ SSE ──▶ React War Room
```

The whole backend is packaged into a single container and wrapped by **Cloud
Run**. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full component breakdown,
Mermaid diagrams, and the incident state machine.

---

## Multi-agent lineup

The agent registry (`backend/seed/seed_data.py`, surfaced at `GET /api/registry`):

| Agent | Scope | Allowed tools |
|---|---|---|
| **Orchestrator** | Owns incident lifecycle + state machine | `subagent_handoff`, `state_writer` |
| **Triage** | Classify severity, service, blast radius, routing | `severity_classifier`, `service_resolver` |
| **Diagnosis** | Summarize logs + read Grafana image (vision) | `log_fetcher`, `grafana_vision`, `log_classifier` |
| **Correlation** | Correlate deploys/changes to the incident window | `deploy_history_query`, `change_correlator` |
| **Memory** | Vector-similarity search over past incident fingerprints | `incident_memory_search` |
| **Remediation** | Propose a reversible fix; **HALT for human approval** | `remediation_planner`, `approval_gate`, `executor` |
| **Comms** | Generate RCA + timeline; post Slack; file ticket | `rca_writer`, `slack_poster`, `ticket_filer` |

All sub-agents run **`gemini-3.5-flash`**. The Orchestrator routes an incident
through them in order and owns the state machine; the Remediation agent owns the
approval-gate transitions because only it knows the gate outcome.

---

## Prerequisites

- **Python 3.11**
- **Node 18+** (only needed to build/run the frontend)
- A free **Google AI Studio API key** — https://aistudio.google.com/apikey
  (no billing account required)

---

## Setup

Run from the repo root:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install backend dependencies
pip install -r backend/requirements.txt

# 3. Configure your key
cp .env.example .env             # Windows: copy .env.example .env
#   then edit .env and set GEMINI_API_KEY=<your AI Studio key>
```

Nothing in AegisOps is stubbed — the agents make real Gemini calls, so a valid
`GEMINI_API_KEY` is required before the first incident.

---

## Run the backend

From the repo root:

```bash
uvicorn backend.main:app --port 8080
```

On startup the app initializes the SQLite schema, seeds realistic fixtures (a bad
deploy 12 min before the alert, a 5xx log stream, a matching prior-incident
memory, the agent registry) and generates the demo Grafana snapshot. Health
check:

```bash
curl http://localhost:8080/api/health
# {"status":"ok","model":"gemini-3.5-flash","gemini_key_present":true,"slack_configured":false}
```

## Run the frontend

The React "Incident War Room" lives in `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

Keep the backend running on `:8080` — the war room consumes its REST API and the
`GET /api/stream` SSE feed. In the single-container Cloud Run build, the backend
serves the compiled frontend directly (`backend/main.py` mounts `frontend/dist`
at `/` when it exists), so no separate dev server is needed in production.

## Fire the demo

With the backend running, drop the demo alert onto the event bus:

```bash
python scripts/publish_alert.py
# optional: python scripts/publish_alert.py --url http://localhost:8080
```

This POSTs to `/api/alerts` (exactly as a real Pub/Sub push would), the
Orchestrator spins up an incident, and the war room lights up.

### Demo flow (spec §5)

1. `scripts/publish_alert.py` drops a real alert: `HighErrorRate` on
   `checkout-svc` at `42%`, with the Grafana snapshot path.
2. Event bus → Orchestrator spins up an incident (`DETECTED`).
3. UI lights up: agents activate one by one, reasoning streaming live.
4. **Triage** → SEV1, `checkout-svc`, ~40% of traffic.
5. **Diagnosis** → summarizes the error logs *and* Gemini vision reads the
   Grafana image, confirms the latency spike, classifies the log lines.
6. **Correlation** → "`checkout-svc v2.4.1` deployed 12 min ago — ~0.91
   confidence root cause."
7. **Memory** → "Seen 2× before, both fixed by rollback, avg ~4 min."
8. **Remediation** → proposes `rollback checkout-svc → v2.4.0`, risk low, and
   **halts for approval**.
9. Human clicks **Approve** → the executor runs (a clean, explicit simulation),
   status → `RESOLVED`.
10. **Comms** → generates the RCA + timeline, posts to Slack (real webhook if
    configured, console fallback otherwise), files a ticket.
11. UI shows the full audit trail + generated RCA + resolution time.

Approve/reject from the UI, or directly:

```bash
curl -X POST http://localhost:8080/api/incidents/<id>/approve \
     -H 'Content-Type: application/json' -d '{"approver":"on-call-engineer"}'
```

---

## Cloud-portable

AegisOps is written cloud-native in *shape* while running for free. The two
local implementations — `SQLiteStorage` (behind the `StorageService` interface)
and `InProcessBus` (behind the `EventBus` interface) — are chosen in exactly one
place, the FastAPI lifespan in `backend/main.py`:

```python
# --- The one place local impls are chosen. Firestore/PubSub swap here. ---
storage = SQLiteStorage(settings.db_path)
bus = InProcessBus()
# ------------------------------------------------------------------------
```

Swapping to real GCP is writing `FirestoreStorage(StorageService)` /
`PubSubBus(EventBus)` and changing those two constructor lines — the agents, the
orchestrator, and the publisher script don't change.

---

## API endpoints

All served by `backend/main.py`:

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/alerts` | Publish an `Alert` onto the event bus |
| `GET` | `/api/health` | Status, model, key/slack presence |
| `GET` | `/api/registry` | The agent registry |
| `GET` | `/api/incidents` | All incidents |
| `GET` | `/api/incidents/{id}` | One incident (with `findings`) |
| `GET` | `/api/incidents/{id}/audit` | Full audit trail |
| `GET` | `/api/incidents/{id}/rca` | Generated RCA + comms findings |
| `GET` | `/api/incidents/{id}/grafana` | The exact PNG the vision agent read |
| `POST` | `/api/incidents/{id}/approve` | Approve the remediation (body `{approver,note}`) |
| `POST` | `/api/incidents/{id}/reject` | Reject the remediation |
| `GET` | `/api/stream` | SSE — all incidents |
| `GET` | `/api/stream/{id}` | SSE — one incident |

---

## Environment variables

Configured in `.env` (see `.env.example`). Read once via `backend/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | *(empty)* | **Required.** Google AI Studio key (free tier, not Vertex). |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Flash-only model id. Change if your key 403/404s on the default. |
| `SLACK_WEBHOOK_URL` | *(empty)* | Optional. Comms agent falls back to console when unset. |
| `HOST` | `0.0.0.0` | Server bind host. |
| `PORT` | `8080` | Server port. |
| `AEGIS_DB_PATH` | `aegisops.db` | SQLite path (resolved against repo root). |
| `GEMINI_MAX_RETRIES` | `5` | Retry attempts for the 503-safe wrapper. |
| `GEMINI_BASE_DELAY` | `1.0` | Base backoff delay (seconds). |

---

## Deploy to Cloud Run

```bash
./deploy.sh
```

The script reads `GEMINI_API_KEY`, `GEMINI_MODEL`, and optional
`SLACK_WEBHOOK_URL` from your local `.env` and passes them as Cloud Run env vars
— **secrets are never baked into the image**. See [deploy.sh](deploy.sh) and
[docker/Dockerfile](docker/Dockerfile).

---

## Troubleshooting

- **Gemini 503 / 429 / "overloaded".** Expected on the free tier under load — the
  built-in exponential-backoff-with-jitter retry (`GEMINI_MAX_RETRIES`,
  `GEMINI_BASE_DELAY`) absorbs it. No action needed; the demo won't crash.
- **Model id 403/404.** If your key rejects `gemini-3.5-flash`, change **only**
  the `GEMINI_MODEL` line in `.env` (e.g. `gemini-2.0-flash`). Stay on a Flash
  model — Pro is paid-tier-only and will 403 on a free key.
- **`GEMINI_API_KEY is not set`.** Copy `.env.example` → `.env` and paste your
  AI Studio key; `/api/health` reports `gemini_key_present`.
- **Approval never resolves.** The gate times out after 10 minutes and is
  treated as a hold (never auto-approves). Click Approve/Reject in the UI, or
  POST to `/api/incidents/{id}/approve`.
- **Slack shows "console" channel.** `SLACK_WEBHOOK_URL` is unset — that's the
  honest fallback, not a failure. Set the webhook in `.env` to post for real.
