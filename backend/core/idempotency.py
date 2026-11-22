"""
RESQ 4.0 Idempotency & Concurrency Controller
Prevents duplicate coordination actions, guarantees exactly-once workflow dispatch,
and logs deduplication events into the auditable timeline.
"""
from typing import Tuple, Optional
from datetime import datetime
from backend.models.incident import CoordinationAction, TimelineEvent
from backend.core.persistence import db_engine
from backend.models.enums import ActionStatus

class IdempotencyManager:
    @staticmethod
    def process_action(
        idempotency_key: str,
        incident_id: str,
        action_type: str,
        target_agency: str,
        payload: dict,
        operator_approved: bool = False,
        operator_id: Optional[str] = None
    ) -> Tuple[CoordinationAction, bool, str]:
        """
        Returns: (CoordinationAction, is_duplicate, message)
        If duplicate, returns existing action without creating duplicate dispatch.
        """
        existing = db_engine.get_action_by_idempotency_key(idempotency_key)
        if existing:
            # Duplicate call detected!
            evt = TimelineEvent(
                incident_id=incident_id,
                event_type="DUPLICATE_PREVENTED",
                actor="Central Orchestration & Safety Engine",
                summary=f"Blocked duplicate action request for '{action_type}' (Key: {idempotency_key})",
                details={
                    "idempotency_key": idempotency_key,
                    "original_action_id": existing.action_id,
                    "existing_status": existing.status.value,
                    "target_agency": target_agency
                }
            )
            db_engine.log_event(evt)
            return existing, True, f"Duplicate request detected with idempotency key '{idempotency_key}'. Cached response returned."

        # New action creation
        action = CoordinationAction(
            idempotency_key=idempotency_key,
            incident_id=incident_id,
            action_type=action_type,
            target_agency=target_agency,
            payload=payload,
            status=ActionStatus.CREATED,
            operator_approved=operator_approved,
            operator_id=operator_id,
            created_at=datetime.utcnow().isoformat()
        )
        db_engine.save_action(action)
        
        evt = TimelineEvent(
            incident_id=incident_id,
            event_type="ACTION_REGISTERED",
            actor="Central Orchestration & Safety Engine",
            summary=f"Registered coordination action '{action_type}' with agency '{target_agency}'",
            details={
                "action_id": action.action_id,
                "idempotency_key": idempotency_key,
                "status": action.status.value
            }
        )
        db_engine.log_event(evt)
        return action, False, "New coordination action successfully registered."

idempotency_mgr = IdempotencyManager()
