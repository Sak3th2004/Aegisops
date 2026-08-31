# AegisOps — Upgrade to Full Google Cloud (billing now active)

> Paste this into Claude Code AFTER the free-tier build is working and committed.
> $300 Cloud credit is now live. We upgrade from local substitutes to real managed
> Google Cloud services, in SAFE phases. **Commit after every phase.** Never break a
> working state — each phase must pass a full end-to-end incident run before the next.

---

## GUARDING RULES (do not violate)

1. **Commit after every phase.** If a phase fails, we can always submit the last good commit.
2. **Keep the 503-safe retry wrapper on every model call** — Vertex throttles too.
3. **Keep the local implementations in the codebase** behind their interfaces (StorageService, EventBus) as a fallback — do NOT delete SQLite/in-process bus. Add cloud impls alongside; select via env var (`BACKEND=cloud|local`). This protects the demo.
4. **After each swap, run a full incident** (DETECTED → RESOLVED) and show me the result before moving on.
5. Do not remove or weaken any existing feature (6 agents, SSE, war-room UI, approval gate, audit trail, multimodal vision).

---

## PHASE 1 — Wire REAL google-adk (compliance — highest priority)

The custom orchestrator follows the ADK pattern but doesn't import `google-adk`. Hackathon rules require a real Google agent framework. Fix it for real, without losing the retry/SSE reliability.

- Wrap each of the six sub-agents as an **ADK `LlmAgent`** with its existing instruction prompt and tools.
- Orchestrate them via ADK's **`Runner`** / agent hand-off mechanism, preserving the state machine (`DETECTED → TRIAGED → DIAGNOSED → CORRELATED → AWAITING_APPROVAL → REMEDIATING → RESOLVED`).
- Bridge the **503-safe retry** and **SSE streaming** through ADK **callbacks** (before/after model + tool callbacks) so every agent step still streams to the UI exactly as now.
- Keep the human-in-the-loop approval gate intact (pause the run, resume on UI approval).
- Verify: `grep -r "google.adk" backend/` returns real imports; a full incident still runs end to end.

**Commit:** `feat: real google-adk orchestration via LlmAgent + Runner`

---

## PHASE 2 — Switch Gemini to Vertex AI

Billing is active, so route through Vertex (credit-covered, enterprise path, what Google judges expect).

- Configure the `google-genai` client for Vertex: read `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` from env. Authenticate via **Application Default Credentials** (no API key).
- Keep the retry wrapper wrapping the Vertex calls.
- Model ids: default `gemini-3.5-flash`. Keep a fallback env (`GEMINI_MODEL`) so one line changes it if a model id 404s.
- Verify: one real Vertex Flash call succeeds; full incident runs.

**Commit:** `feat: route Gemini through Vertex AI (ADC auth, credit-covered)`

---

## PHASE 3 — SQLite → Firestore

The StorageService interface already exists. Add a `FirestoreStorage` implementation.

- Mirror the existing tables as collections: `incidents`, `deploys`, `logs`, `incident_memory`, `agent_registry`, `audit_log`.
- Port the seed fixtures into a Firestore seeding script.
- Select impl via `BACKEND` env var; keep `SQLiteStorage` as fallback.
- Verify: seed runs; full incident reads/writes against real Firestore; audit trail persists.

**Commit:** `feat: Firestore storage backend (StorageService impl)`

---

## PHASE 4 — In-process bus → Pub/Sub

The EventBus interface already exists. Add a `PubSubBus` implementation.

- Topic `incident-alerts`, subscription pushing to the FastAPI alert endpoint.
- `scripts/publish_alert.py` publishes to the real Pub/Sub topic.
- Select via `BACKEND` env var; keep in-process bus as fallback.
- Verify: publishing an alert to Pub/Sub triggers a full incident run.

**Commit:** `feat: Pub/Sub event ingestion (EventBus impl)`

---

## PHASE 5 — Gemini Pro for the RCA agent only

Billing lets us use Pro now. Two-tier for quality + cost discipline.

- Comms Agent's **RCA-writing step** uses `gemini-3.5-pro` (via `GEMINI_MODEL_PRO`).
- All other agents stay on `gemini-3.5-flash`.
- Keep retry wrapper on the Pro calls too.
- Verify: RCA quality visibly stronger; full run still passes.

**Commit:** `feat: Gemini Pro for RCA reasoning, Flash for fast agents`

---

## PHASE 6 — Deploy to Cloud Run

- Containerize the backend (Dockerfile already scaffolded).
- Deploy with **min-instances 0, max-instances 2**, small CPU/RAM (cost-safe).
- Wire the Pub/Sub push subscription to the deployed Cloud Run URL.
- Confirm the live URL serves health + frontend + runs an incident.
- Capture the **Cloud Run dashboard** screenshot for the demo (GCP proof).

**Commit:** `feat: Cloud Run deployment + Pub/Sub push wiring`

---

## PHASE 7 — Submission assets

- **ARCHITECTURE.md** + architecture diagram: Alert → Pub/Sub → Cloud Run (FastAPI) → ADK Runner → 6 agents (Flash) + RCA (Pro) via Vertex → Firestore → SSE → React war-room; approval gate + guardrails called out.
- **README** spin-up: env setup, `gcloud auth application-default login`, seed, run, deploy. Reproducible.
- Push to **GitHub** (public, or share private with the judge emails in the rules).
- **~4-min live demo**: fire alert → agents work live → approval gate → RESOLVED → RCA + Slack → show Cloud Run console proof.
- **Bonus:** dev.to blog + LinkedIn/X post with **#AllThingsAgenticHackathon**.

**Commit:** `docs: architecture, README, submission assets`

---

## ENV (final)

```
GOOGLE_CLOUD_PROJECT=your_project_id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true
GEMINI_MODEL=gemini-3.5-flash
GEMINI_MODEL_PRO=gemini-3.5-pro
BACKEND=cloud            # or 'local' to fall back to SQLite + in-process bus
SLACK_WEBHOOK_URL=your_webhook   # optional; console fallback if unset
```

Auth is via Application Default Credentials (`gcloud auth application-default login`) — no API key in env.

---

## STANDING INSTRUCTIONS

- Work phases in order. After each: show me it runs end to end, then stop for my go.
- If a cloud service errors on setup, tell me the exact error — don't silently fall back and hide it.
- Never delete the local fallback impls.
- Every model call keeps the retry wrapper. The live demo cannot crash.
- Real code only — no stubs, no fake success.
