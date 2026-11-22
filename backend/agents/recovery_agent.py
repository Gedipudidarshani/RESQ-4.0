"""
RESQ 4.0 Recovery Agent (Agent 4)
Monitors continuity, identifies interrupted workflows and orphaned sessions,
orchestrates state restoration from durable persistence, and executes bounded,
idempotent retries while requesting human intervention when automation cannot safely proceed.
"""
from typing import Dict, Any, List
from datetime import datetime

from backend.models.incident import IncidentRecord, CoordinationAction, TimelineEvent
from backend.models.enums import ActionStatus, IncidentState, ConnectionState
from backend.core.persistence import db_engine

class RecoveryAgent:
    def analyze_incident_continuity(self, incident: IncidentRecord) -> Dict[str, Any]:
        """
        Assesses incident continuity and detects any interrupted or pending operations.
        """
        issues = []
        pending_actions = []
        recovery_plan = []
        
        # 1. Connection Interruption Check
        if incident.connection_state == ConnectionState.DISCONNECTED:
            issues.append("Caller disconnected prior to intake completion")
            recovery_plan.append("Cross-reference historical calls and check for caller callback requests")
            
        # 2. Incomplete Actions / Pending Acknowledgments
        for act in incident.coordination_actions:
            if act.status in [ActionStatus.CREATED, ActionStatus.QUEUED]:
                pending_actions.append(act.action_id)
                recovery_plan.append(f"Action '{act.action_type}' is awaiting operator approval")
            elif act.status == ActionStatus.SENT:
                pending_actions.append(act.action_id)
                recovery_plan.append(f"Action '{act.action_type}' transmitted to {act.target_agency}; awaiting agency receipt ACK")
            elif act.status == ActionStatus.FAILED:
                recovery_plan.append(f"Action '{act.action_type}' failed; check retry policy or assign manual alternative")
                
        # 3. Missing Critical Data without Resolution
        if incident.locations.incident_location.verification_status.value in ["MISSING", "UNCERTAIN"]:
            issues.append("Incident location lacks GPS or street-level precision")
            recovery_plan.append("Surface map pinpoint tool to operator")
            
        return {
            "incident_id": incident.incident_id,
            "continuity_health": "INTERRUPTED" if (issues or pending_actions) else "HEALTHY",
            "detected_issues": issues,
            "pending_action_ids": pending_actions,
            "recommended_recovery_plan": recovery_plan,
            "requires_human_intervention": bool(issues or [a for a in incident.coordination_actions if a.status == ActionStatus.FAILED])
        }

    def reconcile_incident_after_restart(self, incident_id: str) -> IncidentRecord:
        """
        Reconciles an individual incident restored after system crash or reboot.
        Enforces rule: 'The system must never assume an action succeeded simply because it was requested.'
        """
        incident = db_engine.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
            
        now = datetime.utcnow().isoformat()
        incident.is_recovered_session = True
        
        # Reconcile actions
        for act in incident.coordination_actions:
            if act.status == ActionStatus.SENT and not act.acknowledged_at:
                # Transmitted before restart but not yet acknowledged
                act.status = ActionStatus.RETRY_SCHEDULED
                act.retry_count += 1
                if act.retry_count > act.max_retries:
                    act.status = ActionStatus.FAILED
                    evt = TimelineEvent(
                        incident_id=incident_id,
                        event_type="RECOVERY_ESCALATED",
                        actor="Recovery Agent",
                        summary=f"Max retries exhausted for action {act.action_type}. Requiring human intervention.",
                        details={"action_id": act.action_id, "retries": act.retry_count},
                        is_failure_event=True
                    )
                    db_engine.log_event(evt)
                else:
                    evt = TimelineEvent(
                        incident_id=incident_id,
                        event_type="RECOVERY_RETRY",
                        actor="Recovery Agent",
                        summary=f"Reconciled unconfirmed action {act.action_type}; scheduled safe retry #{act.retry_count}",
                        details={"action_id": act.action_id, "idempotency_key": act.idempotency_key}
                    )
                    db_engine.log_event(evt)
                    
        db_engine.save_incident(incident)
        return incident

recovery_agent = RecoveryAgent()
