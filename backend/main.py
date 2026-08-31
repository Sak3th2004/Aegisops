"""AegisOps FastAPI app — event-bus consumer, REST API, and SSE streaming.

Startup wires the local implementations of the cloud-portable interfaces
(SQLiteStorage, InProcessBus) into the Orchestrator and subscribes it to the
bus. Swapping to Firestore/PubSub for real GCP means changing only the two
constructor lines marked below.
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.adk.orchestrator import AdkOrchestrator
from backend.agents.base import Deps
from backend.config import SEED_DIR, get_settings
from backend.guardrails import ApprovalDecision, ApprovalGate
from backend.models import Alert
from backend.orchestrator import Orchestrator
from backend.seed.generate_grafana import OUT as GRAFANA_IMG, generate as generate_grafana
from backend.seed.seed_data import seed_all
from backend.services.eventbus import InProcessBus
from backend.services.gemini import gemini
from backend.services.storage import SQLiteStorage
from backend.services.stream import hub

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("aegisops.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Export Vertex config so ADK's Gemini + google-genai pick the Vertex backend.
    settings.apply_google_env()

    # --- The one place local impls are chosen. Firestore/PubSub swap here. ---
    storage = SQLiteStorage(settings.db_path)
    bus = InProcessBus()
    # ------------------------------------------------------------------------
    storage.init_schema()
    seed_all(storage, settings.gemini_model)
    if not GRAFANA_IMG.exists():
        generate_grafana()

    gate = ApprovalGate()
    deps = Deps(storage=storage, gemini=gemini, hub=hub, gate=gate)
    # Orchestrator selection: real google-adk (default) or the local fallback.
    # The local Orchestrator is never deleted — set ORCHESTRATOR=local to use it.
    if settings.orchestrator.lower() == "adk":
        orchestrator = AdkOrchestrator(deps)
    else:
        orchestrator = Orchestrator(deps)
    bus.subscribe(orchestrator.handle_alert)

    app.state.settings = settings
    app.state.storage = storage
    app.state.bus = bus
    app.state.gate = gate
    app.state.orchestrator = orchestrator

    log.info("AegisOps ready. orchestrator=%s  vertex=%s  model=%s  slack=%s",
             type(orchestrator).__name__, settings.use_vertex, settings.gemini_model, settings.has_slack)
    yield


app = FastAPI(title="AegisOps", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #
@app.post("/api/alerts")
async def post_alert(alert: Alert, request: Request):
    """Drop an alert on the event bus (the demo publisher hits this)."""
    await request.app.state.bus.publish(alert)
    return {"accepted": True, "service": alert.service}


# --------------------------------------------------------------------------- #
# Read API
# --------------------------------------------------------------------------- #
@app.get("/api/health")
async def health(request: Request):
    s = request.app.state.settings
    return {
        "status": "ok",
        "orchestrator": type(request.app.state.orchestrator).__name__,
        "model": s.gemini_model,
        "model_pro": s.gemini_model_pro,
        "auth": "vertex-adc" if s.use_vertex else ("ai-studio-key" if s.has_gemini_key else "none"),
        "vertex": s.use_vertex,
        "project": s.google_cloud_project or None,
        "vertex_location": s.vertex_location if s.use_vertex else None,
        "compute_location": s.google_cloud_location,
        "backend": s.backend,
        "slack_configured": s.has_slack,
    }


@app.get("/api/registry")
async def registry(request: Request):
    return [a.model_dump() for a in request.app.state.storage.list_agents()]


@app.get("/api/incidents")
async def incidents(request: Request):
    return [i.model_dump() for i in request.app.state.storage.list_incidents()]


@app.get("/api/incidents/{incident_id}")
async def incident(incident_id: str, request: Request):
    inc = request.app.state.storage.get_incident(incident_id)
    if not inc:
        raise HTTPException(404, "incident not found")
    return inc.model_dump()


@app.get("/api/incidents/{incident_id}/audit")
async def audit(incident_id: str, request: Request):
    return [s.model_dump() for s in request.app.state.storage.audit_for_incident(incident_id)]


@app.get("/api/incidents/{incident_id}/rca")
async def rca(incident_id: str, request: Request):
    inc = request.app.state.storage.get_incident(incident_id)
    if not inc:
        raise HTTPException(404, "incident not found")
    return {"rca": inc.rca_doc or "", "findings": inc.findings.get("comms", {})}


@app.get("/api/incidents/{incident_id}/grafana")
async def grafana(incident_id: str, request: Request):
    """Serve the exact Grafana image the vision agent analyzed."""
    inc = request.app.state.storage.get_incident(incident_id)
    path: Path = GRAFANA_IMG
    if inc and inc.alert and inc.alert.grafana_snapshot:
        p = Path(inc.alert.grafana_snapshot)
        if not p.is_absolute():
            p = SEED_DIR.parent.parent / p
        if p.exists():
            path = p
    if not path.exists():
        raise HTTPException(404, "snapshot not available")
    return FileResponse(path, media_type="image/png")


# --------------------------------------------------------------------------- #
# Human-in-the-loop approval
# --------------------------------------------------------------------------- #
class Decision(BaseModel):
    approver: str = "on-call-engineer"
    note: str = ""


@app.post("/api/incidents/{incident_id}/approve")
async def approve(incident_id: str, decision: Decision, request: Request):
    ok = request.app.state.gate.resolve(
        incident_id, ApprovalDecision(approved=True, approver=decision.approver, note=decision.note)
    )
    if not ok:
        raise HTTPException(409, "no open approval gate for this incident")
    return {"resolved": True, "approved": True}


@app.post("/api/incidents/{incident_id}/reject")
async def reject(incident_id: str, decision: Decision, request: Request):
    ok = request.app.state.gate.resolve(
        incident_id, ApprovalDecision(approved=False, approver=decision.approver, note=decision.note)
    )
    if not ok:
        raise HTTPException(409, "no open approval gate for this incident")
    return {"resolved": True, "approved": False}


# --------------------------------------------------------------------------- #
# SSE — live reasoning-chain stream
# --------------------------------------------------------------------------- #
async def _sse(incident_id: str | None):
    async for event in hub.subscribe(incident_id):
        yield {"event": event.type, "data": event.model_dump_json()}
        # Cooperative yield so a burst of events flushes promptly.
        await asyncio.sleep(0)


@app.get("/api/stream")
async def stream_all(request: Request):
    return EventSourceResponse(_sse(None))


@app.get("/api/stream/{incident_id}")
async def stream_one(incident_id: str, request: Request):
    return EventSourceResponse(_sse(incident_id))


# --------------------------------------------------------------------------- #
# Static frontend (single-container Cloud Run). Mounted last so /api wins.
# --------------------------------------------------------------------------- #
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run("backend.main:app", host=s.host, port=s.port, reload=False)
