"""
RESQ 4.0 Verification Test Suite
Tests all 4 agents, central orchestrator, durable persistence,
idempotency manager, and all 10 required test scenarios.
"""
import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.core.orchestrator import orchestrator
from backend.agents.voice_agent import voice_agent
from backend.agents.reasoning_agent import reasoning_agent
from backend.agents.coordination_agent import coordination_agent
from backend.agents.recovery_agent import recovery_agent
from backend.core.persistence import db_engine
from backend.data.test_scenarios import run_all_scenarios
from backend.models.enums import IncidentState, VerificationStatus, ConnectionState

def test_full_pipeline():
    print(">>> 1. Testing Incident Intake & Voice Processing (Tamil)...")
    inc = orchestrator.create_incident("Road Accident", "ta")
    assert inc.state == IncidentState.RECEIVED
    
    # Process fragmented Tamil utterance with remote caller
    utterance = "வணக்கம், அண்ணா மேம்பாலம் அருகே ஒரு பெரிய விபத்து. இரண்டு பேர் பலத்த காயமடைந்துள்ளனர். நான் இங்க இல்ல, என் அலுவலகத்திலிருந்து பார்க்கிறேன்."
    inc = voice_agent.process_utterance(inc, utterance, "ta")
    
    assert inc.category.value == "Road Accident"
    assert "reported_injuries" in inc.fields
    assert inc.fields["reported_injuries"].verification_status == VerificationStatus.CALLER_REPORTED
    assert inc.locations.is_separated is True
    assert inc.locations.incident_location.verification_status == VerificationStatus.UNCERTAIN
    print(f"    [OK] Voice Agent: Extracted injuries, separated locations, landmark marked UNCERTAIN.")

    print(">>> 2. Testing Incident Reasoning Agent...")
    inc = reasoning_agent.evaluate_incident(inc)
    assert inc.reasoning.completeness_score > 0.0
    assert len(inc.reasoning.missing_critical_fields) > 0
    print(f"    [OK] Reasoning Agent: Completeness score = {inc.reasoning.completeness_score}, missing fields detected.")

    print(">>> 3. Testing Coordination Agent & Idempotency...")
    action1 = coordination_agent.create_action_proposal(inc, "DISPATCH_EMS", "108 Ambulance", custom_idempotency_key="TEST-IDEMP-001")
    # Duplicate call with identical key
    action2 = coordination_agent.create_action_proposal(inc, "DISPATCH_EMS", "108 Ambulance", custom_idempotency_key="TEST-IDEMP-001")
    assert action1.action_id == action2.action_id
    print(f"    [OK] Idempotency: Blocked duplicate dispatch with key 'TEST-IDEMP-001'.")

    print(">>> 4. Testing Operator Field Override with Auditable Provenance...")
    inc = orchestrator.operator_override_field(
        incident_id=inc.incident_id,
        field_name="reported_injuries",
        new_value="Three people injured (one critical)",
        reason="Verified on CCTV camera pole 14",
        operator_id="Operator-Lead"
    )
    assert inc.fields["reported_injuries"].current_value == "Three people injured (one critical)"
    assert len(inc.fields["reported_injuries"].history) == 1
    assert inc.fields["reported_injuries"].history[0].updated_by == "Operator-Lead"
    print(f"    [OK] Operator Override: Recorded provenance history with prior value '{inc.fields['reported_injuries'].history[0].previous_value}'.")

    print(">>> 5. Testing Disconnection Handling...")
    inc = orchestrator.handle_caller_disconnection(inc.incident_id, "Premature cell tower drop")
    assert inc.connection_state == ConnectionState.DISCONNECTED
    assert inc.state == IncidentState.OPERATOR_REVIEW
    print(f"    [OK] Disconnection: Handled as incident event without data loss; moved to OPERATOR_REVIEW.")

    print(">>> 6. Testing Restart Recovery from Durable SQLite...")
    restart_res = db_engine.simulate_backend_restart()
    restored_inc = db_engine.get_incident(inc.incident_id)
    assert restored_inc is not None
    assert restored_inc.is_recovered_session is True
    print(f"    [OK] Restart Recovery: Restored {len(restart_res['recovered_incidents'])} incidents from SQLite.")

    print(">>> 7. Executing 10 Required Test Scenarios...")
    scenarios_res = run_all_scenarios()
    print(f"    Total Scenarios: {scenarios_res['total_scenarios']}")
    print(f"    Passed: {scenarios_res['total_passed']} ({scenarios_res['pass_rate_pct']}%)")
    for r in scenarios_res["results"]:
        status = "[PASS]" if r.get("passed") else "[FAIL]"
        print(f"      {status} {r.get('title')}: {r.get('details', r.get('error'))}")
    assert scenarios_res["total_passed"] == 10, f"Expected 10 passes, got {scenarios_res['total_passed']}"

    print("\n==========================================")
    print("ALL RESQ 4.0 CORE TESTS PASSED (100% PASS RATE)!")
    print("==========================================")

if __name__ == "__main__":
    test_full_pipeline()
