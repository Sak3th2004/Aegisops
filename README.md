# AegisPilot — Autonomous SRE On-Call Agent

> **An autonomous multi-agent SRE that works the entire 3am on-call loop.** When a
> production alert fires, AegisPilot triages it, diagnoses the logs **and reads the
> Grafana dashboard with multimodal Gemini vision**, correlates against recent
> deploys, recalls similar past incidents, proposes a remediation **gated by human
> approval**, executes it, auto-writes the RCA, posts to Slack, and files a ticket —
> streaming every reasoning step live to an "Incident War Room".

Built for **#AllThingsAgenticHackathon** (The Taskmaster track) on real Google Cloud:
**Google ADK** (`LlmAgent` + `Runner`) orchestrating six specialized agents on
**Gemini 3.5 Flash** (+ **Gemini Pro** for the RCA) via **Vertex AI**, with
**Firestore**, **Pub/Sub**, and **Cloud Run**.

**🔴 Live demo:** https://aegisops-kjacopurja-uc.a.run.app · **Health:** [`/api/health`](https://aegisops-kjacopurja-uc.a.run.app/api/health)

---

## What makes it strong

- **Real multi-agent, not one big prompt.** An ADK `Runner` orchestrates six scoped
  `LlmAgent`s (Triage · Diagnosis · Correlation · Memory · Remediation · Comms), each
  with its own instruction, tools, and model config. Reasoning fans out across agents.
- **Multimodal.** The Diagnosis agent sends the actual Grafana PNG to Gemini vision to
  confirm the anomaly and produce an annotation the UI overlays on the image.
- **Human-in-the-loop governance.** The Remediation agent physically **halts** on an
  async approval gate; the destructive executor is never exposed to the model. A PII
  scrubber ("Model Armor") redacts anything bound for Slack.
- **Every decision observable.** Every agent step (input, reasoning, tool call, output,
  tokens, latency) is persisted to an audit trail **and** streamed live over SSE.
- **503-safe.** Every model call — Flash and Pro, ADK and local — is wrapped in
  exponential-backoff-with-jitter retry. The live demo cannot crash on a throttle.
- **Cloud-portable by design.** `StorageService` and `EventBus` interfaces let the same
  code run locally (SQLite + in-process bus) or on GCP (Firestore + Pub/Sub) by flipping
  one env var. Both implementations are kept in the repo.
- **Interactive & self-improving.** The war room's **Fire Incident** button rotates three
  real scenarios (checkout 5xx · cart OOM · payments latency), each with its own deploys,
  logs, memory, and Grafana snapshot. **Custom** lets anyone submit *their own* incident —
  service, error rate, pasted log lines, an optional recent deploy, even a dashboard
  screenshot for the vision agent. And **closed-loop learning**: every resolved incident is
  written back to memory, so a recurring fingerprint is instantly recalled ("seen before,
  resolved via rollback") — the system gets smarter the more it's used.

---

## Architecture (short)

```
Alert ─▶ Pub/Sub topic ─▶ Cloud Run (FastAPI)
                              │  push /api/pubsub/push
                              ▼
                     ADK Runner (Orchestrator)
        ┌──────────┬───────────┬───────────┬──────────┬─────────────┬────────┐
        ▼          ▼           ▼           ▼          ▼             ▼        │
     Triage    Diagnosis   Correlation   Memory   Remediation    Comms      │
     (Flash)   (Flash+     (Flash)       (Flash)  (Flash,        (Pro RCA)  │
                vision)                            approval gate)            │
        └────────────── every model call via RetryGemini ─▶ Vertex AI ──────┘
                              │
             Firestore (state/audit) ─ StreamHub ─▶ SSE ─▶ React War Room
```

Full details + Mermaid diagrams: [ARCHITECTURE.md](ARCHITECTURE.md).

### The six agents (from the Firestore `agent_registry`)

| Agent | Job | Tools |
|---|---|---|
| **Triage** | Severity (SEV1–4), affected service, blast radius, on-call routing | `resolve_service_and_severity` |
| **Diagnosis** | Summarize + classify logs; **read the Grafana image (vision)**; fingerprint | `fetch_and_classify_logs`, `grafana_vision` |
| **Correlation** | Score recent deploys by proximity; name probable root cause + confidence | `query_recent_deploys` |
| **Memory** | Vector-similarity search over past-incident fingerprints | `search_incident_memory` |
| **Remediation** | Propose reversible fix (rollback/scale/restart/flag-off); **halt for approval** | `propose_remediation`, `approval_gate`, `executor` |
| **Comms** | Auto-write the RCA (**Gemini Pro**); PII-scrub + post to Slack; file a ticket | `rca_writer`, `slack_poster`, `ticket_filer` |

---

## Prerequisites

- **Python 3.11**, **Node 18+**
- **Google Cloud** project with billing, and these APIs enabled: Vertex AI, Firestore,
  Pub/Sub, Cloud Run, Cloud Build, Artifact Registry
- **gcloud CLI**, authenticated with Application Default Credentials:
  ```bash
  gcloud auth login
  gcloud config set project <YOUR_PROJECT_ID>
  gcloud auth application-default login      # ADC — no API key needed
  ```
- A **Native-mode Firestore** database (one-time):
  ```bash
  gcloud firestore databases create --location=us-central1 --type=firestore-native
  ```
- *(Optional)* a Slack incoming-webhook URL for real notifications.

> **Free-tier alternative (no billing):** set `GOOGLE_GENAI_USE_VERTEXAI=false` and
> `GEMINI_API_KEY=<AI Studio key>`, plus `BACKEND=local` / `ORCHESTRATOR=local`. The app
> then runs entirely on SQLite + an in-process bus with the AI Studio key.

---

## Setup

```bash
# 1. Backend deps
python -m venv .venv
source .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Config
cp .env.example .env               # then edit .env (see the env table below)
```

### `.env` (Vertex / full-GCP mode)

| Variable | Example | Meaning |
|---|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` | Route Gemini through Vertex AI (ADC auth) |
| `GOOGLE_CLOUD_PROJECT` | `aegisops-12345` | Your GCP project |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | Compute region (Firestore/Pub-Sub/Run) |
| `VERTEX_LOCATION` | `global` | **Model** region — `gemini-3.5-flash` is published in `global` |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Model for the five fast agents |
| `GEMINI_MODEL_PRO` | `gemini-2.5-pro` | Model for the Comms RCA (3.5-pro not yet on Vertex) |
| `BACKEND` | `cloud` | `cloud` = Firestore + Pub/Sub · `local` = SQLite + in-proc |
| `ORCHESTRATOR` | `adk` | `adk` = real google-adk Runner · `local` = custom fallback |
| `PUBSUB_MODE` | `pull` | `pull` for local dev · `push` for Cloud Run |
| `SLACK_WEBHOOK_URL` | *(optional)* | Real Slack posts; console fallback if unset |

---

## Run locally

```bash
# Seed Firestore once (idempotent). Skip for BACKEND=local (SQLite seeds on boot).
python scripts/seed_firestore.py

# Backend (from repo root):
uvicorn backend.main:app --port 8080

# Frontend (separate terminal):
cd frontend && npm install && npm run dev   # war room at http://localhost:5173
```

### Fire an incident

From the **war room UI** (recommended): click **Fire Incident** to run the next rotating
scenario, or **Custom** to submit your own. From the CLI:

```bash
python scripts/publish_alert.py --pubsub                 # rotating scenario via real Pub/Sub → push
python scripts/publish_alert.py --scenario cart --pubsub # force one: checkout | cart | payments
python scripts/publish_alert.py                          # via HTTP → /api/alerts
```

Bring your own incident (the agents process exactly your data — nothing random):

```bash
curl -X POST "$URL/api/incidents/custom" \
  -F service=auth-svc -F alert=HighErrorRate -F error_rate=23% \
  -F deploy_version=v3.2.0 -F rollback_target=v3.1.9 \
  -F $'logs=ERROR JWT validation failed: signature mismatch after key rotation\nWARN auth error rate 23% exceeds SLO 2%' \
  # optional: -F image=@your_dashboard.png   (read by Gemini vision)
```

Then watch the war room: the six agents activate one by one, reasoning streams live,
Diagnosis reads the Grafana image, Remediation halts for your **Approve**, and on approval
it resolves, writes the RCA (Gemini Pro), posts to Slack, and files a ticket.

### The demo flow (end to end)

1. Alert `{HighErrorRate, checkout-svc, 42%, grafana_snapshot}` lands on the bus.
2. **Triage** → SEV1, checkout-svc, ~40% blast radius.
3. **Diagnosis** → summarizes 5xx/DB-pool logs + **Gemini vision confirms the latency spike**.
4. **Correlation** → "checkout-svc v2.4.1 deployed ~12 min ago — probable root cause".
5. **Memory** → "seen before, resolved via rollback in ~4 min".
6. **Remediation** → proposes `rollback → v2.4.0`, risk low, **halts for approval**.
7. Human clicks **Approve** → executor runs (clean simulation) → status `RESOLVED`.
8. **Comms** → Gemini-Pro RCA + timeline, PII-scrubbed Slack post, ticket filed.

---

## Deploy to Cloud Run

```bash
./deploy.sh
```

One script: enables APIs, grants the runtime service account its roles, builds the
single container from `docker/Dockerfile` via Cloud Build, deploys to Cloud Run
(min 1 / max 2, CPU always-allocated so the async approval-gated pipeline runs), and
wires a **Pub/Sub push subscription** to `<url>/api/pubsub/push`. No secret keys are
baked into the image — auth is the runtime service account's ADC.

Fire the live demo:
```bash
python scripts/publish_alert.py --pubsub    # real Pub/Sub → push → Cloud Run
```

---

## Verify without spending much

| Script | Proves |
|---|---|
| `python scripts/verify_vertex.py` | One real Vertex Flash call (ADC + model id) |
| `python scripts/validate_offline.py` | Full pipeline wiring, **no API key** (fake model) |
| `python scripts/validate_adk.py` | Full incident on **real google-adk + Vertex** |
| `python scripts/validate_firestore.py` | Full incident persisted + re-read from **real Firestore** |

---

## Repo layout

```
backend/
  main.py            FastAPI app, SSE, approval + Pub/Sub-push endpoints, impl selection
  orchestrator.py    local (custom) orchestrator — fallback (ORCHESTRATOR=local)
  adk/               REAL google-adk path: retry_llm, tools, callbacks, agents, orchestrator
  agents/            local agent implementations (fallback) + shared BaseAgent runtime
  tools/             deterministic tools (every tool = real function)
  services/          gemini (503-safe, Vertex/AI-Studio) · storage (SQLite|Firestore)
                     · eventbus (in-proc|Pub/Sub) · stream (SSE) · slack · embedding
  guardrails.py      approval gate + PII scrubber
  seed/              fixtures + matplotlib Grafana snapshot
frontend/            React + Vite + TS + Tailwind war room
scripts/             publish_alert, seed_firestore, verify_vertex, validate_*
docker/Dockerfile    single-container build (frontend + backend)
deploy.sh            Cloud Run deploy + Pub/Sub push wiring
```

---

## Troubleshooting

- **`gemini-3.5-flash` 404 on Vertex** → it's published in `VERTEX_LOCATION=global`, not
  `us-central1`. Keep them separate (already the default). Any model id can be overridden
  in one line via `GEMINI_MODEL`.
- **503 / 429 from Vertex** → handled automatically by the retry wrapper (backoff + jitter).
- **Firestore `NotFound (default) does not exist`** → create the Native-mode DB (see Prereqs).
- **Cloud Build 403 on the source bucket** → `deploy.sh` grants the build roles; re-run it.
- **Comms empty on Cloud Run** → the pipeline needs CPU outside request handling;
  `deploy.sh` sets `--no-cpu-throttling --min-instances 1`.
