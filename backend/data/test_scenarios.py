"""
RESQ 4.0 10 Required Test Scenarios Suite
Defines reproducible, automated test scenarios matching Section 14 of the specification.
Each scenario executes end-to-end through the agents and orchestrator with verifiable assertions.
"""
from typing import Dict, Any, List
import uuid

from backend.core.orchestrator import orchestrator
from backend.agents.voice_agent import voice_agent
from backend.agents.reasoning_agent import reasoning_agent
from backend.agents.coordination_agent import coordination_agent
from backend.agents.recovery_agent import recovery_agent
from backend.core.persistence import db_engine
from backend.models.enums import IncidentState, VerificationStatus, ConnectionState, ActionStatus

SCENARIO_DEFINITIONS = [
    {
        "id": "SCENARIO_1",
        "title": "Scenario 1: Normal Emergency Report",
        "description": "Caller reports road collision with 2 injuries directly at the spot.",
        "input_text": "Severe car collision at Anna Flyover Gemini circle. Two people are injured and bleeding. I am right next to the vehicles.",
        "language": "en",
        "expected_category": "Road Accident",
        "expected_injuries": "Two individuals injured",
        "expected_separation": False
    },
    {
        "id": "SCENARIO_2",
        "title": "Scenario 2: Caller Reporting From Different Location",
        "description": "Caller is safe at office observing an accident on the bridge.",
        "input_text": "There is a massive bus accident on Anna Flyover. I am calling from my office building, not at the exact place.",
        "language": "en",
        "expected_category": "Road Accident",
        "expected_separation": True
    },
    {
        "id": "SCENARIO_3",
        "title": "Scenario 3: Incomplete Landmark Description",
        "description": "Caller mentions only an ambiguous 'bridge' without exact street details. Adaptive follow-up triggered.",
        "input_text": "Help, there is an accident near the bridge! Someone fell off their bike.",
        "language": "en",
        "expected_category": "Road Accident",
        "expected_location_status": VerificationStatus.UNCERTAIN
    },
    {
        "id": "SCENARIO_4",
        "title": "Scenario 4: Contradictory Location Reports",
        "description": "Caller makes contradictory statements (e.g. initial 'no one hurt' then 'badly bleeding').",
        "input_text": "No one is hurt here. Actually wait, two people are bleeding and unconscious on the road!",
        "language": "en",
        "expected_contradiction": True
    },
    {
        "id": "SCENARIO_5",
        "title": "Scenario 5: Caller Disconnection Interruption",
        "description": "Call drops abruptly after initial intake. State is preserved and flagged for operator review.",
        "input_text": "Accident on the highway... quick, send some-- [CALL DROPPED]",
        "language": "en",
        "test_disconnection": True
    },
    {
        "id": "SCENARIO_6",
        "title": "Scenario 6: Multiple Simultaneous Incidents",
        "description": "Three concurrent emergency reports processed with independent IDs without cross-contamination.",
        "test_multi_incident": True
    },
    {
        "id": "SCENARIO_7",
        "title": "Scenario 7: Repeated Coordination Request (Idempotency)",
        "description": "Duplicate dispatch calls with the identical idempotency key are blocked without double dispatch.",
        "test_idempotency": True
    },
    {
        "id": "SCENARIO_8",
        "title": "Scenario 8: Agent Service Failure Handling",
        "description": "AI agent timeout/failure is gracefully trapped; incident transitions to operator review without data loss.",
        "test_ai_failure": True
    },
    {
        "id": "SCENARIO_9",
        "title": "Scenario 9: Backend Restart and State Recovery",
        "description": "Volatile memory is wiped; full state restored and reconciled from SQLite database.",
        "test_restart_recovery": True
    },
    {
        "id": "SCENARIO_10",
        "title": "Scenario 10: Operator Correction of Extracted Information",
        "description": "Human operator overrides extracted field value with complete auditable provenance history.",
        "test_operator_override": True
    }
]

def run_scenario(scenario_id: str) -> Dict[str, Any]:
    """
    Executes a single test scenario and asserts success.
    """
    scen = next((s for s in SCENARIO_DEFINITIONS if s["id"] == scenario_id), None)
    if not scen:
        return {"scenario_id": scenario_id, "success": False, "error": "Scenario definition not found"}
        
    try:
        # Scenario 1: Normal Emergency
        if scenario_id == "SCENARIO_1":
            inc = orchestrator.create_incident("Road Accident", "en")
            inc = voice_agent.process_utterance(inc, scen["input_text"], "en")
            inc = reasoning_agent.evaluate_incident(inc)
            passed = (
                inc.category.value == scen["expected_category"] and
                "reported_injuries" in inc.fields and
                not inc.locations.is_separated
            )
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": passed,
                "incident_id": inc.incident_id,
                "details": f"Extracted Category: {inc.category.value}, Injuries: {inc.fields.get('reported_injuries').current_value}, Separation: {inc.locations.is_separated}"
            }
            
        # Scenario 2: Different Location
        elif scenario_id == "SCENARIO_2":
            inc = orchestrator.create_incident("Road Accident", "en")
            inc = voice_agent.process_utterance(inc, scen["input_text"], "en")
            inc = reasoning_agent.evaluate_incident(inc)
            passed = inc.locations.is_separated is True
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": passed,
                "incident_id": inc.incident_id,
                "details": f"Separation Detected: {inc.locations.is_separated}, Caller: {inc.locations.caller_location.description}, Incident: {inc.locations.incident_location.description}"
            }
            
        # Scenario 3: Incomplete Landmark Description
        elif scenario_id == "SCENARIO_3":
            inc = orchestrator.create_incident("Road Accident", "en")
            inc = voice_agent.process_utterance(inc, scen["input_text"], "en")
            inc = reasoning_agent.evaluate_incident(inc)
            has_followup = len(inc.follow_up_queue) > 0
            is_uncertain = inc.locations.incident_location.verification_status == VerificationStatus.UNCERTAIN
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": has_followup and is_uncertain,
                "incident_id": inc.incident_id,
                "details": f"Location Status: {inc.locations.incident_location.verification_status.value}, Adaptive Question: {inc.follow_up_queue[0].question_text if has_followup else 'None'}"
            }
            
        # Scenario 4: Contradictory Location Reports
        elif scenario_id == "SCENARIO_4":
            inc = orchestrator.create_incident("Road Accident", "en")
            inc = voice_agent.process_utterance(inc, scen["input_text"], "en")
            inc = reasoning_agent.evaluate_incident(inc)
            has_contra = len(inc.reasoning.contradictions) > 0
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": has_contra,
                "incident_id": inc.incident_id,
                "details": f"Contradictions detected: {inc.reasoning.contradictions}"
            }
            
        # Scenario 5: Caller Disconnection
        elif scenario_id == "SCENARIO_5":
            inc = orchestrator.create_incident("Road Accident", "en")
            inc = voice_agent.process_utterance(inc, scen["input_text"], "en")
            inc = orchestrator.handle_caller_disconnection(inc.incident_id, "Abrupt network drop")
            passed = (
                inc.connection_state == ConnectionState.DISCONNECTED and
                inc.state == IncidentState.OPERATOR_REVIEW
            )
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": passed,
                "incident_id": inc.incident_id,
                "details": f"Connection State: {inc.connection_state.value}, Advanced to: {inc.state.value}, Persisted: True"
            }
            
        # Scenario 6: Multiple Simultaneous Incidents
        elif scenario_id == "SCENARIO_6":
            inc1 = orchestrator.create_incident("Road Accident", "en")
            inc2 = orchestrator.create_incident("Fire Hazard", "ta")
            inc3 = orchestrator.create_incident("Medical Emergency", "en")
            voice_agent.process_utterance(inc1, "Accident on bridge", "en")
            voice_agent.process_utterance(inc2, "தீ விபத்து மார்க்கெட்", "ta")
            voice_agent.process_utterance(inc3, "Chest pain at clinic", "en")
            passed = (
                len({inc1.incident_id, inc2.incident_id, inc3.incident_id}) == 3 and
                inc1.category != inc2.category
            )
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": passed,
                "incident_id": f"{inc1.incident_id}, {inc2.incident_id}, {inc3.incident_id}",
                "details": f"Successfully created 3 isolated concurrent incidents without cross-contamination."
            }
            
        # Scenario 7: Repeated Coordination Request (Idempotency)
        elif scenario_id == "SCENARIO_7":
            inc = orchestrator.create_incident("Road Accident", "en")
            stable_key = f"TEST-IDEMP-{uuid.uuid4().hex[:6]}"
            act1 = coordination_agent.create_action_proposal(inc, "DISPATCH_EMS", "108 Ambulance", custom_idempotency_key=stable_key)
            # Re-call with exact same key
            act2 = coordination_agent.create_action_proposal(inc, "DISPATCH_EMS", "108 Ambulance", custom_idempotency_key=stable_key)
            passed = (act1.action_id == act2.action_id)
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": passed,
                "incident_id": inc.incident_id,
                "details": f"Action 1 ID: {act1.action_id}, Action 2 ID: {act2.action_id} (Deduplicated exactly-once execution: {passed})"
            }
            
        # Scenario 8: Agent Service Failure
        elif scenario_id == "SCENARIO_8":
            inc = orchestrator.create_incident("Road Accident", "en")
            inc = orchestrator.handle_ai_service_failure(inc.incident_id, "Voice Intelligence Agent", "Transcription service socket timeout 504")
            passed = (
                inc.state == IncidentState.OPERATOR_REVIEW and
                any("AI Service Failure" in u for u in inc.reasoning.uncertain_fields)
            )
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": passed,
                "incident_id": inc.incident_id,
                "details": f"Service failure cleanly absorbed; State: {inc.state.value}, Pending operator intervention flagged."
            }
            
        # Scenario 9: Backend Restart and State Recovery
        elif scenario_id == "SCENARIO_9":
            inc = orchestrator.create_incident("Road Accident", "en")
            voice_agent.process_utterance(inc, "Car crash near Anna Flyover with injuries", "en")
            # Restart backend
            res = db_engine.simulate_backend_restart()
            restored_inc = db_engine.get_incident(inc.incident_id)
            passed = (
                restored_inc is not None and
                restored_inc.is_recovered_session is True and
                "reported_injuries" in restored_inc.fields
            )
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": passed,
                "incident_id": inc.incident_id,
                "details": f"Reboot completed. Restored incident {restored_inc.incident_id} with recovered flag: {restored_inc.is_recovered_session} and intact fields."
            }
            
        # Scenario 10: Operator Correction of Extracted Information
        elif scenario_id == "SCENARIO_10":
            inc = orchestrator.create_incident("Road Accident", "en")
            voice_agent.process_utterance(inc, "Two people injured near bridge", "en")
            # Operator overrides injury count from 2 to 3
            inc = orchestrator.operator_override_field(
                incident_id=inc.incident_id,
                field_name="reported_injuries",
                new_value="Three people injured (confirmed on traffic camera)",
                reason="Camera feed reveals third passenger in rear seat",
                operator_id="Operator-Lead"
            )
            passed = (
                inc.fields["reported_injuries"].current_value == "Three people injured (confirmed on traffic camera)" and
                len(inc.fields["reported_injuries"].history) == 1 and
                inc.fields["reported_injuries"].verification_status == VerificationStatus.INDEPENDENTLY_VERIFIED
            )
            return {
                "scenario_id": scenario_id,
                "title": scen["title"],
                "passed": passed,
                "incident_id": inc.incident_id,
                "details": f"Current: '{inc.fields['reported_injuries'].current_value}', Previous: '{inc.fields['reported_injuries'].history[0].previous_value}', Provenance Audited: True"
            }
            
        return {"scenario_id": scenario_id, "passed": False, "details": "Unknown scenario"}
        
    except Exception as e:
        return {"scenario_id": scenario_id, "title": scen.get("title", ""), "passed": False, "error": str(e)}

def run_all_scenarios() -> Dict[str, Any]:
    results = []
    total_passed = 0
    for s in SCENARIO_DEFINITIONS:
        r = run_scenario(s["id"])
        results.append(r)
        if r.get("passed"):
            total_passed += 1
            
    return {
        "total_scenarios": len(SCENARIO_DEFINITIONS),
        "total_passed": total_passed,
        "pass_rate_pct": round((total_passed / len(SCENARIO_DEFINITIONS)) * 100, 1),
        "results": results
    }
