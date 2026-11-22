"""
RESQ 4.0 FastAPI Application Entrypoint
Exposes the complete REST API and Server-Sent Events (SSE) live stream
for the Operator Intelligence Dashboard, Agent Orchestration, and Continuity Engine.
"""
import os
import asyncio
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.models.incident import IncidentRecord, CoordinationAction, TimelineEvent
from backend.models.enums import IncidentState, VerificationStatus, ConnectionState
from backend.core.persistence import db_engine
from backend.core.orchestrator import orchestrator
from backend.agents.voice_agent import voice_agent
from backend.agents.reasoning_agent import reasoning_agent
from backend.agents.coordination_agent import coordination_agent
from backend.agents.recovery_agent import recovery_agent
from backend.services.speech_service import speech_service
from backend.services.evaluation_service import evaluation_service
from backend.data.test_scenarios import SCENARIO_DEFINITIONS, run_scenario, run_all_scenarios
from backend.data.demo_script import DEMO_STEPS, demo_runner

app = FastAPI(
    title="RESQ 4.0 Emergency Intelligence Platform",
    description="Failure-Aware Agentic Emergency Intelligence & Incident Continuity Platform",
    version="4.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Client listeners for real-time SSE stream
sse_subscribers = set()

async def broadcast_event(event_type: str, data: Dict[str, Any]):
    message = json.dumps({"event": event_type, "data": data, "timestamp": datetime.utcnow().isoformat()})
    dead_subscribers = set()
    for queue in sse_subscribers:
        try:
            await queue.put(message)
        except Exception:
            dead_subscribers.add(queue)
    for dead in dead_subscribers:
        sse_subscribers.remove(dead)

# Request Models
class CreateIncidentRequest(BaseModel):
    category: str = "Road Accident"
    language: str = "en"

class VoiceIntakeRequest(BaseModel):
    transcript: str
    language: str = "en"
    audio_url: Optional[str] = None

class DisconnectRequest(BaseModel):
    reason: str = "Caller network dropped unexpectedly"

class AIFailureRequest(BaseModel):
    agent_name: str = "Voice Intelligence Agent"
    error_msg: str = "Transcription service socket timeout 504"

class FieldOverrideRequest(BaseModel):
    field_name: str
    new_value: Any
    reason: str
    operator_id: str = "Operator-1"

class ProposeActionRequest(BaseModel):
    action_type: str
    target_agency: str
    idempotency_key: Optional[str] = None

class ApproveActionRequest(BaseModel):
    action_id: str
    operator_id: str = "Operator-1"

class AgencyAckRequest(BaseModel):
    action_id: str
    responder_ref: str = "AMBULANCE-UNIT-108"

# Mount static folder
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>RESQ 4.0 Running - Static files loading...</h1>")

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "platform": "RESQ 4.0",
        "tagline": "Listen. Understand. Validate. Recover. Coordinate. Escalate. Learn.",
        "incidents_count": len(db_engine.list_incidents()),
        "continuity_engine": "ACTIVE"
    }

# ----------------- Incidents Management -----------------

@app.get("/api/incidents")
async def list_incidents(category: Optional[str] = None, state: Optional[str] = None):
    all_incidents = db_engine.list_incidents()
    if category:
        all_incidents = [i for i in all_incidents if i.category.value == category]
    if state:
        all_incidents = [i for i in all_incidents if i.state.value == state]
    return all_incidents

@app.post("/api/incidents")
async def create_incident(req: CreateIncidentRequest):
    inc = orchestrator.create_incident(req.category, req.language)
    await broadcast_event("INCIDENT_CREATED", inc.model_dump())
    return inc

@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    inc = db_engine.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc

@app.post("/api/incidents/{incident_id}/voice-intake")
async def process_voice_intake(incident_id: str, req: VoiceIntakeRequest):
    inc = db_engine.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Run Voice Agent
    inc = voice_agent.process_utterance(inc, req.transcript, req.language, req.audio_url)
    
    # Run Incident Reasoning Agent
    inc = reasoning_agent.evaluate_incident(inc)
    
    await broadcast_event("INCIDENT_UPDATED", inc.model_dump())
    return inc

@app.post("/api/incidents/{incident_id}/disconnect")
async def simulate_disconnect(incident_id: str, req: DisconnectRequest):
    inc = orchestrator.handle_caller_disconnection(incident_id, req.reason)
    await broadcast_event("CALLER_DISCONNECTED", inc.model_dump())
    return inc

@app.post("/api/incidents/{incident_id}/ai-failure")
async def simulate_ai_failure(incident_id: str, req: AIFailureRequest):
    inc = orchestrator.handle_ai_service_failure(incident_id, req.agent_name, req.error_msg)
    await broadcast_event("AI_FAILURE_SIMULATED", inc.model_dump())
    return inc

@app.post("/api/incidents/{incident_id}/acknowledge")
async def operator_acknowledge(incident_id: str, operator_id: str = "Operator-1"):
    inc = orchestrator.operator_acknowledge(incident_id, operator_id)
    await broadcast_event("OPERATOR_ACKNOWLEDGED", inc.model_dump())
    return inc

@app.post("/api/incidents/{incident_id}/override-field")
async def override_field(incident_id: str, req: FieldOverrideRequest):
    inc = orchestrator.operator_override_field(
        incident_id=incident_id,
        field_name=req.field_name,
        new_value=req.new_value,
        reason=req.reason,
        operator_id=req.operator_id
    )
    await broadcast_event("FIELD_OVERRIDDEN", inc.model_dump())
    return inc

@app.post("/api/incidents/{incident_id}/propose-action")
async def propose_coordination_action(incident_id: str, req: ProposeActionRequest):
    inc = db_engine.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    action = coordination_agent.create_action_proposal(
        incident=inc,
        action_type=req.action_type,
        target_agency=req.target_agency,
        custom_idempotency_key=req.idempotency_key
    )
    updated_inc = db_engine.get_incident(incident_id)
    await broadcast_event("ACTION_PROPOSED", updated_inc.model_dump())
    return action

@app.post("/api/incidents/{incident_id}/approve-action")
async def approve_coordination_action(incident_id: str, req: ApproveActionRequest):
    action = orchestrator.operator_approve_action(
        incident_id=incident_id,
        action_id=req.action_id,
        operator_id=req.operator_id
    )
    updated_inc = db_engine.get_incident(incident_id)
    await broadcast_event("ACTION_APPROVED", updated_inc.model_dump())
    return action

@app.post("/api/incidents/{incident_id}/simulate-ack")
async def simulate_agency_ack(incident_id: str, req: AgencyAckRequest):
    action = orchestrator.simulate_agency_acknowledgment(
        incident_id=incident_id,
        action_id=req.action_id,
        responder_ref=req.responder_ref
    )
    updated_inc = db_engine.get_incident(incident_id)
    await broadcast_event("AGENCY_ACKNOWLEDGED", updated_inc.model_dump())
    return action

@app.get("/api/incidents/{incident_id}/timeline")
async def get_incident_timeline(incident_id: str):
    return db_engine.get_events(incident_id)

@app.get("/api/incidents/{incident_id}/continuity-analysis")
async def get_continuity_analysis(incident_id: str):
    inc = db_engine.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return recovery_agent.analyze_incident_continuity(inc)

# ----------------- Continuity & System Recovery -----------------

@app.post("/api/recovery/restart-backend")
async def simulate_restart():
    result = db_engine.simulate_backend_restart()
    await broadcast_event("BACKEND_RESTARTED", result)
    return result

# ----------------- Evaluation & Baselines -----------------

@app.get("/api/evaluation/benchmarks")
async def get_evaluation_benchmarks():
    return evaluation_service.get_benchmark_comparison()

# ----------------- 10 Required Test Scenarios -----------------

@app.get("/api/scenarios")
async def get_scenarios_list():
    return SCENARIO_DEFINITIONS

@app.post("/api/scenarios/run/{scenario_id}")
async def run_single_scenario(scenario_id: str):
    res = run_scenario(scenario_id)
    await broadcast_event("SCENARIO_EXECUTED", res)
    return res

@app.post("/api/scenarios/run-all")
async def run_all_test_scenarios():
    res = run_all_scenarios()
    await broadcast_event("ALL_SCENARIOS_EXECUTED", res)
    return res

# ----------------- 3-Minute Demonstration Plan -----------------

@app.get("/api/demo/steps")
async def get_demo_steps():
    return DEMO_STEPS

@app.post("/api/demo/step/{step_number}")
async def run_demo_step(step_number: int, incident_id: Optional[str] = None):
    res = demo_runner.execute_step(step_number, incident_id)
    await broadcast_event("DEMO_STEP_EXECUTED", res)
    return res

# ----------------- Speech & Audio Service -----------------

@app.get("/api/speech/samples")
async def get_speech_samples():
    return speech_service.get_sample_utterances()

# ----------------- Server-Sent Events (SSE) Live Feed -----------------

@app.get("/api/events/stream")
async def event_stream(request: Request):
    queue = asyncio.Queue()
    sse_subscribers.add(queue)
    
    async def event_generator():
        try:
            # Send initial ping
            yield f"data: {json.dumps({'event': 'CONNECTED', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                message = await queue.get()
                yield f"data: {message}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in sse_subscribers:
                sse_subscribers.remove(queue)
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Seed initial demonstration incidents if empty
@app.on_event("startup")
async def startup_event():
    existing = db_engine.list_incidents()
    if not existing:
        # Seed initial rich incident
        inc = orchestrator.create_incident("Road Accident", "ta")
        inc = voice_agent.process_utterance(
            incident=inc,
            raw_text="வணக்கம், அண்ணா மேம்பாலம் அருகே ஒரு பெரிய விபத்து. இரண்டு பேர் பலத்த காயமடைந்துள்ளனர். நான் இங்க இல்ல, என் அலுவலகத்திலிருந்து பார்க்கிறேன்.",
            language="ta"
        )
        inc = reasoning_agent.evaluate_incident(inc)
        coordination_agent.create_action_proposal(inc, "DISPATCH_EMS", "Emergency Medical Services (108)")
        orchestrator.operator_acknowledge(inc.incident_id, "Operator-Lead-Priya")
        print(f"RESQ 4.0 Initialized with Seed Incident: {inc.incident_id}")
