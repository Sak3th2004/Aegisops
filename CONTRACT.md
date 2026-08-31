# AegisOps Build Contract (internal — for builder subagents)

This is the single source of truth so independently-built modules interlock.
**Do not deviate from names, paths, or payload shapes here.**

## Ground rules (from the master spec — non-negotiable)
- No placeholder/TODO code. Every function does real work.
- Every Gemini call goes through `ctx.think(...)` (which uses the 503-safe
  `GeminiService`). Never call the SDK directly.
- Flash-only, model id from config. Never hardcode a key.
- Comment the *why*, not the *what*.

## The agent runtime (already built — `backend/agents/base.py`)
Each agent subclasses `BaseAgent`, sets metadata, implements `async def execute(self, ctx: RunContext)`.

`RunContext` API (use ONLY these to touch the outside world):
- `await ctx.think(agent, step, prompt, *, system=None, response_json=False, temperature=0.3, image_path=None) -> (value, GenResult)`
  - `value` is a parsed dict when `response_json=True`, else text. Auto-streams a `reasoning` event + writes an audit row (tokens/latency). If your JSON includes a `"reasoning"` field it becomes the live-panel text.
- `await ctx.tool(agent, tool_name, detail, output)` — record a deterministic tool call (streams `tool_call`, audits).
- `ctx.remember(key, value)` — persist a durable finding onto `incident.findings[key]`.
- `await ctx.transition(new_status)` — validated state-machine move (agents generally DON'T call this except Remediation).
- `await ctx.emit(event_type, *, agent=None, **payload)` — custom stream event.
- `ctx.incident` — the live `Incident`; `ctx.deps.storage|gemini|hub|gate`.

`BaseAgent.run()` already emits `agent_start` / `agent_end` / `agent_error` around your `execute`. Set on your subclass: `name`, `version="1.0.0"`, `allowed_tools`, `scope`, `headline`.

Reference implementations to copy the pattern from: `backend/agents/triage.py`,
`backend/agents/diagnosis.py` (diagnosis shows the vision call via `image_path=`).

## Agents to build (each in its own file; class names EXACT)

### `backend/agents/correlation.py` → `class CorrelationAgent(BaseAgent)`
- name="Correlation", tools=["deploy_history_query","change_correlator"], headline="Correlating recent deploys".
- Use `backend.tools.correlation`: `deploys_in_window(storage, service, detected_at)` then `correlate_changes(deploys, detected_at)`.
- Stream each via `ctx.tool`. Then `ctx.think(response_json=True)` to name the probable root cause + confidence (0..1), grounded in the top suspect's proximity_score.
- Set `ctx.incident.probable_cause` and `ctx.incident.confidence`; save incident.
- `ctx.remember("correlation", {...})` with keys: `probable_cause`, `confidence` (float 0..1), `suspect` {service,version,deployed_by,commit_sha,minutes_before,rollback_target}, `ranked` (list of {service,version,minutes_before,proximity_score}), `reasoning`.
- Emit `correlation_result` with `probable_cause`, `confidence`.

### `backend/agents/memory.py` → `class MemoryAgent(BaseAgent)`
- name="Memory", tools=["incident_memory_search"], headline="Recalling past incidents".
- Use `backend.tools.memory.search_memory(storage, ctx.incident.fingerprint)`. Stream via `ctx.tool`.
- `ctx.think(response_json=True)` to phrase the recommendation ("seen Nx, resolved in ~Xm via Y").
- `ctx.remember("memory", {...})` keys: `match` {similarity, typical_cause, typical_fix, avg_resolution_minutes, past_incident_ids, times_seen}, `recommendation`, `reasoning`. If best similarity < 0.4, set `match=None` and say "no strong prior".
- Emit `memory_result` with `similarity`, `times_seen`, `avg_resolution_minutes`.

### `backend/agents/remediation.py` → `class RemediationAgent(BaseAgent)`
- name="Remediation", tools=["remediation_planner","approval_gate","executor"], headline="Proposing a fix (human gate)".
- Use `backend.tools.remediation`: `build_plan(action, service, rollback_target, rationale)` and `execute_remediation(plan, service)`.
- Decide the action with `ctx.think(response_json=True)` grounded in correlation + memory findings (for a bad-deploy regression the answer is `rollback` to the suspect's `rollback_target`). Prefer the memory's `typical_fix`.
- Set `ctx.incident.remediation_plan = plan`; save. `ctx.remember("remediation", {...})`.
- **Approval handshake (critical):**
  1. `await ctx.transition(IncidentStatus.AWAITING_APPROVAL)`
  2. `ctx.deps.gate.open_gate(ctx.incident.id)`
  3. `await ctx.emit("approval_required", agent=self.name, plan=plan.model_dump())`
  4. `decision = await ctx.deps.gate.wait_for(ctx.incident.id)`
  5. If `decision.approved`: emit `approved` {approver}; set `incident.approved_by`; `await ctx.transition(REMEDIATING)`; `res = await execute_remediation(...)`; stream each step via `ctx.tool` (or emit `exec_step`); set `incident.resolved_at = now_ms()`; `ctx.remember("execution", {...})`; `await ctx.transition(RESOLVED)`; emit `resolved` {resolution_minutes}.
  6. Else: emit `rejected` {approver}; `await ctx.transition(REJECTED)`.
- Only destructive plans require the gate (`plan.requires_approval`). Rollback is destructive → always gate in the demo.

### `backend/agents/comms.py` → `class CommsAgent(BaseAgent)`
- name="Comms", tools=["rca_writer","slack_poster","ticket_filer"], headline="Writing RCA + notifying".
- Generate a full RCA markdown via `ctx.think` (NOT json; return prose) from all findings + timeline. Set `ctx.incident.rca_doc`; save.
- Scrub PII before Slack: `from backend.guardrails import scrub_pii`. Post via `backend.services.slack.post_incident(scrubbed_text, summary=...)`. If `SlackResult.delivered is False`, that's the console fallback — record it honestly.
- File a ticket: `backend.tools.comms.file_ticket(incident, rca_summary)`.
- `ctx.remember("comms", {...})` keys: `rca` (markdown), `slack` {delivered, channel, redactions}, `ticket` {id, url, path}, `resolution_minutes`.
- Emit `comms_result` with `ticket_id`, `slack_channel`, `resolution_minutes`, and `rca_present=True`.

## Stream events the FRONTEND consumes (SSE `GET /api/stream`)
Each event: `{type, incident_id, agent?, payload, ts}`. Types:
`incident_created{service,alert,status}`, `agent_start{agent,headline,tools}`,
`reasoning_start{agent,step}`, `reasoning{agent,step,text,tokens,latency_ms,attempts,model}`,
`tool_call{agent,tool,detail,output}`, `state_change{from,to}`, `agent_end{agent}`,
`triage_result`, `vision_result{image_url,confirmed,observation,annotation}`,
`correlation_result`, `memory_result`, `approval_required{plan}`, `approved{approver}`,
`rejected{approver}`, `exec_step`, `resolved{resolution_minutes}`, `comms_result`,
`agent_error{agent,error}`, `done{status}`.

## REST API (already built — for the frontend)
- `GET /api/health` → {status,model,gemini_key_present,slack_configured}
- `GET /api/registry` → [{id,name,version,model,allowed_tools,scope,status}]
- `GET /api/incidents` / `GET /api/incidents/{id}` → Incident (with `findings`)
- `GET /api/incidents/{id}/audit` → [AuditStep]
- `GET /api/incidents/{id}/rca` → {rca, findings}
- `GET /api/incidents/{id}/grafana` → PNG (the exact image vision read)
- `POST /api/incidents/{id}/approve` body {approver,note} ; `POST .../reject`
- `POST /api/alerts` body Alert → publishes to bus
- SSE: `GET /api/stream` (all) and `GET /api/stream/{id}`

Agent node order for the graph: Orchestrator → Triage → Diagnosis → Correlation → Memory → Remediation → Comms.
```
The 6 sub-agent names EXACTLY: Triage, Diagnosis, Correlation, Memory, Remediation, Comms.
```
