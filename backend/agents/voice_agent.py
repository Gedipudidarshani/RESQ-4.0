"""
RESQ 4.0 Voice Intelligence Agent (Agent 1)
Understands fragmented Tamil and English emergency conversations, detects intent,
extracts structured fields, separates caller vs incident locations, and generates
adaptive clarification questions without delaying human operator escalation.
"""
from typing import Dict, Any, List, Optional
import re
from datetime import datetime

from backend.models.incident import (
    IncidentRecord,
    FieldProvenance,
    LocationRecord,
    DualLocation,
    AdaptiveFollowUp,
    TimelineEvent
)
from backend.models.enums import (
    IncidentCategory,
    VerificationStatus,
    ProvenanceSource,
    UrgencyLevel,
    IncidentState
)
from backend.core.persistence import db_engine

# Common Tamil and English emergency keyword maps
TAMIL_INTENTS = {
    "விபத்து": IncidentCategory.ROAD_ACCIDENT,
    "காயம்": "injuries",
    "ரத்தம்": "bleeding / severe injury",
    "தீ": IncidentCategory.FIRE_HAZARD,
    "நெருப்பு": IncidentCategory.FIRE_HAZARD,
    "மருத்துவ": IncidentCategory.MEDICAL_EMERGENCY,
    "மாரடைப்பு": IncidentCategory.MEDICAL_EMERGENCY,
    "பாலம்": "bridge landmark",
    "அண்ணா மேம்பாலம்": "Anna Flyover",
    "நான் இங்க இல்ல": "caller_separated"
}

class VoiceIntelligenceAgent:
    def process_utterance(
        self,
        incident: IncidentRecord,
        raw_text: str,
        language: str = "en",
        audio_url: Optional[str] = None
    ) -> IncidentRecord:
        """
        Processes voice transcript or audio recording into structured provenance fields.
        """
        incident.raw_transcript = (incident.raw_transcript + " " + raw_text).strip()
        incident.language = language
        if audio_url:
            incident.audio_reference_url = audio_url
            
        text_lower = raw_text.lower()
        now = datetime.utcnow().isoformat()
        
        # 1. Emergency Intent Detection
        detected_category = self._detect_category(raw_text, text_lower)
        incident.category = detected_category
        
        # 2. Extract Reported Injuries & Affected Count
        injuries_found, count_val = self._extract_injuries(raw_text, text_lower)
        if injuries_found:
            incident.fields["reported_injuries"] = FieldProvenance(
                field_name="reported_injuries",
                current_value=injuries_found,
                original_value=injuries_found,
                source=ProvenanceSource.CALLER_VOICE,
                timestamp=now,
                confidence=0.92,
                verification_status=VerificationStatus.CALLER_REPORTED,
                extraction_method="Voice Intent & Entity Extraction",
                transcript_reference=raw_text
            )
            incident.urgency = UrgencyLevel.CRITICAL
            
        if count_val is not None:
            incident.fields["affected_count"] = FieldProvenance(
                field_name="affected_count",
                current_value=count_val,
                original_value=count_val,
                source=ProvenanceSource.CALLER_VOICE,
                timestamp=now,
                confidence=0.89,
                verification_status=VerificationStatus.CALLER_REPORTED,
                extraction_method="Numeric Entity Parser",
                transcript_reference=raw_text
            )

        # 3. Dual-Location Intelligence Extraction
        self._extract_dual_locations(incident, raw_text, text_lower, now)
        
        # 4. Immediate Danger Indicators
        if any(w in text_lower for w in ["fire", "smoke", "explosion", "leak", "trapped", "unconscious", "bleeding", "தீ", "புகை", "மயக்கம்"]):
            incident.fields["immediate_danger"] = FieldProvenance(
                field_name="immediate_danger",
                current_value="Active Hazard / Vulnerable Victims Reported",
                original_value="Active Hazard / Vulnerable Victims Reported",
                source=ProvenanceSource.CALLER_VOICE,
                timestamp=now,
                confidence=0.95,
                verification_status=VerificationStatus.CALLER_REPORTED,
                extraction_method="Hazard Keyword Classifier",
                transcript_reference=raw_text
            )

        # 5. Missing Field Detection & Adaptive Follow-Up Question
        self._generate_adaptive_follow_up(incident, language)
        
        # Update incident state to INFORMATION_GATHERING or VALIDATION
        if incident.state == IncidentState.RECEIVED:
            incident.state = IncidentState.INFORMATION_GATHERING
            
        db_engine.save_incident(incident)
        
        evt = TimelineEvent(
            incident_id=incident.incident_id,
            event_type="AGENT_INFERENCE",
            actor="Voice Intelligence Agent",
            summary=f"Processed voice intake ({language.upper()}): Extracted category '{incident.category.value}', injuries: {injuries_found or 'None stated'}",
            details={
                "extracted_fields": list(incident.fields.keys()),
                "caller_loc": incident.locations.caller_location.description,
                "incident_loc": incident.locations.incident_location.description,
                "location_separated": incident.locations.is_separated
            }
        )
        db_engine.log_event(evt)
        return incident

    def _detect_category(self, text: str, text_lower: str) -> IncidentCategory:
        # Check fire hazard first (including Tamil 'தீ விபத்து' fire accident)
        if any(w in text_lower for w in ["fire", "flames", "smoke", "burning", "தீ விபத்து", "தீ", "நெருப்பு", "புகை"]):
            return IncidentCategory.FIRE_HAZARD
        if any(w in text_lower for w in ["chest pain", "heart attack", "collapsed", "breathing", "unconscious", "மருத்துவ", "மாரடைப்பு"]):
            return IncidentCategory.MEDICAL_EMERGENCY
        if any(w in text_lower for w in ["chemical", "gas leak", "fumes", "leak", "விஷம்"]):
            return IncidentCategory.INDUSTRIAL_LEAK
        if any(w in text_lower for w in ["collapse", "building fell", "wall broke", "இடிந்து"]):
            return IncidentCategory.STRUCTURAL_COLLAPSE
        if any(w in text_lower for w in ["accident", "crash", "collision", "hit", "bike", "car", "lorry", "bus", "விபத்து"]):
            return IncidentCategory.ROAD_ACCIDENT
        return IncidentCategory.ROAD_ACCIDENT

    def _extract_injuries(self, text: str, text_lower: str):
        injuries = None
        count = None
        
        # Match numeric phrases
        if "two people" in text_lower or "2 people" in text_lower or "இரண்டு பேர்" in text:
            count = 2
            injuries = "Two individuals injured"
        elif "one person" in text_lower or "1 person" in text_lower or "ஒருவர்" in text:
            count = 1
            injuries = "One individual injured"
        elif "three" in text_lower or "3 people" in text_lower or "மூன்று பேர்" in text:
            count = 3
            injuries = "Three individuals injured"
        elif any(w in text_lower for w in ["injur", "hurt", "bleeding", "unconscious", "casualt", "காயம்", "ரத்தம்"]):
            injuries = "Injuries reported by caller (count unconfirmed)"
            
        return injuries, count

    def _extract_dual_locations(self, incident: IncidentRecord, text: str, text_lower: str, timestamp: str):
        """
        Explicitly distinguishes caller location from actual incident location.
        Ensures landmark mentions are marked UNCERTAIN and never elevated to GPS automatically.
        """
        # Separation signals:
        # e.g., "I am at my office", "calling from home", "I am not at the exact place", "நான் இங்க இல்ல"
        caller_away = any(phrase in text_lower for phrase in [
            "not at the exact place",
            "not at the spot",
            "calling from my office",
            "calling from office",
            "calling from home",
            "driving past",
            "saw it from afar",
            "not there"
        ]) or ("நான் இங்க இல்ல" in text) or ("அலுவலகத்தில் இருந்து" in text)
        
        # Extract incident location landmark
        incident_loc_str = None
        lat, lng = None, None
        
        if "anna flyover" in text_lower or "anna bridge" in text_lower or "அண்ணா மேம்பாலம்" in text:
            incident_loc_str = "Anna Flyover / Gemini Circle Bridge"
            lat, lng = 13.0524, 80.2508
        elif "bridge" in text_lower or "மேம்பாலம்" in text or "பாலம்" in text:
            incident_loc_str = "Unspecified Bridge Landmark"
            lat, lng = 13.0450, 80.2400
        elif "highway" in text_lower or "bypass" in text_lower or "நெடுஞ்சாலை" in text:
            incident_loc_str = "Highway Bypass Section"
            lat, lng = 13.0100, 80.2000
        elif "market" in text_lower or "சந்தை" in text:
            incident_loc_str = "Central Market Area"
            lat, lng = 13.0827, 80.2707
            
        if caller_away:
            incident.locations.is_separated = True
            incident.locations.separation_rationale = "Caller explicitly stated they are not at the incident location"
            
            # Caller location:
            caller_desc = "Caller Office / Remote Location" if ("office" in text_lower or "அலுவலக" in text) else "Remote / In-transit location"
            incident.locations.caller_location = LocationRecord(
                description=caller_desc,
                latitude=13.0850,
                longitude=80.2100,
                source=ProvenanceSource.CALLER_VOICE,
                timestamp=timestamp,
                precision="Approximate / Remote caller",
                verification_status=VerificationStatus.CALLER_REPORTED,
                confidence=0.85,
                notes="Caller stated they are observing or reporting remotely"
            )
            
            # Incident location:
            if incident_loc_str:
                incident.locations.incident_location = LocationRecord(
                    description=incident_loc_str,
                    latitude=lat,
                    longitude=lng,
                    source=ProvenanceSource.CALLER_VOICE,
                    timestamp=timestamp,
                    precision="Landmark / Approximate (Requires exact pin)",
                    verification_status=VerificationStatus.UNCERTAIN, # Explicit requirement: landmark must NOT be verified GPS
                    confidence=0.65,
                    notes="Landmark identified from voice; exact GPS coordinates unverified."
                )
            else:
                incident.locations.incident_location = LocationRecord(
                    description="Missing incident location",
                    source=ProvenanceSource.CALLER_VOICE,
                    timestamp=timestamp,
                    precision="Unknown",
                    verification_status=VerificationStatus.MISSING,
                    confidence=0.0,
                    notes="Caller did not specify the incident location"
                )
        else:
            # Caller claims to be at scene or unspecified
            if incident_loc_str:
                incident.locations.is_separated = False
                incident.locations.incident_location = LocationRecord(
                    description=incident_loc_str,
                    latitude=lat,
                    longitude=lng,
                    source=ProvenanceSource.CALLER_VOICE,
                    timestamp=timestamp,
                    precision="Landmark / Approximate",
                    verification_status=VerificationStatus.UNCERTAIN, # Approximate landmark requires confirmation
                    confidence=0.70,
                    notes="Caller reported location near landmark; exact coordinates pending confirmation"
                )
                incident.locations.caller_location = LocationRecord(
                    description=f"At or near {incident_loc_str}",
                    latitude=lat,
                    longitude=lng,
                    source=ProvenanceSource.CALLER_VOICE,
                    timestamp=timestamp,
                    precision="Approximate",
                    verification_status=VerificationStatus.CALLER_REPORTED,
                    confidence=0.75
                )

    def _generate_adaptive_follow_up(self, incident: IncidentRecord, language: str):
        """
        Creates adaptive follow-up questions targeting missing critical fields.
        """
        incident.follow_up_queue.clear()
        
        # Check incident location precision
        if incident.locations.incident_location.verification_status in [VerificationStatus.MISSING, VerificationStatus.UNCERTAIN]:
            if language == "ta":
                q = AdaptiveFollowUp(
                    question_text="விபத்து நடக்கும் இடம் அல்லது அருகில் உள்ள முக்கிய கட்டிடம், அடையாளம் என்ன?",
                    target_field="incident_location_landmark",
                    language="ta",
                    rationale="Incident location landmark is uncertain; need nearest identifiable point."
                )
            else:
                q = AdaptiveFollowUp(
                    question_text="Can you identify the nearest road, junction, building, or landmark to the accident?",
                    target_field="incident_location_landmark",
                    language="en",
                    rationale="Incident location is approximate; need nearest identifiable landmark."
                )
            incident.follow_up_queue.append(q)
            
        # Check injuries count
        if "reported_injuries" in incident.fields and "affected_count" not in incident.fields:
            if language == "ta":
                q = AdaptiveFollowUp(
                    question_text="எத்தனை நபர்கள் காயமடைந்துள்ளனர்? யாராவது மயக்கத்தில் உள்ளார்களா?",
                    target_field="affected_count",
                    language="ta",
                    rationale="Injuries reported but count unconfirmed."
                )
            else:
                q = AdaptiveFollowUp(
                    question_text="How many people appear injured, and is anyone unconscious or in immediate danger?",
                    target_field="affected_count",
                    language="en",
                    rationale="Injuries reported but count unconfirmed."
                )
            incident.follow_up_queue.append(q)

voice_agent = VoiceIntelligenceAgent()
