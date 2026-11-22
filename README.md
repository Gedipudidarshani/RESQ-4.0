# RESQ 4.0

**Failure-Aware Agentic Emergency Intelligence & Incident Continuity Platform**

RESQ 4.0 is a FastAPI and web-based prototype for maintaining emergency incidents when caller communication is fragmented or interrupted. It combines a voice/text intake agent, incident reasoning, coordination proposals, durable SQLite persistence, and human-supervised operator controls.

> RESQ 4.0 is a decision-support prototype. It does not autonomously dispatch real emergency services or provide medical treatment advice.

## Key capabilities

- Tamil and English emergency intake from text or structured voice transcripts
- Caller and incident location separation
- Provenance, confidence, verification, and operator override audit trails
- Human-authorized coordination proposals for EMS, fire, and traffic agencies
- Idempotency keys to prevent duplicate coordination actions
- Disconnection and service-failure handling
- SQLite-backed incident continuity and restart recovery
- Server-Sent Events for live dashboard updates
- Ten automated verification scenarios

## Architecture

```text
Caller Voice / Text
        |
        v
Voice Intelligence Agent --> structured fields and location separation
        |
        v
Central Orchestrator <--> SQLite persistence and state validation
        |           |
        v           v
Reasoning Agent  Coordination Agent
        |           |
        v           v
Operator Dashboard <-> Recovery Agent
```

The orchestrator is the authoritative state machine. Agents create proposals and extracted data, while consequential actions require operator approval.

### Incident lifecycle

`RECEIVED` -> `INFORMATION_GATHERING` -> `VALIDATION` -> `OPERATOR_REVIEW` -> `ESCALATION_PENDING` -> `ESCALATION_SENT` -> `ACKNOWLEDGED` -> `ASSIGNED` -> `ACTIVE_MONITORING` -> `RESOLUTION_REVIEW` -> `CLOSED`

## Project structure

```text
backend/
  agents/          Specialized voice, reasoning, coordination, and recovery agents
  core/            Orchestrator, persistence, and idempotency logic
  data/            Demo script and verification scenarios
  models/          Pydantic models and state enums
  services/        Speech and evaluation services
  main.py          FastAPI application and REST/SSE endpoints
static/
  css/             Dashboard styling
  js/              API client and dashboard behavior
  index.html       Operator interface
tests/
  test_resq.py     End-to-end verification suite
run_server.py      Uvicorn server launcher
```

## Requirements

- Python 3.10 or newer
- Python packages: `fastapi`, `uvicorn`, `pydantic`, `python-multipart`, `httpx`

## Quick start

From the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python run_server.py
```

Open:

- Operator dashboard: http://127.0.0.1:8000/
- Swagger API documentation: http://127.0.0.1:8000/docs
- Health endpoint: http://127.0.0.1:8000/api/health

Stop the server with `Ctrl+C`.

## Verification

Run the complete core pipeline and ten scenario checks:

```powershell
python tests/test_resq.py
```

The suite validates intake, Tamil/English extraction, dual-location separation, provenance, operator overrides, disconnection continuity, idempotency, restart recovery, and all verification scenarios.

## Example API flow

```text
POST /api/incidents
POST /api/incidents/{incident_id}/voice-intake
GET  /api/incidents/{incident_id}/continuity-analysis
POST /api/incidents/{incident_id}/propose-action
POST /api/incidents/{incident_id}/approve-action
POST /api/incidents/{incident_id}/simulate-ack
GET  /api/incidents/{incident_id}/timeline
```

Real-time updates are available through `GET /api/events/stream`.

## Safety and responsible use

- Human authorization is required for consequential coordination actions.
- Confidence scores do not convert extracted or inferred information into verified facts.
- Caller location and incident location remain separate.
- Communication loss is represented as an incident event and does not erase the incident.
- SQLite data and action audit events may persist locally; use a protected runtime directory for sensitive deployments.

## Demonstrated verification

The included verification suite currently reports:

- 10 scenarios executed
- 10 scenarios passed
- 100% pass rate

These are automated prototype checks, not measured performance claims for a production emergency system.

## License

No license has been configured for this repository. All rights are reserved by the repository owner until a license is added.
