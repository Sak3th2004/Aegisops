# AegisOps — Master Build Spec (ZERO-CARD / FREE TIER)

> **Paste this entire file as your first message to Claude Code.**
> This is the no-billing version: runs entirely on the free Gemini API key.
> No Google Cloud billing account required to build or demo.

---

## 0. YOUR ROLE & HARD RULES

You are a **staff-level SRE + platform engineer** building a production-grade autonomous incident-response system for a hackathon judged by Google Cloud engineers. Build like it ships to prod Monday.

**Non-negotiable — violating any of these fails the build:**

1. **NO placeholder code.** No `# TODO`, no `# in a real app you would...`. Every function does real work.
2. **NO vibe-coded monolith.** Real modular architecture. Each agent is its own module with its own prompt, tools, and tests.
3. **Multi-agent, not one big call.** Distinct specialized agents coordinated by an orchestrator, each with a scoped job and its own tool set. Reasoning fans out across agents.
4. **Real Google tech doing real work (mandatory per rules):**
   - **Gemini 3.5 Flash**, accessed via the **Gemini API (Google AI Studio key)**. Model id: `gemini-3.5-flash`.
   - **Google ADK (Agent Development Kit, Python)** for orchestration — configured to use the AI Studio API key, NOT Vertex.
   - **≥1 GCP infra service** → **Cloud Run** at deploy time (free tier, for the "runs on Google Cloud" proof).
5. **Flash-only.** Do NOT use any Gemini Pro model — Pro is paid-tier-only as of April 2026 and will 403 on the free key. `gemini-3.5-flash` handles every agent, including RCA writing. It is frontier-class and strong enough.
6. **Event-driven.** System reacts to an event on a local Pub/Sub-style event bus, then runs autonomously (except one human-in-the-loop approval gate).
7. **Every decision observable.** Stream the reasoning chain to the UI (OpenTelemetry-style trace). Judges must SEE the agents think and act.
8. **Resilient to 503s.** The free Gemini tier throttles under load. EVERY model call wraps in exponential-backoff retry (3–5 attempts). Non-negotiable — this is what makes the live demo not crash.

---

## 1. THE PRODUCT

**AegisOps** — an autonomous SRE on-call agent. When a production alert fires, it triages, diagnoses (reading logs AND a Grafana dashboard image via multimodal Gemini), correlates against recent deploys, checks its memory of past incidents, proposes a remediation gated by human approval, executes, and auto-writes the RCA — then posts the full incident timeline to Slack and files a ticket.

**Friction removed:** the entire 3am on-call loop — triage, log-diving, root-cause guessing, remediation, postmortem.

**Track:** The Taskmaster.

---

## 2. MULTI-AGENT ARCHITECTURE

One **Orchestrator** (ADK) routes an incident through six specialized sub-agents. Each is a separate ADK agent with its own instruction prompt, tools, and model config. **All run `gemini-3.5-flash`.**

| Agent | Job | Tools |
|---|---|---|
| **Orchestrator** | Owns the incident lifecycle; routes between sub-agents; maintains the state machine (`DETECTED → TRIAGED → DIAGNOSED → CORRELATED → AWAITING_APPROVAL → REMEDIATING → RESOLVED`) | sub-agent handoff, state writer |
| **Triage Agent** | Classify severity (SEV1–4), affected service, blast radius, on-call routing | severity_classifier, service_resolver |
| **Diagnosis Agent** | Pull + summarize logs; **read the Grafana screenshot with Gemini vision** to confirm the anomaly; classify log lines | log_fetcher, grafana_vision, log_classifier |
| **Correlation Agent** | Cross-reference recent deploys/config changes against the incident window; name probable root cause with confidence score | deploy_history_query, change_correlator |
| **Memory Agent** | Query past-incident store for similar fingerprints; surface "seen before, resolved in Xm via Y" | incident_memory_search (vector similarity over fingerprints) |
| **Remediation Agent** | Propose the fix (rollback / scale / restart / flag-off) with a reversible plan + risk rating; **HALT for human approval** on destructive actions | remediation_planner, approval_gate, executor (guarded) |
| **Comms Agent** | Generate the incident timeline + full RCA; post to Slack; file a ticket | rca_writer, slack_poster, ticket_filer |

**Governance layer (architecture-score differentiator):**
- **Approval gate** — Remediation Agent cannot execute a destructive action until a human clicks Approve in the UI. Guardrail also strips PII from anything sent to Slack (the "Model Armor" concept, self-implemented).
- **Agent registry** — a local catalog listing each agent, its version, allowed tools, and scope. Shown in the UI.
- **Full audit trail** — every agent step (input, reasoning, tool call, output, latency, token estimate) persisted and streamed to the UI.

---

## 3. TECH STACK (zero-card)

**Backend**
- Python 3.11, **FastAPI** (deploys to **Cloud Run** free tier at the end)
- **Google ADK** for agents, using the **AI Studio API key** (`GEMINI_API_KEY`)
- **Gemini 3.5 Flash** via `google-genai` SDK — all agents + vision
- **Storage/state/memory → SQLite** (local, zero-billing) behind a `StorageService` interface. *The interface is written so the same code swaps to Firestore later by changing one implementation class — call this out in the README as "cloud-portable."*
- **Event ingestion → in-process async event bus** behind an `EventBus` interface (same swap-to-Pub/Sub story). A publisher script drops an alert onto it.
- **Server-Sent Events (SSE)** for real-time reasoning-chain streaming to the UI

**Frontend**
- **React + Vite + TypeScript + TailwindCSS**
- Real-time "Incident War Room" dashboard
- **shadcn/ui**, **lucide-react**, **framer-motion** (live agent-flow animation), **Recharts**

**Why:** everything runs with no billing account. The `StorageService` / `EventBus` interfaces mean the architecture is genuinely cloud-native in shape — you demo the Pub/Sub + Firestore *pattern* with local implementations, and Cloud Run gives the required GCP footprint. Judges see the same product; you pay nothing.

---

## 4. DATA MODELS (SQLite tables, mirror future Firestore collections)

```
incidents(id, status, severity, service, blast_radius, detected_at,
          probable_cause, confidence, remediation_plan, approved_by,
          resolved_at, rca_doc, fingerprint)
deploys(id, service, version, deployed_at, deployed_by, commit_sha, rollback_target)
logs(id, service, ts, level, message, log_class)
incident_memory(fingerprint_id, fingerprint, embedding, past_incident_ids,
                typical_cause, typical_fix, avg_resolution_minutes)
agent_registry(id, name, version, model, allowed_tools, scope, status)
audit_log(id, incident_id, agent, step, input, reasoning, tool_call,
          output, tokens, latency_ms, ts)
```

Seed `deploys`, `logs`, `incident_memory` with realistic fixtures so the demo runs on real reads. (The autonomy is what's judged, not live prod infra.)

---

## 5. THE DEMO FLOW (build to make THIS work live, end to end)

1. `scripts/publish_alert.py` drops a real alert onto the event bus:
   `{"alert":"HighErrorRate","service":"checkout-svc","error_rate":"42%","grafana_snapshot":"<local_image_path>"}`
2. Event bus → Orchestrator spins up an incident.
3. UI lights up: agents activate one by one, reasoning streaming live.
4. Triage → SEV1, checkout-svc, ~40% of traffic.
5. Diagnosis → summarizes error logs + **Gemini vision reads the Grafana image** and confirms the latency spike; classifies the log lines.
6. Correlation → "checkout-svc v2.4.1 deployed 12 min ago — 0.91 confidence root cause."
7. Memory → "Seen 2× before, both fixed by rollback, avg 4 min."
8. Remediation → proposes `rollback checkout-svc → v2.4.0`, risk: low, **halts for approval**.
9. Human clicks **Approve** → executor runs (simulated cleanly, not faked), status → RESOLVED.
10. Comms → generates the RCA + timeline, posts to Slack (real webhook), files a ticket.
11. UI shows full audit trail + generated RCA + resolution time.

---

## 6. FRONTEND — "INCIDENT WAR ROOM"

Carries **Best Multimodal UX** + the wow factor. Requirements:

- **Dark ops-console aesthetic** — Datadog/Grafana but cleaner. Deep charcoal bg, signal colors (amber/red/green), monospace telemetry.
- **Live agent graph** — the 6 agents as nodes; active one pulses; edges animate as the incident hands off (framer-motion). Centerpiece.
- **Reasoning stream panel** — each agent's thoughts + tool calls scroll in live via SSE, with token/latency badges.
- **Grafana snapshot panel** — show the actual image the vision agent analyzed, with the AI's annotation overlaid.
- **Approval modal** — the human-in-the-loop moment: proposed action, risk, rollback target, Approve/Reject.
- **RCA + timeline tab** — the auto-generated postmortem, rendered clean.
- **Agent Registry drawer** — agents, versions, allowed tools, scope.
- Responsive, keyboard-accessible, real loading/error states.

**Design bar:** looks like a funded startup's product. No default-bootstrap look. Intentional typography, spacing, motion.

---

## 7. REPO STRUCTURE

```
aegisops/
├── README.md                 # spin-up + deploy + "cloud-portable" note (REQUIRED)
├── ARCHITECTURE.md           # + architecture diagram
├── docker/Dockerfile
├── deploy.sh                 # Cloud Run deploy
├── backend/
│   ├── main.py               # FastAPI app, event-bus consumer, SSE
│   ├── orchestrator.py       # ADK orchestrator + state machine
│   ├── agents/               # triage diagnosis correlation memory remediation comms
│   ├── tools/                # every tool = real function
│   ├── services/
│   │   ├── gemini.py         # google-genai client + RETRY/BACKOFF wrapper (503-safe)
│   │   ├── storage.py        # StorageService interface + SQLiteStorage impl
│   │   ├── eventbus.py       # EventBus interface + InProcessBus impl
│   │   └── slack.py
│   ├── guardrails.py         # approval gate + PII strip
│   ├── models.py             # pydantic schemas
│   └── seed/                 # SQLite fixtures
├── frontend/                 # React + Vite + Tailwind war-room UI
└── scripts/publish_alert.py  # fires the demo incident
```

---

## 8. BUILD ORDER (finish each phase before the next — no skipping)

1. **Scaffold** repo, FastAPI skeleton, ADK install, `google-genai` client, `.env` loading.
2. **Gemini service + retry** — the 503-safe wrapper FIRST (everything depends on it). Test one real Flash call.
3. **Storage + event bus** — SQLite impl, in-process bus, seed fixtures.
4. **Orchestrator** — incident state machine + audit logging.
5. **Agents** — all six with real prompts + real tools; wire handoffs. Get a full incident running end to end in the terminal first.
6. **Multimodal** — Gemini vision on the Grafana image; log classification.
7. **Guardrails + approval gate** — halt/resume on human approval; PII strip.
8. **SSE streaming** — push every agent step to the client.
9. **Frontend war room** — build against the live stream; make it beautiful.
10. **Slack + RCA + ticket** — real webhook, generated RCA.
11. **Deploy backend to Cloud Run**, run full live demo, capture GCP-console proof.
12. **Docs** — README, ARCHITECTURE.md, diagram.

---

## 9. `.env`

```
GEMINI_API_KEY=your_new_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash
SLACK_WEBHOOK_URL=your_webhook   # optional; comms falls back to console if unset
```

---

## 10. GEMINI CALL PATTERN (use this everywhere)

```python
# services/gemini.py
import time, random
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

def generate(contents, system=None, max_retries=5):
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system) if system else None,
            )
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            # 503 / rate-limit → exponential backoff + jitter
            time.sleep((2 ** attempt) + random.random())
```

Vision calls pass the Grafana image as an inline image part alongside the text prompt.

---

## 11. SUBMISSION CHECKLIST (Devpost)

- [ ] Hosted URL (Cloud Run) — optional but strong
- [ ] Write-up: features, tech used, other data sources, findings
- [ ] Public repo with **README spin-up instructions**
- [ ] **Architecture diagram** (Gemini ↔ agents ↔ storage ↔ event bus ↔ UI ↔ Cloud Run)
- [ ] **~4-min live, unedited demo** + GCP-console proof (Cloud Run dashboard)
- [ ] **Bonus:** dev.to/Medium blog ("built for #AllThingsAgenticHackathon")
- [ ] **Bonus:** LinkedIn/X post with **#AllThingsAgenticHackathon**

---

## 12. STANDING INSTRUCTIONS TO CLAUDE CODE

- Decide sound defaults yourself; note them; don't stall on questions.
- After each phase: show what you built, how to run it, then stop for my go.
- Real code only. If something must be simulated (the executor running a rollback), make the simulation clean and explicit — never a fake stub pretending to be real.
- Secrets in env vars only. Never hardcode keys or webhooks.
- Wrap EVERY Gemini call in the retry helper. The demo cannot crash on a 503.
- Comment the *why*, not the *what*.
```
