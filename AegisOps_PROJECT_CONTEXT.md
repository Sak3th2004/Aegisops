# AegisPilot — Full Project Context (handoff / Claude context doc)

> Paste this whole file into a Claude chat as context. It describes the complete,
> deployed system: what it is, the full tech stack, the architecture, every
> feature, the file layout, the APIs, the cloud setup, and honest limitations.
> (Not committed to git — this is a working context document.)

---

## 1. One-liner

**AegisPilot** is an autonomous, human-governed **multi-agent SRE on-call agent**. When a
production alert fires, six specialized AI agents (on **Google ADK** + **Gemini on
Vertex AI**) triage it, diagnose the logs, **read the Grafana dashboard with vision**,
correlate the bad deploy, recall past incidents, propose a fix **gated by human
approval**, execute it, auto-write the RCA, post to Slack, and file a ticket — streaming
every step live to an "Incident War Room". It **learns** from every resolution and runs
entirely on **Google Cloud**.

- **Hackathon:** #AllThingsAgenticHackathon — "The Taskmaster" track.
- **Live URL:** https://aegisops-kjacopurja-uc.a.run.app  (health: `/api/health`)
- **Repo:** https://github.com/Sak3th2004/Aegisops
- **GCP project:** `aegisops-12345` (project number `853443425329`), region `us-central1`.

---

## 2. Tech stack (exact)

**AI / agents**
- **Google ADK** (`google-adk==2.8.0`) — `LlmAgent` + `Runner` orchestration, real imports.
- **Gemini via `google-genai==2.20.0`** on **Vertex AI** (ADC auth, no API keys).
  - `gemini-3.5-flash` — the five fast agents (published in Vertex region **`global`**).
  - `gemini-2.5-pro` — the Comms **RCA** step (Gemini 3.5 Pro isn't on Vertex yet; one-line swap via `GEMINI_MODEL_PRO`).

**Backend**
- **Python 3.11**, **FastAPI 0.141.1**, **Uvicorn 0.34.0**, **sse-starlette 2.2.1** (SSE).
- **pydantic 2.13.5** / **pydantic-settings 2.7.1** (config + models).
- **google-cloud-firestore 2.29.0**, **google-cloud-pubsub 2.39.2**.
- **httpx 0.28.1** (Slack), **numpy 2.2.1** (vector similarity), **matplotlib 3.10.0** (Grafana snapshot rendering).

**Frontend**
- **React 18 + Vite 5 + TypeScript + TailwindCSS**, **framer-motion** (animation), **Recharts**, **lucide-react** (icons). Dependency-free markdown renderer for the RCA.

**Cloud (GCP)**
- **Cloud Run** (single container: FastAPI + built React), **Firestore** (Native mode), **Pub/Sub** (push), **Vertex AI**, **Cloud Build**, **Artifact Registry**.
- Auth is **Application Default Credentials** (runtime service account); **no secret keys** are baked into the image.

**Local fallback (kept in the repo, selectable via env)**
- **SQLite** (storage) + an **in-process async event bus** — same interfaces as Firestore/Pub-Sub.

---

## 3. Architecture

```
Alert ─▶ Pub/Sub topic (incident-alerts) ─▶ Cloud Run (FastAPI)
                                               │ push → POST /api/pubsub/push
                                               ▼
                                    AdkOrchestrator (state machine + approval gate)
        ┌──────────┬───────────┬────────────┬─────────┬───────────────┬──────────┐
        ▼          ▼           ▼            ▼         ▼               ▼          │
     Triage    Diagnosis   Correlation   Memory   Remediation      Comms        │
     (Flash)   (Flash +    (Flash)       (Flash)  (Flash, gate)    (Pro RCA)     │
                vision)                                                          │
        └───────────── every model call via RetryGemini (503-safe) ─▶ Vertex AI ┘
                                               │
                    Firestore (state + audit) ─ StreamHub ─▶ SSE ─▶ React War Room
                    Comms → PII-scrubbed Slack card + ticket artifact
```

**Incident state machine** (enforced by `LEGAL_TRANSITIONS` in `backend/models.py`):
`DETECTED → TRIAGED → DIAGNOSED → CORRELATED → AWAITING_APPROVAL → REMEDIATING → RESOLVED`
plus `REJECTED` (human declines / gate times out) and `FAILED` (unrecoverable). The
**Memory** agent runs between Correlation and Remediation but does not move the state.

**Two orchestration paths (both real, selectable via `ORCHESTRATOR` env):**
- `adk` (default, deployed) — `backend/adk/`: six real ADK `LlmAgent`s executed by a real
  ADK `Runner`. The LLM calls real tools (ADK `FunctionTool`s); tool outputs are captured
  via ADK callbacks to build authoritative findings. Retry is a real `BaseLlm` subclass.
- `local` (fallback) — `backend/orchestrator.py` + `backend/agents/*`: a custom
  orchestrator with the same behavior, kept so the demo can never be blocked by ADK.

---

## 4. The agents (from the Firestore `agent_registry`)

| Agent | Model | Job | Tools |
|---|---|---|---|
| **Orchestrator** | — | Owns the incident lifecycle + state machine; routes hand-offs | subagent_handoff, state_writer |
| **Triage** | Flash | Severity (SEV1–4), affected service, blast radius, on-call routing | resolve_service_and_severity (topology + rubric) |
| **Diagnosis** | Flash + **vision** | Fetch + classify logs; **read the Grafana image with Gemini vision**; build a fingerprint | fetch_and_classify_logs, grafana_vision |
| **Correlation** | Flash | Score the service's own recent deploys by time-proximity; name root cause + calibrated confidence | query_recent_deploys, change_correlator |
| **Memory** | Flash | Vector-similarity (cosine) search over past-incident fingerprints | search_incident_memory |
| **Remediation** | Flash | Propose a reversible fix (rollback/scale/restart/flag-off); **HALT for human approval**; execute (simulated) | propose_remediation, approval_gate, executor |
| **Comms** | **Pro** | Auto-write the RCA (Markdown); PII-scrub + post to Slack; file a ticket | rca_writer, slack_poster, ticket_filer |

**Grounding / honesty (why answers are trustworthy):** each agent runs deterministic
tools and the orchestrator **reconciles** the model's output against hard signals —
severity has a rubric floor the model can't soften; correlation confidence is capped to
the deploy proximity score; memory has a 0.4 similarity floor (below it → "novel
incident"). On weak input it degrades honestly instead of hallucinating.

---

## 5. Key features (complete list)

1. **Real multi-agent orchestration** via Google ADK `LlmAgent` + `Runner` (not one big prompt).
2. **Multimodal diagnosis** — Gemini vision reads the actual Grafana PNG and produces an
   annotation the UI overlays on the image.
3. **Human-in-the-loop approval gate** — async `asyncio` gate; the destructive executor is
   never exposed as a model tool, so the LLM plans but can't act unilaterally.
4. **503-safe everywhere** — every Gemini call (Flash & Pro; ADK & local) is wrapped in
   exponential-backoff-with-jitter retry.
5. **Full observability** — every step (input, reasoning, tool call, output, tokens,
   latency) is persisted to `audit_log` **and** streamed live over SSE.
6. **Governance layer** — approval gate + self-implemented PII scrubber ("Model Armor") +
   agent registry + audit trail (all shown in the UI).
7. **Two-tier models** — Flash for speed on the 5 fast agents, **Gemini Pro** for deeper RCA reasoning.
8. **Three rotating scenarios** (the Fire button cycles them), each real end-to-end:
   - `checkout-svc` — bad deploy → DB connection-pool exhaustion + downstream 5xx timeouts.
   - `cart-svc` — bad deploy → memory leak → OOMKilled pods.
   - `payments-svc` — bad deploy → latency blow-out + thread-pool saturation + ledger timeouts.
   Each has its own deploys, logs, memory fingerprint, and Grafana snapshot.
9. **Bring-your-own-incident** — `POST /api/incidents/custom` / the "Custom" modal: judges
   enter their own service, error rate, **log lines** (Diagnosis classifies them), an optional
   **recent deploy** (Correlation uses it), and an optional **dashboard screenshot** (Gemini
   vision reads it). Nothing is randomized — the agents process exactly the input.
10. **Closed-loop learning** — on RESOLVED, `learn_incident` writes the incident's
    fingerprint + confirmed cause + effective fix + resolution time back into memory. A
    recurring fingerprint updates a running average (no duplicates). Verified: a novel
    incident reads as "novel" first; a repeat is recalled at similarity 1.0 ("seen before,
    resolved via rollback").
11. **Cloud-portable seam** — `StorageService` (SQLite ↔ Firestore) and `EventBus`
    (in-process ↔ Pub/Sub) swap via one env var; both impls ship in the repo.
12. **Real-time "Incident War Room"** — animated agent graph, live reasoning stream with
    token/latency badges, Grafana vision panel, approval modal, RCA + timeline tab, agent
    registry drawer, guided empty/connecting/error states, root error boundary.

---

## 6. Repo structure (key files)

```
backend/
  main.py                 FastAPI app: SSE, approval + Pub/Sub-push + custom + demo/fire endpoints, impl selection, static serving
  config.py               pydantic-settings config (Vertex/backend/orchestrator/pubsub_mode); apply_google_env()
  models.py               pydantic schemas + IncidentStatus state machine (LEGAL_TRANSITIONS)
  guardrails.py           ApprovalGate (async) + PII scrubber
  orchestrator.py         LOCAL custom orchestrator (fallback, ORCHESTRATOR=local)
  adk/
    orchestrator.py       AdkOrchestrator — runs each LlmAgent via ADK Runner; state machine; gate; findings; learning
    agents.py             the six LlmAgents (5 Flash + Comms Pro), instruction prompts + tools + callbacks
    retry_llm.py          RetryGemini(BaseLlm) — 503-safe retry on every ADK model call
    tools.py              real deterministic tools exposed as ADK FunctionTools (executor NOT exposed)
    callbacks.py          before/after model+tool callbacks → SSE + audit + tool-output capture
  agents/                 LOCAL agent implementations (fallback) + shared BaseAgent runtime (base.py)
  tools/                  deterministic tools: triage, diagnosis (log classifier), correlation, memory (+ learn_incident), remediation (simulated executor), comms (ticket filing)
  services/
    gemini.py             GeminiService — Vertex/AI-Studio client + 503-safe retry + vision + per-call model override
    storage.py            StorageService interface + SQLiteStorage
    firestore_storage.py  FirestoreStorage (cloud)
    eventbus.py           EventBus interface + InProcessBus
    pubsub_bus.py         PubSubBus (topic + push/pull)
    stream.py             StreamHub (SSE broadcast + replay)
    slack.py              best-effort Slack posting (never crashes an incident)
    embedding.py          local feature-hashed fingerprint vectors (real cosine similarity)
  seed/
    scenarios.py          the 3 scenarios' fixtures + rotation + refresh_all_timelines
    seed_data.py          seeds all scenarios' memories + agent registry
    generate_grafana.py   matplotlib renderers for the 3 scenario dashboards
frontend/                 React + Vite + TS + Tailwind war room (src/App.tsx, components/*, warroom.ts reducer, useIncidentStream.ts, api.ts)
scripts/                  publish_alert.py (--pubsub/--scenario), seed_firestore.py, verify_vertex.py, validate_offline.py, validate_adk.py, validate_firestore.py
docker/Dockerfile         multi-stage: node builds frontend → python serves backend + dist
deploy.sh                 Cloud Run deploy: APIs, IAM, Cloud Build, deploy, Pub/Sub push wiring
README.md, ARCHITECTURE.md, CONTRACT.md, AegisPilot_DEMO_SCRIPT.md
```

---

## 7. HTTP API

- `GET  /api/health` — orchestrator, model, model_pro, auth (`vertex-adc`), project, regions, backend, slack.
- `POST /api/alerts` — publish a raw Alert to the bus.
- `POST /api/demo/fire` — fire the NEXT rotating scenario (checkout → cart → payments). *(send an empty JSON body `{}` — Cloud Run rejects bodyless POST with 411.)*
- `POST /api/incidents/custom` — multipart form: `service, alert, error_rate, logs` (newline-separated), optional `deploy_version, rollback_target`, optional `image` (dashboard screenshot).
- `POST /api/pubsub/push` — Pub/Sub push endpoint (Cloud Run ingestion).
- `POST /api/incidents/{id}/approve` · `POST /api/incidents/{id}/reject` — body `{approver, note}`.
- `GET  /api/incidents` · `GET /api/incidents/{id}` — incident(s) with `findings`.
- `GET  /api/incidents/{id}/audit` — full audit trail.
- `GET  /api/incidents/{id}/rca` — `{rca, findings.comms}`.
- `GET  /api/incidents/{id}/grafana` — the exact image the vision agent read (404 if none).
- `GET  /api/registry` — the agents.
- `GET  /api/stream` (all) and `GET /api/stream/{id}` — SSE reasoning-chain stream.

---

## 8. Data model (Firestore collections ≙ SQLite tables)

```
incidents(id, status, severity, service, blast_radius, detected_at, probable_cause,
          confidence, remediation_plan, approved_by, resolved_at, rca_doc, fingerprint,
          findings, alert)
deploys(id, service, version, deployed_at, deployed_by, commit_sha, rollback_target)
logs(id, service, ts, level, message, log_class)
incident_memory(fingerprint_id, fingerprint, embedding, past_incident_ids,
                typical_cause, typical_fix, avg_resolution_minutes)
agent_registry(id, name, version, model, allowed_tools, scope, status)
audit_log(id, incident_id, agent, step, input, reasoning, tool_call, output,
          tokens, latency_ms, ts)
```

`findings` (per incident) holds each agent's structured output: `triage, diagnosis
(incl. vision), correlation (suspect + ranked), memory (match), remediation, execution,
comms (rca, slack, ticket, resolution_minutes)`.

---

## 9. Configuration (env vars)

```
GOOGLE_GENAI_USE_VERTEXAI=true        # route Gemini through Vertex (ADC auth)
GOOGLE_CLOUD_PROJECT=aegisops-12345
GOOGLE_CLOUD_LOCATION=us-central1     # compute region (Firestore/Pub-Sub/Run)
VERTEX_LOCATION=global                # model region (gemini-3.5-flash lives here)
GEMINI_MODEL=gemini-3.5-flash         # five fast agents
GEMINI_MODEL_PRO=gemini-2.5-pro       # Comms RCA
BACKEND=cloud                         # cloud=Firestore+Pub/Sub | local=SQLite+in-proc
ORCHESTRATOR=adk                      # adk=real google-adk | local=custom fallback
PUBSUB_MODE=push                      # push (Cloud Run) | pull (local)
SLACK_WEBHOOK_URL=...                 # live; PII-scrubbed console fallback if unset
GEMINI_MAX_RETRIES=5  GEMINI_BASE_DELAY=1.0
# Free-tier alternative: GOOGLE_GENAI_USE_VERTEXAI=false + GEMINI_API_KEY=<AI Studio key>
```

---

## 10. Deployment (Cloud Run)

- One command: `./deploy.sh` — enables APIs; grants the runtime SA
  (`853443425329-compute@developer.gserviceaccount.com`) the roles
  `aiplatform.user, datastore.user, pubsub.editor, cloudbuild.builds.builder,
  logging.logWriter, artifactregistry.writer, storage.admin`; builds the image from
  `docker/Dockerfile` via Cloud Build; deploys to Cloud Run; wires the Pub/Sub push
  subscription.
- **Cloud Run config:** `--allow-unauthenticated --port 8080 --min-instances 1
  --max-instances 2 --no-cpu-throttling --cpu 1 --memory 1Gi --timeout 300`.
  (`--no-cpu-throttling` + `--min-instances 1` are required so the async, approval-gated
  pipeline and the post-response Comms step keep CPU.)
- **Pub/Sub:** topic `incident-alerts`; push subscription `aegisops-push` →
  `<url>/api/pubsub/push`; pull sub `aegisops-worker` (used only in local/pull mode).
- **Firestore:** Native-mode `(default)` in `us-central1`, seeded (idempotent; skipped on
  boot if already seeded).

---

## 11. Verification (proof it's real)

- `scripts/verify_vertex.py` — one real Vertex Flash call (ADC + model id) → `VERTEX-OK`.
- `scripts/validate_offline.py` — full pipeline wiring with a fake model (no key) → 16/16.
- `scripts/validate_adk.py` — full incident on **real google-adk + Vertex** → 14/14.
- `scripts/validate_firestore.py` — full incident persisted + re-read from real Firestore → 9/9.
- Live audit trail shows per-step real Gemini calls (e.g., Diagnosis 2989 tok/6.3s, Comms
  RCA 4469 tok/34s on Pro). Verified live: 3 scenarios + a custom `auth-svc` incident
  (blamed auth-svc v3.2.0 @ 0.79) all resolved; learning recalled a repeat at similarity 1.0.

---

## 12. Honest limitations (defensible scoping)

- The **remediation executor is a clean, clearly-labeled simulation** (no real cluster to
  roll back) — it runs ordered steps and tags them `simulated=True`; it never claims to
  touch prod infra.
- **Demo data is seeded** (3 realistic scenarios) — the *autonomy and reasoning* are real
  and re-generated per run; the underlying incidents are fixtures (spec explicitly allows
  this). Custom incidents run on the judge's real input.
- **`gemini-3.5-pro`** isn't on Vertex yet, so the Pro tier uses `gemini-2.5-pro` (one-line
  swap when 3.5-pro publishes).
- Cross-instance SSE: with `max-instances 2`, a live SSE client and an incident could land
  on different instances; in practice a single warm instance serves both during a demo.

---

## 13. Status

**Complete and live.** All 7 GCP-upgrade phases done (ADK, Vertex, Firestore, Pub/Sub,
Pro RCA, Cloud Run, docs) + scenario variety + custom input + learning + UI redesign, all
committed and pushed to GitHub. Remaining are human tasks: record the ~4-min demo video
(see `AegisPilot_DEMO_SCRIPT.md`), submit on Devpost, optional blog/social posts.
```

